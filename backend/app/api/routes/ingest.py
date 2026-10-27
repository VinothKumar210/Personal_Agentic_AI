from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.api.deps import ScopedApiKeyAuth
from app.schemas.document import IngestionJobRead
from app.services.web_ingestion_service import process_web_clip

router = APIRouter()

class WebClipRequest(BaseModel):
    url: str
    title: Optional[str] = None
    html_content: Optional[str] = None
    selected_text: Optional[str] = None

# Create the dependency instance for 'capture_page' scope
capture_page_auth = ScopedApiKeyAuth(required_scopes=["capture_page"])

@router.post("/clip", response_model=IngestionJobRead)
def clip_web_page(
    req: WebClipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(capture_page_auth)
):
    """
    Ingest a web clip via browser extension. Secured by API key with 'capture_page' scope.
    """
    job = process_web_clip(db, current_user.id, req.url, req.title, req.html_content, req.selected_text)
    return job
