import pytest
from unittest.mock import patch, MagicMock
from app.services.rag_service import evaluate_rag_confidence, answer_question, stream_grounded_answer
from app.schemas.rag import RagQuestionRequest
from app.services.vector_service import search_chunks

def test_evaluate_rag_confidence_empty():
    passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence([], "balanced")
    assert passed is False
    assert best_sim == 0.0
    assert "No relevant chunks found" in ev_summary
    assert fallbacks == ["search_web", "general_model"]

def test_evaluate_rag_confidence_weak_balanced():
    # In balanced mode, min_dense_sim = 0.28, min_passed_count = 1
    weak_results = [
        {"chunk_id": "c1", "score": 0.15, "distance": 0.85, "text": "weak chunk"}
    ]
    passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(weak_results, "balanced")
    assert passed is False
    assert best_sim == 0.15
    assert "but only 0/1 met the 'balanced' multi-factor criteria" in ev_summary
    assert fallbacks == ["search_web", "general_model"]

def test_evaluate_rag_confidence_strong_balanced():
    strong_results = [
        {"chunk_id": "c1", "score": 0.75, "distance": 0.25, "text": "strong chunk"}
    ]
    passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(strong_results, "balanced")
    assert passed is True
    assert best_sim == 0.75
    assert "Passed confidence check" in ev_summary
    assert fallbacks == []

def test_evaluate_rag_confidence_strict_requires_two_chunks():
    # In strict mode, min_dense_sim = 0.45 and min_passed_count = 2
    one_strong_result = [
        {"chunk_id": "c1", "score": 0.80, "distance": 0.20, "text": "strong chunk 1"},
        {"chunk_id": "c2", "score": 0.20, "distance": 0.80, "text": "weak chunk 2"}
    ]
    passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(one_strong_result, "strict")
    assert passed is False  # only 1 passed, strict requires 2
    assert best_sim == 0.80
    assert "only 1/2 met the 'strict' multi-factor criteria" in ev_summary

def test_evaluate_rag_confidence_distance_fallback():
    # If score is None but distance is present, similarity = 1.0 - distance
    results = [
        {"chunk_id": "c1", "score": None, "distance": 0.30, "text": "distance chunk"}
    ]
    passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(results, "balanced")
    assert passed is True
    assert pytest.approx(best_sim, 0.001) == 0.70

@patch("app.services.rag_service.embed_query", return_value=[0.1, 0.2])
@patch("app.services.rag_service.search_chunks", return_value=[{"chunk_id": "c1", "score": 0.10, "distance": 0.90, "text": "weak"}])
def test_answer_question_insufficient_knowledge(mock_search, mock_embed):
    req = RagQuestionRequest(question="Where is the treasure hidden?", confidence_mode="balanced")
    res = answer_question(req, user_id="test-user")
    assert res.status == "insufficient_knowledge"
    assert res.best_similarity == 0.10
    assert res.fallback_options == ["search_web", "general_model"]
    assert "evidence_summary" in res.model_dump()

@patch("app.services.rag_service.embed_query", return_value=[0.1, 0.2])
@patch("app.services.rag_service.search_chunks", return_value=[{"chunk_id": "c1", "score": 0.10, "distance": 0.90, "text": "weak"}])
def test_stream_grounded_answer_insufficient_knowledge(mock_search, mock_embed):
    req = RagQuestionRequest(question="Where is the treasure hidden?", confidence_mode="balanced")
    generator = stream_grounded_answer(req, user_id="test-user")
    events = list(generator)
    
    # Ensure action_required event is emitted
    action_event = next((e for e in events if "event: action_required" in e), None)
    assert action_event is not None
    assert '"status": "insufficient_knowledge"' in action_event
    assert '"fallback_options": ["search_web", "general_model"]' in action_event

    # Ensure done event indicates insufficient_knowledge
    done_event = next((e for e in events if "event: done" in e), None)
    assert done_event is not None
    assert '"status": "insufficient_knowledge"' in done_event

@patch("app.services.vector_service.get_collection")
def test_vector_service_distance_conversion(mock_get_coll):
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        "ids": [["c_101"]],
        "metadatas": [[{
            "document_id": "doc1",
            "document_title": "Doc 1",
            "source_type": "pdf",
            "chunk_index": 0
        }]],
        "documents": [["Sample text"]],
        "distances": [[0.25]]
    }
    mock_get_coll.return_value = mock_coll

    results = search_chunks([0.1, 0.2], limit=5)
    assert len(results) == 1
    assert results[0]["distance"] == 0.25
    assert pytest.approx(results[0]["score"], 0.001) == 0.75
