# Resultados de práctica

La API utiliza el JWT del usuario y las tablas existentes `texts`, `games` y
`game_participants`. No requiere una migración nueva.

## Guardar una prueba

`POST /api/v1/matches/practice`, con `Authorization: Bearer <token>`.

Para un texto local:

```json
{
  "text": { "content": "casa mesa gato", "language": "spa" },
  "timeMs": 12000,
  "ppm": 45,
  "precisionPct": 96,
  "progress": 1
}
```

Si el texto ya está registrado, enviar `"textId": 123` en lugar de `text`.
La petición debe incluir exactamente una de esas dos alternativas.

El servidor devuelve `201` con `id`, `textId`, `language`, `difficulty`, las
métricas, `score`, `startedAt` y `finishedAt`. Los campos JSON siguen la
convención camelCase de `CamelModel`.

El texto local pasa por `TextFacade.process`: validación de caracteres,
normalización y clasificación. Se reutiliza un texto con el mismo contenido
normalizado, idioma y dificultad. El frontend envía `difficulty` con el nivel
seleccionado para el texto local. Si falta ese campo, se conserva la clasificación
automática del backend como respaldo para clientes anteriores. Un `textId` ya
registrado no se puede reutilizar con una dificultad distinta. Los resultados
anteriores conservan su dificultad original.

El servicio conserva la transacción hasta guardar el texto, la partida y el
participante. Si falla una inserción, hace rollback de toda la operación.
El usuario se obtiene del JWT y la puntuación se calcula en el servidor como
`round(ppm * precisionPct / 100)`, con el mismo redondeo positivo del frontend.
Las métricas recibidas son las medidas por el cliente; este endpoint no verifica
las pulsaciones ni certifica resultados competitivos.

Si la prueba se completa y tiene precisión de al menos 75%, el servidor actualiza
`texts.ideal_time_ms` y `texts.record_user_id` cuando el tiempo supera la marca
anterior (o cuando el texto todavía no tenía marca). Las pruebas incompletas o con
menos precisión no modifican el récord. La actualización es atómica: si otra
partida guarda una marca mejor al mismo tiempo, se conserva la menor.

Errores: `422` para datos inválidos, `404` si no existe `textId` y `503` ante un
fallo de almacenamiento. La autenticación usa la dependencia existente.

## Consultar el historial

`GET /api/v1/matches/practice?limit=20&offset=0`, con el mismo JWT.

Devuelve únicamente las prácticas terminadas del usuario autenticado, de la más
reciente a la más antigua. `limit` admite entre 1 y 100 y `offset` debe ser
positivo o cero. Un usuario sin partidas recibe una lista vacía.

La vista `/practice/history` permite filtrar por `difficulty` y `language` y
recorre los resultados en páginas de diez pruebas.

## Ranking mensual

`GET /api/v1/matches/leaderboard?month=2026-11&difficulty=easy&language=spa`.
Requiere JWT. `month` es opcional y toma el mes actual en `America/Santiago`.
El límite predeterminado es 50 y admite hasta 100 participantes. El filtro de
idioma es opcional.

Solo cuenta prácticas terminadas (`progress = 1`) con precisión de al menos 75%.
Se selecciona la mejor partida por usuario y se ordena por puntuación descendente,
precisión descendente, menor tiempo y fecha de finalización más temprana. El
identificador de partida resuelve
empates exactos. No se suman puntos por repetir pruebas. El período incluye el
inicio del mes en Santiago y excluye el inicio del siguiente mes.

La respuesta contiene `month`, `difficulty`, `language`, `timezone` y `entries`.
Cada entrada incluye posición, identificador público, nombre de usuario y las
métricas de la mejor partida; no expone correos ni datos de autenticación.
La vista `/practice/leaderboard` marca al usuario actual cuando aparece en el top.

## Pruebas

Desde `backend`:

```sh
.venv/bin/python -m unittest discover -s tests -p test_practice_matches.py -v
.venv/bin/ruff check .
```

Las pruebas HTTP usan SQLite en memoria y activan sus claves foráneas. Verifican
persistencia, autenticación, privacidad, validaciones, reutilización del texto,
paginación, redondeo y rollback ante una inserción fallida.

La suite completa utiliza PostgreSQL desechable:

```sh
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner
docker compose -f docker-compose.test.yml down --volumes --remove-orphans
```

Las pruebas de práctica en PostgreSQL crean y eliminan su propio esquema dentro
de la base de pruebas. No usan la base configurada para desarrollo o producción.
