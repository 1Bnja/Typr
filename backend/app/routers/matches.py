from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.practice import PracticeMatchCreate, PracticeMatchPublic
from app.services.practice import (
    PracticeStorageError,
    PracticeTextNotFound,
    list_practice_matches,
    save_practice_match,
)
from app.services.texts_handler.errors import TextValidationError

router = APIRouter(tags=["matches"])


@router.post(
    "/practice", response_model=PracticeMatchPublic, status_code=status.HTTP_201_CREATED
)
def create_practice_match(
    data: PracticeMatchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return save_practice_match(db, user.id, data)
    except PracticeTextNotFound:
        raise HTTPException(status_code=404, detail="El texto no existe.")
    except TextValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except PracticeStorageError:
        raise HTTPException(
            status_code=503,
            detail="No se pudo guardar el resultado. Inténtalo nuevamente.",
        )


@router.get("/practice", response_model=list[PracticeMatchPublic])
def practice_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_practice_matches(db, user.id, limit, offset)
    except PracticeStorageError:
        raise HTTPException(
            status_code=503, detail="No se pudieron cargar tus resultados."
        )
