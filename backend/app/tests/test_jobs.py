import pytest
from app.models.document import Document, IngestionJob, DocumentChunk

def test_get_job_status_success(client, db):
    doc = Document(user_id="dev-user-id", title="Test", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    job = IngestionJob(user_id="dev-user-id", document_id=doc.id, job_type="parse", status="running", message="Working")
    db.add(job)
    db.commit()
    db.refresh(job)
    
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, text="A chunk", character_count=7)
    db.add(chunk)
    db.commit()
    
    response = client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["job"]["status"] == "running"
    assert data["document"]["id"] == doc.id
    assert data["chunks_created"] == 1
    assert data["message"] == "Working"

def test_get_job_status_not_found(client):
    response = client.get("/api/jobs/some-fake-id")
    assert response.status_code == 404

from unittest.mock import patch
from app.services.job_runner import run_ingestion_job
import os

def test_no_db_job_runner(client, db):
    # Setup initial records
    doc = Document(user_id="dev-user-id", title="Test Runner", source_type="text", status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    job = IngestionJob(user_id="dev-user-id", document_id=doc.id, job_type="file_upload", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Create dummy file to process
    from app.core.config import settings
    doc_dir = os.path.join(settings.STORAGE_DIR, "originals", doc.id)
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, "test.txt")
    with open(file_path, "w") as f:
        f.write("Hello from no db runner")

    from app.tests.conftest import TestingSessionLocal
    
    # Patch SessionLocal to use the test TestingSessionLocal so it doesn't try to connect to real Postgres
    with patch("app.services.job_runner.SessionLocal", new=TestingSessionLocal):
        with patch("app.services.job_runner.index_document_chunks", return_value={"failed_count": 0, "indexed_count": 1, "message": "OK"}):
            # Pass NO db argument
            run_ingestion_job(job.id, "file_upload", {"file_path": file_path, "source_type": "text"})
            
    # Verify records updated correctly (refresh our db session view)
    db.expire_all()
    doc_after = db.query(Document).filter(Document.id == doc.id).first()
    job_after = db.query(IngestionJob).filter(IngestionJob.id == job.id).first()
    
    assert doc_after.status == "ready"
    assert job_after.status == "succeeded"
    
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert len(chunks) > 0
    assert "Hello from no db runner" in chunks[0].text
