import pytest
from unittest.mock import patch, MagicMock
import os
from app.models.document import Document, IngestionJob, DocumentChunk
from app.services.job_runner import run_ingestion_job
from app.core.config import settings

def create_upload_file(filename: str, content: bytes):
    return {"file": (filename, content)}

def test_unsupported_file_extension(client, db):
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.txt", b"dummy")
    )
    assert response.status_code == 415
    assert db.query(Document).count() == 0

@patch("app.services.job_runner.extract_ocr_text")
@patch("app.services.job_runner.index_document_chunks")
def test_valid_image_ocr_success(mock_index, mock_extract, client, db):
    mock_extract.return_value = ("Extracted OCR text long enough to pass limits." * 5, {"source_kind": "image", "pages_processed": 1})
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.png", b"dummy")
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "test.png")
    
    run_ingestion_job(job_id, "ocr", {"file_path": file_path, "filename": "test.png"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert doc.source_type == "image_ocr"
    assert job.status == "succeeded"
    
    mock_extract.assert_called_once()
    mock_index.assert_called_once()
    args, kwargs = mock_index.call_args
    assert args[1] == doc.id

@patch("app.services.job_runner.extract_ocr_text")
@patch("app.services.job_runner.index_document_chunks")
def test_valid_scanned_pdf_ocr_success(mock_index, mock_extract, client, db):
    mock_extract.return_value = ("Extracted OCR text long enough to pass limits." * 5, {"source_kind": "scanned_pdf", "pages_processed": 2})
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.pdf", b"dummy")
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "test.pdf")
    
    run_ingestion_job(job_id, "ocr", {"file_path": file_path, "filename": "test.pdf"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert doc.source_type == "scanned_pdf"
    assert job.status == "succeeded"
    
    mock_extract.assert_called_once()
    mock_index.assert_called_once()
    args, kwargs = mock_index.call_args
    assert args[1] == doc.id

@patch("app.services.job_runner.extract_ocr_text")
def test_too_short_ocr_text(mock_extract, client, db):
    mock_extract.side_effect = ValueError("Extracted text is too short or empty.")
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.png", b"dummy")
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "test.png")
    
    run_ingestion_job(job_id, "ocr", {"file_path": file_path, "filename": "test.png"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "too short" in doc.error_message.lower()

@patch("app.services.job_runner.extract_ocr_text")
def test_ocr_dependency_failure(mock_extract, client, db):
    mock_extract.side_effect = RuntimeError("OCR engine is not installed or not available")
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.pdf", b"dummy")
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "test.pdf")
    
    run_ingestion_job(job_id, "ocr", {"file_path": file_path, "filename": "test.pdf"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "ocr engine is not installed" in doc.error_message.lower()

@patch("app.services.job_runner.extract_ocr_text")
@patch("app.services.job_runner.index_document_chunks")
def test_indexing_failure_keeps_document_ready(mock_index, mock_extract, client, db):
    mock_extract.return_value = ("Extracted OCR text long enough to pass limits." * 5, {"source_kind": "image", "pages_processed": 1})
    mock_index.return_value = {"failed_count": 1, "indexed_count": 0, "message": "Chroma error"}
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.jpg", b"dummy")
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "test.jpg")
    
    run_ingestion_job(job_id, "ocr", {"file_path": file_path, "filename": "test.jpg"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert job.status == "succeeded"
    assert "indexing failed" in job.message.lower()
    
    mock_index.assert_called_once()
    args, kwargs = mock_index.call_args
    assert args[1] == doc.id

@patch("app.api.routes.sources.settings")
def test_ocr_disabled_returns_503(mock_settings, client, db):
    mock_settings.OCR_ENABLED = False
    
    response = client.post(
        "/api/sources/ocr",
        files=create_upload_file("test.png", b"dummy")
    )
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
    assert db.query(Document).count() == 0
