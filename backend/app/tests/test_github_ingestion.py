import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.models.document import Document, IngestionJob, DocumentChunk
from app.services.job_runner import run_ingestion_job

def test_invalid_domain_422(client, db):
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://gitlab.com/owner/repo"})
    assert response.status_code == 422
    assert "Unsupported URL scheme" in response.json()["detail"]
    assert db.query(Document).count() == 0

def test_unsupported_url_path_422(client, db):
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo/tree/main/src"})
    assert response.status_code == 422
    assert "Branch/path-scoped URLs are not supported" in response.json()["detail"]
    assert db.query(Document).count() == 0

@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_repo_404_returns_failed_job(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "not found" in doc.error_message.lower()

@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_repo_rate_limit_returns_failed_job(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "API rate limit exceeded for xxx.xxx.xxx.xxx"
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "rate limit" in doc.error_message.lower()

@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_network_failure_returns_failed_job(mock_get, client, db):
    mock_get.side_effect = httpx.TimeoutException("Timeout")
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "timed out" in doc.error_message.lower()

@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_no_allowed_files_returns_failed_job(mock_get, client, db):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tree": [
            {"path": "image.png", "type": "blob"},
            {"path": "video.mp4", "type": "blob"}
        ]
    }
    mock_get.return_value = mock_response
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "failed"
    assert job.status == "failed"
    assert "No ingestable files" in doc.error_message

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_successful_ingestion_and_filtering(mock_get, mock_index, client, db):
    def mock_get_impl(*args, **kwargs):
        url = args[0]
        resp = MagicMock()
        resp.status_code = 200
        
        if "api.github.com/repos" in url:
            resp.json.return_value = {
                "tree": [
                    {"path": "main.py", "type": "blob", "size": 1000}, # valid
                    {"path": "README.md", "type": "blob", "size": 500}, # valid
                    {"path": "too_big.py", "type": "blob", "size": 9999999}, # Excluded: Over limit
                    {"path": ".git/config", "type": "blob", "size": 100}, # Excluded: Ignored directory (.git/)
                    {"path": "node_modules/lib.js", "type": "blob", "size": 100}, # Excluded: Ignored directory
                    {"path": "package-lock.json", "type": "blob", "size": 100}, # Excluded: lockfile
                    {"path": "image.jpg", "type": "blob", "size": 100} # Excluded: unsupported extension
                ]
            }
        else:
            # Raw content fetch
            if "main.py" in url:
                resp.content = b"def main():\n    print('hello world')\n" * 10
            elif "README.md" in url:
                resp.content = b"# Readme\nThis is a readme file.\n" * 10
            else:
                resp.content = b""
        return resp
        
    mock_get.side_effect = mock_get_impl
    mock_index.return_value = {"failed_count": 0, "indexed_count": 2, "message": "Success"}
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo", "title": "My Repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "queued"
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    
    assert doc.title == "My Repo"
    assert doc.source_type == "github_repo"
    assert doc.status == "ready"
    assert job.status == "succeeded"
    
    chunks = db.query(DocumentChunk).all()
    assert len(chunks) > 0
    all_text = " ".join([c.text for c in chunks])
    assert "File: main.py" in all_text
    assert "File: README.md" in all_text
    assert "too_big.py" not in all_text
    assert ".git/config" not in all_text
    assert "node_modules/lib.js" not in all_text
    assert "package-lock.json" not in all_text
    
    mock_index.assert_called_once()

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_indexing_failure_leaves_doc_ready(mock_get, mock_index, client, db):
    def mock_get_impl(*args, **kwargs):
        url = args[0]
        resp = MagicMock()
        resp.status_code = 200
        
        if "api.github.com" in url:
            resp.json.return_value = {"tree": [{"path": "main.py", "type": "blob", "size": 1000}]}
        else:
            resp.content = b"def main():\n    print('hello world')\n" * 10
        return resp
        
    mock_get.side_effect = mock_get_impl
    mock_index.return_value = {"failed_count": 1, "indexed_count": 0, "message": "Chroma error"}
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    doc = db.query(Document).filter(Document.id == data["document"]["id"]).first()
    job = db.query(IngestionJob).filter(IngestionJob.id == data["job"]["id"]).first()
    assert doc.status == "ready"
    assert job.status == "succeeded"
    assert "indexing failed" in job.message
    
    mock_index.assert_called_once()

@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_list_github_repos_endpoint(mock_get, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"name": "repo1", "full_name": "owner/repo1", "private": False, "html_url": "https://github.com/owner/repo1", "description": "Desc", "default_branch": "main"}
    ]
    mock_get.return_value = mock_resp
    
    response = client.get("/api/sources/github/repos?pat=ghp_test123")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "owner/repo1"

@patch("app.services.job_runner.index_document_chunks")
@patch("app.services.github_ingestion_service.httpx.Client.get")
def test_delta_sync_skips_unchanged_files(mock_get, mock_index, client, db):
    def mock_get_impl(*args, **kwargs):
        url = args[0]
        resp = MagicMock()
        resp.status_code = 200
        if "api.github.com/repos" in url:
            resp.json.return_value = {
                "tree": [
                    {"path": "main.py", "type": "blob", "size": 1000, "sha": "abc123sha"}
                ]
            }
        else:
            resp.content = b"def main():\n    print('hello world')\n"
        return resp
        
    mock_get.side_effect = mock_get_impl
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "Success"}
    
    response = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo", "title": "Delta Repo"})
    assert response.status_code == 200
    data = response.json()
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    chunks_after_first = db.query(DocumentChunk).filter(DocumentChunk.document_id == data["document"]["id"]).all()
    assert len(chunks_after_first) == 1
    first_chunk_id = chunks_after_first[0].id
    
    # Second run: run ingestion job again with same sha ("abc123sha")
    mock_get.reset_mock()
    mock_index.reset_mock()
    mock_index.return_value = {"failed_count": 0, "indexed_count": 1, "message": "All 1 chunks up-to-date"}
    
    run_ingestion_job(data["job"]["id"], "github_repo", {"owner": "owner", "repo": "repo"}, db=db)
    
    chunks_after_second = db.query(DocumentChunk).filter(DocumentChunk.document_id == data["document"]["id"]).all()
    assert len(chunks_after_second) == 1
    assert chunks_after_second[0].id == first_chunk_id
