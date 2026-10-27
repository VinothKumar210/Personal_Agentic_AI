import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate, DocumentListResponse, IngestionJobRead, DocumentChunkListResponse, FileUploadResponse, DocumentIndexResponse
from app.services import document_service
from app.services.extraction_service import extract_text
from app.core.config import settings
from app.models.document import Document, IngestionJob, DocumentChunk, utc_now
from app.models.user import User
from app.services.ingestion_pipeline import index_document_chunks, create_chunks_for_document
from app.api.deps import get_current_user
from app.schemas.notes import NoteCreate, NoteRead
from app.services import note_service

router = APIRouter()

@router.post("", response_model=DocumentRead)
def create_document(document_in: DocumentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return document_service.create_document_metadata(db, document_in, user_id=current_user.id)

@router.get("", response_model=DocumentListResponse)
def get_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items, total = document_service.list_documents(db, user_id=current_user.id, skip=skip, limit=limit)
    return DocumentListResponse(items=items, total=total)

@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(document_id: str, document_in: DocumentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_service.update_document(db, document, document_in)

@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    document_service.delete_document(db, document)

@router.post("/upload", response_model=FileUploadResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(None),
    source_uri: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    
    ext_to_type = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text"
    }
    
    if ext not in ext_to_type:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ext}")
        
    source_type = ext_to_type[ext]
    doc_title = title if title else filename
    
    doc_in = DocumentCreate(
        title=doc_title,
        source_type=source_type,
        source_uri=source_uri,
        original_filename=filename
    )
    doc = document_service.create_document_metadata(db, doc_in, user_id=current_user.id)
    doc.status = "processing"
    
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="local_file_upload",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)
    
    sanitized_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in ' .-_']).rstrip()
    if not sanitized_filename:
        sanitized_filename = "document"
        
    doc_dir = os.path.join(settings.STORAGE_DIR, "originals", str(doc.id))
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, sanitized_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        payload = {
            "file_path": file_path,
            "source_type": source_type
        }
        from app.services.job_runner import run_ingestion_job
        background_tasks.add_task(run_ingestion_job, job.id, "file_upload", payload)
        
        return FileUploadResponse(
            document=doc,
            job=job,
            chunks_created=0,
            message="Ingestion queued"
        )
        
    except Exception as e:
        db.rollback()
        
        doc.status = "failed"
        doc.error_message = str(e)
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = utc_now()
        
        db.commit()
        db.refresh(doc)
        db.refresh(job)
        
        return FileUploadResponse(
            document=doc,
            job=job,
            chunks_created=0,
            message=f"Upload failed: {str(e)}"
        )

@router.post("/{document_id}/index", response_model=DocumentIndexResponse)
def index_document_route(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no chunks")
        
    return index_document_chunks(db, document_id)

@router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def get_document_chunks(document_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)\
               .order_by(DocumentChunk.chunk_index.asc())\
               .offset(skip).limit(limit).all()
               
    total = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    return DocumentChunkListResponse(items=chunks, total=total)

@router.get("/{document_id}/jobs", response_model=List[IngestionJobRead])
def get_document_jobs(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_service.list_ingestion_jobs_for_document(db, document_id, user_id=current_user.id)

@router.post("/{document_id}/chunks/{chunk_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_chunk_note_endpoint(
    document_id: str,
    chunk_id: str,
    note_in: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return note_service.create_chunk_note(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        chunk_id=chunk_id,
        note_text=note_in.note_text
    )

@router.get("/{document_id}/notes", response_model=List[NoteRead])
def list_document_notes_endpoint(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify document access
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return note_service.list_document_notes(db=db, user_id=current_user.id, document_id=document_id)

@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk_note_endpoint(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = note_service.delete_chunk_note(db=db, user_id=current_user.id, note_id=note_id)
    if not success:
        raise HTTPException(status_code=404, detail="Note not found or access denied")
    return None

