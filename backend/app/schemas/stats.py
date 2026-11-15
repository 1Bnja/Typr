from datetime import datetime

from app.models.enums import GameMode
from app.schemas.base import CamelModel
from app.text_enums import Difficulty, Language


class StatsSummary(CamelModel):
    """Totales y promedios de todas las partidas terminadas del usuario."""

    total_matches: int
    practice_matches: int
    multiplayer_matches: int
    # None cuando el usuario todavía no juega: no hay promedio que mostrar.
    average_ppm: float | None
    average_precision_pct: float | None
    best_ppm: int | None


class TrendPoint(CamelModel):
    game_id: int
    finished_at: datetime
    mode: GameMode
    ppm: int
    precision_pct: float


class HistoryEntry(CamelModel):
    game_id: int
    finished_at: datetime
    mode: GameMode
    language: Language
    difficulty: Difficulty
    ppm: int
    precision_pct: float
    score: int
    time_ms: int
    progress: float
    # Solo en multijugador: el lugar obtenido en la ronda.
    position: int | None


class UserStats(CamelModel):
    summary: StatsSummary
    # Últimas partidas en orden cronológico, para el gráfico de evolución.
    trend: list[TrendPoint]
    # Página del historial, de la más reciente a la más antigua.
    history: list[HistoryEntry]
    has_more: bool
