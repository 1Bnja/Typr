# Resultados del primer cálculo de calibración

**Cálculo ejecutado; modelo inicial, no validación de dificultad humana.**

Se evaluaron 16 textos: {'medium': 8, 'advanced': 8}. El puntaje va de **31.3560 a 64.6770**. Hay 10 diferencias con las etiquetas tentativas; no son fallos de pruebas.

No se ajustaron pesos, escalas, textos ni cortes para obtener estos resultados.

## Reproducir

```bash
python3 docs/issues-camilo/t-02.1/calculate_calibration.py
```

El script usa solo la biblioteca estándar y genera este informe y [los datos completos](calibration-results.json). No importa la aplicación, no accede a BD/red ni implementa la normalización de producción.

Los 16 textos ya tienen espacios canónicos; se verifica ese requisito sin reescribir su puntuación ni sus decimales. Los hashes de ambas fuentes quedan en JSON.

## Supuesto operativo pendiente de aprobación

Para poder ejecutar este experimento, se separan tokens por espacios, se elimina la puntuación externa y se cuentan letras/dígitos dentro de cada token. Así, `don't` mide 4 y es una palabra; `9.30` mide 3 y es un token numérico. Este último criterio no estaba definido: es un supuesto del experimento, no una regla aprobada para producción. No se generaliza todavía a palabras con guion. Los ejemplos no tienen ese caso.

## Escalas y costes fijos

Se usan los pesos 35/30/15/10/10 para entropía/esfuerzo/longitud media/variedad/longitud máxima. Las longitudes se dividen por 12 y 24, con tope 1. Entropía y variedad se dividen por `log2(A)` y `A`; esfuerzo por el máximo coste del alfabeto admitido del idioma. Todos excluyen espacios donde corresponde.

| Idioma | A | Coste máximo fijo | Caracteres de coste máximo |
| --- | ---: | ---: | --- |
| `eng` | 73 | 3.56155281 | `!()` |
| `spa` | 89 | 5.28077641 | `Ü` |

Los mapas completos de secuencias y costes están en JSON y siguen [el modelo de teclado aprobado](keyboard-effort.md). La referencia se fija en el script; no depende del teclado de la máquina.

## Métricas sin normalizar

`H`: bits por carácter; `U`: caracteres distintos; `N`: palabras/tokens; `Lmed/Lmax`: longitudes; `Cmed`: coste medio sin espacios.

| ID | H | U | N | Lmed | Lmax | Cmed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPA-01 | 3.0472 | 11 | 9 | 2.8889 | 5 | 1.4005 |
| SPA-02 | 3.1348 | 12 | 9 | 3.1111 | 4 | 1.4200 |
| SPA-03 | 4.0923 | 23 | 9 | 5.1111 | 8 | 1.8497 |
| SPA-04 | 4.2375 | 24 | 11 | 4.6364 | 8 | 1.9923 |
| SPA-05 | 4.3755 | 26 | 12 | 4.9167 | 13 | 1.9380 |
| SPA-06 | 4.2468 | 26 | 11 | 7.0000 | 14 | 2.0672 |
| SPA-07 | 4.7468 | 38 | 11 | 8.0909 | 16 | 2.1438 |
| SPA-08 | 4.5718 | 37 | 18 | 6.1667 | 21 | 2.0453 |
| ENG-01 | 3.2090 | 12 | 10 | 2.6000 | 3 | 1.5147 |
| ENG-02 | 3.4712 | 13 | 10 | 2.9000 | 4 | 1.7907 |
| ENG-03 | 3.9121 | 19 | 11 | 4.6364 | 6 | 1.8220 |
| ENG-04 | 4.1464 | 23 | 11 | 5.0000 | 7 | 1.9537 |
| ENG-05 | 4.2205 | 23 | 10 | 5.2000 | 13 | 2.0068 |
| ENG-06 | 4.0703 | 24 | 12 | 5.8333 | 12 | 1.8629 |
| ENG-07 | 4.6177 | 36 | 12 | 8.0833 | 15 | 2.0516 |
| ENG-08 | 4.3525 | 34 | 16 | 8.0000 | 17 | 1.9527 |

## Métricas normalizadas

| ID | E | K | Lmed | V | Lmax |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPA-01 | 0.4706 | 0.2652 | 0.2407 | 0.1236 | 0.2083 |
| SPA-02 | 0.4841 | 0.2689 | 0.2593 | 0.1348 | 0.1667 |
| SPA-03 | 0.6319 | 0.3503 | 0.4259 | 0.2584 | 0.3333 |
| SPA-04 | 0.6544 | 0.3773 | 0.3864 | 0.2697 | 0.3333 |
| SPA-05 | 0.6757 | 0.3670 | 0.4097 | 0.2921 | 0.5417 |
| SPA-06 | 0.6558 | 0.3914 | 0.5833 | 0.2921 | 0.5833 |
| SPA-07 | 0.7330 | 0.4060 | 0.6742 | 0.4270 | 0.6667 |
| SPA-08 | 0.7060 | 0.3873 | 0.5139 | 0.4157 | 0.8750 |
| ENG-01 | 0.5184 | 0.4253 | 0.2167 | 0.1644 | 0.1250 |
| ENG-02 | 0.5608 | 0.5028 | 0.2417 | 0.1781 | 0.1667 |
| ENG-03 | 0.6320 | 0.5116 | 0.3864 | 0.2603 | 0.2500 |
| ENG-04 | 0.6699 | 0.5485 | 0.4167 | 0.3151 | 0.2917 |
| ENG-05 | 0.6818 | 0.5635 | 0.4333 | 0.3151 | 0.5417 |
| ENG-06 | 0.6576 | 0.5231 | 0.4861 | 0.3288 | 0.5000 |
| ENG-07 | 0.7460 | 0.5760 | 0.6736 | 0.4932 | 0.6250 |
| ENG-08 | 0.7032 | 0.5483 | 0.6667 | 0.4658 | 0.7083 |

## Contribuciones en puntos y clasificación

La clasificación usa el puntaje sin redondear: `<25 easy`, `<50 medium`, `<75 advanced`, resto `expert`. Solo las cifras mostradas se redondean.

| ID | E × 35 | K × 30 | Lmed × 15 | V × 10 | Lmax × 10 | Puntaje | Tentativo | Calculado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| SPA-01 | 16.4695 | 7.9561 | 3.6111 | 1.2360 | 2.0833 | **31.3560** | `easy` | `medium` |
| SPA-02 | 16.9432 | 8.0671 | 3.8889 | 1.3483 | 1.6667 | **31.9141** | `easy` | `medium` |
| SPA-03 | 22.1179 | 10.5082 | 6.3889 | 2.5843 | 3.3333 | **44.9325** | `medium` | `medium` |
| SPA-04 | 22.9027 | 11.3184 | 5.7955 | 2.6966 | 3.3333 | **46.0465** | `medium` | `medium` |
| SPA-05 | 23.6489 | 11.0098 | 6.1458 | 2.9213 | 5.4167 | **49.1425** | `advanced` | `medium` |
| SPA-06 | 22.9529 | 11.7435 | 8.7500 | 2.9213 | 5.8333 | **52.2011** | `advanced` | `advanced` |
| SPA-07 | 25.6556 | 12.1790 | 10.1136 | 4.2697 | 6.6667 | **58.8845** | `expert` | `advanced` |
| SPA-08 | 24.7098 | 11.6192 | 7.7083 | 4.1573 | 8.7500 | **56.9446** | `expert` | `advanced` |
| ENG-01 | 18.1449 | 12.7589 | 3.2500 | 1.6438 | 1.2500 | **37.0476** | `easy` | `medium` |
| ENG-02 | 19.6275 | 15.0834 | 3.6250 | 1.7808 | 1.6667 | **41.7833** | `easy` | `medium` |
| ENG-03 | 22.1207 | 15.3475 | 5.7955 | 2.6027 | 2.5000 | **48.3664** | `medium` | `medium` |
| ENG-04 | 23.4456 | 16.4562 | 6.2500 | 3.1507 | 2.9167 | **52.2191** | `medium` | `advanced` |
| ENG-05 | 23.8644 | 16.9038 | 6.5000 | 3.1507 | 5.4167 | **55.8356** | `advanced` | `advanced` |
| ENG-06 | 23.0154 | 15.6916 | 7.2917 | 3.2877 | 5.0000 | **54.2863** | `advanced` | `advanced` |
| ENG-07 | 26.1103 | 17.2811 | 10.1042 | 4.9315 | 6.2500 | **64.6770** | `expert` | `advanced` |
| ENG-08 | 24.6111 | 16.4478 | 10.0000 | 4.6575 | 7.0833 | **62.7997** | `expert` | `advanced` |

## Interpretación y límites

- No se obtuvo ningún `easy` ni `expert`: hay ocho `medium` y ocho `advanced`. En español son cinco `medium` y tres `advanced`; en inglés, tres y cinco.
- La distribución calculada debe leerse con los valores anteriores: no acredita que las etiquetas humanas estén equivocadas ni que el modelo esté validado.
- El alfabeto fijo incluye símbolos poco frecuentes en prosa. Las divisiones por `A` y `log2(A)` no obligan a textos naturales a cubrir todo el intervalo.
- La normalización por el carácter más costoso reduce especialmente el esfuerzo español: las composiciones con teclas muertas elevan el máximo de referencia.
- Los cortes equidistantes 25/50/75 no son cuantiles ni garantizan muestras en los cuatro niveles. No se cambian automáticamente para reproducir etiquetas tentativas.
- El corpus es pequeño y construido: faltan muestras independientes y evidencia de velocidad/errores humanos. Entropía y variedad están correlacionadas.

## Comprobaciones ejecutadas

Se completaron **48 comprobaciones** mediante excepciones explícitas (también activas con `python -O`): cobertura exacta de alfabetos, secuencias no vacías, suma de pesos, costes relativos, ñ como tecla única, entropía 1 en ambos controles, contracción/decimal, intervalos normalizados, suma de contribuciones y repetición idéntica.

La ejecución se repitió y los SHA-256 de ambos archivos generados fueron idénticos. También se ejecutó con `python3 -O` y pasó las 48 comprobaciones; Ruff pasó. Estos controles prueban coherencia del experimento, no integración del backend.

## Próximo paso

Revisar las contribuciones y los supuestos de tokenización antes de proponer cambios explícitos de escala o cortes. No cambiar simultáneamente todas las variables ni ajustar solo para coincidir con este conjunto.
