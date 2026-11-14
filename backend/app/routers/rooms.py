"""Endpoints de salas: crear, configurar, ingresar, salir, expulsar y cerrar."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.room import RoomCreate, RoomPublic, RoomUpdate
from app.services import rooms
from app.services.rooms import RoomError

router = APIRouter(tags=["rooms"])

RoomCode = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{6}$")]


def _http_error(error: RoomError) -> HTTPException:
    return HTTPException(
        status_code=error.status,
        detail={"code": error.code, "message": error.message},
    )


@router.post("", response_model=RoomPublic, status_code=status.HTTP_201_CREATED)
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


@router.get("/me", response_model=RoomPublic | None)
def my_room(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sala a la que pertenece el usuario, o null si no está en ninguna."""
    room = rooms.current_room(db, user.id)
    return None if room is None else rooms.room_public(db, room)


@router.get("/{code}", response_model=RoomPublic)
def get_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return rooms.room_public(db, rooms.get_member_room(db, code, user.id))
    except RoomError as error:
        raise _http_error(error)


@router.patch("/{code}", response_model=RoomPublic)
def update_room(
    code: RoomCode,
    data: RoomUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia la configuración. Solo el anfitrión, con la sala en espera."""
    try:
        return rooms.room_public(db, rooms.update_room(db, user.id, code, data))
    except RoomError as error:
        raise _http_error(error)


@router.post("/{code}/join", response_model=RoomPublic)
def join_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingresa a la sala por su código, como miembro sin permisos de anfitrión."""
    try:
        return rooms.room_public(db, rooms.join_room(db, user.id, code))
    except RoomError as error:
        raise _http_error(error)


@router.post("/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_room(
    code: RoomCode,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Abandona la sala. Si lo hace el anfitrión, la sala se elimina."""
    try:
        rooms.leave_room(db, user.id, code)
    except RoomError as error:
        raise _http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{code}/members/{member_id}", response_model=RoomPublic)
def kick_member(
    code: RoomCode,
    member_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Expulsa a un jugador. Solo el anfitrión, con la sala en espera."""
    try:
        return rooms.room_public(db, rooms.kick_member(db, user.id, code, member_id))
    except RoomError as error:
        raise _http_error(error)


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)
