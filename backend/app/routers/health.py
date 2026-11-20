from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Liveness probe. Returns `{\"status\": \"ok\"}` when the API process is running.",
)
def health():
    return {"status": "ok"}