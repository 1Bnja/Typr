"""Endpoints de salas: crear, configurar, ingresar, salir, expulsar y cerrar."""

from typing import Annotated

from anyio import from_thread
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.api_docs import ROOM_ERROR_NOTE, UNAUTHORIZED
from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.room import RoomCreate, RoomPublic, RoomUpdate
from app.services import rooms
from app.services.rooms import RoomError
from app.ws.rooms import hub

router = APIRouter(tags=["rooms"])

RoomCode = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{6}$")]


def _http_error(error: RoomError) -> HTTPException:
    return HTTPException(
        status_code=error.status,
        detail={"code": error.code, "message": error.message},
    )


def _notify(function, *args) -> None:
    """Avisa a los sockets de la sala, que viven en el event loop."""
    from_thread.run(function, *args)


@router.post(
    "",
    response_model=RoomPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a room",
    description=(
        "Creates a room in the waiting state. The creator becomes host and member. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        409: {"description": "The user already belongs to a room (`already_in_room`)."},
    },
)
def create_room(
    data: RoomCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea una sala en espera; quien la crea queda como anfitrión y miembro."""
    try:
        return rooms.room_public(db, rooms.create_room(db, user.id, data))
    except RoomError as error:
        raise _http_error(error)


@router.get(
    "/me",
    response_model=RoomPublic | None,
    summary="Get my room",
    description=(
        "Returns the room the user belongs to, or `null` when the user is in none. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
    },
)
def my_room(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sala a la que pertenece el usuario, o null si no está en ninguna."""
    room = rooms.current_room(db, user.id)
    return None if room is None else rooms.room_public(db, room)


@router.get(
    "/{code}",
    response_model=RoomPublic,
    summary="Get a room",
    description=(
        "Returns a room by its 6-character code. Only members can read it. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        403: {"description": "The user is not a member (`not_member`)."},
        404: {"description": "Unknown room code (`room_not_found`)."},
    },
)
def get_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return rooms.room_public(db, rooms.get_member_room(db, code, user.id))
    except RoomError as error:
        raise _http_error(error)


@router.patch(
    "/{code}",
    response_model=RoomPublic,
    summary="Update room settings",
    description=(
        "Changes the room configuration and notifies connected sockets. Host only, while the room is waiting. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        403: {"description": "Not a member or not the host (`not_member`, `not_host`)."},
        404: {"description": "Unknown room code (`room_not_found`)."},
        409: {"description": "A match is in progress (`room_in_progress`)."},
    },
)
def update_room(
    code: RoomCode,
    data: RoomUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia la configuración. Solo el anfitrión, con la sala en espera."""
    try:
        room = rooms.room_public(db, rooms.update_room(db, user.id, code, data))
    except RoomError as error:
        raise _http_error(error)
    _notify(hub.room_changed, room.code)
    return room


@router.post(
    "/{code}/join",
    response_model=RoomPublic,
    summary="Join a room",
    description=(
        "Joins a room by code as a regular member and notifies connected sockets. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        404: {"description": "Unknown room code (`room_not_found`)."},
        409: {"description": "Already in a room, room full or match in progress (`already_in_room`, `room_full`, `room_in_progress`)."},
    },
)
def join_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingresa a la sala por su código, como miembro sin permisos de anfitrión."""
    try:
        room = rooms.room_public(db, rooms.join_room(db, user.id, code))
    except RoomError as error:
        raise _http_error(error)
    _notify(hub.room_changed, room.code)
    return room


@router.post(
    "/{code}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a room",
    description=(
        "Leaves the room. If the host leaves, the room is deleted and every socket is told it closed. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        403: {"description": "The user is not a member (`not_member`)."},
        404: {"description": "Unknown room code (`room_not_found`)."},
    },
)
def leave_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Abandona la sala. Si lo hace el anfitrión, la sala se elimina."""
    try:
        deleted = rooms.leave_room(db, user.id, code)
    except RoomError as error:
        raise _http_error(error)
    if deleted:
        _notify(hub.room_closed, code.upper())
    else:
        _notify(hub.member_removed, code.upper(), user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{code}/members/{member_id}",
    response_model=RoomPublic,
    summary="Kick a member",
    description=(
        "Removes a player from the room. Host only, while the room is waiting. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        403: {"description": "Not a member or not the host (`not_member`, `not_host`)."},
        404: {"description": "Unknown room or player not in the room (`room_not_found`, `member_not_found`)."},
        409: {"description": "A match is in progress (`room_in_progress`)."},
        422: {"description": "The host cannot kick themselves (`cannot_kick_host`)."},
    },
)
def kick_member(
    code: RoomCode,
    member_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Expulsa a un jugador. Solo el anfitrión, con la sala en espera."""
    try:
        room = rooms.room_public(db, rooms.kick_member(db, user.id, code, member_id))
    except RoomError as error:
        raise _http_error(error)
    _notify(hub.member_removed, room.code, member_id)
    return room


@router.delete(
    "/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close a room",
    description=(
        "Closes the room and removes all its players. Host only. "
        + ROOM_ERROR_NOTE
    ),
    responses={
        **UNAUTHORIZED,
        403: {"description": "Not a member or not the host (`not_member`, `not_host`)."},
        404: {"description": "Unknown room code (`room_not_found`)."},
    },
)
def close_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cierra la sala y saca a todos sus jugadores. Solo el anfitrión."""
    try:
        rooms.close_room(db, user.id, code)
    except RoomError as error:
        raise _http_error(error)
    _notify(hub.room_closed, code.upper())
    return Response(status_code=status.HTTP_204_NO_CONTENT)
