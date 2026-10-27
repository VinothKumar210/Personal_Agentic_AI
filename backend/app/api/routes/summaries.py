from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.summary import DocumentSummaryRequest, CollectionSummaryRequest, SummaryResponse
from app.services.summary_service import summarize_document, summarize_collection
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/documents/{document_id}/summary", response_model=SummaryResponse)
async def api_summarize_document(document_id: str, request: DocumentSummaryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return summarize_document(document_id, request, db, user_id=current_user.id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/collections/{collection_id}/summary", response_model=SummaryResponse)
async def api_summarize_collection(collection_id: str, request: CollectionSummaryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return summarize_collection(collection_id, request, db, user_id=current_user.id)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
