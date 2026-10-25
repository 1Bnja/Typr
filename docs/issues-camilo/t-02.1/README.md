# Textos: generación, procesamiento y persistencia

`TextFacade` centraliza las operaciones de textos. La generación es independiente;
las cadenas de procesamiento usan **Chain of Responsibility**.

| Operación | Resultado | Efectos |
|---|---|---|
| `generate()` | `str` original de Gemini | Petición externa; no procesa ni guarda |
| `process(content, language)` | `TextContext` con clasificación | Sin base de datos |
| `create(content, language)` | `PersistedText` inmutable | Requiere sesión; confirma una escritura |
| `update()` | `None` | Reservado; todavía contiene `pass` |

```text
process: validar → normalizar → clasificar
create:  validar → normalizar → comprobar duplicado → clasificar → guardar
```

## Uso

```python
from app.services.texts_handler import TextFacade

context = TextFacade().process(" Hola ,mundo. ", "spa")
```

Para guardar, inyectar una sesión del conector existente:

```python
from app.database import SessionLocal
from app.services.texts_handler import TextFacade

with SessionLocal() as db:
    record = TextFacade(db).create("Hola, mundo.", "spa")
```

`generate()` necesita `GEMINI_API_KEY` y `GEMINI_MODEL`; estas variables son
opcionales para las otras operaciones. Conserva el prompt del compañero:
solicita 30 frases en español, pero devuelve una sola cadena sin modificar.
El llamador usa `splitlines()` y pasa cada frase a `process()` o `create()`.
No se garantiza que Gemini respete el prompt. No hay Strategy ni política de
lotes implícita; cada `create()` confirma por separado.

## Dónde cambiar cada responsabilidad

- `services/texts_handler/__init__.py`: facade y composición de cadenas.
- `processing/`: pasos y sus contratos; `TextContext` transporta resultados y
  rechaza estados desactualizados o pasos fuera de orden.
- `generator/__init__.py`: generador original reubicado, independiente de la cadena.
- `processing/classiffy/weights.py`: pesos, escalas, umbrales y versión.
- `app/database.py`: conector reutilizado por las consultas SQL parametrizadas.

[Reglas y clasificación](processing.md) · [Pruebas y CI](testing.md).
