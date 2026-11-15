from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.stats import UserStats
from app.schemas.user import UserMe
from app.services.stats import user_stats

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)):
    """Datos del usuario autenticado."""
    return user


@router.get("/me/stats", response_model=UserStats)
def my_stats(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analítica personal: promedios, evolución de las últimas 30 partidas e historial.

    Incluye partidas de práctica y rondas multijugador. `limit` y `offset`
    paginan el historial; el resumen y la evolución no dependen de ellos.
    """
    return user_stats(db, user.id, limit, offset)
