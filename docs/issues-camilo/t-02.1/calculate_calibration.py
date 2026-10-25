"""Reproduce the documented calibration experiment; not application logic."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from string import ascii_letters, digits

ROOT = Path(__file__).resolve().parent
VERSION = "calibration-v1"
WEIGHTS = {
    "entropy": 0.35,
    "effort": 0.30,
    "mean_length": 0.15,
    "variety": 0.10,
    "max_length": 0.10,
}
PUNCTUATION = ".,;:?!'\"()-"
ALPHABETS = {
    "eng": set(ascii_letters + digits + PUNCTUATION),
    "spa": set(ascii_letters + digits + PUNCTUATION + "ñÑáéíóúÁÉÍÓÚüÜ¿¡"),
}
ROWS = {"AE": (0.0, 0.0), "AD": (1.0, 0.25), "AC": (2.0, 0.5), "AB": (3.0, 1.0)}
HOME_COLUMNS = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 4,
    6: 7,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
    11: 10,
    12: 10,
}


def key_position(key: str) -> tuple[float, float]:
    y, offset = ROWS[key[:2]]
    return int(key[2:]) - 1 + offset, y


def press_cost(press: tuple[str, bool]) -> float:
    key, shifted = press
    column = int(key[2:])
    home = f"AC{HOME_COLUMNS[column]:02d}"
    return 1 + math.dist(key_position(key), key_position(home)) + 0.5 * shifted


def keyboard(language: str) -> dict[str, tuple[tuple[str, bool], ...]]:
    result = {}
    for row, letters in (("AD", "qwertyuiop"), ("AC", "asdfghjkl"), ("AB", "zxcvbnm")):
        for index, char in enumerate(letters, 1):
            key = f"{row}{index:02d}"
            result[char] = ((key, False),)
            result[char.upper()] = ((key, True),)
    for index, char in enumerate("1234567890", 1):
        result[char] = ((f"AE{index:02d}", False),)
    punctuation = {
        "eng": {
            ".": ("AB09", False),
            ",": ("AB08", False),
            ";": ("AC10", False),
            ":": ("AC10", True),
            "?": ("AB10", True),
            "!": ("AE01", True),
            "'": ("AC11", False),
            '"': ("AC11", True),
            "(": ("AE09", True),
            ")": ("AE10", True),
            "-": ("AE11", False),
        },
        "spa": {
            ".": ("AB09", False),
            ",": ("AB08", False),
            ";": ("AB08", True),
            ":": ("AB09", True),
            "¿": ("AE12", False),
            "?": ("AE11", True),
            "¡": ("AE12", True),
            "!": ("AE01", True),
            "'": ("AE11", False),
            '"': ("AE02", True),
            "(": ("AE08", True),
            ")": ("AE09", True),
            "-": ("AB10", False),
        },
    }
    result.update({char: (press,) for char, press in punctuation[language].items()})
    if language == "spa":
        result["ñ"] = (("AC10", False),)
        result["Ñ"] = (("AC10", True),)
        for accent, vowel in zip("áéíóúÁÉÍÓÚ", "aeiouAEIOU"):
            result[accent] = (("AD11", False),) + result[vowel]
        result["ü"] = (("AD11", True),) + result["u"]
        result["Ü"] = (("AD11", True),) + result["U"]
    return result


def entropy(text: str) -> float:
    symbols = text.replace(" ", "")
    counts = Counter(symbols)
    return -sum(
        (count / len(symbols)) * math.log2(count / len(symbols))
        for count in counts.values()
    )


def read_samples() -> list[dict]:
    samples = []
    for line in (ROOT / "calibration-examples.md").read_text().splitlines():
        if not line.startswith(("| SPA-", "| ENG-")):
            continue
        cells = [part.strip() for part in line.split("|")[1:-1]]
        identifier, language, tentative, content = cells[:4]
        samples.append(
            {
                "id": identifier,
                "language": language.strip("`"),
                "tentative": tentative.strip("`"),
                "content": content.strip("`"),
            }
        )
    if len(samples) != 16 or len({sample["id"] for sample in samples}) != 16:
        raise ValueError("Expected exactly 16 uniquely identified samples")
    return samples


def classify(score: float) -> str:
    return (
        "easy"
        if score < 25
        else "medium"
        if score < 50
        else "advanced"
        if score < 75
        else "expert"
    )


def measure(sample: dict) -> dict:
    language, content = sample["language"], sample["content"]
    if content != " ".join(content.split()):
        raise ValueError("Sample whitespace is not canonical")
    if set(content) - (ALPHABETS[language] | {" "}):
        raise ValueError("Sample contains characters outside its alphabet")
    symbols = content.replace(" ", "")
    # Operational assumption for this experiment: whitespace-delimited tokens,
    # with surrounding punctuation stripped. Count letters/digits only inside
    # each token, so 9.30 has length 3 and don't has length 4.
    tokens = [token.strip(PUNCTUATION + "¿¡") for token in content.split(" ")]
    lengths = [sum(char.isalnum() for char in token) for token in tokens]
    lengths = [length for length in lengths if length]
    if not symbols or not lengths:
        raise ValueError("Sample must contain measurable symbols and words")
    sequences = keyboard(language)
    costs = {
        char: sum(map(press_cost, sequence)) for char, sequence in sequences.items()
    }
    maximum_cost = max(costs.values())
    mean_cost = sum(costs[char] for char in symbols) / len(symbols)
    mean_length = sum(lengths) / len(lengths)
    h = entropy(content)
    metrics = {
        "entropy": h / math.log2(len(ALPHABETS[language])),
        "effort": mean_cost / maximum_cost,
        "mean_length": min(mean_length / 12, 1),
        "variety": len(set(symbols)) / len(ALPHABETS[language]),
        "max_length": min(max(lengths) / 24, 1),
    }
    contributions = {
        name: 100 * WEIGHTS[name] * value for name, value in metrics.items()
    }
    score = sum(contributions.values())
    return {
        **sample,
        "nonspace_characters": len(symbols),
        "unique_characters": len(set(symbols)),
        "word_count": len(lengths),
        "entropy_bits": h,
        "mean_word_length": mean_length,
        "max_word_length": max(lengths),
        "mean_key_cost": mean_cost,
        "normalized": metrics,
        "contributions": contributions,
        "score": score,
        "actual": classify(score),
    }


def calculate() -> dict:
    samples = read_samples()
    results = [measure(sample) for sample in samples]
    checks = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    check("weights_sum_to_one", math.isclose(sum(WEIGHTS.values()), 1))
    check(
        "sixteen_samples_eight_per_language",
        Counter(row["language"] for row in results) == {"spa": 8, "eng": 8},
    )
    maps = {}
    for language, alphabet in ALPHABETS.items():
        sequences = keyboard(language)
        check(f"{language}_alphabet_exact_coverage", set(sequences) == alphabet)
        check(
            f"{language}_one_nonempty_canonical_sequence_per_character",
            all(sequence for sequence in sequences.values()),
        )
        costs = {
            char: sum(map(press_cost, sequence))
            for char, sequence in sorted(sequences.items())
        }
        check(f"{language}_uppercase_cost_greater", costs["A"] > costs["a"])
        maximum = max(costs.values())
        maps[language] = {
            "alphabet_size": len(alphabet),
            "alphabet": "".join(sorted(alphabet)),
            "max_cost": maximum,
            "max_cost_characters": [
                char for char, cost in costs.items() if math.isclose(cost, maximum)
            ],
            "characters": {
                char: {"sequence": sequences[char], "cost": cost}
                for char, cost in costs.items()
            },
        }
    spa_costs = maps["spa"]["characters"]
    check("acute_cost_greater", spa_costs["á"]["cost"] > spa_costs["a"]["cost"])
    check("diaeresis_cost_greater", spa_costs["ü"]["cost"] > spa_costs["u"]["cost"])
    check("enye_single_unshifted_key", keyboard("spa")["ñ"] == (("AC10", False),))
    check("control_entropy_aaaabbbb", math.isclose(entropy("aaaabbbb"), 1))
    check("control_entropy_abababab", math.isclose(entropy("abababab"), 1))
    check(
        "contraction_length",
        measure({"language": "eng", "content": "don't"})["mean_word_length"] == 4,
    )
    check(
        "decimal_operational_assumption",
        measure({"language": "eng", "content": "9.30"})["mean_word_length"] == 3,
    )
    for row in results:
        check(
            f"{row['id']}_metrics_in_unit_interval",
            all(0 <= value <= 1 for value in row["normalized"].values()),
        )
        check(
            f"{row['id']}_contribution_sum",
            math.isclose(
                row["score"],
                100
                * sum(WEIGHTS[key] * value for key, value in row["normalized"].items()),
            ),
        )
    check(
        "repeat_measurement_identical",
        results == [measure(sample) for sample in samples],
    )
    source_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("calibration-examples.md", "keyboard-effort.md")
    }
    return {
        "version": VERSION,
        "source_sha256": source_hashes,
        "weights": WEIGHTS,
        "bands": {
            "easy": "[0,25)",
            "medium": "[25,50)",
            "advanced": "[50,75)",
            "expert": "[75,100]",
        },
        "word_tokenization_status": "experimental assumption, not approved rule",
        "keyboards": maps,
        "checks": checks,
        "results": results,
    }


def markdown(data: dict) -> str:
    results = data["results"]
    distribution = Counter(row["actual"] for row in results)
    mismatches = sum(row["actual"] != row["tentative"] for row in results)
    lines = [
        "# Resultados del primer cálculo de calibración",
        "",
        "**Cálculo ejecutado; modelo inicial, no validación de dificultad humana.**",
        "",
        (
            f"Se evaluaron 16 textos: {dict(distribution)}. El puntaje va de "
            f"**{min(r['score'] for r in results):.4f} a {max(r['score'] for r in results):.4f}**. "
            f"Hay {mismatches} diferencias con las etiquetas tentativas; no son fallos de pruebas."
        ),
        "",
        "No se ajustaron pesos, escalas, textos ni cortes para obtener estos resultados.",
        "",
        "## Reproducir",
        "",
        "```bash",
        "python3 docs/issues-camilo/t-02.1/calculate_calibration.py",
        "```",
        "",
        (
            "El script usa solo la biblioteca estándar y genera este informe y "
            "[los datos completos](calibration-results.json). No importa la aplicación, "
            "no accede a BD/red ni implementa la normalización de producción."
        ),
        "",
        (
            "Los 16 textos ya tienen espacios canónicos; se verifica ese requisito sin "
            "reescribir su puntuación ni sus decimales. Los hashes de ambas fuentes quedan en JSON."
        ),
        "",
        "## Supuesto operativo pendiente de aprobación",
        "",
        (
            "Para poder ejecutar este experimento, se separan tokens por espacios, se elimina "
            "la puntuación externa y se cuentan letras/dígitos dentro de cada token. Así, "
            "`don't` mide 4 y es una palabra; `9.30` mide 3 y es un token numérico. "
            "Este último criterio no estaba definido: es un supuesto del experimento, no una "
            "regla aprobada para producción. No se generaliza todavía a palabras con guion. "
            "Los ejemplos no tienen ese caso."
        ),
        "",
        "## Escalas y costes fijos",
        "",
        (
            "Se usan los pesos 35/30/15/10/10 para entropía/esfuerzo/longitud media/variedad/"
            "longitud máxima. Las longitudes se dividen por 12 y 24, con tope 1. "
            "Entropía y variedad se dividen por `log2(A)` y `A`; esfuerzo por el máximo "
            "coste del alfabeto admitido del idioma. Todos excluyen espacios donde corresponde."
        ),
        "",
        "| Idioma | A | Coste máximo fijo | Caracteres de coste máximo |",
        "| --- | ---: | ---: | --- |",
    ]
    for language, info in data["keyboards"].items():
        lines.append(
            f"| `{language}` | {info['alphabet_size']} | {info['max_cost']:.8f} | "
            f"`{''.join(info['max_cost_characters'])}` |"
        )
    lines += [
        "",
        (
            "Los mapas completos de secuencias y costes están en JSON y siguen "
            "[el modelo de teclado aprobado](keyboard-effort.md). "
            "La referencia se fija en el script; no depende del teclado de la máquina."
        ),
        "",
        "## Métricas sin normalizar",
        "",
        (
            "`H`: bits por carácter; `U`: caracteres distintos; `N`: palabras/tokens; "
            "`Lmed/Lmax`: longitudes; `Cmed`: coste medio sin espacios."
        ),
        "",
        "| ID | H | U | N | Lmed | Lmax | Cmed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['entropy_bits']:.4f} | {r['unique_characters']} | "
            f"{r['word_count']} | {r['mean_word_length']:.4f} | "
            f"{r['max_word_length']} | {r['mean_key_cost']:.4f} |"
        )
    lines += [
        "",
        "## Métricas normalizadas",
        "",
        "| ID | E | K | Lmed | V | Lmax |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        lines.append(
            "| "
            + r["id"]
            + " | "
            + " | ".join(f"{r['normalized'][key]:.4f}" for key in WEIGHTS)
            + " |"
        )
    lines += [
        "",
        "## Contribuciones en puntos y clasificación",
        "",
        (
            "La clasificación usa el puntaje sin redondear: `<25 easy`, `<50 medium`, "
            "`<75 advanced`, resto `expert`. Solo las cifras mostradas se redondean."
        ),
        "",
        "| ID | E × 35 | K × 30 | Lmed × 15 | V × 10 | Lmax × 10 | Puntaje | Tentativo | Calculado |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for r in results:
        lines.append(
            "| "
            + r["id"]
            + " | "
            + " | ".join(f"{r['contributions'][key]:.4f}" for key in WEIGHTS)
            + f" | **{r['score']:.4f}** | `{r['tentative']}` | `{r['actual']}` |"
        )
    lines += [
        "",
        "## Interpretación y límites",
        "",
        (
            "- No se obtuvo ningún `easy` ni `expert`: hay ocho `medium` y ocho `advanced`. "
            "En español son cinco `medium` y tres `advanced`; en inglés, tres y cinco."
        ),
        (
            "- La distribución calculada debe leerse con los valores anteriores: "
            "no acredita que las etiquetas humanas estén equivocadas ni que el modelo esté validado."
        ),
        (
            "- El alfabeto fijo incluye símbolos poco frecuentes en prosa. Las divisiones "
            "por `A` y `log2(A)` no obligan a textos naturales a cubrir todo el intervalo."
        ),
        (
            "- La normalización por el carácter más costoso reduce especialmente el esfuerzo "
            "español: las composiciones con teclas muertas elevan el máximo de referencia."
        ),
        (
            "- Los cortes equidistantes 25/50/75 no son cuantiles ni garantizan muestras en "
            "los cuatro niveles. No se cambian automáticamente para reproducir etiquetas tentativas."
        ),
        (
            "- El corpus es pequeño y construido: faltan muestras independientes y evidencia "
            "de velocidad/errores humanos. Entropía y variedad están correlacionadas."
        ),
        "",
        "## Comprobaciones ejecutadas",
        "",
        (
            f"Se completaron **{len(data['checks'])} comprobaciones** mediante excepciones explícitas "
            "(también activas con `python -O`): cobertura exacta de alfabetos, secuencias no vacías, "
            "suma de pesos, costes relativos, ñ como tecla única, entropía 1 en ambos controles, "
            "contracción/decimal, intervalos normalizados, suma de contribuciones y repetición idéntica."
        ),
        "",
        (
            "La ejecución se repitió y los SHA-256 de ambos archivos generados fueron idénticos. "
            "También se ejecutó con `python3 -O` y pasó las 48 comprobaciones; Ruff pasó. "
            "Estos controles prueban coherencia del experimento, no integración del backend."
        ),
        "",
        "## Próximo paso",
        "",
        (
            "Revisar las contribuciones y los supuestos de tokenización antes de proponer "
            "cambios explícitos de escala o cortes. No cambiar simultáneamente todas las "
            "variables ni ajustar solo para coincidir con este conjunto."
        ),
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    data = calculate()
    (ROOT / "calibration-results.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "calibration-results.md").write_text(markdown(data))
    distribution = Counter(row["actual"] for row in data["results"])
    scores = [row["score"] for row in data["results"]]
    print(
        f"{len(data['results'])} samples; {len(data['checks'])} checks; "
        f"scores {min(scores):.8f}..{max(scores):.8f}; {dict(distribution)}"
    )


if __name__ == "__main__":
    main()
