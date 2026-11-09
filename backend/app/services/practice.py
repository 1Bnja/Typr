from datetime import datetime, timedelta, timezone
from math import floor

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Game, GameMode, GameParticipant, Text
from app.schemas.practice import PracticeMatchCreate, PracticeMatchPublic
from app.services.texts_handler import TextFacade


class PracticeTextNotFound(Exception):
    pass


class PracticeStorageError(Exception):
    pass


def get_practice_text(db: Session, data: PracticeMatchCreate) -> Text:
    if data.text_id is not None:
        text = db.get(Text, data.text_id)
        if text is None:
            raise PracticeTextNotFound()
        return text

    context = TextFacade().process(data.text.content, data.text.language)
    text = db.scalar(
        select(Text)
        .where(
            Text.content == context.content,
            Text.language == context.language,
        )
        .limit(1)
    )
    if text is not None:
        return text
    return Text(
        content=context.content,
        language=context.language,
        difficulty=context.difficulty,
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
    db: Session, user_id: int, limit: int, offset: int
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
    try:
        return [
            match_public(game, participant, text)
            for game, participant, text in db.execute(statement)
        ]
    except SQLAlchemyError as error:
        db.rollback()
        raise PracticeStorageError() from error
