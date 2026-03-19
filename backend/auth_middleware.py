from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError

from backend.config import SECRET_KEY, APP_PASSWORD


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple password-based auth for Phase 1."""

    EXEMPT_PATHS = {"/api/auth/login", "/api/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow static files, exempt paths, and non-API routes
        if not path.startswith("/api") or path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Check Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            # Accept raw APP_PASSWORD or JWT
            if token == APP_PASSWORD:
                return await call_next(request)
            try:
                jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                return await call_next(request)
            except JWTError:
                pass

        # Check session cookie
        cookie_token = request.cookies.get("session_token")
        if cookie_token:
            try:
                jwt.decode(cookie_token, SECRET_KEY, algorithms=["HS256"])
                return await call_next(request)
            except JWTError:
                pass

        raise HTTPException(status_code=401, detail="Authentication required")
