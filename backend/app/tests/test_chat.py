import pytest
import uuid
import json
from unittest.mock import patch, MagicMock
from app.models.chat import Conversation, ChatMessage

def test_create_conversation(client):
    response = client.post("/api/conversations", json={"title": "Test Chat"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Chat"
    assert "id" in data

def test_list_conversations(client, db):
    client.post("/api/conversations", json={"title": "Chat 1"})
    client.post("/api/conversations", json={"title": "Chat 2"})
    
    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

def test_delete_conversation_cascades(client, db):
    conv_res = client.post("/api/conversations", json={"title": "To Delete"}).json()
    conv_id = conv_res["id"]
    
    msg = ChatMessage(conversation_id=conv_id, role="user", content="hello")
    db.add(msg)
    db.commit()
    
    del_res = client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 204
    
    assert db.query(Conversation).filter_by(id=conv_id).first() is None
    assert db.query(ChatMessage).filter_by(conversation_id=conv_id).first() is None

def test_missing_conversation_404(client):
    response = client.get(f"/api/conversations/{uuid.uuid4()}")
    assert response.status_code == 404
    
    response = client.post(f"/api/conversations/{uuid.uuid4()}/messages", json={"content": "hello"})
    assert response.status_code == 404

def test_blank_chat_message_422(client):
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "   "})
    assert response.status_code == 422

@patch("app.services.chat_service.search_chunks")
@patch("app.services.chat_service.embed_query")
@patch("app.services.chat_service.generate_grounded_answer")
def test_send_message_no_chunks(mock_generate, mock_embed, mock_search, client, db):
    mock_search.return_value = []
    
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "what?"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["user_message"]["role"] == "user"
    assert data["user_message"]["citations"] == []
    
    assert data["assistant_message"]["role"] == "assistant"
    assert "not contain enough information" in data["assistant_message"]["content"]
    assert data["assistant_message"]["citations"] == []
    
    mock_generate.assert_not_called()
    
    # Title should be set
    conv = db.query(Conversation).filter_by(id=conv_id).first()
    assert conv.title == "what?"

@patch("app.services.chat_service.is_groq_configured", return_value=True)
@patch("app.services.chat_service.search_chunks")
@patch("app.services.chat_service.embed_query")
@patch("app.services.chat_service.generate_grounded_answer")
def test_send_message_success(mock_generate, mock_embed, mock_search, mock_groq, client, db):
    mock_search.return_value = [
        {
            "chunk_id": str(uuid.uuid4()), 
            "document_id": str(uuid.uuid4()), 
            "document_title": "Doc 1", 
            "source_type": "txt", 
            "original_filename": None, 
            "source_uri": None, 
            "chunk_index": 0, 
            "text": "content chunk"
        }
    ]
    mock_generate.return_value = "Here is the answer."
    
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "my question"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"]["content"] == "Here is the answer."
    assert len(data["assistant_message"]["citations"]) == 1
    assert data["assistant_message"]["citations"][0]["document_title"] == "Doc 1"
    
    # Assert generate_grounded_answer received ONLY retrieved chunks context and raw user message, not expanded query
    call_args = mock_generate.call_args[0]
    assert call_args[0] == "my question"
    assert len(call_args[1]) == 1
    
    ctx = call_args[1][0]
    assert ctx["citation_id"] == 1
    assert ctx["document_title"] == "Doc 1"
    assert ctx["source_type"] == "txt"
    assert ctx["filename_uri"] == "unknown"
    assert ctx["chunk_index"] == 0
    assert ctx["text"] == "content chunk"

@patch("app.services.chat_service.is_groq_configured", return_value=False)
@patch("app.services.chat_service.search_chunks")
@patch("app.services.chat_service.embed_query")
def test_missing_groq_key_503(mock_embed, mock_search, mock_groq, client, db):
    mock_search.return_value = [{
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "document_title": "test",
        "source_type": "txt",
        "chunk_index": 0,
        "text": "text"
    }]
    
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "test"})
    assert response.status_code == 503
    
    # User message saved, but assistant message not saved
    messages = db.query(ChatMessage).filter_by(conversation_id=conv_id).all()
    assert len(messages) == 1
    assert messages[0].role == "user"

@patch("app.services.chat_service.search_chunks", side_effect=Exception("Chroma error"))
@patch("app.services.chat_service.embed_query")
def test_vector_failure_503(mock_embed, mock_search, client, db):
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "test"})
    assert response.status_code == 503
    
    messages = db.query(ChatMessage).filter_by(conversation_id=conv_id).all()
    assert len(messages) == 1

def test_invalid_citations_json_returns_empty(client, db):
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    msg = ChatMessage(conversation_id=conv_id, role="assistant", content="test", citations_json="invalid json")
    db.add(msg)
    db.commit()
    
    response = client.get(f"/api/conversations/{conv_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["citations"] == []

@patch("app.services.chat_service.is_groq_configured", return_value=True)
@patch("app.services.chat_service.search_chunks")
@patch("app.services.chat_service.embed_query")
@patch("app.services.chat_service.generate_grounded_answer")
def test_contextual_query_includes_recent_messages(mock_generate, mock_embed, mock_search, mock_groq, client, db):
    mock_search.return_value = [{
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "document_title": "test",
        "source_type": "txt",
        "chunk_index": 0,
        "text": "retrieved context chunk",
        "original_filename": "test.txt",
        "source_uri": None
    }]
    mock_generate.return_value = "Answer."
    
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    # Seed history
    db.add_all([
        ChatMessage(conversation_id=conv_id, role="user", content="msg 1"),
        ChatMessage(conversation_id=conv_id, role="assistant", content="ans 1", citations_json="[]"),
    ])
    db.commit()
    
    client.post(f"/api/conversations/{conv_id}/messages", json={"content": "latest"})
    
    call_args = mock_embed.call_args[0]
    query_str = call_args[0]
    assert "msg 1" in query_str
    assert "ans 1" in query_str
    assert "latest" in query_str
    
    # Assert generate_grounded_answer args
    generate_args = mock_generate.call_args[0]
    assert generate_args[0] == "latest"  # Raw message only
    assert len(generate_args[1]) == 1    # Only retrieved chunks
    assert generate_args[1][0]["text"] == "retrieved context chunk"
    
    # Ensure history did not leak into Groq contexts
    for ctx in generate_args[1]:
        assert "msg 1" not in ctx["text"]
        assert "ans 1" not in ctx["text"]

@patch("app.services.chat_service.is_groq_configured", return_value=True)
@patch("app.services.groq_client.is_groq_configured", return_value=True)
@patch("app.services.groq_client.Groq")
@patch("app.services.chat_service.search_chunks")
@patch("app.services.chat_service.embed_query")
def test_chat_groq_context_compatibility(mock_embed, mock_search, mock_groq_class, mock_groq_config1, mock_groq_config2, client, db):
    # This test hits the whole route, allowing `chat_service` to build the context and pass it to `groq_client.generate_grounded_answer`
    # We patch `Groq` class to intercept the call to the real API and ensure formatting works without throwing KeyError.
    
    mock_search.return_value = [{
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "document_title": "Real Test Doc",
        "source_type": "txt",
        "original_filename": "hello.txt",
        "source_uri": None,
        "chunk_index": 0,
        "text": "context test chunk"
    }]
    
    mock_instance = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Fake generated answer"
    mock_instance.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    mock_groq_class.return_value = mock_instance
    
    conv_id = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(f"/api/conversations/{conv_id}/messages", json={"content": "does it format?"})
    
    assert response.status_code == 200
    
    # Ensure Groq was called, which proves generate_grounded_answer succeeded formatting
    mock_instance.chat.completions.create.assert_called_once()
    create_kwargs = mock_instance.chat.completions.create.call_args[1]
    
    messages = create_kwargs["messages"]
    system_prompt = messages[0]["content"]
    assert "Real Test Doc" in system_prompt
    assert "hello.txt" in system_prompt
    assert "context test chunk" in system_prompt
