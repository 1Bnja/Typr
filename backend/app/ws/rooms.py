"""Sala en vivo por WebSocket: presencia, "listo" y la carrera.

El cliente abre /api/v1/ws/rooms/{code} y su primer mensaje debe ser la
autenticación (así el token no viaja en la URL). Todos los mensajes son JSON.

Cliente -> servidor
  {"type": "auth", "token": "<JWT>"}
  {"type": "ready", "ready": true|false}
  {"type": "start"}                               solo el anfitrión
  {"type": "progress", "typed": n, "errors": n}   durante la carrera

Servidor -> cliente
  room_state       {room}                         foto de la sala ante cada cambio
  player_joined    {userId, username}
  player_left      {userId}
  countdown        {round, rounds, seconds}
  race_start       {round, rounds, text, timeLimitMs, elapsedMs, players, you?}
  progress_update  {userId, progress, finished}
  race_end         {round, rounds, results, nextRoundInS}
  room_closed      {}
  error            {code, detail}

La membresía, la configuración y el estado de la sala viven en la base de
datos. Aquí solo se guarda lo efímero: quién está conectado y la carrera en
curso. Eso alcanza mientras el backend corra en un único proceso.
"""

import asyncio
import logging
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Path, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.security import decode_access_token
from app.services import rooms
from app.services.race import Racer, RaceText, build_results, time_limit_ms
from app.services.rooms import MatchConfig, RoomError

logger = logging.getLogger(__name__)
router = APIRouter()

AUTH_TIMEOUT_S = 5
COUNTDOWN_S = 3
INTERMISSION_S = 8
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_MEMBER = 4403
CLOSE_ROOM_GONE = 4404
CLOSE_REPLACED = 4409
CLOSE_REMOVED = 4410


async def run_db(app: FastAPI, function, *args):
    """Ejecuta una función de servicio con su propia sesión, fuera del event loop."""
    provider = app.dependency_overrides.get(get_db, get_db)

    def call():
        with contextmanager(provider)() as db:
            return function(db, *args)

    return await run_in_threadpool(call)


def _load_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def _room_state(db: Session, code: str) -> dict:
    room = rooms.room_public(db, rooms.get_room(db, code))
    return room.model_dump(by_alias=True, mode="json")


async def _close_quietly(socket: WebSocket, code: int) -> None:
    try:
        await socket.close(code=code)
    except (WebSocketDisconnect, RuntimeError):
        pass


class Race:
    """Una ronda en curso. El reloj y las posiciones los lleva el servidor."""

    def __init__(
        self,
        round_number: int,
        rounds: int,
        text: RaceText,
        limit_ms: int,
        players: dict[int, str],
    ) -> None:
        self.round = round_number
        self.rounds = rounds
        self.text = text
        self.limit_ms = limit_ms
        self.racers = {
            user_id: Racer(user_id, username) for user_id, username in players.items()
        }
        self.finish_order: list[int] = []
        self.started = time.monotonic()
        self.started_at = datetime.now(timezone.utc)
        self.done = asyncio.Event()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def standings(self) -> list[Racer]:
        """Jugadores con quienes terminaron primero y en su orden de llegada.

        Así dos llegadas en el mismo milisegundo se desempatan por quién
        cruzó antes, no por el orden de la lista de miembros.
        """
        finished = [self.racers[user_id] for user_id in self.finish_order if user_id in self.racers]
        pending = [racer for racer in self.racers.values() if racer.finished_ms is None]
        return finished + pending

    def start_message(self, user_id: int | None = None) -> dict:
        length = len(self.text.content)
        message = {
            "type": "race_start",
            "round": self.round,
            "rounds": self.rounds,
            "text": {
                "id": self.text.id,
                "content": self.text.content,
                "language": self.text.language.value,
                "difficulty": self.text.difficulty.value,
            },
            "timeLimitMs": self.limit_ms,
            "elapsedMs": self.elapsed_ms(),
            "players": [
                {
                    "userId": racer.user_id,
                    "username": racer.username,
                    "progress": racer.typed / length,
                    "finished": racer.finished_ms is not None,
                }
                for racer in self.racers.values()
            ],
        }
        # Quien se reconecta a mitad de carrera retoma desde su propio avance.
        racer = self.racers.get(user_id)
        if racer is not None:
            message["you"] = {"typed": racer.typed, "errors": racer.errors}
        return message


class LiveRoom:
    def __init__(self, app: FastAPI, code: str) -> None:
        self.app = app
        self.code = code
        self.sockets: dict[int, WebSocket] = {}
        self.players: dict[int, str] = {}
        self.match: asyncio.Task | None = None
        self.race: Race | None = None
        self.start_lock = asyncio.Lock()


class RoomHub:
    def __init__(self) -> None:
        self.rooms: dict[str, LiveRoom] = {}

    async def send(self, socket: WebSocket, message: dict) -> None:
        try:
            await socket.send_json(message)
        except (WebSocketDisconnect, RuntimeError):
            # Ese socket ya se cayó; su propio bucle se encarga de sacarlo.
            pass

    async def broadcast(
        self, live: LiveRoom, message: dict, exclude: WebSocket | None = None
    ) -> None:
        for socket in list(live.sockets.values()):
            if socket is not exclude:
                await self.send(socket, message)

    async def broadcast_state(self, live: LiveRoom) -> None:
        try:
            room = await run_db(live.app, _room_state, live.code)
        except RoomError:
            return  # la sala se cerró mientras tanto
        for member in room["members"]:
            member["connected"] = member["id"] in live.sockets
        await self.broadcast(live, {"type": "room_state", "room": room})

    # --- conexiones ---

    def attach(self, app: FastAPI, code: str, user_id: int, socket: WebSocket):
        """Registra el socket. Si el usuario ya tenía uno, el nuevo lo reemplaza."""
        live = self.rooms.get(code)
        if live is None:
            live = self.rooms[code] = LiveRoom(app, code)
        previous = live.sockets.get(user_id)
        live.sockets[user_id] = socket
        return live, previous

    async def welcome(
        self, live: LiveRoom, user: User, socket: WebSocket, previous: WebSocket | None
    ) -> None:
        if previous is not None:
            await _close_quietly(previous, CLOSE_REPLACED)
        async with live.start_lock:
            if live.match is None:
                # Si el servidor se reinició a mitad de una partida, la sala
                # quedó "en curso" sin carrera viva: se devuelve a espera.
                await run_db(live.app, rooms.end_match, live.code)
        if previous is None:
            await self.broadcast(
                live,
                {"type": "player_joined", "userId": user.id, "username": user.username},
                exclude=socket,
            )
        await self.broadcast_state(live)
        if live.race is not None:
            await self.send(socket, live.race.start_message(user.id))

    async def disconnect(self, live: LiveRoom, user_id: int, socket: WebSocket) -> None:
        if live.sockets.get(user_id) is not socket:
            return  # otra conexión del mismo usuario ya ocupó su lugar
        del live.sockets[user_id]
        await self._after_departure(live, user_id)

    async def _after_departure(self, live: LiveRoom, user_id: int) -> None:
        if not live.sockets:
            # Sin nadie conectado no hay carrera que sostener.
            if live.match is not None:
                live.match.cancel()
            if self.rooms.get(live.code) is live:
                del self.rooms[live.code]
            return
        await self.broadcast(live, {"type": "player_left", "userId": user_id})
        await self.broadcast_state(live)
        self._check_race_done(live)

    # --- avisos desde los endpoints REST ---

    async def room_changed(self, code: str) -> None:
        live = self.rooms.get(code)
        if live is not None:
            await self.broadcast_state(live)

    async def member_removed(self, code: str, user_id: int) -> None:
        """Un jugador salió o fue expulsado: deja la sala y la carrera."""
        live = self.rooms.get(code)
        if live is None:
            return
        live.players.pop(user_id, None)
        if live.race is not None:
            live.race.racers.pop(user_id, None)
        socket = live.sockets.pop(user_id, None)
        if socket is not None:
            await _close_quietly(socket, CLOSE_REMOVED)
        await self._after_departure(live, user_id)

    async def room_closed(self, code: str) -> None:
        live = self.rooms.pop(code, None)
        if live is None:
            return
        if live.match is not None:
            live.match.cancel()
        sockets = list(live.sockets.values())
        live.sockets.clear()
        for socket in sockets:
            await self.send(socket, {"type": "room_closed"})
            await _close_quietly(socket, CLOSE_ROOM_GONE)

    # --- mensajes del cliente ---

    async def handle(
        self, live: LiveRoom, user: User, socket: WebSocket, message
    ) -> None:
        kind = message.get("type") if isinstance(message, dict) else None
        if kind == "ready" and isinstance(message.get("ready"), bool):
            await run_db(
                live.app, rooms.set_ready, user.id, live.code, message["ready"]
            )
            await self.broadcast_state(live)
        elif kind == "start":
            await self.start(live, user.id)
        elif kind == "progress":
            await self.progress(live, user.id, socket, message)
        else:
            raise RoomError("invalid_message")

    async def start(self, live: LiveRoom, user_id: int) -> None:
        async with live.start_lock:
            if live.match is not None:
                raise RoomError("room_in_progress")
            config = await run_db(
                live.app, rooms.begin_match, user_id, live.code, set(live.sockets)
            )
            live.players = dict(config.players)
            live.match = asyncio.create_task(self._run_match(live, config))
        await self.broadcast_state(live)

    async def progress(
        self, live: LiveRoom, user_id: int, socket: WebSocket, message: dict
    ) -> None:
        race = live.race
        racer = race.racers.get(user_id) if race is not None else None
        if racer is None or racer.finished_ms is not None:
            return  # un avance que llega tarde ya no cuenta
        typed, errors = message.get("typed"), message.get("errors")
        length = len(race.text.content)
        if (
            type(typed) is not int
            or type(errors) is not int
            or not racer.typed <= typed <= length
            or errors < racer.errors
        ):
            raise RoomError("invalid_message")
        racer.typed, racer.errors = typed, errors
        finished = typed == length
        if finished:
            racer.finished_ms = race.elapsed_ms()
            race.finish_order.append(user_id)
        await self.broadcast(
            live,
            {
                "type": "progress_update",
                "userId": user_id,
                "progress": typed / length,
                "finished": finished,
            },
            exclude=socket,
        )
        if finished:
            self._check_race_done(live)

    def _check_race_done(self, live: LiveRoom) -> None:
        """La ronda termina cuando todos los jugadores conectados completaron."""
        race = live.race
        if race is not None and all(
            racer.finished_ms is not None
            for user_id, racer in race.racers.items()
            if user_id in live.sockets
        ):
            race.done.set()

    # --- la partida ---

    async def _run_match(self, live: LiveRoom, config: MatchConfig) -> None:
        used_texts: list[int] = []
        try:
            for round_number in range(1, config.rounds + 1):
                text = await run_db(
                    live.app,
                    rooms.pick_text,
                    config.language,
                    config.difficulty,
                    used_texts,
                )
                if text is None or not live.players:
                    break
                used_texts.append(text.id)
                await self._run_round(live, config, round_number, text)
                if round_number < config.rounds:
                    await asyncio.sleep(INTERMISSION_S)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("La partida de la sala %s se interrumpió", live.code)
        finally:
            live.race = None
            live.match = None
            live.players = {}
            try:
                await run_db(live.app, rooms.end_match, live.code)
                await self.broadcast_state(live)
            except Exception:
                # La próxima conexión a la sala la devuelve a espera.
                logger.exception("No se pudo reabrir la sala %s", live.code)

    async def _run_round(
        self, live: LiveRoom, config: MatchConfig, round_number: int, text: RaceText
    ) -> None:
        await self.broadcast(
            live,
            {
                "type": "countdown",
                "round": round_number,
                "rounds": config.rounds,
                "seconds": COUNTDOWN_S,
            },
        )
        await asyncio.sleep(COUNTDOWN_S)

        # El texto recién se envía al terminar la cuenta, a todos a la vez.
        race = live.race = Race(
            round_number,
            config.rounds,
            text,
            time_limit_ms(text.ideal_time_ms, config.time_limit_s),
            live.players,
        )
        await self.broadcast(live, race.start_message())
        self._check_race_done(live)
        try:
            await asyncio.wait_for(race.done.wait(), race.limit_ms / 1000)
        except asyncio.TimeoutError:
            pass

        live.race = None
        results = build_results(
            text, min(race.elapsed_ms(), race.limit_ms), race.standings()
        )
        if not results:
            return
        await run_db(
            live.app,
            rooms.save_race,
            config.room_id,
            text,
            race.started_at,
            datetime.now(timezone.utc),
            results,
        )
        last = round_number == config.rounds
        await self.broadcast(
            live,
            {
                "type": "race_end",
                "round": round_number,
                "rounds": config.rounds,
                "results": [
                    {to_camel(key): value for key, value in asdict(result).items()}
                    for result in results
                ],
                "nextRoundInS": None if last else INTERMISSION_S,
            },
        )


hub = RoomHub()


async def _authenticate(socket: WebSocket) -> User | None:
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
    return await run_db(socket.app, _load_user, user_id)


async def _listen(live: LiveRoom, user: User, socket: WebSocket) -> None:
    while True:
        try:
            message = await socket.receive_json()
        except (ValueError, KeyError):
            message = None
        try:
            await hub.handle(live, user, socket, message)
        except RoomError as error:
            await hub.send(
                socket, {"type": "error", "code": error.code, "detail": error.message}
            )


@router.websocket("/rooms/{code}")
async def room_socket(
    socket: WebSocket, code: str = Path(pattern=r"^[A-Za-z0-9]{6}$")
) -> None:
    await socket.accept()
    code = code.upper()
    try:
        user = await _authenticate(socket)
        if user is None:
            await socket.close(code=CLOSE_UNAUTHORIZED)
            return
        try:
            await run_db(socket.app, rooms.get_member_room, code, user.id)
        except RoomError as error:
            gone = error.code == "room_not_found"
            await socket.close(code=CLOSE_ROOM_GONE if gone else CLOSE_NOT_MEMBER)
            return
        live, previous = hub.attach(socket.app, code, user.id, socket)
        try:
            await hub.welcome(live, user, socket, previous)
            await _listen(live, user, socket)
        finally:
            await hub.disconnect(live, user.id, socket)
    except WebSocketDisconnect:
        pass
