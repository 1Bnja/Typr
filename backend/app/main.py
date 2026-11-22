from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routers import auth, health, matches, rooms, texts, users
from app.ws import rooms as rooms_ws

app = FastAPI(title="Typr API")


@app.exception_handler(RequestValidationError)
async def handle_request_validation(request: Request, exc: RequestValidationError):
    if request.scope.get("endpoint") is not auth.register:
        return await request_validation_exception_handler(request, exc)

    return JSONResponse(
        status_code=422,
        content={"detail": auth.registration_validation_details(exc.errors())},
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(texts.router, prefix="/api/v1/texts")
app.include_router(matches.router, prefix="/api/v1/matches")
app.include_router(rooms.router, prefix="/api/v1/rooms")
app.include_router(rooms_ws.router, prefix="/api/v1/ws")
