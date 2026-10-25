# Propuesta determinista del esfuerzo de teclado

**Estado: modelo inicial aprobado, pendiente de calibración.** Quedan aprobadas
las distribuciones, la rejilla, la asignación de dedos y los costes: base `1`,
distancia euclídea y recargo `0.5` por Shift. No tienen validación empírica todavía.
No se implementa lógica ni se calculan puntajes
de los [textos de ejemplo](calibration-examples.md).

## Resultado propuesto

Descomponer cada carácter normalizado en pulsaciones de un teclado fijo, sumar
sus costes y obtener el promedio por carácter, excluyendo espacios. El coste
normalizado será ese promedio dividido por el máximo coste de un carácter
admitido en el mismo idioma.

**Decisión confirmada:** `¿` y `¡` están permitidos únicamente en español.
Se excluyen del conjunto inglés porque `us(basic)` no ofrece esos caracteres.
No se añaden combinaciones alternativas ni se cambia a US International.
Las constantes y la geometría del modelo siguen pendientes de aprobación.

## Fuentes y alcance de la comprobación

Se inspeccionaron los archivos instalados de **xkeyboard-config 2.48**:

- `/usr/share/X11/xkb/symbols/us`, bloque `basic`.
- `/usr/share/X11/xkb/symbols/latam`, bloque `basic`.
- `/usr/share/X11/xkb/symbols/latin`, bloques `basic` y `type4`, heredados por `latam`.

Referencias del proyecto: [organización de símbolos XKB](https://xkeyboard-config.freedesktop.org/doc/symbols/)
y fuentes upstream de [US](https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config/-/blob/master/symbols/us),
[Latinoamérica](https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config/-/blob/master/symbols/latam)
y [Latin](https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config/-/blob/master/symbols/latin).
La documentación de organización fue accesible; los endpoints de código upstream
no pudieron recuperarse con el navegador de investigación. Los mapas se
verificaron contra los archivos locales mencionados, no contra un supuesto
contenido remoto actualizado.

XKB verifica qué símbolo produce una tecla, **no** nuestra asignación de dedos,
geometría, dificultad ni coste. Esas últimas son decisiones del modelo propuesto.
Fijaríamos esta referencia antes de implementar, sin leer el teclado del usuario
durante la clasificación.

## 1. Geometría simplificada y dedos

Usar identificadores de tecla XKB y una rejilla abstracta. Para una columna `i`
contada desde 1, `x = i - 1 + desplazamiento`. Las unidades no son milímetros.

| Fila | Identificadores | `y` | Desplazamiento horizontal |
| --- | --- | --- | --- |
| Números | `AE01` a `AE12` | 0 | 0 |
| Superior | `AD01` a `AD12` | 1 | 0.25 |
| Inicial | `AC01` a `AC11` | 2 | 0.50 |
| Inferior | `AB01` a `AB10` | 3 | 1.00 |

Las letras base de ambas distribuciones son:

| Fila | Secuencia de izquierda a derecha |
| --- | --- |
| `AD01` a `AD10` | `q w e r t y u i o p` |
| `AC01` a `AC09` | `a s d f g h j k l` |
| `AB01` a `AB07` | `z x c v b n m` |
| `AE01` a `AE10` | `1 2 3 4 5 6 7 8 9 0` |

Las mayúsculas usan la misma tecla más Shift. Proponemos la siguiente asignación
fija para **cada una de las cuatro filas**, incluidas las teclas de puntuación:

| Columnas | Dedo | Posición inicial |
| --- | --- | --- |
| 1 | Meñique izquierdo | `AC01` (`a`) |
| 2 | Anular izquierdo | `AC02` (`s`) |
| 3 | Medio izquierdo | `AC03` (`d`) |
| 4 y 5 | Índice izquierdo | `AC04` (`f`) |
| 6 y 7 | Índice derecho | `AC07` (`j`) |
| 8 | Medio derecho | `AC08` (`k`) |
| 9 | Anular derecho | `AC09` (`l`) |
| 10, 11 y 12 | Meñique derecho | `AC10` (`;` en US, `ñ` en latinoamericano) |

Esta asignación es una convención explícita del clasificador, no una afirmación
sobre cómo escribe cada persona. No modelamos dedos que permanecen en la tecla
anterior, ni cambios de mano, ni pulsaciones simultáneas reales.

## 2. Puntuación: carácter a pulsación

`Shift + tecla` significa pulsar con el dedo asignado y usar el Shift de la mano
contraria. Los números se obtienen directamente desde `AE01` a `AE10`.

| Carácter | Latinoamericano `latam(basic)` | Estadounidense `us(basic)` |
| --- | --- | --- |
| `.` | `AB09` | `AB09` |
| `,` | `AB08` | `AB08` |
| `;` | `Shift + AB08` | `AC10` |
| `:` | `Shift + AB09` | `Shift + AC10` |
| `¿` | `AE12` | No admitido en inglés |
| `?` | `Shift + AE11` | `Shift + AB10` |
| `¡` | `Shift + AE12` | No admitido en inglés |
| `!` | `Shift + AE01` | `Shift + AE01` |
| `'` | `AE11` | `AC11` |
| `"` | `Shift + AE02` | `Shift + AC11` |
| `(` | `Shift + AE08` | `Shift + AE09` |
| `)` | `Shift + AE09` | `Shift + AE10` |
| `-` | `AB10` | `AE11` |

Las comillas tipográficas simples no necesitan una entrada propia: ya se acordó
convertirlas a `'` después de validar su emparejamiento. La restricción de
apóstrofos dentro de palabras en español pertenece a validación; no cambia el
coste de las comillas permitidas.

## 3. Letras adicionales del español

La tecla `AD11` del mapa latinoamericano produce una tilde aguda muerta sin Shift
y una diéresis muerta con Shift. Se modela una secuencia de dos pulsaciones para
la vocal resultante. El orden indicado es parte de la propuesta determinista.

| Caracteres | Secuencia |
| --- | --- |
| `ñ` | `AC10` |
| `Ñ` | `Shift + AC10` |
| `á é í ó ú` | `AD11` y después la tecla de `a e i o u`, respectivamente |
| `Á É Í Ó Ú` | `AD11` y después `Shift +` la tecla de la vocal correspondiente |
| `ü` | `Shift + AD11` y después `AD07` (`u`) |
| `Ü` | `Shift + AD11` y después `Shift + AD07` (`U`) |

No añadimos AltGr, Compose, códigos numéricos del sistema ni Caps Lock. Una
secuencia adicional solo se incorporaría si se aprueba explícitamente.

## 4. Fórmula y constantes iniciales propuestas

Para una tecla no modificadora `k`, cuyo dedo asignado parte de `home(k)`:

```text
distance(k) = sqrt((x(k) - x(home(k)))² + (y(k) - y(home(k)))²)
press_cost(k, shift) = 1 + distance(k) + (0.5 si usa Shift; 0 en otro caso)
character_cost(c) = suma de press_cost de su secuencia
```

| Constante | Propuesta | Motivo |
| --- | --- | --- |
| Pulsación base | `1` por tecla no modificadora | Evita que las letras de la fila inicial tengan coste cero. Es una extensión propuesta, no una medida física. |
| Distancia | Euclídea; multiplicador `1` | Regla fija sobre la rejilla anterior. |
| Shift | `0.5` por cada pulsación que lo requiera | Aproxima el modificador; no añade además su distancia o una pulsación base de Shift. |
| Tecla muerta | Su `press_cost` completo | Ya incorpora la pulsación adicional; no añadir otro recargo por tilde o diéresis. |

No se amortiza Shift en secuencias de mayúsculas: cada carácter tiene coste
independiente. Para `Ü`, se cobra Shift en las dos pulsaciones de la secuencia,
aunque una persona pudiera mantenerlo presionado. Es una limitación consciente.

Los espacios no generan coste ni participan en el denominador. Se conservan en
el contenido almacenado y en la separación de palabras. Para texto sin ningún
carácter medible, el cálculo se interrumpe con error de validación; no se divide
por cero ni se asigna dificultad por defecto.

## 5. Normalización del esfuerzo

Sea `S_language` el conjunto fijo de caracteres **normalizados y admitidos**
del idioma, sin espacios. Antes de utilizar el modelo, todos deben tener una
secuencia definida en la tabla del teclado.

```text
Cmax_language = max(character_cost(c) para c en S_language)
Cmean = suma(character_cost(c) para c en texto sin espacios) / cantidad_sin_espacios
K = Cmean / Cmax_language
```

`Cmax_language` depende de la versión fija del mapa, no del texto recibido.
No usamos el máximo observado en cada texto, porque eso haría variar la escala.
No se inventan valores para caracteres sin secuencia. `¿` y `¡` no forman parte
de `S_eng`: su presencia en una entrada inglesa debe producir un error de
validación, no una transformación silenciosa.

`K` se incorpora con el peso de esfuerzo del **30 %** ya acordado. Ni la rejilla
ni las constantes tienen validación empírica todavía. Es posible que las escalas
sean distintas entre idiomas; los umbrales comunes deberán comprobarse con
nuestros ejemplos, no darse por correctos de antemano.

## Comprobaciones antes de implementar

- [x] Permitir `¿` y `¡` únicamente en español, manteniendo QWERTY US para inglés.
- [x] Aprobar la rejilla, asignación de dedos, base `1` y recargo Shift `0.5`.
- [ ] Verificar que cada carácter admitido tenga exactamente una secuencia canónica.
- [ ] Comprobar `cost(A) > cost(a)`, `cost(á) > cost(a)` y `cost(ü) > cost(u)`.
- [ ] Comprobar que `cost(ñ)` usa una tecla, no una composición con tilde.
- [ ] Calcular los máximos por idioma desde los mapas completos y registrar la versión.
- [ ] Calcular las contribuciones en los ejemplos y revisar los umbrales provisionales.

**Siguiente paso:** verificar la cobertura de los mapas, calcular los máximos por
idioma y evaluar los ejemplos antes de revisar los umbrales provisionales.
