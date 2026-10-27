import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.tavily_client import search_web_ephemeral, format_tavily_citations
from app.services.rag_service import answer_question, stream_grounded_answer
from app.schemas.rag import RagQuestionRequest, RagCitation
from app.core.config import settings

def test_format_tavily_citations():
    results = [
        {
            "title": "Tavily AI",
            "url": "https://tavily.com",
            "content": "Tavily is a search engine built specifically for AI agents."
        }
    ]
    citations = format_tavily_citations(results)
    assert len(citations) == 1
    assert isinstance(citations[0], RagCitation)
    assert citations[0].source_type == "web_tavily"
    assert citations[0].source_uri == "https://tavily.com"
    assert citations[0].document_title == "Tavily AI"
    assert citations[0].text_preview == "Tavily is a search engine built specifically for AI agents."
    assert citations[0].citation_id == 1

@patch("httpx.Client.post")
def test_search_web_ephemeral_success(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "results": [
            {
                "title": "FastAPI Guide",
                "url": "https://fastapi.tiangolo.com",
                "content": "FastAPI framework, high performance, easy to learn, fast to code, ready for production"
            }
        ]
    }
    mock_post.return_value = mock_response

    with patch.object(settings, "TAVILY_API_KEY", "test-key-123"):
        chunks = search_web_ephemeral("fastapi performance")
        assert len(chunks) == 1
        assert chunks[0]["source_type"] == "web_tavily"
        assert chunks[0]["source_uri"] == "https://fastapi.tiangolo.com"

def test_search_web_ephemeral_missing_key():
    with patch.object(settings, "TAVILY_API_KEY", None):
        with pytest.raises(ValueError, match="TAVILY_API_KEY is not configured"):
            search_web_ephemeral("test query")

@patch("app.services.rag_service.is_groq_configured", return_value=True)
@patch("app.services.rag_service.generate_grounded_answer", return_value="Here is the web answer.")
@patch("app.services.tavily_client.get_ephemeral_web_contexts")
def test_rag_answer_question_fallback_search_web(mock_web, mock_gen, mock_groq):
    mock_web.return_value = (
        [],
        [{"citation_id": 1, "document_title": "Web Title", "text": "snippet"}],
        [RagCitation(
            citation_id=1,
            chunk_id="00000000-0000-0000-0000-000000000001",
            document_id="00000000-0000-0000-0000-000000000002",
            document_title="Web Title",
            source_type="web_tavily",
            source_uri="https://example.com/web",
            chunk_index=1,
            text_preview="Web snippet content"
        )]
    )
    req = RagQuestionRequest(question="Latest tech news?", fallback_action="search_web")
    res = answer_question(req, user_id="user-1")
    
    assert res.status == "answered"
    assert res.answer == "Here is the web answer."
    assert len(res.citations) == 1
    assert res.citations[0].source_type == "web_tavily"
    mock_web.assert_called_once_with("Latest tech news?", max_results=6)

@patch("app.services.rag_service.is_groq_configured", return_value=True)
@patch("app.services.rag_service.generate_grounded_answer", return_value="General model knowledge answer.")
def test_rag_answer_question_fallback_general_model(mock_gen, mock_groq):
    req = RagQuestionRequest(question="What is quantum mechanics?", fallback_action="general_model")
    res = answer_question(req, user_id="user-1")
    
    assert res.status == "answered"
    assert res.answer == "General model knowledge answer."
    assert len(res.citations) == 0

@patch("app.services.rag_service.is_groq_configured", return_value=True)
@patch("app.services.rag_service.generate_grounded_answer", return_value="Route web answer.")
@patch("app.services.tavily_client.get_ephemeral_web_contexts")
def test_api_rag_search_web_route(mock_web, mock_gen, mock_groq, client):
    mock_web.return_value = (
        [],
        [{"citation_id": 1, "document_title": "Web Title", "text": "snippet"}],
        [RagCitation(
            citation_id=1,
            chunk_id="00000000-0000-0000-0000-000000000001",
            document_id="00000000-0000-0000-0000-000000000002",
            document_title="Web Title",
            source_type="web_tavily",
            source_uri="https://example.com/web",
            chunk_index=1,
            text_preview="Web snippet content"
        )]
    )
    response = client.post(
        "/api/rag/search-web",
        json={"question": "Latest updates?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["source_type"] == "web_tavily"

@patch("app.services.rag_service.is_groq_configured", return_value=True)
@patch("app.services.groq_client.stream_grounded_answer_tokens")
@patch("app.services.tavily_client.get_ephemeral_web_contexts")
def test_stream_grounded_answer_fallback_web(mock_web, mock_stream, mock_groq):
    mock_web.return_value = (
        [],
        [{"citation_id": 1, "document_title": "Web Title", "text": "snippet"}],
        [RagCitation(
            citation_id=1,
            chunk_id="00000000-0000-0000-0000-000000000001",
            document_id="00000000-0000-0000-0000-000000000002",
            document_title="Web Title",
            source_type="web_tavily",
            source_uri="https://example.com/web",
            chunk_index=1,
            text_preview="Web snippet content"
        )]
    )
    def fake_generator(*args, **kwargs):
        yield "Streaming token"
    mock_stream.side_effect = fake_generator

    req = RagQuestionRequest(question="Stream web test?", fallback_action="search_web")
    events = list(stream_grounded_answer(req, user_id="user-1"))
    
    citations_event = next((e for e in events if "event: citations" in e), None)
    assert citations_event is not None
    assert "web_tavily" in citations_event

    done_event = next((e for e in events if "event: done" in e), None)
    assert done_event is not None
    assert '"status": "success"' in done_event
