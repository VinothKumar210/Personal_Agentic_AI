import pytest
from unittest.mock import patch, MagicMock
from app.models.document import Document, DocumentChunk
from app.services.reranking_service import rerank_chunks
from app.services.hybrid_search_service import sparse_keyword_search, hybrid_search_and_rerank
from app.core.config import settings

def test_rerank_chunks_disabled_or_empty():
    assert rerank_chunks("query", []) == []
    
    candidates = [
        {"id": "1", "text": "alpha"},
        {"id": "2", "text": "beta"}
    ]
    with patch("app.services.reranking_service.settings") as mock_settings:
        mock_settings.RERANKING_ENABLED = False
        res = rerank_chunks("query", candidates, top_k=1)
        assert len(res) == 1
        assert res[0]["id"] == "1"

@patch("app.services.reranking_service.get_cross_encoder")
def test_rerank_chunks_with_mock_model(mock_get_model):
    mock_model = MagicMock()
    # Predict returns high score for second item, low score for first item
    mock_model.predict.return_value = [0.1, 0.9]
    mock_get_model.return_value = mock_model
    
    candidates = [
        {"id": "1", "text": "unrelated text"},
        {"id": "2", "text": "highly relevant query match"}
    ]
    with patch("app.services.reranking_service.settings") as mock_settings:
        mock_settings.RERANKING_ENABLED = True
        res = rerank_chunks("match", candidates, top_k=2)
        assert len(res) == 2
        assert res[0]["id"] == "2"
        assert res[0]["rerank_score"] == 0.9
        assert res[1]["id"] == "1"

def test_sparse_keyword_search(db, test_user):
    doc = Document(
        id="doc-1",
        user_id=test_user.id,
        title="Python Guide",
        source_type="text",
        status="completed"
    )
    db.add(doc)
    
    chunk1 = DocumentChunk(
        id="chunk-1",
        document_id="doc-1",
        chunk_index=0,
        text="Python is a powerful programming language for data science and AI.",
        character_count=64
    )
    chunk2 = DocumentChunk(
        id="chunk-2",
        document_id="doc-1",
        chunk_index=1,
        text="Baking a delicious chocolate cake requires flour, sugar, and cocoa.",
        character_count=67
    )
    db.add(chunk1)
    db.add(chunk2)
    db.commit()
    
    results = sparse_keyword_search("python programming", db, test_user.id)
    assert len(results) >= 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["sparse_score"] > 0.0

@patch("app.services.hybrid_search_service.search_chunks")
@patch("app.services.hybrid_search_service.rerank_chunks")
def test_hybrid_search_and_rrf(mock_rerank, mock_dense_search, db, test_user):
    # Setup dense results
    mock_dense_search.return_value = [
        {
            "chunk_id": "dense-1",
            "document_id": "doc-dense",
            "document_title": "Dense Doc",
            "source_type": "text",
            "chunk_index": 0,
            "text": "Dense content match"
        }
    ]
    
    # Setup sparse DB chunk
    doc = Document(
        id="doc-sparse",
        user_id=test_user.id,
        title="Sparse Doc",
        source_type="text",
        status="completed"
    )
    db.add(doc)
    chunk = DocumentChunk(
        id="sparse-1",
        document_id="doc-sparse",
        chunk_index=0,
        text="Unique keyword match alpha beta",
        character_count=31
    )
    db.add(chunk)
    db.commit()
    
    mock_rerank.side_effect = lambda query, pool, top_k: pool[:top_k]
    
    results = hybrid_search_and_rerank("keyword alpha", [0.1, 0.2], db, test_user.id, limit=5)
    assert len(results) == 2
    # Check that both dense and sparse results were merged via RRF
    ids = {r["chunk_id"] for r in results}
    assert "dense-1" in ids
    assert "sparse-1" in ids
