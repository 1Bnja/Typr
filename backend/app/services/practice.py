from datetime import datetime, timedelta, timezone
from math import floor
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Game, GameMode, GameParticipant, Text, User
from app.schemas.practice import (
    LeaderboardEntry,
    MonthlyLeaderboard,
    PracticeMatchCreate,
    PracticeMatchPublic,
)
from app.services.texts_handler import TextFacade
from app.text_enums import Difficulty, Language

RANKING_TIMEZONE = "America/Santiago"


class PracticeTextNotFound(Exception):
    pass


class PracticeStorageError(Exception):
    pass


class PracticeDifficultyMismatch(Exception):
    pass


def get_practice_text(db: Session, data: PracticeMatchCreate) -> Text:
    if data.text_id is not None:
        text = db.get(Text, data.text_id)
        if text is None:
            raise PracticeTextNotFound()
        if data.difficulty is not None and text.difficulty != data.difficulty:
            raise PracticeDifficultyMismatch()
        return text

    context = TextFacade().process(data.text.content, data.text.language)
    difficulty = data.difficulty or context.difficulty
    text = db.scalar(
        select(Text)
        .where(
            Text.content == context.content,
            Text.language == context.language,
            Text.difficulty == difficulty,
        )
        .limit(1)
    )
    if text is not None:
        return text
    return Text(
        content=context.content,
        language=context.language,
        difficulty=difficulty,
    )


def match_public(
    game: Game, participant: GameParticipant, text: Text
) -> PracticeMatchPublic:
    return PracticeMatchPublic(
        id=game.id,
        text_id=game.text_id,
        language=text.language,
        difficulty=text.difficulty,
        time_ms=participant.time_ms,
        ppm=participant.ppm,
        precision_pct=participant.precision_pct,
        progress=participant.progress,
        score=participant.score,
        started_at=game.started_at,
        finished_at=game.finished_at,
    )


def save_practice_match(
    db: Session, user_id: int, data: PracticeMatchCreate
) -> PracticeMatchPublic:
    try:
        text = get_practice_text(db, data)
        finished_at = datetime.now(timezone.utc)
        game = Game(
            text=text,
            mode=GameMode.SINGLEPLAYER,
            started_at=finished_at - timedelta(milliseconds=data.time_ms),
            finished_at=finished_at,
        )
        db.add(game)
        db.flush()
        participant = GameParticipant(
            game_id=game.id,
            user_id=user_id,
            time_ms=data.time_ms,
            ppm=data.ppm,
            precision_pct=data.precision_pct,
            progress=data.progress,
            position=1 if data.progress == 1 else None,
            score=floor(data.ppm * (data.precision_pct / 100) + 0.5),
        )
        db.add(participant)
        result = match_public(game, participant, text)
        # El texto y la partida se guardan juntos; un error revierte todo.
        db.commit()
        return result
    except SQLAlchemyError as error:
        db.rollback()
        raise PracticeStorageError() from error


def list_practice_matches(
    db: Session,
    user_id: int,
    limit: int,
    offset: int,
    difficulty: Difficulty | None = None,
    language: Language | None = None,
) -> list[PracticeMatchPublic]:
    statement = (
        select(Game, GameParticipant, Text)
        .join(GameParticipant, GameParticipant.game_id == Game.id)
        .join(Text, Text.id == Game.text_id)
        .where(
            GameParticipant.user_id == user_id,
            Game.mode == GameMode.SINGLEPLAYER,
            Game.room_id.is_(None),
            Game.finished_at.is_not(None),
        )
        .order_by(Game.finished_at.desc(), Game.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if difficulty is not None:
        statement = statement.where(Text.difficulty == difficulty)
    if language is not None:
        statement = statement.where(Text.language == language)
    try:
        return [
            match_public(game, participant, text)
            for game, participant, text in db.execute(statement)
        ]
    except SQLAlchemyError as error:
        db.rollback()
        raise PracticeStorageError() from error


def monthly_leaderboard(
    db: Session,
    month: str | None,
    difficulty: Difficulty,
    language: Language | None,
    limit: int,
) -> MonthlyLeaderboard:
    zone = ZoneInfo(RANKING_TIMEZONE)
    selected_month = month or datetime.now(zone).strftime("%Y-%m")
    year, number = map(int, selected_month.split("-"))
    start = datetime(year, number, 1, tzinfo=zone)
    if number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(year, number + 1, 1, tzinfo=zone)
    order = (
        GameParticipant.score.desc(),
        GameParticipant.precision_pct.desc(),
        GameParticipant.time_ms.asc(),
        Game.finished_at.asc(),
        Game.id.asc(),
    )
    statement = (
        select(
            GameParticipant.user_id,
            User.username,
            GameParticipant.ppm,
            GameParticipant.precision_pct,
            GameParticipant.score,
            GameParticipant.time_ms,
            Game.finished_at,
            Game.id.label("game_id"),
            func.row_number()
            .over(partition_by=GameParticipant.user_id, order_by=order)
            .label("personal_rank"),
        )
        .select_from(GameParticipant)
        .join(Game, Game.id == GameParticipant.game_id)
        .join(Text, Text.id == Game.text_id)
        .join(User, User.id == GameParticipant.user_id)
        .where(
            Game.mode == GameMode.SINGLEPLAYER,
            Game.room_id.is_(None),
            GameParticipant.progress == 1,
            GameParticipant.score.is_not(None),
            GameParticipant.precision_pct.is_not(None),
            GameParticipant.time_ms > 0,
            GameParticipant.ppm >= 0,
            Text.difficulty == difficulty,
            Game.finished_at >= start.astimezone(timezone.utc),
            Game.finished_at < end.astimezone(timezone.utc),
        )
    )
    if language is not None:
        statement = statement.where(Text.language == language)
    best = statement.subquery()
    ranked = (
        select(best)
        .where(best.c.personal_rank == 1)
        .order_by(
            best.c.score.desc(),
            best.c.precision_pct.desc(),
            best.c.time_ms.asc(),
            best.c.finished_at.asc(),
            best.c.game_id.asc(),
        )
        .limit(limit)
    )
    try:
        rows = db.execute(ranked).mappings().all()
        entries = [
            LeaderboardEntry(
                position=position,
                user_id=row["user_id"],
                username=row["username"],
                ppm=row["ppm"],
                precision_pct=row["precision_pct"],
                score=row["score"],
                time_ms=row["time_ms"],
                finished_at=row["finished_at"],
            )
            for position, row in enumerate(rows, start=1)
        ]
        return MonthlyLeaderboard(
            month=selected_month,
            difficulty=difficulty,
            language=language,
            timezone=RANKING_TIMEZONE,
            entries=entries,
        )
    except SQLAlchemyError as error:
        db.rollback()
        raise PracticeStorageError() from error
