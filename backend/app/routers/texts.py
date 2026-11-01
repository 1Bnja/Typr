"""Authenticated phrase generation, validation and persistence endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.schemas.text import (
    TextBulkSaveRequest,
    TextGenerateResponse,
    TextInput,
    TextPublic,
    TextVerifyResponse,
)
from app.text_constants import DEFAULT_TEXT_LANGUAGE
from app.services.texts_handler import TextFacade
from app.services.texts_handler.errors import TextDatabaseError, TextValidationError
from app.services.texts_handler.load import load_phrases

router = APIRouter(tags=["texts"], dependencies=[Depends(get_current_user)])


def _validation_http_error(error: TextValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT if error.code == "duplicate_content" else 422,
        detail={"code": error.code, "message": str(error)},
    )


@router.post("/generate", response_model=TextGenerateResponse)
def generate_texts() -> TextGenerateResponse:
    try:
        phrases = TextFacade().generate_phrases()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron generar las frases. Inténtalo nuevamente.",
        ) from error
    summary = load_phrases(
        phrases, DEFAULT_TEXT_LANGUAGE, dry_run=True, max_per_difficulty=10
    )
    return TextGenerateResponse(
        language=DEFAULT_TEXT_LANGUAGE,
        generated=summary.generated,
        valid=summary.accepted_in_dry_run,
        stored=summary.stored,
        duplicates=summary.duplicates,
        rejected=summary.rejected,
        phrases=list(summary.phrases),
    )


@router.post("/save", response_model=TextGenerateResponse)
def save_texts(data: TextBulkSaveRequest, db: Session = Depends(get_db)) -> TextGenerateResponse:
    try:
        summary = load_phrases(
            data.phrases, DEFAULT_TEXT_LANGUAGE, dry_run=False, db=db,
            max_per_difficulty=10,
        )
    except TextDatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falló el guardado. Algunas frases anteriores pueden haberse guardado.",
        ) from error
    return TextGenerateResponse(
        language=DEFAULT_TEXT_LANGUAGE,
        generated=summary.generated,
        valid=0,
        stored=summary.stored,
        duplicates=summary.duplicates,
        rejected=summary.rejected,
        phrases=list(summary.phrases),
    )


@router.post("/verify", response_model=TextVerifyResponse)
def verify_text(data: TextInput) -> TextVerifyResponse:
    try:
        context = TextFacade().process(data.content, data.language)
    except TextValidationError as error:
        raise _validation_http_error(error) from error
    return TextVerifyResponse(
        content=context.content,
        language=data.language,
        difficulty=context.difficulty,
        score=context.classification.score,
    )


@router.post("", response_model=TextPublic, status_code=status.HTTP_201_CREATED)
def create_text(data: TextInput, db: Session = Depends(get_db)) -> TextPublic:
    try:
        text = TextFacade(db).create(data.content, data.language)
    except TextValidationError as error:
        raise _validation_http_error(error) from error
    except TextDatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo guardar la frase en la base de datos.",
        ) from error
    return TextPublic.model_validate(text)
