from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.export import KnowledgeExportBundle, RestoreRequest, RestoreResponse
from app.services.export_service import build_export_bundle
from app.services.restore_service import restore_export_bundle

router = APIRouter()

@router.get("/export", response_model=KnowledgeExportBundle)
def export_knowledge_base(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return build_export_bundle(db, current_user)

@router.post("/restore", response_model=RestoreResponse)
def restore_knowledge_base(
    request: RestoreRequest,
    mode: Optional[str] = Query(None, description="Restore mode: dry_run, merge, or replace"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    actual_mode = mode or request.mode or "dry_run"
    try:
        return restore_export_bundle(db, current_user, request.bundle, actual_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"Restore failed: {str(e)}")
