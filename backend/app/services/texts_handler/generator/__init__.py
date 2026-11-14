"""Generate Spanish typing texts without import-time external effects."""

import json
from math import ceil
import re
import time

from app.text_enums import Difficulty

PROMPT = """
    Genera 30 frases para un juego de mecanografía: exactamente 10 de complejidad baja,
    10 de complejidad media y 10 de complejidad alta, en ese orden.
    Respeta exactamente la cantidad de palabras indicada para cada grupo.
    Cuenta como palabra cada término separado por espacios; los signos de puntuación
    unidos a una palabra no cuentan como palabras adicionales.

    Grupo 1 - Complejidad baja:
        - Exactamente 20 palabras por frase.
        - Vocabulario simple y cotidiano del español.
        - Como máximo una coma dentro de la frase, además del punto final.
        - Pueden contener tildes.
        - Sin números, paréntesis, preguntas ni símbolos especiales.

    Grupo 2 - Complejidad media:
        - Exactamente 30 palabras por frase.
        - Vocabulario variado y algo más complejo.
        - Cada frase debe tener al menos una palabra con tilde, una coma y otro signo interno.
        - Usa otra coma, dos puntos o una pregunta completa para variar la escritura.
        - Sin números ni símbolos especiales.

    Grupo 3 - Complejidad alta:
        - Exactamente 40 palabras por frase.
        - Vocabulario avanzado y expresiones idiomáticas.
        - Cada frase debe tener al menos dos palabras con tilde, un número natural para el tema y tres signos internos.
        - Incluye punto y coma, dos puntos, paréntesis equilibrados o una pregunta completa.
        - Sin símbolos especiales.

    Varía también su complejidad de escritura. Algunas deben ser simples y otras pueden contener tildes, mayúsculas, números, comas, dos puntos, punto y coma, paréntesis, signos de interrogación y signos de exclamación.

    Requisitos:
    - Cada frase debe ser única y no repetirse.
    - Antes de responder, cuenta las palabras de cada frase y corrige cualquier frase
      que no tenga exactamente 20, 30 o 40 palabras según su grupo.
    - Cada frase debe tener sentido.
    - Cada frase debe comenzar con una letra mayúscula.
    - Cada frase debe tener una gramatica perfecta.
    - Cada frase debe sonar natural en el español.
    - Las frases deben tener temas variados.
    - Utilizar únicamente caracteres habituales de escritura en español.
    - No utilizar Markdown ni LaTeX.
    - No utilizar $, barra invertida    , _, ^, {, }, [, ], <, >, |, ~ ni `.
    - Devolver exactamente una frase por línea.
    - No utilizar numeración, títulos ni explicaciones.
        """


GROUP_TARGETS = {
    Difficulty.EASY: (20, 20, 20, "palabras cotidianas y puntuación sencilla"),
    Difficulty.MEDIUM: (30, 30, 30, "vocabulario variado, tildes y puntuación dentro de la frase"),
    Difficulty.ADVANCED: (40, 40, 40, "vocabulario avanzado, tildes, números y signos variados"),
}


def matches_typing_difficulty(content: str, difficulty: Difficulty) -> bool:
    """Keep the typing features of generated levels distinct from word count."""
    first = content.lstrip('¿¡("\'')
    if not first or not first[0].isalpha() or not first[0].isupper() or not has_complete_ending(content):
        return False
    accents = sum(char in "áéíóúÁÉÍÓÚüÜ" for char in content)
    marks = sum(char in ",;:¿?¡!()" for char in content)
    if difficulty == Difficulty.EASY:
        return not any(char.isdigit() for char in content) and marks <= 1
    if difficulty == Difficulty.MEDIUM:
        return (
            accents >= 1
            and content.count(",") >= 1
            and marks >= 2
            and not any(char.isdigit() for char in content)
        )
    return (
        accents >= 2
        and any(char.isdigit() for char in content)
        and marks >= 3
        and any(char in ";:()¿¡" for char in content)
    )


def has_complete_ending(content: str) -> bool:
    """Reject obvious closing fragments that only fill the word quota."""
    return (
        content.endswith((".", "?", "!"))
        and re.search(r"[.!?]\s+[¡¿]?\w+[.!?]$", content) is None
        and re.search(r"\bque\s*:", content, flags=re.IGNORECASE) is None
    )


def capitalize_initial(content: str) -> str:
    """Uppercase the first letter without changing the rest of the phrase."""
    for index, char in enumerate(content):
        if char.isalpha():
            return content[:index] + char.upper() + content[index + 1:]
        if char not in '¿¡("\'':
            break
    return content


def group_prompt(
    difficulty: Difficulty, count: int, previous_counts: tuple[int, ...] = ()
) -> str:
    minimum, maximum, target, style = GROUP_TARGETS[difficulty]
    structure = (
        "Usa una o dos oraciones breves, palabras comunes y como máximo una coma. "
        "No incluyas números, paréntesis, punto y coma ni preguntas."
        if difficulty == Difficulty.EASY else
        "Incluye en CADA frase al menos una palabra con tilde, una coma y otro signo "
        "de puntuación interno (otra coma, dos puntos o una pregunta completa con ¿?). "
        "No incluyas números."
        if difficulty == Difficulty.MEDIUM else
        "Incluye en CADA frase al menos dos palabras con tilde, un número natural "
        "para el tema (por ejemplo, una hora, fecha o cantidad), tres signos de "
        "puntuación internos y al menos un punto y coma, dos puntos, paréntesis "
        "equilibrados o pregunta completa con ¿?. Combina varias cláusulas "
        "relacionadas y evita símbolos como %, guiones largos y asteriscos."
    )
    short = sum(value < minimum for value in previous_counts)
    long = sum(value > maximum for value in previous_counts)
    feedback = ""
    if previous_counts:
        feedback = (
            f"En el intento anterior: {short} por debajo de {minimum} palabras "
            f"y {long} por encima de {maximum}. Amplía las cortas y recorta las largas; "
            f"cada frase debe terminar con exactamente {target} palabras."
        )
    return f"""
Genera exactamente {count} frases diferentes para un juego de mecanografía en español.
Cada frase debe tener exactamente {target} palabras, sin excepción.
Cada frase debe comenzar con una letra mayúscula, incluso si inicia con ¿ o ¡.
Cuenta cada palabra separada por espacios; la puntuación unida a una palabra no suma otra.
Estilo: {style}. Cada frase debe ser natural, gramatical y tener sentido completo.
{structure}
{feedback}
Redacta primero cada idea completa y coherente. Después ajusta su longitud reescribiendo
la oración o agregando una idea relacionada y completa. Nunca agregues una palabra suelta,
un adjetivo forzado ni una coletilla al final solo para llegar al conteo. Evita
redundancias, explicaciones innecesarias y exclamaciones de una sola palabra al final.
Antes de responder, verifica que cada frase tenga exactamente {target} palabras y termine
con punto, cierre de pregunta o cierre de exclamación. La última palabra debe completar
naturalmente la idea; ninguna frase puede terminar de forma abrupta.
Usa temas variados, sin repetir frases. Devuelve un arreglo de {count} frases;
cada frase es un arreglo de exactamente {target} palabras, una palabra por elemento.
La puntuación debe ir pegada a una palabra. Utiliza caracteres habituales del español.
"""


def generate_text(prompt: str | None = None) -> str:
    """Return the provider's raw text; downstream processing is caller-owned."""
    from app.config import settings

    if not all(
        value and value.strip()
        for value in (settings.gemini_api_key, settings.gemini_model)
    ):
        raise RuntimeError("Text generation requires GEMINI_API_KEY and GEMINI_MODEL.")

    from google import genai

    with genai.Client(api_key=settings.gemini_api_key) as client:
        response = client.interactions.create(
            model=settings.gemini_model, input=PROMPT if prompt is None else prompt
        )
        text = response.output_text
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text generation must return non-empty text.")
        return text


def _quota_retry_delay(error: Exception) -> int | None:
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return None
    for item in details.get("error", {}).get("details", []):
        if not isinstance(item, dict):
            continue
        match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(item.get("retryDelay", "")))
        if match:
            return ceil(float(match.group(1))) + 1
    return None


def _request_structured(prompt: str, schema: object) -> str | None:
    from app.config import settings

    if not all(
        value and value.strip()
        for value in (settings.gemini_api_key, settings.gemini_model)
    ):
        raise RuntimeError("Text generation requires GEMINI_API_KEY and GEMINI_MODEL.")

    from google import genai
    from google.genai import errors, types

    server_retries = 0
    quota_retried = False
    with genai.Client(api_key=settings.gemini_api_key) as client:
        while True:
            try:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", response_schema=schema
                    ),
                )
                return response.text
            except errors.ServerError as error:
                if error.code != 503 or server_retries == 2:
                    raise
                server_retries += 1
                time.sleep(server_retries)
            except errors.ClientError as error:
                delay = _quota_retry_delay(error) if error.code == 429 else None
                if delay is None or quota_retried:
                    raise
                quota_retried = True
                time.sleep(delay)


def review_phrases(phrases: list[str]) -> list[bool]:
    """Check whether complete phrases read naturally before they reach review UI."""
    if not phrases:
        return []

    from google.genai import types

    schema = types.Schema(
        type=types.Type.ARRAY,
        min_items=len(phrases),
        max_items=len(phrases),
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "apta": types.Schema(type=types.Type.BOOLEAN),
                "motivo": types.Schema(type=types.Type.STRING),
            },
            required=["apta", "motivo"],
        ),
    )
    prompt = f"""
Evalúa estas frases para un juego de mecanografía en español. Responde en el mismo orden.
Marca apta=false cuando haya un error claro: palabras sueltas añadidas para completar
el conteo, una exclamación aislada al final, un cierre abrupto, una idea incoherente,
una puntuación incorrecta o una falta gramatical. No rechaces una frase completa
solo por una preferencia de estilo o por usar vocabulario sencillo.
Marca apta=true si la frase tiene sentido y se puede leer naturalmente de principio a fin.
No corrijas las frases. Explica brevemente el motivo de cada decisión.
Frases: {json.dumps(phrases, ensure_ascii=False)}
"""
    try:
        decisions = json.loads(_request_structured(prompt, schema))
    except (TypeError, ValueError) as error:
        raise ValueError("Phrase review must return valid JSON.") from error
    if (
        not isinstance(decisions, list)
        or len(decisions) != len(phrases)
        or any(not isinstance(item, dict) or type(item.get("apta")) is not bool for item in decisions)
    ):
        raise ValueError("Phrase review must return one decision per phrase.")
    return [item["apta"] for item in decisions]


def generate_group_text(
    difficulty: Difficulty, count: int, previous_counts: tuple[int, ...] = (),
    *, review_quality: bool = True,
) -> str:
    from google.genai import types

    target = GROUP_TARGETS[difficulty][2]
    batch_limit = {
        Difficulty.EASY: 15,
        Difficulty.MEDIUM: 12,
        Difficulty.ADVANCED: 10,
    }[difficulty]
    sample_count = min(batch_limit, count + max(4, count // 2))
    schema = types.Schema(
        type=types.Type.ARRAY,
        min_items=sample_count,
        max_items=sample_count,
        items=types.Schema(
            type=types.Type.ARRAY,
            min_items=target,
            max_items=target,
            items=types.Schema(type=types.Type.STRING),
        ),
    )
    try:
        groups = json.loads(_request_structured(
            group_prompt(difficulty, sample_count, previous_counts), schema
        ))
    except (TypeError, ValueError) as error:
        raise ValueError("Text generation must return valid JSON word arrays.") from error
    if not isinstance(groups, list):
        raise ValueError("Text generation must return a JSON array.")
    phrases = [
        capitalize_initial(" ".join(words))
        for words in groups
        if isinstance(words, list)
        and len(words) == target
        and all(isinstance(word, str) and len(word.split()) == 1 for word in words)
    ]
    phrases = [
        phrase if phrase.endswith((".", "?", "!")) else phrase.rstrip(",;:") + "."
        for phrase in phrases
    ]
    phrases = [phrase for phrase in phrases if has_complete_ending(phrase)]
    approved = review_phrases(phrases) if review_quality else [True] * len(phrases)
    return "\n".join(
        phrase for phrase, accepted in zip(phrases, approved) if accepted
    )


def revise_phrase(difficulty: Difficulty, content: str, word_count: int) -> list[str]:
    minimum, _, target, _ = GROUP_TARGETS[difficulty]
    change = "Amplía" if word_count < minimum else "Recorta"
    prompt = f"""
{change} la siguiente frase en español sin cambiar su tema ni su sentido.
Ahora tiene {word_count} palabras. El resultado debe tener exactamente {target}
palabras, sin una más ni una menos.
Conserva una gramática natural y completa. Puedes agregar o quitar una oración
relacionada, pero no dejes una oración incompleta. Cuenta las palabras antes de responder.
Propón seis versiones diferentes, todas con exactamente {target} palabras.
Devuelve una versión por línea, sin numeración, viñetas ni explicaciones.
Frase original: {content}
"""
    return [line.strip() for line in generate_text(prompt).splitlines() if line.strip()]
