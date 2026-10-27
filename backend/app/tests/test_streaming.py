import pytest
import json
from unittest.mock import patch, MagicMock
from app.models.chat import Conversation, ChatMessage

@patch("app.services.rag_service.search_chunks", return_value=[])
@patch("app.services.rag_service.embed_query", return_value=[0.1, 0.2])
@patch("app.services.rag_service.is_groq_configured", return_value=True)
def test_rag_stream_no_chunks(mock_groq, mock_embed, mock_search, client):
    response = client.post("/api/rag/stream", json={"question": "What is secret?"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    body = response.text
    assert "event: citations" in body
    assert "event: token" in body
    assert "does not contain enough information" in body
    assert "event: done" in body

@patch("app.services.rag_service.search_chunks", return_value=[])
@patch("app.services.rag_service.is_groq_configured", return_value=True)
@patch("app.services.rag_service.embed_query", return_value=[0.1, 0.2])
@patch("app.services.hybrid_search_service.hybrid_search_and_rerank")
@patch("app.services.groq_client.stream_grounded_answer_tokens")
def test_rag_stream_success(mock_stream_tokens, mock_hybrid_search, mock_embed, mock_groq, mock_search, client):
    mock_hybrid_search.return_value = [
        {
            "chunk_id": "00000000-0000-0000-0000-000000000001",
            "document_id": "00000000-0000-0000-0000-000000000002",
            "document_title": "Test Doc",
            "source_type": "text",
            "original_filename": "test.txt",
            "source_uri": None,
            "chunk_index": 0,
            "text": "Streaming RAG works."
        }
    ]
    mock_stream_tokens.return_value = ["Streaming ", "RAG ", "works."]
    
    response = client.post("/api/rag/stream", json={"question": "How does it work?"})
    assert response.status_code == 200
    body = response.text
    
    assert "event: citations" in body
    assert "Test Doc" in body
    assert "event: token" in body
    assert "Streaming " in body
    assert "RAG " in body
    assert "works." in body
    assert "event: done" in body

@patch("app.services.chat_service.search_chunks", return_value=[])
@patch("app.services.chat_service.is_groq_configured", return_value=True)
@patch("app.services.chat_service.embed_query", return_value=[0.1, 0.2])
@patch("app.services.hybrid_search_service.hybrid_search_and_rerank")
@patch("app.services.groq_client.stream_grounded_answer_tokens")
def test_chat_stream_success(mock_stream_tokens, mock_hybrid_search, mock_embed, mock_groq, mock_search, client, test_user, db):
    conv = Conversation(title="Stream Test", user_id=test_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    
    mock_hybrid_search.return_value = [
        {
            "chunk_id": "00000000-0000-0000-0000-000000000001",
            "document_id": "00000000-0000-0000-0000-000000000002",
            "document_title": "Chat Doc",
            "source_type": "text",
            "original_filename": "chat.txt",
            "source_uri": None,
            "chunk_index": 0,
            "text": "Chat streaming text."
        }
    ]
    mock_stream_tokens.return_value = ["Hello ", "from ", "stream!"]
    
    response = client.post(
        f"/api/conversations/{conv.id}/messages/stream",
        json={"content": "Stream message test"}
    )
    assert response.status_code == 200
    body = response.text
    
    assert "event: citations" in body
    assert "Chat Doc" in body
    assert "event: token" in body
    assert "Hello " in body
    assert "event: done" in body
    
    # Verify messages saved to database
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).order_by(ChatMessage.created_at).all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Stream message test"
    assert messages[1].role == "assistant"
    assert messages[1].content == "Hello from stream!"
    assert "Chat Doc" in messages[1].citations_json
