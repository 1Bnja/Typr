from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.practice import (
    MonthlyLeaderboard,
    PracticeMatchCreate,
    PracticeMatchPublic,
)
from app.services.practice import (
    PracticeStorageError,
    PracticeDifficultyMismatch,
    PracticeTextNotFound,
    list_practice_matches,
    save_practice_match,
    monthly_leaderboard,
)
from app.services.texts_handler.errors import TextValidationError
from app.text_enums import Difficulty, Language

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
    except PracticeDifficultyMismatch:
        raise HTTPException(
            status_code=422, detail="La dificultad no coincide con el texto registrado."
        )
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
    difficulty: Difficulty | None = None,
    language: Language | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_practice_matches(db, user.id, limit, offset, difficulty, language)
    except PracticeStorageError:
        raise HTTPException(
            status_code=503, detail="No se pudieron cargar tus resultados."
        )


@router.get("/leaderboard", response_model=MonthlyLeaderboard)
def practice_leaderboard(
    difficulty: Difficulty = Difficulty.EASY,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    language: Language | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return monthly_leaderboard(db, month, difficulty, language, limit)
    except ValueError:
        raise HTTPException(status_code=422, detail="El mes no es válido.")
    except PracticeStorageError:
        raise HTTPException(
            status_code=503, detail="No se pudo cargar el ranking mensual."
        )
