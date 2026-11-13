"""Cálculo de métricas de una partida en el servidor.

Refleja exactamente frontend/src/features/practice/utils/metrics.js: el cliente
solo informa señales crudas (teclas, errores, tiempo y lo tipeado) y el servidor
es la única fuente de PPM, precisión y puntaje.
"""

from math import floor

# Una "palabra" estándar son 5 caracteres, así el PPM no depende del largo real.
CHARS_PER_WORD = 5


def _js_round(value: float) -> int:
    # JS Math.round redondea el .5 hacia arriba; round() de Python usa banker's
    # rounding y daría otro resultado en los empates.
    return floor(value + 0.5)


def count_correct_chars(typed: str, text: str) -> int:
    """Caracteres tipeados que coinciden por posición con el texto mostrado."""
    return sum(1 for i in range(min(len(typed), len(text))) if typed[i] == text[i])


def calculate_ppm(correct_chars: int, elapsed_ms: int) -> int:
    if elapsed_ms <= 0:
        return 0
    minutes = elapsed_ms / 60000
    return _js_round(correct_chars / CHARS_PER_WORD / minutes)


def calculate_precision(keystrokes: int, errors: int) -> float:
    if keystrokes == 0:
        return 100.0
    precision = ((keystrokes - errors) / keystrokes) * 100
    return _js_round(precision * 10) / 10


def calculate_score(ppm: int, precision_pct: float) -> int:
    return _js_round(ppm * (precision_pct / 100))
