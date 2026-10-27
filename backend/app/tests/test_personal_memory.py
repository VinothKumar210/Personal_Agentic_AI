import pytest
from unittest.mock import patch, MagicMock
from app.models.memory import PersonalMemory
from app.services import memory_service, rag_service
from app.schemas.rag import RagQuestionRequest

@patch("app.services.memory_service.index_chunks")
@patch("app.services.memory_service.embed_texts")
def test_memory_crud_endpoints(mock_embed, mock_index, client, db):
    mock_embed.return_value = [[0.1] * 384]
    
    # 1. Create memory
    create_payload = {
        "category": "preference",
        "content": "I always prefer Python 3.13 for backend tasks.",
        "privacy_level": "private",
        "source_citation": "User preferences survey"
    }
    response = client.post("/api/memory", json=create_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["category"] == "preference"
    assert data["content"] == "I always prefer Python 3.13 for backend tasks."
    assert data["privacy_level"] == "private"
    memory_id = data["id"]
    
    mock_index.assert_called_once()
    
    # 2. List memories
    list_resp = client.get("/api/memory?category=preference")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) == 1
    assert list_data[0]["id"] == memory_id
    
    # 3. Update memory via PATCH and PUT
    patch_payload = {"content": "I prefer Python 3.14 now."}
    patch_resp = client.patch(f"/api/memory/{memory_id}", json=patch_payload)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["content"] == "I prefer Python 3.14 now."

    put_payload = {"content": "I prefer Python 3.15 now (PUT test)."}
    put_resp = client.put(f"/api/memory/{memory_id}", json=put_payload)
    assert put_resp.status_code == 200
    assert put_resp.json()["content"] == "I prefer Python 3.15 now (PUT test)."
    
    # 4. Delete memory
    with patch("app.services.memory_service.delete_chunks_by_ids") as mock_del:
        del_resp = client.delete(f"/api/memory/{memory_id}")
        assert del_resp.status_code == 204
        mock_del.assert_called_once_with([memory_id])
        
    list_after = client.get("/api/memory")
    assert len(list_after.json()) == 0

@patch("app.services.memory_service.delete_chunks_by_ids")
@patch("app.services.memory_service.index_chunks")
@patch("app.services.memory_service.embed_texts")
def test_sensitive_memory_never_indexed(mock_embed, mock_index, mock_delete, client):
    payload = {
        "category": "fact",
        "content": "My secret password is 123456",
        "privacy_level": "sensitive"
    }
    resp = client.post("/api/memory", json=payload)
    assert resp.status_code == 201
    assert resp.json()["privacy_level"] == "sensitive"
    
    # Verify index_chunks was NEVER called for sensitive item
    mock_embed.assert_not_called()
    mock_index.assert_not_called()
    # Verify delete_chunks_by_ids was called to ensure cleanliness
    mock_delete.assert_called_once()

def test_search_personal_memories_privacy_gating(db, test_user):
    # Insert one public, one private (belonging to test_user), and one sensitive memory
    mem_pub = PersonalMemory(user_id=test_user.id, category="fact", content="Public fact", privacy_level="public")
    mem_priv = PersonalMemory(user_id=test_user.id, category="preference", content="Private preference", privacy_level="private")
    mem_sens = PersonalMemory(user_id=test_user.id, category="fact", content="Sensitive secret", privacy_level="sensitive")
    db.add_all([mem_pub, mem_priv, mem_sens])
    db.commit()
    
    with patch("app.services.memory_service.embed_query") as mock_eq, \
         patch("app.services.memory_service.search_chunks") as mock_sc:
        mock_eq.return_value = [0.1] * 384
        # Mock vector store returning all three chunks
        mock_sc.return_value = [
            {"chunk_id": mem_pub.id, "text": "Public fact", "source_type": "personal_memory", "score": 0.9},
            {"chunk_id": mem_priv.id, "text": "Private preference", "source_type": "personal_memory", "score": 0.8},
            {"chunk_id": mem_sens.id, "text": "Sensitive secret", "source_type": "personal_memory", "score": 0.95}
        ]
        
        results = memory_service.search_personal_memories(db, user_id=test_user.id, query="test")
        # Verify sensitive memory is excluded from results
        returned_ids = [r["chunk_id"] for r in results]
        assert mem_pub.id in returned_ids
        assert mem_priv.id in returned_ids
        assert mem_sens.id not in returned_ids

def test_rag_service_excludes_sensitive_memory(db, test_user):
    mem_sens = PersonalMemory(user_id=test_user.id, category="fact", content="Sensitive RAG leak test", privacy_level="sensitive")
    db.add(mem_sens)
    db.commit()
    
    req = RagQuestionRequest(question="What is the secret?")
    
    with patch("app.services.rag_service.embed_query") as mock_eq, \
         patch("app.services.rag_service.search_chunks") as mock_sc:
        mock_eq.return_value = [0.1] * 384
        mock_sc.return_value = [
            {"chunk_id": mem_sens.id, "text": "Sensitive RAG leak test", "source_type": "personal_memory", "score": 0.9, "chunk_index": 0, "document_id": mem_sens.id, "document_title": "Memory"}
        ]
        
        # answer_question will evaluate confidence after gating results
        response = rag_service.answer_question(req, user_id=test_user.id, db=db)
        # Because sensitive memory was excluded, results became empty -> insufficient_knowledge
        assert response.status == "insufficient_knowledge"
        assert len(response.citations) == 0

def test_chat_service_excludes_sensitive_and_foreign_memory(db, test_user):
    from app.services import chat_service
    from app.models.chat import Conversation
    from app.models.user import User
    
    other_user = User(email="other@test.com", hashed_password="pw")
    db.add(other_user)
    db.commit()

    mem_sens = PersonalMemory(user_id=test_user.id, category="fact", content="Chat leak sensitive", privacy_level="sensitive")
    mem_foreign = PersonalMemory(user_id=other_user.id, category="preference", content="Foreign private pref", privacy_level="private")
    db.add_all([mem_sens, mem_foreign])
    db.commit()

    conv = Conversation(user_id=test_user.id, title="Test Conv")
    db.add(conv)
    db.commit()

    from app.schemas.chat import ChatMessageCreate
    req = ChatMessageCreate(content="What is the secret or pref?")

    with patch("app.services.chat_service.embed_query") as mock_eq, \
         patch("app.services.chat_service.search_chunks") as mock_sc, \
         patch("app.services.chat_service.is_groq_configured") as mock_groq:
        mock_eq.return_value = [0.1] * 384
        mock_sc.return_value = [
            {"chunk_id": mem_sens.id, "text": "Chat leak sensitive", "source_type": "personal_memory", "score": 0.9, "chunk_index": 0, "document_id": mem_sens.id, "document_title": "Memory"},
            {"chunk_id": mem_foreign.id, "text": "Foreign private pref", "source_type": "personal_memory", "score": 0.85, "chunk_index": 0, "document_id": mem_foreign.id, "document_title": "Memory"}
        ]
        mock_groq.return_value = True

        # Because both chunks are excluded by gate_personal_memory_chunks, confidence check fails and returns insufficient info
        c, u_msg, a_msg = chat_service.add_user_message_and_answer(conv.id, req, db, test_user.id)
        assert "does not contain enough information" in a_msg.content or "none contained strong evidence" in a_msg.content
        assert a_msg.citations == []

def test_vector_service_public_memory_filter():
    from app.services import vector_service
    with patch("app.services.vector_service.get_collection") as mock_get_coll:
        mock_coll = MagicMock()
        mock_get_coll.return_value = mock_coll
        mock_coll.query.return_value = {"ids": [[]], "metadatas": [[]], "documents": [[]], "distances": [[]]}

        vector_service.search_chunks([0.1]*384, limit=5, filters={"user_id": "user_123"})
        call_kwargs = mock_coll.query.call_args[1]
        where_clause = call_kwargs["where"]
        assert where_clause == {"user_id": "user_123"}

def test_github_repo_delta_sync_reuse(client, db, test_user):
    from app.models.document import Document
    doc = Document(
        title="owner/repo",
        source_type="github_repo",
        source_uri="https://github.com/owner/repo",
        user_id=test_user.id,
        status="ready"
    )
    db.add(doc)
    db.commit()

    with patch("app.services.job_runner.run_ingestion_job"):
        # Calling post /api/sources/github-repo with exact same URI should reuse doc
        resp = client.post("/api/sources/github-repo", json={"repo_url": "https://github.com/owner/repo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document"]["id"] == doc.id
        assert "delta-sync" in data["message"]

        # Calling sync endpoint should also work
        sync_resp = client.post(f"/api/sources/github-repo/{doc.id}/sync")
        assert sync_resp.status_code == 200
        assert "delta-sync job queued" in sync_resp.json()["message"]
