import pytest
from unittest.mock import patch
import json
import io
import os
from app.models.document import Document, IngestionJob, DocumentChunk
from app.services.job_runner import run_ingestion_job
from app.core.config import settings

def create_upload_file(filename: str, content: bytes):
    return {"file": (filename, content)}

def test_unsupported_extension_415(client, db):
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("chat.pdf", b"Some content")
    )
    assert response.status_code == 415
    assert db.query(Document).count() == 0

@patch("app.services.job_runner.index_document_chunks")
def test_valid_markdown_import(mock_index, client, db):
    mock_index.return_value = {"failed_count": 0, "indexed_count": 2, "message": "Success"}
    content = b"User: Hello\n\nAssistant: Hi there! How can I help you today? I am a helpful assistant with many skills." * 5
    
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("chat.md", content),
        data={"title": "My MD Chat"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "chat.md")
    
    run_ingestion_job(job_id, "ai_chat", {"file_path": file_path, "filename": "chat.md"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert doc.source_type == "ai_chat"
    assert job.status == "succeeded"
    
    chunks = db.query(DocumentChunk).all()
    assert len(chunks) > 0
    assert "Assistant: Hi there!" in chunks[0].text
    mock_index.assert_called_once()

@patch("app.services.job_runner.index_document_chunks")
def test_valid_txt_import(mock_index, client, db):
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    content = b"User: Testing TXT\n\nAssistant: TXT import is working properly. Here is some extra text to pass the length limit." * 5
    
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("conversation.txt", content)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "conversation.txt")
    
    run_ingestion_job(job_id, "ai_chat", {"file_path": file_path, "filename": "conversation.txt"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert doc.title == "conversation"

@patch("app.services.job_runner.index_document_chunks")
def test_chatgpt_json_import(mock_index, client, db):
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    chatgpt_data = [{
        "mapping": {
            "node1": {
                "message": {
                    "create_time": 1000,
                    "author": {"role": "user"},
                    "content": {"parts": ["Hello GPT"]}
                }
            },
            "node2": {
                "message": {
                    "create_time": 1001,
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Hello User, I am GPT. This is a sufficiently long response to pass the 100 char limit! I am adding extra words to make sure the extracted text easily surpasses one hundred non-whitespace characters!"]}
                }
            }
        }
    }]
    
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("chatgpt.json", json.dumps(chatgpt_data).encode("utf-8"))
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "chatgpt.json")
    
    run_ingestion_job(job_id, "ai_chat", {"file_path": file_path, "filename": "chatgpt.json"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    assert doc.status == "ready"
    
    chunks = db.query(DocumentChunk).all()
    text = chunks[0].text
    assert "User: Hello GPT" in text
    assert "Assistant: Hello User, I am GPT" in text

@patch("app.services.job_runner.index_document_chunks")
def test_too_short_text_returns_failed_job(mock_index, client, db):
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("short.txt", b"Too short.")
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "short.txt")
    
    run_ingestion_job(job_id, "ai_chat", {"file_path": file_path, "filename": "short.txt"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "too short" in doc.error_message.lower()

@patch("app.services.job_runner.index_document_chunks")
def test_indexing_failure_keeps_doc_ready(mock_index, client, db):
    mock_index.return_value = {"failed_count": 1, "indexed_count": 0, "message": "Chroma error"}
    content = b"User: Test\n\nAssistant: I am long enough to pass the one hundred character text limit for the system testing!" * 2
    
    response = client.post(
        "/api/sources/ai-chat",
        files=create_upload_file("chat.txt", content)
    )
    assert response.status_code == 200
    data = response.json()
    
    doc_id = data["document"]["id"]
    job_id = data["job"]["id"]
    file_path = os.path.join(settings.STORAGE_DIR, "originals", doc_id, "chat.txt")
    
    run_ingestion_job(job_id, "ai_chat", {"file_path": file_path, "filename": "chat.txt"}, db=db)
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    
    assert doc.status == "ready"
    assert job.status == "succeeded"
    assert "indexing failed" in job.message
    mock_index.assert_called_once()
