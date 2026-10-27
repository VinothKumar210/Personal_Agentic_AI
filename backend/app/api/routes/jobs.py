from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import IngestionJob, DocumentChunk
from app.schemas.jobs import IngestionJobStatusResponse
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/{job_id}", response_model=IngestionJobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id, IngestionJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    chunks_created = db.query(DocumentChunk).filter(DocumentChunk.document_id == job.document_id).count()
    
    return IngestionJobStatusResponse(
        job=job,
        document=job.document,
        chunks_created=chunks_created,
        message=job.message or job.error_message or f"Job is {job.status}"
    )
