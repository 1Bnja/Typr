from fastapi import FastAPI
from app.routers import auth, health, matches, rooms, texts, users
from app.ws import rooms as rooms_ws

DESCRIPTION = """
REST API for **Typr**, a typing-speed practice and multiplayer race app.

## Authentication

Call `POST /api/v1/auth/login` and send the returned token on every protected
endpoint as `Authorization: Bearer <token>`. Use the **Authorize** button above
to try the endpoints from this page.

## Room WebSocket protocol

WebSockets are not part of the OpenAPI schema, so the live room protocol is
described here. All messages are JSON.

**URL:** `ws(s)://<host>/api/v1/ws/rooms/{code}` where `{code}` is the
6-character room code. The user must already be a member of the room (join it
through `POST /api/v1/rooms/{code}/join` first). A code that does not match
`^[A-Za-z0-9]{6}$` is rejected by path validation before the socket is
accepted, so it never reaches the close codes below.

**Authentication:** the token is never sent in the URL. The first message must
arrive within 5 seconds and be `{"type": "auth", "token": "<token>"}`.

**Client to server**

| Message | Notes |
|---------|-------|
| `{"type": "auth", "token": "..."}` | First message, required. |
| `{"type": "ready", "ready": true}` | Marks the player as ready or not ready. |
| `{"type": "start"}` | Starts the match. Host only. |
| `{"type": "progress", "typed": 12, "errors": 1}` | Sent during a race. |

**Server to client** (`type` field)

| Type | Payload |
|------|---------|
| `room_state` | `room`: snapshot sent on every change. |
| `player_joined` | `userId`, `username`. |
| `player_left` | `userId`. |
| `countdown` | `round`, `rounds`, `seconds`. |
| `race_start` | `round`, `rounds`, `text`, `timeLimitMs`, `elapsedMs`, `players`, and an optional `you` object (`typed`, `errors`, `finishedMs`) when a player reconnects mid-race. |
| `progress_update` | `userId`, `progress`, `finished`. |
| `race_end` | `round`, `rounds`, `results`, `nextRoundInS`, and on the last round `matchResults`, `returnToRoomInS`. |
| `room_closed` | The room was closed. |
| `error` | `code`, `detail`: a rejected client message (for example `invalid_message`, `not_host`, `not_enough_players`, `players_not_ready`). |

**Close codes:** `4401` unauthenticated or session expired, `4403` not a member
of the room, `4404` room not found or closed, `4409` replaced by a newer
connection of the same user, `4410` removed from the room (left or kicked).
"""

TAGS_METADATA = [
    {"name": "health", "description": "Liveness probe."},
    {"name": "auth", "description": "Registration, login, logout and session renewal."},
    {"name": "users", "description": "Current user profile and personal statistics."},
    {"name": "texts", "description": "Typing texts: random pick, AI generation, validation and storage."},
    {"name": "matches", "description": "Practice matches, history and the monthly leaderboard."},
    {"name": "rooms", "description": "Multiplayer rooms: create, configure, join, leave, kick and close."},
]

app = FastAPI(
    title="Typr API",
    version="1.0.0",
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(texts.router, prefix="/api/v1/texts")
app.include_router(matches.router, prefix="/api/v1/matches")
app.include_router(rooms.router, prefix="/api/v1/rooms")
app.include_router(rooms_ws.router, prefix="/api/v1/ws")
