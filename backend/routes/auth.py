from fastapi import APIRouter, HTTPException, Response
from datetime import datetime, timedelta
from jose import jwt

from backend.config import APP_PASSWORD, SECRET_KEY
from backend.models import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(req: LoginRequest, response: Response):
    if req.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.utcnow() + timedelta(days=30)},
        SECRET_KEY,
        algorithm="HS256",
    )
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
    )
    return {"token": token, "message": "Login successful"}
