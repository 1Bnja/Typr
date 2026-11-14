"""Sincronización en vivo de una sala por WebSocket.

Protocolo (JSON):
  cliente -> {"type": "auth", "token": "<JWT>"}        primer mensaje, obligatorio
  servidor -> {"type": "room_state", "players": [...]} al que entra
  servidor -> {"type": "player_joined", "player": {...}} al resto
  cliente -> {"type": "progress", "progress": 0..1}
  servidor -> {"type": "progress_update", "userId": n, "progress": 0..1} al resto
  servidor -> {"type": "player_left", "userId": n} al resto
"""

import asyncio

from fastapi import APIRouter, Depends, Path, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.security import decode_access_token

router = APIRouter()

AUTH_TIMEOUT_S = 5
MAX_PLAYERS = 10
CLOSE_UNAUTHORIZED = 4401
CLOSE_ROOM_FULL = 4403
CLOSE_REPLACED = 4409


class Player:
    def __init__(self, user: User, socket: WebSocket, replaces: "Player | None"):
        self.user_id = user.id
        self.username = user.username
        self.socket = socket
        self.replaces = replaces
        self.progress = replaces.progress if replaces else 0.0

    def public(self) -> dict:
        return {
            "userId": self.user_id,
            "username": self.username,
            "progress": self.progress,
        }


class RoomHub:
    """Salas en memoria: válido mientras el backend corra en un solo proceso."""

    def __init__(self) -> None:
        self.rooms: dict[str, dict[int, Player]] = {}

    def register(self, code: str, user: User, socket: WebSocket) -> Player | None:
        players = self.rooms.setdefault(code, {})
        previous = players.get(user.id)
        if previous is None and len(players) >= MAX_PLAYERS:
            return None
        # Si el usuario ya estaba (recarga u otra pestaña), la conexión nueva
        # reemplaza a la anterior y conserva su avance.
        player = Player(user, socket, previous)
        players[user.id] = player
        return player

    async def welcome(self, code: str, player: Player) -> None:
        if player.replaces is not None:
            await _close_quietly(player.replaces.socket, CLOSE_REPLACED)
        await player.socket.send_json(
            {
                "type": "room_state",
                "players": [other.public() for other in self.rooms[code].values()],
            }
        )
        if player.replaces is None:
            await self.broadcast(
                code, {"type": "player_joined", "player": player.public()}, player
            )

    async def leave(self, code: str, player: Player) -> None:
        players = self.rooms.get(code, {})
        if players.get(player.user_id) is not player:
            return  # otra conexión del mismo usuario ya ocupó su lugar
        del players[player.user_id]
        if not players:
            del self.rooms[code]
            return
        await self.broadcast(code, {"type": "player_left", "userId": player.user_id})

    async def broadcast(
        self, code: str, message: dict, exclude: Player | None = None
    ) -> None:
        for player in list(self.rooms.get(code, {}).values()):
            if player is exclude:
                continue
            try:
                await player.socket.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                # Ese socket ya se cayó; su propio bucle se encarga de sacarlo.
                pass


hub = RoomHub()


async def _close_quietly(socket: WebSocket, code: int) -> None:
    try:
        await socket.close(code=code)
    except (WebSocketDisconnect, RuntimeError):
        pass


async def _authenticate(socket: WebSocket, db: Session) -> User | None:
    try:
        message = await asyncio.wait_for(socket.receive_json(), AUTH_TIMEOUT_S)
    except (asyncio.TimeoutError, ValueError, KeyError):
        return None
    if not isinstance(message, dict) or message.get("type") != "auth":
        return None
    token = message.get("token")
    user_id = decode_access_token(token) if isinstance(token, str) else None
    if user_id is None:
        return None
    try:
        return await run_in_threadpool(db.get, User, user_id)
    finally:
        # La sesión solo sirve para identificar al usuario: se libera ya para
        # no retener una conexión del pool mientras dure el socket.
        db.close()


async def _listen(code: str, player: Player) -> None:
    while True:
        try:
            message = await player.socket.receive_json()
        except (ValueError, KeyError):
            message = None
        progress = (
            message.get("progress")
            if isinstance(message, dict) and message.get("type") == "progress"
            else None
        )
        if (
            isinstance(progress, bool)
            or not isinstance(progress, (int, float))
            or not 0 <= progress <= 1
        ):
            await player.socket.send_json(
                {"type": "error", "detail": "Mensaje inválido."}
            )
            continue
        player.progress = float(progress)
        await hub.broadcast(
            code,
            {
                "type": "progress_update",
                "userId": player.user_id,
                "progress": player.progress,
            },
            player,
        )


@router.websocket("/rooms/{code}")
async def room_socket(
    socket: WebSocket,
    code: str = Path(pattern=r"^[A-Za-z0-9]{4,12}$"),
    db: Session = Depends(get_db),
) -> None:
    await socket.accept()
    try:
        user = await _authenticate(socket, db)
        if user is None:
            await socket.close(code=CLOSE_UNAUTHORIZED)
            return
        player = hub.register(code, user, socket)
        if player is None:
            await socket.close(code=CLOSE_ROOM_FULL)
            return
        try:
            await hub.welcome(code, player)
            await _listen(code, player)
        finally:
            await hub.leave(code, player)
    except WebSocketDisconnect:
        pass
