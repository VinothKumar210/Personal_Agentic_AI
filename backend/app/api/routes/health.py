import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.schemas.health import HealthResponse
from app.db.session import get_db
from app.services.chroma_client import check_chroma_health
from app.services.groq_client import is_groq_configured

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    # Check Database
    db_status = "unavailable"
    if db:
        try:
            db.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception:
            pass

    # Check Storage
    storage_status = "ok"
    if not os.path.isdir(settings.STORAGE_DIR) or not os.access(settings.STORAGE_DIR, os.W_OK):
        storage_status = "unavailable"

    # Check Chroma
    chroma_status = "ok" if check_chroma_health() else "unavailable"

    # Check Groq
    groq_configured = is_groq_configured()

    return HealthResponse(
        status="ok",
        service="backend",
        version=settings.API_VERSION,
        database=db_status,
        chroma=chroma_status,
        groq_configured=groq_configured,
        storage=storage_status,
        auth_dev_mode=settings.AUTH_DEV_MODE,
        embedding_model=settings.EMBEDDING_MODEL_NAME,
        chroma_collection=settings.CHROMA_COLLECTION_NAME
    )
