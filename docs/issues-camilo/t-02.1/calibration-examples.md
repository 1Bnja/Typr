# Conjunto inicial para calibrar la dificultad de textos

**Estado: propuesta para revisión humana; no es una clasificación validada.**

Estos 16 textos originales permiten discutir qué esperamos de los cuatro niveles
antes de fijar escalas y umbrales. Hay dos ejemplos por nivel e idioma. Las
etiquetas son hipótesis: el cálculo futuro puede contradecirlas y tendremos que
revisar los ejemplos o el modelo, no forzar el resultado para que coincida.

## Cómo revisar este conjunto

1. Leer cada texto y revisar su nivel tentativo pensando en mecanografía, no en
   comprensión lectora.
2. Marcar los ejemplos que parezcan mal ordenados y explicar el motivo.
3. Calcular las métricas cuando estén implementadas y comparar sus contribuciones.
4. Ajustar escalas y, después, los umbrales de clasificación.

No se han calculado puntajes ni probado un clasificador con estos textos.

## Español: teclado latinoamericano

| ID | Idioma | Nivel tentativo | Texto | Motivo para revisarlo en ese nivel |
| --- | --- | --- | --- | --- |
| SPA-01 | `spa` | `easy` | `La casa es de Ana. La sala es clara.` | Palabras cortas, repetición y puntuación mínima. |
| SPA-02 | `spa` | `easy` | `Luis sale al sol. Sara lee en la sala.` | Vocabulario corto y estructura repetida; permite contrastar distintas letras sin añadir símbolos. |
| SPA-03 | `spa` | `medium` | `Mañana visitaré el jardín y llevaré una cámara pequeña.` | Añade ñ, vocales acentuadas y palabras de longitud intermedia. |
| SPA-04 | `spa` | `medium` | `El pingüino nadó junto al muelle, mientras Lucía tomó una foto.` | Combina diéresis, tildes, una coma y mayor diversidad de caracteres. |
| SPA-05 | `spa` | `advanced` | `¿Puedes revisar la configuración del equipo? La conexión falló a las 9.30.` | Preguntas, mayúsculas, cifras y decimal, además de palabras más largas. |
| SPA-06 | `spa` | `advanced` | `La lingüista explicó: 'Esta interpretación necesita precisión'; después corrigió el párrafo.` | Comillas emparejadas, dos puntos, punto y coma, diéresis y palabras extensas. |
| SPA-07 | `spa` | `expert` | `¡ATENCIÓN! El diagnóstico (versión 3.14) exige sincronización, reproducibilidad y verificación exhaustiva.` | Mezcla mayúsculas, signos, paréntesis, decimal y términos extensos. |
| SPA-08 | `spa` | `expert` | `La investigadora escribió: "¿Qué relación existe entre la interdisciplinariedad, la ambigüedad y el año 2026?" ¡Explícalo con precisión!` | Combina varios delimitadores, acentos, diéresis, ñ, cifras y una palabra especialmente larga. |

## Inglés: teclado QWERTY US

| ID | Idioma | Nivel tentativo | Texto | Motivo para revisarlo en ese nivel |
| --- | --- | --- | --- | --- |
| ENG-01 | `eng` | `easy` | `Dad has a red hat. Ada has a red bag.` | Palabras cortas, repetición y puntuación mínima. |
| ENG-02 | `eng` | `easy` | `Sam sits at home. The cat sits on a mat.` | Estructura sencilla con un conjunto algo distinto de letras. |
| ENG-03 | `eng` | `medium` | `Please bring the yellow basket and leave it beside the window.` | Más variedad y palabras de longitud intermedia, sin complejidad de símbolos. |
| ENG-04 | `eng` | `medium` | `Don't close the window, because we're waiting for the morning breeze.` | Contracciones permitidas, coma y palabras más largas. |
| ENG-05 | `eng` | `advanced` | `Can you verify the configuration? The connection failed at 9.30.` | Pregunta, decimal y términos largos; permite contrastar con SPA-05 sin asumir puntajes equivalentes. |
| ENG-06 | `eng` | `advanced` | `The analyst wrote: 'Check the measurements'; then she compared the unexpected results.` | Comillas emparejadas, dos puntos, punto y coma y términos extensos. |
| ENG-07 | `eng` | `expert` | `WARNING! The diagnostic report (version 3.14) requires synchronization, reproducibility and thorough verification.` | Mayúsculas, signos, paréntesis, decimal y palabras extensas. |
| ENG-08 | `eng` | `expert` | `The researcher asked: "Which interdependencies affect the 2026 experiment?" Don't overlook uncertainty, characterization or quantitative measurements!` | Delimitadores, contracción, cifras y varias palabras largas en un texto con diversidad de símbolos. |

## Pares de contraste

No asignamos un nivel a estos pares. Sirven para examinar si cada métrica se
comporta como esperamos, sin suponer que un cambio altera únicamente una métrica.
Son controles de diagnóstico, no textos propuestos para cargar al catálogo.

| ID | Idioma | Texto A | Texto B | Qué observar |
| --- | --- | --- | --- | --- |
| C-01 | `eng` | `read the report` | `Read the REPORT` | La caja cambia símbolos y puede añadir uso de Shift. Comparar entropía, variedad y esfuerzo sin cambiar palabras. |
| C-02 | `spa` | `Ana lee el texto` | `¿Ana lee el texto?` | La puntuación participa en entropía, variedad y esfuerzo; no debería alargar las palabras medidas. |
| C-03 | `eng` | `the plan needs care` | `the plan needs characterization` | Observar longitud media y máxima; también cambia la distribución de caracteres. |
| C-04 | `eng` | `aaaabbbb` | `abababab` | Control matemático: ambos tienen entropía de 1 bit por carácter y la misma variedad. Su orden es diferente. |

En C-04, cada símbolo tiene probabilidad 1/2, por lo que
`H = -(1/2 log2(1/2) + 1/2 log2(1/2)) = 1`. La entropía de frecuencias no
observa el orden. Nuestro esfuerzo simplificado desde la posición inicial de
cada dedo tampoco distingue estos dos órdenes: no modela desplazamientos entre
pulsaciones. Este control permite recordar esa limitación, no corregirla con
umbrales arbitrarios.

## Reglas que aplicaremos al medir

- Medir sobre el contenido normalizado que se almacenará.
- Entropía de Shannon con base 2: excluir espacios e incluir puntuación y
  diferencias entre mayúsculas y minúsculas.
- Contar palabras sin puntuación externa; medir longitud media y máxima.
  `don't` cuenta como una palabra de cuatro letras.
- Estimar esfuerzo con el teclado del idioma, distancia desde la posición
  inicial del dedo y costes adicionales por Shift y acentos o diéresis.
- La definición exacta de variedad y la inclusión de espacios en el promedio
  de esfuerzo siguen pendientes; no se calculan resultados mientras falten.

### Pesos iniciales acordados

| Métrica | Peso provisional |
| --- | --- |
| Entropía de Shannon | 35 % |
| Esfuerzo de teclado | 30 % |
| Longitud media de palabras | 15 % |
| Variedad de caracteres | 10 % |
| Longitud máxima de palabra | 10 % |

La cantidad de palabras queda como dato descriptivo, sin peso inicial. Las
métricas necesitan escalas comparables antes de aplicar estos pesos. Todavía no
se han definido los límites de esas escalas ni los umbrales de los cuatro niveles.

## Límites y siguiente paso

- Entropía y variedad están relacionadas; revisar que no estemos dando dos veces
  demasiado peso al mismo fenómeno.
- Un texto más largo no debe recibir automáticamente un nivel mayor. La longitud
  total no tiene peso directo en esta propuesta.
- La dificultad lingüística de una palabra no equivale a esfuerzo de mecanografía.
- Los teclados pueden producir costes diferentes entre idiomas: no asumir que
  los niveles tentativos de ambas tablas implican puntajes idénticos.
- Este conjunto pequeño no representa todos los textos reales. No ajustar el
  modelo únicamente para reproducir sus etiquetas; reservar después otro conjunto
  independiente para comprobar la clasificación.

**Siguiente paso:** revisar los niveles tentativos. Después podremos definir las
escalas, calcular las contribuciones y proponer umbrales con evidencia visible.
La [propuesta general](proposal.md) sigue siendo un borrador; este documento no
implementa ni ejecuta la clasificación.
