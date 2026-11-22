"""Shared OpenAPI response descriptions used by the routers."""

UNAUTHORIZED = {
    401: {"description": "Missing, invalid or expired bearer token."},
}

ROOM_ERROR_NOTE = (
    'Error bodies have the shape `{"detail": {"code": ..., "message": ...}}`.'
)
