# Contratos del procesamiento

## Validar y normalizar

| Regla | Contrato |
|---|---|
| Entrada | Texto no vacío; idioma `spa` o `eng`; máximo 5.000 caracteres tanto antes como después de normalizar |
| Ambos idiomas | Letras ASCII, dígitos ASCII, `. , ; : ? ! ' " ( ) -`, espacios, tabuladores y saltos CR/LF |
| Solo español | `ñÑáéíóúÁÉÍÓÚüÜ¿¡`; inglés rechaza esas letras y signos |
| Comillas simples | Se admiten pares `'…'` y `‘…’`; se rechazan bloques sin cerrar o estilos mezclados |
| Apóstrofos internos | Inglés permite `don't`; español lo rechaza. No se acepta `don’t` como contracción |
| Unicode | Emojis, controles y otros caracteres fuera de la lista se rechazan; no se corrigen tildes descompuestas |
| Normalización | Conserva mayúsculas y tildes, convierte comillas simples tipográficas, colapsa espacios y separa puntuación correctamente |

Ejemplos: `Hola ,mundo.Hola` → `Hola, mundo. Hola`; `¿ Hola ?` → `¿Hola?`.
Se conservan contracciones inglesas y separadores decimales adyacentes a dígitos.
No se añade una validación de balance para paréntesis o comillas dobles.

## Clasificación determinista

Los espacios no participan en las métricas de caracteres. Mayúsculas, números y
puntuación sí son caracteres distintos. Con alfabeto fijo `A` (inglés: 73;
español: 89):

| Métrica normalizada | Cálculo | Peso |
|---|---|---|
| Entropía `E` | Shannon base 2: `H = -Σ p(c)·log2(p(c))`; `E = H/log2(A)` | 0,35 |
| Esfuerzo `K` | Coste medio de teclado / máximo fijo del idioma | 0,30 |
| Largo medio `L` | `min(promedio / 12, 1)` | 0,15 |
| Variedad `V` | Caracteres distintos / `A` | 0,10 |
| Largo máximo `M` | `min(máximo / 24, 1)` | 0,10 |

`score = 100 · (0,35E + 0,30K + 0,15L + 0,10V + 0,10M)`.
Sin redondear: `<25 easy`, `<50 medium`, `<75 advanced`, resto `expert`.
La versión actual es `text-difficulty-v1`; las constantes viven únicamente en
`processing/classiffy/weights.py`.

Las palabras se separan por espacios y su longitud cuenta solo letras/dígitos:
`don't`, `9.30` y `well-known` tienen largos 4, 3 y 9. La cantidad de palabras es
descriptiva, no un peso adicional. Esta tokenización es una aproximación inicial.

Teclados fijos: US QWERTY para inglés y latinoamericano para español. Cada
pulsación cuesta `1 + distancia euclídea desde la posición base del dedo + 0,5
si usa Shift`. Las tildes y la diéresis suman sus pulsaciones de tecla muerta y
vocal, sin recargos duplicados. Las coordenadas, secuencias y máximos son los de
[`keyboard.py`](../../../backend/app/services/texts_handler/processing/classiffy/keyboard.py).
Es una estimación de dificultad, no una medición validada con velocidad humana.

## Duplicados y persistencia

- Se compara contenido **normalizado exacto**, distinguiendo mayúsculas y sin
  filtrar por idioma. Un duplicado interrumpe antes de clasificar/guardar.
- Se reutiliza la sesión recibida; `SELECT` e `INSERT … RETURNING` son SQL puro
  con parámetros separados. No se interpolan textos ni se usan constructores ORM.
- El paso terminal convierte la fila a `PersistedText` y hace `commit`; ante
  fallo hace `rollback`. La sesión la cierra quien la creó. Un fallo de commit
  puede tener resultado ambiguo: no se reintenta automáticamente.
- La consulta previa **no evita duplicados concurrentes**: falta una restricción
  única de base de datos si se necesita esa garantía. No se modificó el esquema.
- Validación: `TextValidationError.code`; errores de BD: `TextDatabaseError`, con
  causa conservada. Generación: configuración ausente → `RuntimeError`, salida
  vacía/no textual → `ValueError`; los errores del SDK se propagan.
