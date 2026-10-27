import pytest
from unittest.mock import patch

def test_search_knowledge_success(client):
    with patch("app.api.routes.search.embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch("app.api.routes.search.search_chunks", return_value=[
             {
                 "chunk_id": "00000000-0000-0000-0000-000000000001",
                 "document_id": "00000000-0000-0000-0000-000000000002",
                 "document_title": "Test Doc",
                 "source_type": "text",
                 "chunk_index": 0,
                 "text": "This is a search result",
                 "score": 0.95
             }
         ]):
        response = client.post("/api/search", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert len(data["results"]) == 1
        assert data["results"][0]["text"] == "This is a search result"

def test_search_knowledge_filters(client):
    with patch("app.api.routes.search.embed_query", return_value=[0.1, 0.2, 0.3]), \
         patch("app.api.routes.search.search_chunks", return_value=[]) as mock_search:
        response = client.post("/api/search", json={
            "query": "test", 
            "source_type": "pdf",
            "document_id": "00000000-0000-0000-0000-000000000002"
        })
        assert response.status_code == 200
        mock_search.assert_called_once()
        filters = mock_search.call_args[1]["filters"]
        assert filters["source_type"] == "pdf"
        assert filters["document_id"] == "00000000-0000-0000-0000-000000000002"

def test_search_knowledge_unavailable(client):
    with patch("app.api.routes.search.embed_query", side_effect=Exception("Chroma down")):
        response = client.post("/api/search", json={"query": "test query"})
        assert response.status_code == 503
        assert "Search service unavailable" in response.json()["detail"]

def test_search_knowledge_blank_query(client):
    response = client.post("/api/search", json={"query": "   "})
    assert response.status_code == 422
