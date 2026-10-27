from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, BackgroundTasks
from sqlalchemy.orm import Session
import os
from typing import Optional

from app.db.session import get_db
from app.schemas.document import DocumentCreate
from app.schemas.web import WebpageIngestRequest, WebpageIngestResponse, SaveWebResultRequest, SaveWebResultResponse
from app.schemas.github import GithubRepoIngestRequest, GithubRepoIngestResponse, GithubRepoRead
from app.schemas.chat_import import ChatImportResponse
from app.schemas.ocr import OcrIngestResponse
from app.services import document_service
from app.models.document import Document, IngestionJob, utc_now
from app.services.ingestion_pipeline import create_chunks_for_document, index_document_chunks
from app.services.web_ingestion_service import validate_url, fetch_webpage, extract_readable_text, derive_title
from app.services.github_ingestion_service import (
    parse_github_repo_url, fetch_repository_tree, filter_ingestable_files, build_repository_text, list_user_repositories
)
from app.services.chat_import_service import extract_chat_text
from app.services.ocr_service import extract_ocr_text, is_image_file, is_pdf_file
from app.core.config import settings

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/github/repos", response_model=list[GithubRepoRead])
def list_github_repos(pat: Optional[str] = None, current_user: User = Depends(get_current_user)):
    try:
        return list_user_repositories(pat)
    except ValueError as e:
        raise HTTPException(status_code=401 if "Unauthorized" in str(e) or "authentication required" in str(e) else 400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {str(e)}")

@router.post("/github-repo", response_model=GithubRepoIngestResponse)
def ingest_github_repo(request: GithubRepoIngestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        owner, repo = parse_github_repo_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc = db.query(Document).filter(
        Document.user_id == current_user.id,
        Document.source_type == "github_repo",
        Document.source_uri == request.repo_url
    ).first()

    if not doc:
        doc_in = DocumentCreate(
            title=request.title or f"{owner}/{repo}",
            source_type="github_repo",
            source_uri=request.repo_url
        )
        doc = document_service.create_document_metadata(db, doc_in, user_id=current_user.id)
    else:
        if request.title:
            doc.title = request.title

    doc.status = "processing"
    
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="github_repo_ingestion",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    payload = {
        "owner": owner,
        "repo": repo
    }
    from app.services.job_runner import run_ingestion_job
    background_tasks.add_task(run_ingestion_job, job.id, "github_repo", payload)
    
    return GithubRepoIngestResponse(
        document=doc,
        job=job,
        files_ingested=0,
        chunks_created=0,
        message="Ingestion queued (delta-sync if prior chunks exist)"
    )

@router.post("/github-repo/{document_id}/sync", response_model=GithubRepoIngestResponse)
def sync_github_repo_endpoint(document_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
        Document.source_type == "github_repo"
    ).first()
    if not doc or not doc.source_uri:
        raise HTTPException(status_code=404, detail="GitHub repository document not found.")

    try:
        owner, repo = parse_github_repo_url(doc.source_uri)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid stored repository URI: {str(e)}")

    doc.status = "processing"
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="github_repo_ingestion",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    payload = {"owner": owner, "repo": repo}
    from app.services.job_runner import run_ingestion_job
    background_tasks.add_task(run_ingestion_job, job.id, "github_repo", payload)

    return GithubRepoIngestResponse(
        document=doc,
        job=job,
        files_ingested=0,
        chunks_created=0,
        message="Repository delta-sync job queued"
    )
@router.post("/webpage", response_model=WebpageIngestResponse)
def ingest_webpage(request: WebpageIngestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        url = validate_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc_in = DocumentCreate(
        title=request.title or url,
        source_type="webpage",
        source_uri=url
    )
    doc = document_service.create_document_metadata(db, doc_in, user_id=current_user.id)
    doc.status = "processing"
    
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="webpage_ingestion",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    payload = {
        "url": url
    }
    from app.services.job_runner import run_ingestion_job
    background_tasks.add_task(run_ingestion_job, job.id, "webpage", payload)

    return WebpageIngestResponse(
        document=doc,
        job=job,
        chunks_created=0,
        message="Ingestion queued"
    )

@router.post("/ai-chat", response_model=ChatImportResponse)
async def ingest_ai_chat(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename:
        raise HTTPException(status_code=422, detail="No filename provided.")
        
    ext = file.filename.lower().split(".")[-1]
    if ext not in ["json", "md", "txt"]:
        raise HTTPException(status_code=415, detail=f"Unsupported file extension for AI Chat Import: .{ext}")

    content = await file.read()
    
    doc_title = title if title else os.path.splitext(file.filename)[0]
    
    doc_in = DocumentCreate(
        title=doc_title,
        source_type="ai_chat",
        original_filename=file.filename
    )
    doc = document_service.create_document_metadata(db, doc_in, user_id=current_user.id)
    doc.status = "processing"
    
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="ai_chat_import",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)
    
    # Save file
    try:
        import shutil
        sanitized_filename = "".join([c for c in file.filename if c.isalpha() or c.isdigit() or c in ' .-_']).rstrip()
        if not sanitized_filename:
            sanitized_filename = "chat_export"
            
        doc_dir = os.path.join(settings.STORAGE_DIR, "originals", str(doc.id))
        os.makedirs(doc_dir, exist_ok=True)
        file_path = os.path.join(doc_dir, sanitized_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
            
        payload = {
            "file_path": file_path,
            "filename": file.filename
        }
        from app.services.job_runner import run_ingestion_job
        background_tasks.add_task(run_ingestion_job, job.id, "ai_chat", payload)
        
        return ChatImportResponse(
            document=doc,
            job=job,
            chunks_created=0,
            detected_format="unknown",
            message="Ingestion queued"
        )
    except Exception as e:
        doc.status = "failed"
        doc.error_message = f"File save failed: {str(e)}"
        job.status = "failed"
        job.error_message = f"File save failed: {str(e)}"
        db.commit()
        return ChatImportResponse(
            document=doc,
            job=job,
            chunks_created=0,
            detected_format="unknown",
            message=f"File save failed: {str(e)}"
        )

@router.post("/ocr", response_model=OcrIngestResponse)
async def ingest_ocr(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not settings.OCR_ENABLED:
        raise HTTPException(status_code=503, detail="OCR ingestion is disabled on this server.")
        
    is_img = is_image_file(file.filename, file.content_type)
    is_pdf = is_pdf_file(file.filename, file.content_type)
    
    if not is_img and not is_pdf:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type for OCR. Only images and PDFs are supported."
        )
        
    doc_title = title if title else os.path.splitext(file.filename)[0]
    source_type = "image_ocr" if is_img else "scanned_pdf"
    
    doc = Document(
        title=doc_title,
        original_filename=file.filename,
        source_type=source_type,
        status="processing",
        user_id=current_user.id
    )
    db.add(doc)
    db.flush()
    
    job = IngestionJob(
        document_id=doc.id,
        user_id=current_user.id,
        job_type="ocr_ingestion",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)
    
    content = await file.read()
    
    # Save file
    try:
        import shutil
        sanitized_filename = "".join([c for c in file.filename if c.isalpha() or c.isdigit() or c in ' .-_']).rstrip()
        if not sanitized_filename:
            sanitized_filename = "ocr_upload"
            
        doc_dir = os.path.join(settings.STORAGE_DIR, "originals", str(doc.id))
        os.makedirs(doc_dir, exist_ok=True)
        file_path = os.path.join(doc_dir, sanitized_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(content)
            
        payload = {
            "file_path": file_path,
            "filename": file.filename,
            "content_type": file.content_type
        }
        from app.services.job_runner import run_ingestion_job
        background_tasks.add_task(run_ingestion_job, job.id, "ocr", payload)
        
        return OcrIngestResponse(
            document=doc,
            job=job,
            chunks_created=0,
            source_kind="unknown",
            pages_processed=0,
            message="Ingestion queued"
        )
    except Exception as e:
        doc.status = "failed"
        doc.error_message = f"File save failed: {str(e)}"
        job.status = "failed"
        job.error_message = f"File save failed: {str(e)}"
        db.commit()
        return OcrIngestResponse(
            document=doc,
            job=job,
            chunks_created=0,
            source_kind="unknown",
            pages_processed=0,
            message=f"File save failed: {str(e)}"
        )

@router.post("/save-web-result", response_model=SaveWebResultResponse)
def save_web_result(
    request: SaveWebResultRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.services.web_ingestion_service import save_web_result_to_kb
    doc, job = save_web_result_to_kb(
        db=db,
        user_id=current_user.id,
        title=request.title,
        url=request.url,
        content=request.content
    )
    payload = {
        "content": request.content,
        "url": request.url,
        "title": request.title
    }
    from app.services.job_runner import run_ingestion_job
    background_tasks.add_task(run_ingestion_job, job.id, "web_search_saved", payload)

    return SaveWebResultResponse(
        document=doc,
        job=job,
        message="Web result saved and queued for indexing"
    )
