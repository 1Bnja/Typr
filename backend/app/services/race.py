"""Reglas de la carrera multijugador: tiempos, posiciones y puntaje.

Puntaje = 100 × (tiempo ideal ÷ tiempo del jugador) × precisión × multiplicador + bonos

Son funciones puras: reciben el estado de la carrera y devuelven resultados,
sin tocar la base de datos ni los sockets.
"""

from dataclasses import dataclass
from math import floor

from app.services.metrics import MIN_PRECISION, calculate_ppm, calculate_precision
from app.text_enums import Difficulty, Language

DIFFICULTY_MULTIPLIER = {
    Difficulty.EASY: 1.0,
    Difficulty.MEDIUM: 1.2,
    Difficulty.ADVANCED: 1.5,
    # La especificación define tres niveles; "expert" usa el tope conocido.
    Difficulty.EXPERT: 1.5,
}
POSITION_BONUS = {1: 20, 2: 10, 3: 5}
RECORD_BONUS = 30
# Referencia de 60 PPM (5 caracteres por segundo) para textos sin marca.
REFERENCE_MS_PER_CHAR = 200
TIME_LIMIT_FACTOR = 2


@dataclass(frozen=True)
class RaceText:
    id: int
    content: str
    language: Language
    difficulty: Difficulty
    ideal_time_ms: int


@dataclass
class Racer:
    user_id: int
    username: str
    typed: int = 0
    errors: int = 0
    finished_ms: int | None = None


@dataclass(frozen=True)
class RaceResult:
    user_id: int
    username: str
    position: int
    time_ms: int
    ppm: int
    precision_pct: float
    progress: float
    score: int
    finished: bool
    is_record: bool


def ideal_time_ms(content: str, best_time_ms: int | None) -> int:
    """Mejor marca del texto; si nadie lo ha jugado, N/5 segundos."""
    return best_time_ms or len(content) * REFERENCE_MS_PER_CHAR


def time_limit_ms(ideal_ms: int, room_limit_s: int | None) -> int:
    """El límite de la sala si lo configuró; si no, 2 veces el tiempo ideal."""
    return room_limit_s * 1000 if room_limit_s else TIME_LIMIT_FACTOR * ideal_ms


def race_points(
    *,
    ideal_ms: int,
    time_ms: int,
    precision_pct: float,
    difficulty: Difficulty,
    progress: float = 1.0,
    position: int | None = None,
    is_record: bool = False,
) -> float:
    base = (
        100
        * (ideal_ms / time_ms)
        * (precision_pct / 100)
        * DIFFICULTY_MULTIPLIER[difficulty]
    )
    if progress < 1:
        # Quien no termina recibe la parte proporcional a su avance, sin bonos.
        return base * progress
    return base + POSITION_BONUS.get(position, 0) + (RECORD_BONUS if is_record else 0)


def build_results(
    text: RaceText, elapsed_ms: int, racers: list[Racer]
) -> list[RaceResult]:
    """Ordena a los jugadores y calcula las métricas y el puntaje de cada uno.

    Primero quienes terminaron, por tiempo; después el resto, por avance.
    """
    length = len(text.content)
    ordered = sorted(
        racers,
        key=lambda racer: (
            racer.finished_ms is None,
            racer.finished_ms if racer.finished_ms is not None else -racer.typed,
        ),
    )
    results = []
    for position, racer in enumerate(ordered, start=1):
        finished = racer.finished_ms is not None
        time_ms = max(1, racer.finished_ms if finished else elapsed_ms)
        precision_pct = calculate_precision(racer.typed + racer.errors, racer.errors)
        progress = racer.typed / length
        is_record = (
            position == 1
            and finished
            and time_ms < text.ideal_time_ms
            and precision_pct >= MIN_PRECISION
        )
        points = race_points(
            ideal_ms=text.ideal_time_ms,
            time_ms=time_ms,
            precision_pct=precision_pct,
            difficulty=text.difficulty,
            progress=progress,
            position=position,
            is_record=is_record,
        )
        results.append(
            RaceResult(
                user_id=racer.user_id,
                username=racer.username,
                position=position,
                time_ms=time_ms,
                ppm=calculate_ppm(racer.typed, time_ms),
                precision_pct=precision_pct,
                progress=progress,
                score=floor(points + 0.5),
                finished=finished,
                is_record=is_record,
            )
        )
    return results
