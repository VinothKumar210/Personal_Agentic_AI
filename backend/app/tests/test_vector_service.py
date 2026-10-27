import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def reset_chroma_client(monkeypatch):
    import app.services.vector_service as vs
    monkeypatch.setattr(vs.settings, "CHROMA_API_KEY", "")
    vs._chroma_client = None
    yield
    vs._chroma_client = None

@patch("app.services.vector_service.chromadb.HttpClient")
def test_index_chunks(mock_client_cls):
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_cls.return_value = mock_client

    from app.services.vector_service import index_chunks

    chunks_data = [
        {
            "id": "chunk1",
            "text": "text1",
            "document_id": "doc1",
            "chunk_index": 0,
            "document_title": "title1",
            "source_type": "pdf",
            "original_filename": "file.pdf",
            "source_uri": "http://example.com/file.pdf",
            "user_id": "test-user-id"
        }
    ]
    embeddings = [[0.1, 0.2]]

    index_chunks(chunks_data, embeddings)

    mock_collection.upsert.assert_called_once()
    args, kwargs = mock_collection.upsert.call_args
    assert kwargs["ids"] == ["chunk1"]
    assert kwargs["embeddings"] == [[0.1, 0.2]]
    assert kwargs["documents"] == ["text1"]
    assert kwargs["metadatas"] == [{
        "chunk_id": "chunk1",
        "document_id": "doc1",
        "chunk_index": 0,
        "document_title": "title1",
        "source_type": "pdf",
        "original_filename": "file.pdf",
        "source_uri": "http://example.com/file.pdf",
        "user_id": "test-user-id"
    }]

@patch("app.services.vector_service.chromadb.HttpClient")
def test_search_chunks(mock_client_cls):
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["chunk1"]],
        "distances": [[0.1]],
        "metadatas": [[{
            "chunk_id": "chunk1",
            "document_id": "doc1",
            "chunk_index": 0,
            "document_title": "title1",
            "source_type": "pdf",
            "user_id": "test-user-id"
        }]],
        "documents": [["text1"]]
    }
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client_cls.return_value = mock_client

    from app.services.vector_service import search_chunks

    results = search_chunks([0.1, 0.2], filters={"source_type": "pdf", "document_id": "doc1", "user_id": "test-user-id"})
    
    mock_collection.query.assert_called_once()
    args, kwargs = mock_collection.query.call_args
    
    assert kwargs["query_embeddings"] == [[0.1, 0.2]]
    assert kwargs["n_results"] == 8
    
    # Check if where clause is correctly shaped for Chroma (AND condition)
    where_clause = kwargs["where"]
    assert "$and" in where_clause
    assert {"source_type": "pdf"} in where_clause["$and"]
    assert {"document_id": "doc1"} in where_clause["$and"]
    assert {"user_id": "test-user-id"} in where_clause["$and"]

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk1"
    assert results[0]["text"] == "text1"
    assert results[0]["distance"] == 0.1
    assert results[0]["score"] == 0.9
