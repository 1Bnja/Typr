# Validar y normalizar textos antes de clasificar

**Implementado:** validación de entrada, normalización y delegación entre
manejadores. La [clasificación](classification.md) también está implementada;
la fachada construye y ejecuta la cadena. `process()` no consulta la BD;
`create()` añade [duplicados y persistencia](persistence.md) con una sesión
inyectada. Su comprobación automatizada utiliza mocks, no Supabase.

## Uso del módulo

Con `backend` en la ruta de importación:

```python
from app.services.texts_handler import TextFacade

context = TextFacade().process(" Hola ,mundo.Hola ", "spa")
assert context.content == "Hola, mundo. Hola"
print(context.difficulty.value)
```

`TextFacade.__init__` construye una vez por instancia la cadena
`ValidateTextHandler -> NormalizeTextHandler -> ClassifyTextHandler`.
`process` crea un contexto nuevo y llama solo al primer `handle`. Cada manejador
delega mediante `forward` únicamente cuando termina correctamente; una excepción
interrumpe el flujo. No hay llamadas directas entre implementaciones concretas.

La validación guarda los roles de comillas y la entrada comprobada en el contexto.
La normalización consume esos datos, sin volver a validar la entrada, y comprueba
su propio límite de salida: añadir espacios puede superar los 5000 caracteres.
La clasificación exige el contenido marcado como normalizado y solo calcula.
Los conjuntos compartidos viven en `characters.py`, no en otro manejador.
La clasificación y su auxiliar de teclado viven en `handler/classiffy/`;
`errors.py` permanece en el nivel común porque también lo utiliza el contexto.

Los snapshots de contenido e idioma impiden reutilizar datos de una etapa si
la entrada cambió. Un normalizador sin validación previa lanza `not_validated`;
un clasificador sin normalización previa lanza `not_normalized`. Los métodos
auxiliares reciben ese mismo contexto y no son entradas públicas independientes.
Para procesar texto bruto se utiliza siempre la fachada.

`create` lanza `NotImplementedError`: esta entrada procesa en memoria, no guarda
ni aparenta haber creado un registro de base de datos.

## Reglas aplicadas

| Área | Comportamiento |
| --- | --- |
| Idioma | Solo `spa` y `eng`; admite sus enums basados en `str`. No detecta el idioma del contenido. |
| Letras | Inglés: `a-z/A-Z`. Español: añade `ñÑáéíóúÁÉÍÓÚüÜ`. |
| Dígitos | Solo `0-9`, no otros dígitos Unicode. |
| Puntuación | `. , ; : ? ! ' " ( ) -` en ambos; `¿ ¡` solo en español. |
| Espacios | Espacio, tabulación, CR y LF se convierten en un espacio; se eliminan los extremos. |
| Longitud | Entre 1 y 5000 caracteres, sin contenido compuesto solo por espacios. La validación comprueba la entrada y el normalizador comprueba su salida. |
| Comillas simples | Se exige pareja del mismo estilo: `'hola'` o `‘hola’`. Se comprueba la dirección antes de convertir las tipográficas a rectas. |
| Apóstrofos | En español se rechazan dentro de palabras. En inglés se conservan las contracciones con apóstrofo recto, como `don't`. |
| Caracteres | Se conservan mayúsculas, tildes y diéresis; no se eliminan caracteres no admitidos. |

El límite de longitud procede de
[`app/text_constants.py`](../../../backend/app/text_constants.py), compartido con
el schema existente. Así, importar estos manejadores no carga modelos ORM,
configuración, credenciales ni sesiones de base de datos.

## Simplificación funcional sin cambiar las reglas

La validación utiliza conjuntos de caracteres predefinidos por idioma y
`issuperset` para comprobar la entrada completa. La normalización filtra los
espacios con un generador que conserva los índices originales: así no pierde
las posiciones necesarias para comillas y decimales. Las decisiones de espaciado
y emparejamiento mantienen bucles explícitos porque dependen del estado previo.
No se introducen lambdas ni `reduce` para ocultar esas transiciones.

La clasificación conserva sus etapas enlazadas y usa `bisect_right` sobre los
cortes `25/50/75`, sin cambiar la fórmula ni redondear el puntaje.

## Ejemplos de normalización

| Entrada | Salida |
| --- | --- |
| `Hola ,mundo.Hola` | `Hola, mundo. Hola` |
| `¿ Hola ?` | `¿Hola?` |
| `Dijo: ‘ hola ’.` | `Dijo: 'hola'.` |
| `( Hola ) . Adiós` | `(Hola). Adiós` |
| `Versión 3.14.El valor es 9.30.` | `Versión 3.14. El valor es 9.30.` |
| `Don't stop, we're ready.` (`eng`) | Sin cambios. |

No se añaden espacios dentro de delimitadores ni entre signos finales
consecutivos. Se preservan separadores numéricos `.` y `,` entre dígitos y
contracciones inglesas. La normalización es idempotente para los casos probados.
Los 16 textos de [calibración](calibration-examples.md) se mantienen sin cambios.

## Errores de validación

`TextValidationError` deriva de `ValueError` y expone `code`:

| Código | Motivo |
| --- | --- |
| `not_validated` | Falta validación previa del contenido e idioma actuales. |
| `not_normalized` | Falta normalización previa del contenido e idioma actuales. |
| `unsupported_language` | Idioma no admitido o de tipo incorrecto. |
| `invalid_content` | El contenido no es una cadena. |
| `empty_content` | Contenido vacío o compuesto solo por los espacios admitidos. |
| `content_too_long` | Longitud superior al límite, antes o después de normalizar. |
| `invalid_character` | Carácter fuera del conjunto admitido. |
| `invalid_apostrophe` | Apóstrofo interno no admitido. |
| `unpaired_quote` | Comillas simples sin pareja, invertidas o de estilos incompatibles. |

## Límites explícitos

- No hay corrección gramatical ni de mayúsculas, abreviaturas o sintaxis numérica.
- No se añade validación de emparejamiento de paréntesis o comillas dobles: no se
  había acordado rechazar esos casos. Su espaciado sigue un criterio determinista.
- No se aplica normalización Unicode NFC/NFKC. Una vocal seguida de un acento
  combinante se rechaza, aunque visualmente parezca una letra admitida. Esta
  política puede ampliarse cuando se acuerde expresamente.
- Las contracciones inglesas con apóstrofo tipográfico interno, como `don’t`,
  se rechazan por ahora: solo se acordó convertir bloques tipográficos emparejados.
- No se cambia el guion ni se define cómo cuenta al medir palabras; esa medición
  pertenece al clasificador. Se conserva su separación existente.
- La normalización no consulta duplicados: produce el contenido canónico que
  utiliza el manejador de duplicados de la cadena de creación.

## Verificación reproducible

Desde la raíz del repositorio:

```bash
PYTHONPATH=backend python3 -m unittest discover \
  -s backend/tests/services/texts_handler -v
ruff check backend/app/services/texts_handler \
  backend/app/text_constants.py backend/app/schemas/text.py \
  backend/tests/services/texts_handler
```

Se utilizó TDD con `unittest` de la biblioteca estándar porque `pytest` no está
instalado en el intérprete disponible. Las pruebas también son descubribles por
pytest cuando esté instalado. Las comprobaciones no necesitan BD, red ni secretos.

**Operación de creación:** la fachada añade manejadores de duplicados y
persistencia cuando recibe una sesión de BD. Las pruebas usan exclusivamente
mocks; véanse los [contratos y límites](persistence.md).
