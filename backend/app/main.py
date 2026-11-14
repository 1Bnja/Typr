from fastapi import FastAPI
from app.routers import auth, health, matches, rooms, texts, users
from app.ws import rooms as rooms_ws

app = FastAPI(title="Typr API")

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(texts.router, prefix="/api/v1/texts")
app.include_router(matches.router, prefix="/api/v1/matches")
app.include_router(rooms.router, prefix="/api/v1/rooms")
app.include_router(rooms_ws.router, prefix="/api/v1/ws")
