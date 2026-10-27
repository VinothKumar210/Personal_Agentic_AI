"""
Tests for the Autonomous Multi-Step Research Agent Service.

Covers:
- Query decomposition with mocked Groq responses
- Parallel retrieval execution with ThreadPoolExecutor
- Self-correction loop and web-safe policy enforcement
- Synthesis with empty evidence guard
- Chat persistence of metadata_json research_steps
- ResearchStepRecord structured schema
"""
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.services.research_agent_service import (
    ResearchStepRecord,
    decompose_query,
    execute_research_step,
    reflect_and_correct,
    synthesize_research_answer,
    run_autonomous_research,
    _deduplicate_chunks,
    _retrieve_web,
)
from app.schemas.rag import RagQuestionRequest, RagAnswerResponse, RagCitation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id=None, text="Sample text", score=0.9, source_type="pdf"):
    cid = chunk_id or str(uuid.uuid4())
    did = str(uuid.uuid4())
    return {
        "chunk_id": cid,
        "document_id": did,
        "document_title": "Test Doc",
        "source_type": source_type,
        "original_filename": "test.pdf",
        "source_uri": None,
        "chunk_index": 0,
        "text": text,
        "score": score,
    }


def _make_mock_groq_response(content: str):
    """Create a mock Groq completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


def _patch_groq(response_content: str):
    """Context manager that patches groq.Groq globally so deferred imports work."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_mock_groq_response(response_content)
    return patch("groq.Groq", return_value=mock_client)


# ---------------------------------------------------------------------------
# 1. ResearchStepRecord Schema
# ---------------------------------------------------------------------------

def test_research_step_record_schema():
    step = ResearchStepRecord(
        iteration=1,
        query="test query",
        target_sources=["code", "documents"],
        source_counts={"local": 3, "personal_memory": 1},
        status="retrieved",
        reason="Retrieved 4 chunks"
    )
    d = step.model_dump()
    assert d["iteration"] == 1
    assert d["query"] == "test query"
    assert d["target_sources"] == ["code", "documents"]
    assert d["source_counts"]["local"] == 3
    assert d["status"] == "retrieved"
    assert d["reason"] == "Retrieved 4 chunks"


def test_research_step_record_defaults():
    step = ResearchStepRecord(iteration=1, query="q", target_sources=["code"])
    assert step.status == "pending"
    assert step.reason is None
    assert step.source_counts == {}


# ---------------------------------------------------------------------------
# 2. Query Decomposition
# ---------------------------------------------------------------------------

def test_decompose_query_with_groq():
    response_json = json.dumps({
        "queries": [
            {"query": "How does JWT auth middleware work?", "target_sources": ["code"]},
            {"query": "Privacy rules for personal memories", "target_sources": ["code", "personal_memory"]}
        ]
    })
    with patch("app.services.research_agent_service.is_groq_configured", return_value=True), \
         _patch_groq(response_json):
        result = decompose_query("Compare JWT auth with personal memory privacy rules")
    assert len(result) == 2
    assert result[0]["query"] == "How does JWT auth middleware work?"
    assert result[0]["target_sources"] == ["code"]
    assert result[1]["target_sources"] == ["code", "personal_memory"]


def test_decompose_query_fallback_without_groq():
    with patch("app.services.research_agent_service.is_groq_configured", return_value=False):
        result = decompose_query("Some complex question")
    assert len(result) == 1
    assert result[0]["query"] == "Some complex question"
    assert "code" in result[0]["target_sources"]


def test_decompose_query_handles_groq_error():
    with patch("app.services.research_agent_service.is_groq_configured", return_value=True), \
         patch("groq.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.side_effect = RuntimeError("API down")
        result = decompose_query("Some question")
    assert len(result) == 1
    assert result[0]["query"] == "Some question"


# ---------------------------------------------------------------------------
# 3. Parallel Retrieval Execution
# ---------------------------------------------------------------------------

def test_execute_research_step_routes_to_local():
    chunks = [_make_chunk(text="code chunk")]
    with patch("app.services.research_agent_service._retrieve_local_chunks", return_value=chunks) as mock_local:
        db = MagicMock()
        result_chunks, counts = execute_research_step(
            db, "auth middleware", ["code"], "user1", limit=6, web_allowed=False
        )
        mock_local.assert_called_once()
        assert len(result_chunks) == 1
        assert counts["local"] == 1


def test_execute_research_step_routes_to_memory():
    mem_chunks = [_make_chunk(text="memory item", source_type="personal_memory")]
    with patch("app.services.research_agent_service._retrieve_personal_memories", return_value=mem_chunks):
        db = MagicMock()
        result_chunks, counts = execute_research_step(
            db, "my preferences", ["personal_memory"], "user1", limit=6, web_allowed=False
        )
        assert counts["personal_memory"] == 1
        assert result_chunks[0]["source_type"] == "personal_memory"


def test_execute_research_step_blocks_web_when_not_allowed():
    with patch("app.services.research_agent_service._retrieve_web") as mock_web:
        db = MagicMock()
        execute_research_step(
            db, "external info", ["web"], "user1", limit=6, web_allowed=False
        )
        mock_web.assert_not_called()


def test_execute_research_step_allows_web_when_permitted():
    web_chunks = [_make_chunk(text="web result", source_type="web_tavily")]
    with patch("app.services.research_agent_service._retrieve_web", return_value=web_chunks):
        db = MagicMock()
        result_chunks, counts = execute_research_step(
            db, "external info", ["web"], "user1", limit=6, web_allowed=True
        )
        assert counts["web"] == 1


# ---------------------------------------------------------------------------
# 4. Self-Correction & Web-Safe Policy
# ---------------------------------------------------------------------------

def test_reflect_passes_when_confidence_sufficient():
    chunks = [_make_chunk(score=0.9), _make_chunk(score=0.85)]
    sufficient, _, reason = reflect_and_correct(
        "test question",
        [{"query": "q1", "target_sources": ["code"]}],
        chunks, iteration=1, max_iterations=2
    )
    assert sufficient is True
    assert "passed" in reason.lower() or "Passed" in reason


def test_reflect_stops_at_max_iterations():
    chunks = [_make_chunk(score=0.05)]  # Very weak
    sufficient, _, reason = reflect_and_correct(
        "test question",
        [{"query": "q1", "target_sources": ["code"]}],
        chunks, iteration=2, max_iterations=2
    )
    assert sufficient is False
    assert "Max iterations" in reason


def test_reflect_never_injects_web():
    """Self-correction must NOT add 'web' if it wasn't in original sub-queries."""
    chunks = [_make_chunk(score=0.05)]  # Very weak

    # LLM tries to inject "web" — our code should strip it
    rewrite_json = json.dumps({
        "queries": [{"query": "broader search", "target_sources": ["code", "web"]}]
    })
    with patch("app.services.research_agent_service.is_groq_configured", return_value=True), \
         _patch_groq(rewrite_json):
        sufficient, rewritten, reason = reflect_and_correct(
            "test question",
            [{"query": "q1", "target_sources": ["code"]}],
            chunks, iteration=1, max_iterations=2
        )
    assert sufficient is False
    # Verify web was stripped
    for rq in rewritten:
        assert "web" not in rq["target_sources"], "Web should not be injected by self-correction"


# ---------------------------------------------------------------------------
# 5. Synthesis with Empty Evidence Guard
# ---------------------------------------------------------------------------

def test_synthesize_returns_insufficient_with_no_chunks():
    steps = [ResearchStepRecord(iteration=1, query="q", target_sources=["code"])]
    answer, status, citations, contexts = synthesize_research_answer(
        "test question", [], steps, "balanced"
    )
    assert status == "insufficient_knowledge"
    assert citations == []
    assert "insufficient evidence" in answer.lower()


def test_synthesize_returns_insufficient_when_gating_fails():
    weak_chunks = [_make_chunk(score=0.05)]
    steps = [ResearchStepRecord(iteration=1, query="q", target_sources=["code"])]
    answer, status, citations, contexts = synthesize_research_answer(
        "test question", weak_chunks, steps, "strict"
    )
    assert status == "insufficient_knowledge"
    assert citations == []


def test_synthesize_calls_groq_with_good_evidence():
    good_chunks = [_make_chunk(score=0.9), _make_chunk(score=0.85)]
    steps = [ResearchStepRecord(iteration=1, query="q", target_sources=["code"])]

    with patch("app.services.research_agent_service.is_groq_configured", return_value=True), \
         _patch_groq("Synthesized answer based on [1] and [2]."):
        answer, status, citations, contexts = synthesize_research_answer(
            "test question", good_chunks, steps, "balanced"
        )
    assert status == "answered"
    assert len(citations) == 2
    assert "Synthesized" in answer


# ---------------------------------------------------------------------------
# 6. Deduplication
# ---------------------------------------------------------------------------

def test_deduplicate_chunks_keeps_highest_score():
    cid = str(uuid.uuid4())
    c1 = _make_chunk(chunk_id=cid, score=0.5)
    c2 = _make_chunk(chunk_id=cid, score=0.9)
    deduped = _deduplicate_chunks([c1, c2])
    assert len(deduped) == 1
    assert deduped[0]["score"] == 0.9


# ---------------------------------------------------------------------------
# 7. Full Orchestrator (run_autonomous_research)
# ---------------------------------------------------------------------------

def test_run_autonomous_research_full_flow():
    good_chunks = [_make_chunk(score=0.9)]
    decomposed = [{"query": "sub query 1", "target_sources": ["code"]}]

    # Create a proper RagCitation for the mock
    mock_citation = RagCitation(
        citation_id=1,
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="Test Doc",
        source_type="pdf",
        chunk_index=0,
        text_preview="Sample text"
    )

    with patch("app.services.research_agent_service.decompose_query", return_value=decomposed), \
         patch("app.services.research_agent_service.execute_research_step", return_value=(good_chunks, {"local": 1})), \
         patch("app.services.research_agent_service.reflect_and_correct", return_value=(True, decomposed, "Passed")), \
         patch("app.services.research_agent_service.synthesize_research_answer") as mock_synth:

        mock_synth.return_value = ("Final answer [1].", "answered", [mock_citation], [{}])

        db = MagicMock()
        request = RagQuestionRequest(question="Complex question", research_mode=True)
        result = run_autonomous_research(db, request, "user1")

        assert result.status == "answered"
        assert result.research_steps is not None
        assert len(result.research_steps) >= 1


# ---------------------------------------------------------------------------
# 8. Chat persistence of metadata_json
# ---------------------------------------------------------------------------

def test_chat_message_metadata_persistence():
    """Verify ChatMessage model and schema handle metadata_json correctly."""
    from app.models.chat import ChatMessage

    steps_data = [{"iteration": 1, "query": "q", "target_sources": ["code"], "source_counts": {"local": 2}, "status": "retrieved", "reason": "ok"}]
    meta = {"research_steps": steps_data}

    msg = ChatMessage(
        id=str(uuid.uuid4()),
        conversation_id=str(uuid.uuid4()),
        role="assistant",
        content="Research answer",
        citations_json="[]",
        metadata_json=json.dumps(meta)
    )

    assert msg.metadata_json is not None
    parsed = json.loads(msg.metadata_json)
    assert "research_steps" in parsed
    assert parsed["research_steps"][0]["iteration"] == 1
    assert parsed["research_steps"][0]["target_sources"] == ["code"]


# ---------------------------------------------------------------------------
# 9. Stable synthetic UUIDs for web citations
# ---------------------------------------------------------------------------

def test_web_chunks_get_stable_uuids():
    fake_chunks = [
        {"chunk_id": "random", "document_id": "random", "source_uri": "https://example.com/page1",
         "document_title": "Example", "source_type": "web_tavily", "chunk_index": 1,
         "text": "content", "score": 0.9}
    ]
    with patch("app.services.tavily_client.search_web_ephemeral", return_value=fake_chunks):
        result = _retrieve_web("test query", limit=5)
    # Should have deterministic UUIDv5 based on URL
    expected_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.com/page1"))
    assert result[0]["chunk_id"] == expected_uuid
    assert result[0]["document_id"] == expected_uuid
