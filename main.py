import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db
from backend.auth_middleware import AuthMiddleware
from backend.routes.auth import router as auth_router
from backend.routes.regulations import router as regulations_router
from backend.routes.generate import router as generate_router
from backend.routes.questions import router as questions_router
from backend.routes.export import router as export_router
from backend.routes.kb import router as kb_router
from backend.routes.sessions import router as sessions_router
from backend.seed import seed_regulations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ExamsGen", description="ACCA TX(VNM) Exam Question Generator")

# Auth middleware
app.add_middleware(AuthMiddleware)

# Routes
app.include_router(auth_router)
app.include_router(regulations_router)
app.include_router(generate_router)
app.include_router(questions_router)
app.include_router(export_router)
app.include_router(kb_router)
app.include_router(sessions_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "ExamsGen"}


@app.on_event("startup")
def startup():
    logger.info("Initializing database...")
    try:
        init_db()
        seed_regulations()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("App will run but DB features will be unavailable")


# Serve React frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "ExamsGen API running. Frontend not built yet — run `cd frontend && npm run build`"}
