from fastapi import APIRouter, Depends
from app.deps import get_current_user
from app.models import User
from app.schemas.user import UserMe

router = APIRouter(tags=["users"])

@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)):
    return user