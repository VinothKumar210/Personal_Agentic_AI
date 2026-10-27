import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.models.document import Document, IngestionJob, DocumentChunk
from app.services.job_runner import run_ingestion_job

def test_invalid_url_422(client, db):
    response = client.post("/api/sources/webpage", json={"url": "not a url"})
    assert response.status_code == 422
    assert "Unsupported URL scheme" in response.json()["detail"]
    assert db.query(Document).count() == 0

def test_unsupported_scheme_422(client, db):
    response = client.post("/api/sources/webpage", json={"url": "ftp://example.com/file"})
    assert response.status_code == 422
    assert "Unsupported URL scheme" in response.json()["detail"]
    assert db.query(Document).count() == 0

@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_unsupported_content_type_415(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com/file.pdf"})
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com/file.pdf"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "Unsupported content type" in job.error_message

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_missing_content_type_with_html_body_succeeds(mock_get, mock_index, client, db):
    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.text = "<html><body>" + ("P " * 100) + "</body></html>"
    mock_response.url = "https://example.com"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    assert doc.status == "ready"

@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_missing_content_type_with_non_html_body_fails(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.text = "Just some plain text data that does not contain html tags."
    mock_response.url = "https://example.com"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com"}, db=db)
    
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert job.status == "failed"
    assert "Unsupported content type" in job.error_message

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_successful_ingestion(mock_get, mock_index, client, db):
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    html_content = """
    <html>
        <head><title>My HTML Title</title></head>
        <body>
            <script>let a = 1;</script>
            <style>body { color: red; }</style>
            <nav>Menu item</nav>
            <header>Logo</header>
            <main>
                <div>Unrelated sidebar content that should not be extracted if article exists</div>
                <article>
                    <p>This is the actual readable content that should be extracted. It needs to be at least one hundred characters long to pass the threshold test, so I am writing a reasonably long paragraph here to ensure it works correctly without failing the minimum length requirement. Extra text added to be sure.</p>
                </article>
            </main>
            <footer>Copyright 2026</footer>
            <noscript>You need JS</noscript>
            <svg><path/></svg>
        </body>
    </html>
    """
    mock_response.text = html_content
    mock_response.url = "https://example.com/article"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com/article"})
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com/article"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    
    assert doc.source_type == "webpage"
    assert doc.title == "My HTML Title"
    assert doc.status == "ready"
    assert job.status == "succeeded"
    
    chunks = db.query(DocumentChunk).all()
    assert len(chunks) > 0
    all_text = " ".join([c.text for c in chunks])
    assert "let a = 1" not in all_text
    assert "color: red" not in all_text
    assert "Menu item" not in all_text
    assert "Logo" not in all_text
    assert "Copyright" not in all_text
    assert "You need JS" not in all_text
    assert "Unrelated sidebar content" not in all_text
    assert "actual readable content" in all_text

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_user_title_overrides_html_title(mock_get, mock_index, client, db):
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><head><title>HTML Title</title></head><body>" + ("P " * 100) + "</body></html>"
    mock_response.url = "https://example.com"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com", "title": "User Override"})
    assert response.status_code == 200
    assert response.json()["document"]["title"] == "User Override"

@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_too_short_text_fails(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><body>Too short</body></html>"
    mock_response.url = "https://example.com"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "too short" in doc.error_message

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_indexing_failure_leaves_doc_ready(mock_get, mock_index, client, db):
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html><body>" + ("Content text here that is sufficiently long. " * 10) + "</body></html>"
    mock_response.url = "https://example.com"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    mock_index.return_value = {"failed_count": 1, "indexed_count": 0, "message": "Chroma error"}
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "ready"
    assert job.status == "succeeded"
    assert "indexing failed" in job.message

@patch("app.services.web_ingestion_service.httpx.Client.get")
def test_network_timeout_handled(mock_get, client, db):
    mock_get.side_effect = httpx.TimeoutException("Timeout")
    
    response = client.post("/api/sources/webpage", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "webpage", {"url": "https://example.com"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "timed out" in doc.error_message
