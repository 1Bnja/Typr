# Clasificación determinista implementada

**Estado: clasificación implementada.** `process()` no accede a BD;
`create()` dispone de [manejadores de duplicados y persistencia](persistence.md),
verificados mediante mocks. No hay endpoints nuevos. El
manejador aplica el modelo inicial aceptado y conserva su explicación en el
contexto. No se modificaron los pesos, escalas ni cortes de la calibración.

## Flujo de llamadas

```text
TextFacade.process -> ValidateTextHandler -> NormalizeTextHandler -> ClassifyTextHandler
                                                |
                                                v
classify_text -> _prepare -> _measure_characters -> _measure_words
                 -> _measure_keyboard -> _normalize_metrics -> _score
```

Cada etapa calcula un subproceso y devuelve la llamada a la siguiente:

```python
def _measure_characters(values):
    # Calculate character measurements.
    return _measure_words(values)
```

Es una secuencia de llamadas de profundidad fija, no una recursión por cada
carácter. Un texto de 5000 caracteres no añade 5000 niveles a la pila.

## Uso

La fachada es la entrada pública para texto bruto y construye la cadena:

```python
from app.services.texts_handler import TextFacade

context = TextFacade().process("  Hola ,mundo.Hola ", "spa")
print(context.content)
print(context.difficulty.value)
print(context.classification.score)
```

La fachada llama únicamente al primer manejador. Validación, normalización y
clasificación se suceden mediante `forward(context)`, sin importar ni ejecutar
funciones de otro manejador concreto. La clasificación ya no vuelve a normalizar
ni validar: consume el resultado de las etapas anteriores.

El cálculo auxiliar `classify_text(context)` exige un contexto marcado como
normalizado. Si el contenido o idioma cambió, o se omitió esa etapa, lanza
`TextValidationError` con código `not_normalized`. No intenta repararlo ni ejecutar
manejadores previos. Los snapshots son comprobaciones de orden y coherencia de
un flujo interno, no una frontera de seguridad frente a código que manipule
atributos privados del contexto.

El manejador asigna `context.classification` y `context.difficulty` únicamente
después de completar el cálculo y luego delega. Ante un error no asigna un
resultado parcial ni llama al siguiente manejador.

## Cálculo y resultado

| Métrica | Escala | Peso |
| --- | --- | --- |
| Entropía de Shannon, sin espacios y sensible a mayúsculas | `H / log2(A)` | 35 % |
| Esfuerzo medio de teclado, sin espacios | `coste_medio / coste_máximo_del_idioma` | 30 % |
| Longitud media de palabras | `min(media / 12, 1)` | 15 % |
| Variedad de caracteres, sin espacios | `distintos / A` | 10 % |
| Longitud máxima de palabra | `min(máximo / 24, 1)` | 10 % |

`A` es fijo: 73 caracteres para inglés y 89 para español. Los mapas y las
secuencias siguen [el modelo de teclado aprobado](keyboard-effort.md); `¿` y
`¡` solo están admitidos en español. Los costes máximos se calculan desde la
tabla completa, no desde el texto recibido.

El puntaje es la suma de las contribuciones en una escala de 0 a 100, sin
redondear antes de clasificar:

- `[0, 25)`: `easy`.
- `[25, 50)`: `medium`.
- `[50, 75)`: `advanced`.
- `[75, 100]`: `expert`.

`ClassificationResult` conserva la versión `text-difficulty-v1`, métricas
originales, métricas normalizadas, contribuciones, puntaje y el enum
`Difficulty`. El resultado y sus mapas de explicación son de solo lectura.

## Distribución de archivos

| Archivo | Responsabilidad |
| --- | --- |
| [`handler/classiffy/__init__.py`](../../../backend/app/services/texts_handler/handler/classiffy/__init__.py) | Manejador, etapas del cálculo y resultado explicable. |
| [`handler/classiffy/keyboard.py`](../../../backend/app/services/texts_handler/handler/classiffy/keyboard.py) | Mapas fijos de pulsaciones, costes y cobertura del alfabeto. |
| [`context.py`](../../../backend/app/services/texts_handler/context.py) | Entrada, roles de comillas, snapshots de etapas y resultado compartidos. |
| [`__init__.py`](../../../backend/app/services/texts_handler/__init__.py) | Fachada que compone y ejecuta la cadena. |
| [`characters.py`](../../../backend/app/services/texts_handler/characters.py) | Constantes de caracteres compartidas sin depender de manejadores. |
| [`text_enums.py`](../../../backend/app/text_enums.py) | `Language` y `Difficulty` sin dependencias de ORM o configuración. |

`models/enums.py` sigue reexportando los mismos enums y construyendo los mismos
tipos SQL. Esta extracción evita que calcular una dificultad inicialice la
configuración de BD. No se modificó el inicializador del paquete de modelos ni
se duplicaron los enums.

### Simplificación con operaciones de Python

Las etapas mantienen nombres explícitos y `return siguiente(valores)`. No se
usan lambdas para reemplazarlas: acortar una función a una expresión anónima
no haría más claro el flujo ni sus errores.

- `Counter` obtiene las frecuencias para la entropía y la variedad.
- `sum(map(str.isalnum, token))` cuenta letras y dígitos sin una lambda auxiliar.
- `filter(None, longitudes)` elimina tokens sin letras ni dígitos.
- `sum`, `len`, `min` y `max` expresan los agregados y límites directamente.
- El coste usa `sum(map(layout.costs.__getitem__, symbols))`, conservando el
  orden de suma y los valores de calibración.

El paquete `handler/classiffy/` reúne la clasificación y su auxiliar de teclado.
`keyboard.py` no es otro manejador: proporciona los datos y costes que usa esa
etapa. No quedan módulos paralelos `handler/classify.py`, `classification.py`
ni un `keyboard.py` en la raíz de `texts_handler`.

### Revisión de código sin uso

Se eliminó `calculate_difficulty`: solo lo invocaba una prueba dedicada y
duplicaba `classify_text(context).difficulty`, sin participar en el flujo real.
Se revisaron las referencias y llamadas del resto del módulo sin encontrar
otros auxiliares privados eliminables con evidencia suficiente. Los métodos
`handle` y `forward` participan mediante delegación dinámica, y los campos de
`ClassificationResult` forman parte de la explicación pública, no son código
muerto. `TextFacade.create` utiliza ahora una sesión inyectada para el flujo
de [duplicados y persistencia con SQL explícito](persistence.md).

## Supuestos y límites conservados

- La tokenización reproduce el experimento: separar por espacios y contar
  letras o dígitos dentro de cada token. `don't` mide 4; `9.30` mide 3 y cuenta
  como un token. La política numérica sigue siendo un supuesto experimental,
  no una decisión de negocio aprobada de forma independiente.
- Un token como `well-known` cuenta como uno de longitud 9. No se introduce un
  analizador lingüístico ni una regla nueva de separación por guiones.
- Un contenido válido compuesto solo por puntuación tiene cero palabras y
  longitudes cero; se calculan las otras métricas sin división por cero. No se
  añade una regla de rechazo que no se haya acordado.
- Se mantienen las limitaciones de Unicode descompuesto y apóstrofos
  tipográficos internos de la [validación existente](validation-normalization.md).
- El modelo es reproducible; su aceptación no demuestra dificultad humana.
  HTTP sigue pendiente; duplicados y guardado están probados únicamente con mocks.
- `TextFacade.create` requiere una sesión y devuelve un snapshot persistido.
  `process` devuelve un contexto nuevo y no necesita una sesión de BD.

## Evidencia de comprobación

```bash
PYTHONPATH=backend python3 -m unittest discover \
  -s backend/tests/services/texts_handler -v
```

- TDD: 16 pruebas nuevas inicialmente en RED contra el esqueleto (7 fallos y
  29 errores contando subcasos). Después de implementar y ampliar controles,
  las 40 pruebas del módulo pasan: 18 nuevas y 22 previas.
- Las 16 muestras reproducen las métricas y los puntajes de
  [la referencia congelada](calibration-results.json), sin reescribirla:
  ocho `medium` y ocho `advanced`.
- Cobertura exacta de ambos alfabetos, mapas/costes, umbrales y ausencia de
  redondeo previo; entrada inválida interrumpe la cadena.
- Ejecución normal y con `python3 -O`, importación sin configuración de BD,
  texto de 5000 caracteres, resultados repetibles y explicación inmutable.
- La prueba de compatibilidad de enums carga su fuente con un adaptador de
  SQLAlchemy simulado: comprueba identidad y conexión de tipos, no una
  integración real con PostgreSQL.
- Refactor de ubicación: las 40 pruebas previas pasaron; una prueba nueva de
  propiedad del módulo falló antes del traslado. Tras mover el cálculo a
  el módulo de clasificación, pasaron las 41 pruebas y se conservaron las 16 referencias
  de calibración sin modificar pesos, escalas ni umbrales.

La integración posterior añade pruebas de fachada, aislamiento de manejadores,
orden único de ejecución y rechazo de contextos sin preparar o modificados.
Las pruebas anteriores de entrada se conservan mediante la fachada o mediante
contextos preparados explícitamente; no se ejecutan etapas ocultas en helpers.

### Comparaciones numéricas entre versiones de Python

Las referencias de puntaje y la suma de pesos se comparan con tolerancia absoluta
`1e-12`, no mediante igualdad exacta. Python 3.12 cambió la suma de valores
flotantes; las últimas cifras pueden diferir entre el Python 3.11 del contenedor
y el intérprete que generó la referencia. Véase la
[documentación oficial](https://docs.python.org/3.12/whatsnew/3.12.html).
Las pruebas admiten una diferencia de una unidad de representación, pero siguen
rechazando desviaciones de `1e-6`. No se modifica la fórmula ni se redondea el
puntaje antes de asignar dificultad; contenido y niveles se comparan exactamente.

En Compose, la suite unitaria se ejecuta antes de la integración. Si falla esta
primera suite, todavía no se han ejecutado las pruebas reales de PostgreSQL.

La clasificación no escribe datos. La integración posterior de
[duplicados y persistencia](persistence.md) tiene pruebas de transacción con
mocks, no una comprobación contra una BD real. Para retirar esta unidad se
revierten el clasificador, el mapa de
teclado, la integración del manejador/contexto, la extracción de enums y sus
pruebas/documentación, conservando la normalización y validación anteriores.
