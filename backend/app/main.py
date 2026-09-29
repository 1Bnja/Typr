from fastapi import FastAPI
from app.routers import auth, health, users

app = FastAPI(title="Typr API")

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(users.router, prefix="/api/v1/users")
