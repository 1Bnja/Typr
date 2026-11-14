"""Reglas de las salas: creación, configuración, ingreso y membresías.

Todas las funciones reciben la sesión y confirman su propia transacción. Los
rechazos se informan con `RoomError`, cuyo código identifica el motivo para el
router HTTP y para el WebSocket.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Game,
    GameMode,
    GameParticipant,
    Room,
    RoomStatus,
    Text,
    User,
    room_members,
)
from app.schemas.room import RoomCreate, RoomMemberPublic, RoomPublic, RoomUpdate
from app.services.race import RaceResult, RaceText, ideal_time_ms
from app.text_enums import Difficulty, Language

MAX_MEMBERS = 10
MIN_PLAYERS = 2
# Sin 0/O ni 1/I/L: el código se dicta o se copia a mano.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
CODE_ATTEMPTS = 5

ERRORS = {
    "room_not_found": (404, "El código de sala no es válido."),
    "already_in_room": (409, "Ya perteneces a una sala."),
    "room_full": (409, "La sala está llena."),
    "room_in_progress": (
        409,
        "La sala tiene una partida en curso. Espera a que terminen las rondas.",
    ),
    "not_host": (403, "Solo el anfitrión puede hacer esto."),
    "not_member": (403, "No perteneces a esta sala."),
    "member_not_found": (404, "Ese jugador no pertenece a la sala."),
    "cannot_kick_host": (422, "El anfitrión no puede expulsarse a sí mismo."),
    "not_enough_players": (409, "Se necesitan al menos 2 jugadores."),
    "players_not_ready": (
        409,
        "Todos los jugadores deben estar conectados y listos.",
    ),
    "no_texts": (409, "No hay textos para el idioma y la dificultad de la sala."),
    "invalid_message": (422, "Mensaje inválido."),
}


class RoomError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        self.status, self.message = ERRORS[code]
        super().__init__(self.message)


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def get_room(db: Session, code: str, *, lock: bool = False) -> Room:
    """Sala vigente por código. Una sala cerrada ya no es accesible."""
    statement = select(Room).where(
        Room.code == code.upper(), Room.status != RoomStatus.FINISHED
    )
    if lock:
        # Serializa ingresos, inicio y cierre concurrentes sobre la misma sala.
        statement = statement.with_for_update()
    room = db.scalar(statement)
    if room is None:
        raise RoomError("room_not_found")
    return room


def current_room(db: Session, user_id: int) -> Room | None:
    return db.scalar(
        select(Room)
        .join(room_members, room_members.c.room_id == Room.id)
        .where(room_members.c.member_id == user_id)
    )


def is_member(db: Session, room_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(room_members.c.member_id).where(
                room_members.c.room_id == room_id,
                room_members.c.member_id == user_id,
            )
        )
        is not None
    )


def get_member_room(db: Session, code: str, user_id: int, *, lock: bool = False) -> Room:
    room = get_room(db, code, lock=lock)
    if not is_member(db, room.id, user_id):
        raise RoomError("not_member")
    return room


def _get_host_room(db: Session, code: str, user_id: int) -> Room:
    room = get_member_room(db, code, user_id, lock=True)
    if room.host_id != user_id:
        raise RoomError("not_host")
    return room


def room_public(db: Session, room: Room) -> RoomPublic:
    rows = db.execute(
        select(User.id, User.username, room_members.c.is_ready)
        .join(room_members, room_members.c.member_id == User.id)
        .where(room_members.c.room_id == room.id)
        # El anfitrión primero; el resto en orden alfabético.
        .order_by(User.id != room.host_id, User.username)
    )
    return RoomPublic(
        id=room.id,
        code=room.code,
        host_id=room.host_id,
        type=room.type,
        language=room.language,
        difficulty=room.difficulty,
        rounds=room.rounds,
        time_limit_s=room.time_limit_s,
        status=room.status,
        members=[
            RoomMemberPublic(
                id=user_id,
                username=username,
                is_host=user_id == room.host_id,
                is_ready=is_ready,
            )
            for user_id, username, is_ready in rows
        ],
    )


def create_room(db: Session, user_id: int, data: RoomCreate) -> Room:
    if current_room(db, user_id) is not None:
        raise RoomError("already_in_room")
    for _ in range(CODE_ATTEMPTS):
        room = Room(
            code=_new_code(),
            host_id=user_id,
            type=data.type,
            language=data.language,
            difficulty=data.difficulty,
            rounds=data.rounds,
            time_limit_s=data.time_limit_s,
            status=RoomStatus.WAITING,
        )
        db.add(room)
        try:
            db.flush()
            db.execute(
                insert(room_members).values(room_id=room.id, member_id=user_id)
            )
            db.commit()
            return room
        except IntegrityError:
            db.rollback()
            # O el usuario entró a otra sala en paralelo, o el código ya
            # existía; solo lo segundo amerita reintentar.
            if current_room(db, user_id) is not None:
                raise RoomError("already_in_room")
    raise RuntimeError("No se pudo generar un código de sala único.")


def update_room(db: Session, user_id: int, code: str, data: RoomUpdate) -> Room:
    room = _get_host_room(db, code, user_id)
    if room.status != RoomStatus.WAITING:
        raise RoomError("room_in_progress")
    for field, value in data.model_dump(exclude_unset=True).items():
        # Solo el tiempo límite acepta null: significa "automático".
        if value is not None or field == "time_limit_s":
            setattr(room, field, value)
    db.commit()
    return room


def join_room(db: Session, user_id: int, code: str) -> Room:
    room = get_room(db, code, lock=True)
    mine = current_room(db, user_id)
    if mine is not None:
        if mine.id == room.id:
            return room
        raise RoomError("already_in_room")
    if room.status != RoomStatus.WAITING:
        raise RoomError("room_in_progress")
    members = db.scalar(
        select(func.count())
        .select_from(room_members)
        .where(room_members.c.room_id == room.id)
    )
    if members >= MAX_MEMBERS:
        raise RoomError("room_full")
    try:
        db.execute(insert(room_members).values(room_id=room.id, member_id=user_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RoomError("already_in_room")
    return room


def _remove_member(db: Session, room_id: int, user_id: int) -> bool:
    removed = db.execute(
        delete(room_members).where(
            room_members.c.room_id == room_id, room_members.c.member_id == user_id
        )
    )
    return removed.rowcount > 0


def leave_room(db: Session, user_id: int, code: str) -> bool:
    """Saca al usuario de la sala. Devuelve True si la sala se eliminó.

    Si quien se va es el anfitrión, la sala se elimina con sus membresías.
    """
    room = get_member_room(db, code, user_id, lock=True)
    if room.host_id != user_id:
        _remove_member(db, room.id, user_id)
        db.commit()
        return False
    room_id = room.id
    db.expunge(room)
    db.execute(delete(room_members).where(room_members.c.room_id == room_id))
    db.execute(delete(Room).where(Room.id == room_id))
    db.commit()
    return True


def kick_member(db: Session, host_id: int, code: str, member_id: int) -> Room:
    room = _get_host_room(db, code, host_id)
    if room.status != RoomStatus.WAITING:
        raise RoomError("room_in_progress")
    if member_id == host_id:
        raise RoomError("cannot_kick_host")
    if not _remove_member(db, room.id, member_id):
        raise RoomError("member_not_found")
    db.commit()
    return room


def close_room(db: Session, host_id: int, code: str) -> None:
    """Cierra la sala: queda como terminada y sin miembros."""
    room = _get_host_room(db, code, host_id)
    room.status = RoomStatus.FINISHED
    db.execute(delete(room_members).where(room_members.c.room_id == room.id))
    db.commit()


def set_ready(db: Session, user_id: int, code: str, ready: bool) -> None:
    room = get_member_room(db, code, user_id)
    if room.status != RoomStatus.WAITING:
        raise RoomError("room_in_progress")
    db.execute(
        update(room_members)
        .where(
            room_members.c.room_id == room.id, room_members.c.member_id == user_id
        )
        .values(is_ready=ready)
    )
    db.commit()


@dataclass(frozen=True)
class MatchConfig:
    """Foto de la sala al iniciar: la partida no vuelve a leer su configuración."""

    room_id: int
    language: Language
    difficulty: Difficulty
    rounds: int
    time_limit_s: int | None
    players: dict[int, str]


def pick_text(
    db: Session,
    language: Language,
    difficulty: Difficulty,
    exclude_ids: list[int] | None = None,
) -> RaceText | None:
    """Texto al azar para una ronda, evitando repetir los ya jugados si se puede."""

    def choose(excluded: list[int] | None) -> Text | None:
        statement = select(Text).where(
            Text.language == language, Text.difficulty == difficulty
        )
        if excluded:
            statement = statement.where(Text.id.not_in(excluded))
        return db.scalars(statement.order_by(func.random()).limit(1)).first()

    text = choose(exclude_ids) or (choose(None) if exclude_ids else None)
    if text is None:
        return None
    return RaceText(
        id=text.id,
        content=text.content,
        language=text.language,
        difficulty=text.difficulty,
        ideal_time_ms=ideal_time_ms(text.content, text.ideal_time_ms),
    )


def begin_match(
    db: Session, host_id: int, code: str, connected_ids: set[int]
) -> MatchConfig:
    """Valida el inicio y deja la sala "en curso".

    Exige al menos 2 jugadores, todos conectados y listos (el anfitrión se da
    por listo al iniciar) y que existan textos para la configuración.
    """
    room = _get_host_room(db, code, host_id)
    if room.status != RoomStatus.WAITING:
        raise RoomError("room_in_progress")
    members = db.execute(
        select(User.id, User.username, room_members.c.is_ready)
        .join(room_members, room_members.c.member_id == User.id)
        .where(room_members.c.room_id == room.id)
        .order_by(User.id != room.host_id, User.username)
    ).all()
    if len(members) < MIN_PLAYERS:
        raise RoomError("not_enough_players")
    if any(
        user_id not in connected_ids or not (is_ready or user_id == host_id)
        for user_id, _, is_ready in members
    ):
        raise RoomError("players_not_ready")
    if pick_text(db, room.language, room.difficulty) is None:
        raise RoomError("no_texts")
    config = MatchConfig(
        room_id=room.id,
        language=room.language,
        difficulty=room.difficulty,
        rounds=room.rounds,
        time_limit_s=room.time_limit_s,
        players={user_id: username for user_id, username, _ in members},
    )
    room.status = RoomStatus.IN_PROGRESS
    db.commit()
    return config


def save_race(
    db: Session,
    room_id: int,
    text: RaceText,
    started_at: datetime,
    finished_at: datetime,
    results: list[RaceResult],
) -> None:
    """Guarda la ronda: una partida multijugador y un resultado por jugador."""
    try:
        game = Game(
            room_id=room_id,
            text_id=text.id,
            mode=GameMode.MULTIPLAYER,
            started_at=started_at,
            finished_at=finished_at,
        )
        db.add(game)
        db.flush()
        db.add_all(
            GameParticipant(
                game_id=game.id,
                user_id=result.user_id,
                time_ms=result.time_ms,
                ppm=result.ppm,
                precision_pct=result.precision_pct,
                progress=result.progress,
                position=result.position,
                score=result.score,
            )
            for result in results
        )
        record = next((result for result in results if result.is_record), None)
        if record is not None:
            # Solo mejora la marca: otra sala pudo superarla durante la carrera.
            db.execute(
                update(Text)
                .where(
                    Text.id == text.id,
                    or_(
                        Text.ideal_time_ms.is_(None),
                        Text.ideal_time_ms > record.time_ms,
                    ),
                )
                .values(ideal_time_ms=record.time_ms, record_user_id=record.user_id)
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def end_match(db: Session, code: str) -> None:
    """Devuelve la sala a "esperando" y limpia los "listo" para la próxima."""
    room = db.scalar(
        select(Room).where(Room.code == code, Room.status == RoomStatus.IN_PROGRESS)
    )
    if room is None:
        return
    room.status = RoomStatus.WAITING
    db.execute(
        update(room_members)
        .where(room_members.c.room_id == room.id)
        .values(is_ready=False)
    )
    db.commit()
