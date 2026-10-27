import pytest
from unittest.mock import patch
from app.models.document import Document, IngestionJob, DocumentChunk
from app.services.job_runner import run_ingestion_job

@patch("app.services.job_runner.index_document_chunks")
def test_save_web_result_endpoint_and_job(mock_index, client, db):
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    payload = {
        "title": "Saved Web Article",
        "url": "https://example.com/article",
        "content": "This is a very informative web article about RAG systems and multi-factor confidence gating that we want to save to the knowledge base permanently. " * 5
    }
    response = client.post("/api/sources/save-web-result", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Web result saved and queued for indexing"
    assert data["document"]["title"] == "Saved Web Article"
    assert data["document"]["source_type"] == "web_search_saved"
    assert data["job"]["status"] == "queued"

    # Run background job synchronously
    job_id = data["job"]["id"]
    run_ingestion_job(job_id, "web_search_saved", payload, db=db)

    # Verify database records
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == str(doc.id)).all()

    assert doc.status == "ready"
    assert job.status == "succeeded"
    assert len(chunks) > 0
    assert "RAG systems" in chunks[0].text
