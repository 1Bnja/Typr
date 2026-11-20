"""Authenticated phrase generation, validation and persistence endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Text
from app.schemas.text import (
    TextBulkSaveRequest,
    TextGenerateResponse,
    TextGenerationRequest,
    TextInput,
    TextPublic,
    TextVerifyResponse,
)
from app.text_enums import Difficulty, Language
from app.services.texts_handler import TextFacade
from app.services.texts_handler.errors import TextDatabaseError, TextValidationError
from app.services.texts_handler.load import load_phrases

router = APIRouter(
    tags=["texts"],
    dependencies=[Depends(get_current_user)],
    responses={401: {"description": "Missing, invalid or expired bearer token."}},
)
logger = logging.getLogger(__name__)


def _validation_http_error(error: TextValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT if error.code == "duplicate_content" else 422,
        detail={"code": error.code, "message": str(error)},
    )


@router.get(
    "/random",
    response_model=TextPublic,
    summary="Get a random text",
    description="Returns a stored text, optionally filtered by language and difficulty. `excludeId` avoids repeating the previous text when possible.",
    responses={
        404: {"description": "No stored texts match the filters."},
        503: {"description": "The stored texts could not be queried."},
    },
)
def random_text(
    language: Language | None = None,
    difficulty: Difficulty | None = None,
    exclude_id: int | None = Query(default=None, alias="excludeId", gt=0),
    db: Session = Depends(get_db),
) -> TextPublic:
    """Return a stored text for optional filters, avoiding the previous ID when possible."""
    base = select(Text)
    if language is not None:
        base = base.where(Text.language == language)
    if difficulty is not None:
        base = base.where(Text.difficulty == difficulty)
    try:
        if exclude_id is not None:
            text = db.scalar(
                base.where(Text.id != exclude_id).order_by(func.random()).limit(1)
            )
            if text is not None:
                return TextPublic.model_validate(text)
        text = db.scalar(base.order_by(func.random()).limit(1))
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudieron consultar las frases guardadas.",
        ) from error
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay frases guardadas para este idioma y dificultad.",
        )
    return TextPublic.model_validate(text)


@router.post(
    "/generate",
    response_model=TextGenerateResponse,
    summary="Generate candidate texts",
    description="Generates a batch of phrases with the AI provider and validates them without storing anything (dry run). Language defaults to Spanish.",
    responses={
        429: {"description": "The AI provider rate limit was reached. Retry after the `Retry-After` header (seconds)."},
        502: {"description": "The phrase generation failed."},
    },
)
def generate_texts(data: TextGenerationRequest | None = None) -> TextGenerateResponse:
    language = data.language if data is not None else Language.SPA
    try:
        phrases = TextFacade().generate_phrases(language)
    except Exception as error:
        if getattr(error, "code", None) == 429:
            logger.warning("Gemini rate limit reached during phrase generation")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gemini alcanzó su límite temporal de solicitudes. Espera un minuto antes de generar otro lote.",
                headers={"Retry-After": "60"},
            ) from error
        logger.exception("Phrase generation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron generar las frases. Inténtalo nuevamente.",
        ) from error
    summary = load_phrases(
        phrases, language, dry_run=True, max_per_difficulty=10,
        expected_word_ranges=((20, 20),) * 10 + ((30, 30),) * 10 + ((40, 40),) * 10,
    )
    return TextGenerateResponse(
        language=language,
        generated=summary.generated,
        valid=summary.accepted_in_dry_run,
        stored=summary.stored,
        duplicates=summary.duplicates,
        rejected=summary.rejected,
        phrases=list(summary.phrases),
    )


@router.post(
    "/save",
    response_model=TextGenerateResponse,
    summary="Save a batch of texts",
    description="Validates and stores a batch of phrases. Duplicates and invalid phrases are reported in the summary instead of failing the request.",
    responses={503: {"description": "Saving failed. Some earlier phrases may have been stored."}},
)
def save_texts(data: TextBulkSaveRequest, db: Session = Depends(get_db)) -> TextGenerateResponse:
    try:
        summary = load_phrases(
            data.phrases, data.language, dry_run=False, db=db,
            max_per_difficulty=10, allowed_word_counts=frozenset({20, 30, 40}),
        )
    except TextDatabaseError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falló el guardado. Algunas frases anteriores pueden haberse guardado.",
        ) from error
    return TextGenerateResponse(
        language=data.language,
        generated=summary.generated,
        valid=0,
        stored=summary.stored,
        duplicates=summary.duplicates,
        rejected=summary.rejected,
        phrases=list(summary.phrases),
    )


@router.post(
    "/verify",
    response_model=TextVerifyResponse,
    summary="Verify a text",
    description="Validates a text and returns its difficulty and score without storing it.",
    responses={
        409: {"description": "The content duplicates an existing text (`duplicate_content`)."},
        422: {"description": "The text failed validation. The body carries a `code` and a `message`."},
    },
)
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


@router.post(
    "",
    response_model=TextPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a text",
    description="Validates, classifies and stores a new text.",
    responses={
        409: {"description": "The content duplicates an existing text (`duplicate_content`)."},
        422: {"description": "The text failed validation. The body carries a `code` and a `message`."},
        503: {"description": "The text could not be saved."},
    },
)
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
