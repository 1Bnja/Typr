# Generación de texto independiente del procesamiento

`TextFacade.generate()` devuelve un `str` con la salida de Gemini sin modificar.
No valida, normaliza, clasifica ni guarda esa salida. El llamador decide cuándo
pasarla a `process()` o `create()`.

El generador vive en `backend/app/services/texts_handler/generator/__init__.py`.

## Uso

```python
from app.services.texts_handler import TextFacade

facade = TextFacade()
raw = facade.generate()

contexts = [
    facade.process(line, "spa")
    for line in raw.splitlines()
    if line.strip()
]
```

Se conserva el prompt de `7242406`: solicita 30 frases en español, una por
línea. `generate()` entrega **una sola cadena**, no una lista, y conserva sus
espacios y saltos de línea. No comprueba que Gemini respete la cantidad o las
reglas del prompt. Las categorías solicitadas a Gemini tampoco reemplazan la
dificultad calculada por nuestro clasificador.

Para guardar cada frase de forma explícita:

```python
from app.database import SessionLocal
from app.services.texts_handler import TextFacade

raw = TextFacade().generate()
with SessionLocal() as db:
    facade = TextFacade(db)
    for line in raw.splitlines():
        if line.strip():
            record = facade.create(line, "spa")
```

Cada `create()` confirma su propia transacción. Si una frase falla, el ejemplo
se detiene y las anteriores siguen guardadas: no es una operación de lote
atómica. La decisión de omitir errores, reintentar o continuar pertenece al
llamador; no se implementó una política de lote implícita.

## Configuración y errores

- `GEMINI_API_KEY` y `GEMINI_MODEL` deben estar configurados para generar.
  Son opcionales para las rutas que solo procesan o persisten textos.
- Importar la fachada o `generator` no carga la configuración ni el SDK y no
  realiza peticiones. Esas dependencias se cargan al invocar `generate()`.
- Sin clave o modelo, se lanza `RuntimeError` antes de crear el cliente.
- Una respuesta sin texto utilizable provoca `ValueError`; los errores del SDK
  se propagan sin convertirlos en textos ni resultados exitosos.
- El cliente de Gemini se cierra mediante su context manager, también si falla
  la petición. `generate()` no utiliza la sesión de base de datos inyectada.

## Verificación

Las pruebas usan configuración y SDK simulados: verifican la salida exacta,
los argumentos de la petición, el cierre del cliente, los errores, la ausencia
de efectos al importar y el envío explícito a `process()` y `create()`.
No se hizo una petición real a Gemini ni se utilizaron credenciales reales.

La integración conserva `interactions.create()` y `output_text`, verificados
contra el [cliente oficial de python-genai 2.25.0](https://github.com/googleapis/python-genai/blob/v2.25.0/google/genai/client.py)
y su [adaptador de respuestas](https://github.com/googleapis/python-genai/blob/v2.25.0/google/genai/_gaos/google_genai.py).
