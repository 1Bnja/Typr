"""Analítica personal: promedios, evolución reciente e historial de partidas.

Cuenta las partidas terminadas de ambos modos: práctica individual y rondas
multijugador. Una ronda multijugador que el jugador no completó también cuenta,
porque refleja su desempeño real en esa carrera.
"""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Game, GameMode, GameParticipant, Text
from app.schemas.stats import HistoryEntry, StatsSummary, TrendPoint, UserStats

TREND_SIZE = 30


def _finished_matches(user_id: int):
    """Participaciones del usuario en partidas terminadas y con métricas."""
    return (
        select(Game, GameParticipant, Text)
        .join(GameParticipant, GameParticipant.game_id == Game.id)
        .join(Text, Text.id == Game.text_id)
        .where(
            GameParticipant.user_id == user_id,
            Game.finished_at.is_not(None),
            GameParticipant.ppm.is_not(None),
            GameParticipant.precision_pct.is_not(None),
        )
    )


def _summary(db: Session, user_id: int) -> StatsSummary:
    is_multiplayer = Game.mode == GameMode.MULTIPLAYER
    row = db.execute(
        select(
            func.count(),
            func.count(case((is_multiplayer, 1))),
            func.avg(GameParticipant.ppm),
            func.avg(GameParticipant.precision_pct),
            func.max(GameParticipant.ppm),
        )
        .select_from(GameParticipant)
        .join(Game, Game.id == GameParticipant.game_id)
        .where(
            GameParticipant.user_id == user_id,
            Game.finished_at.is_not(None),
            GameParticipant.ppm.is_not(None),
            GameParticipant.precision_pct.is_not(None),
        )
    ).one()
    total, multiplayer, average_ppm, average_precision, best_ppm = row
    return StatsSummary(
        total_matches=total,
        practice_matches=total - multiplayer,
        multiplayer_matches=multiplayer,
        average_ppm=None if average_ppm is None else round(float(average_ppm), 1),
        average_precision_pct=(
            None if average_precision is None else round(float(average_precision), 1)
        ),
        best_ppm=best_ppm,
    )


def user_stats(db: Session, user_id: int, limit: int, offset: int) -> UserStats:
    newest_first = (Game.finished_at.desc(), Game.id.desc())
    latest = db.execute(
        _finished_matches(user_id).order_by(*newest_first).limit(TREND_SIZE)
    ).all()
    page = db.execute(
        _finished_matches(user_id).order_by(*newest_first).limit(limit + 1).offset(offset)
    ).all()
    return UserStats(
        summary=_summary(db, user_id),
        trend=[
            TrendPoint(
                game_id=game.id,
                finished_at=game.finished_at,
                mode=game.mode,
                ppm=participant.ppm,
                precision_pct=participant.precision_pct,
            )
            for game, participant, _ in reversed(latest)
        ],
        history=[
            HistoryEntry(
                game_id=game.id,
                finished_at=game.finished_at,
                mode=game.mode,
                language=text.language,
                difficulty=text.difficulty,
                ppm=participant.ppm,
                precision_pct=participant.precision_pct,
                score=participant.score or 0,
                time_ms=participant.time_ms or 0,
                progress=participant.progress or 0,
                position=participant.position if game.mode == GameMode.MULTIPLAYER else None,
            )
            for game, participant, text in page[:limit]
        ],
        has_more=len(page) > limit,
    )
