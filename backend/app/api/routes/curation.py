from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.models.curation import CurationSuggestion, CurationLog, KnowledgeBriefing
from app.schemas.curation import (
    CurationSuggestionRead,
    CurationLogRead,
    KnowledgeBriefingRead,
    CurationSweepRequest,
    CurationSweepResponse
)
from app.services.curation_orchestrator import (
    execute_curation_sweep,
    apply_suggestion,
    rollback_suggestion
)

router = APIRouter()

def utc_now():
    return datetime.now(timezone.utc)

@router.post("/sweep", response_model=CurationSweepResponse)
def trigger_curation_sweep(
    request: CurationSweepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Runs background curation across personal memories and knowledge graph.
    Defaults to dry_run=True (creating reviewable CurationSuggestion records).
    """
    try:
        result = execute_curation_sweep(db, current_user.id, dry_run=request.dry_run)
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Curation sweep failed: {str(e)}")

@router.get("/suggestions", response_model=List[CurationSuggestionRead])
def list_curation_suggestions(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected, applied, rolled_back"),
    suggestion_type: Optional[str] = Query(None, description="Filter by type: memory_merge, memory_contradiction, graph_bridge, graph_prune"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(CurationSuggestion).filter(CurationSuggestion.user_id == current_user.id)
    if status:
        query = query.filter(CurationSuggestion.status == status)
    if suggestion_type:
        query = query.filter(CurationSuggestion.suggestion_type == suggestion_type)
    return query.order_by(CurationSuggestion.created_at.desc()).all()

@router.post("/suggestions/{suggestion_id}/approve", response_model=CurationSuggestionRead)
def approve_curation_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sugg = db.query(CurationSuggestion).filter(
        CurationSuggestion.id == suggestion_id,
        CurationSuggestion.user_id == current_user.id
    ).first()
    if not sugg:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    if sugg.status != "pending":
        raise HTTPException(status_code=400, detail=f"Only pending suggestions can be approved. Current status: {sugg.status}")
    
    sugg.status = "approved"
    sugg.reviewed_at = utc_now()
    db.commit()
    db.refresh(sugg)
    return sugg

@router.post("/suggestions/{suggestion_id}/reject", response_model=CurationSuggestionRead)
def reject_curation_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sugg = db.query(CurationSuggestion).filter(
        CurationSuggestion.id == suggestion_id,
        CurationSuggestion.user_id == current_user.id
    ).first()
    if not sugg:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    if sugg.status not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot reject suggestion with status: {sugg.status}")
    
    sugg.status = "rejected"
    sugg.reviewed_at = utc_now()
    db.commit()
    db.refresh(sugg)
    return sugg

@router.post("/suggestions/{suggestion_id}/apply", response_model=CurationSuggestionRead)
def apply_curation_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return apply_suggestion(db, suggestion_id, current_user.id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply suggestion: {str(e)}")

@router.post("/suggestions/{suggestion_id}/rollback", response_model=CurationSuggestionRead)
def rollback_curation_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return rollback_suggestion(db, suggestion_id, current_user.id)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rollback suggestion: {str(e)}")

@router.get("/briefings", response_model=List[KnowledgeBriefingRead])
def list_knowledge_briefings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(KnowledgeBriefing).filter(
        KnowledgeBriefing.user_id == current_user.id
    ).order_by(KnowledgeBriefing.created_at.desc()).limit(20).all()

@router.get("/logs", response_model=List[CurationLogRead])
def list_curation_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(CurationLog).filter(
        CurationLog.user_id == current_user.id
    ).order_by(CurationLog.created_at.desc()).limit(50).all()
