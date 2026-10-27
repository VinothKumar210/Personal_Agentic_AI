import pytest
from unittest.mock import patch, MagicMock
def test_ask_question_blank(client):
    response = client.post("/api/rag/answer", json={"question": "   "})
    assert response.status_code == 422

@patch("app.api.routes.rag.answer_question")
def test_ask_question_missing_groq_key(mock_answer, client):
    mock_answer.side_effect = RuntimeError("GROQ API Key is not configured")
    response = client.post("/api/rag/answer", json={"question": "What is life?"})
    assert response.status_code == 503
    assert "GROQ API Key" in response.json()["detail"]

@patch("app.services.rag_service.embed_query")
def test_ask_question_vector_failure(mock_embed, client):
    mock_embed.side_effect = Exception("Chroma down")
    response = client.post("/api/rag/answer", json={"question": "What is life?"})
    assert response.status_code == 503
    assert "Failed to generate query embedding: Chroma down" in response.json()["detail"]

@patch("app.services.rag_service.generate_grounded_answer")
@patch("app.services.rag_service.embed_query")
@patch("app.services.rag_service.search_chunks")
def test_ask_question_no_chunks(mock_search, mock_embed, mock_generate, client):
    mock_embed.return_value = [0.1, 0.2]
    mock_search.return_value = []
    
    response = client.post("/api/rag/answer", json={"question": "What is life?"})
    assert response.status_code == 200
    data = response.json()
    assert "does not contain enough information" in data["answer"]
    assert len(data["citations"]) == 0
    mock_generate.assert_not_called()

@patch("app.services.rag_service.is_groq_configured")
@patch("app.services.rag_service.embed_query")
@patch("app.services.rag_service.search_chunks")
@patch("app.services.rag_service.generate_grounded_answer")
def test_ask_question_success(mock_generate, mock_search, mock_embed, mock_is_groq, client):
    mock_is_groq.return_value = True
    mock_embed.return_value = [0.1, 0.2]
    mock_search.return_value = [
        {
            "chunk_id": "00000000-0000-0000-0000-000000000001",
            "document_id": "00000000-0000-0000-0000-000000000002",
            "document_title": "Test Doc",
            "source_type": "text",
            "original_filename": "test.txt",
            "source_uri": None,
            "chunk_index": 0,
            "text": "Life is beautiful."
        }
    ]
    mock_generate.return_value = "Life is beautiful [1]."
    
    response = client.post("/api/rag/answer", json={"question": "What is life?"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["question"] == "What is life?"
    assert data["answer"] == "Life is beautiful [1]."
    assert len(data["citations"]) == 1
    
    cit = data["citations"][0]
    assert cit["citation_id"] == 1
    assert cit["document_title"] == "Test Doc"
    assert cit["original_filename"] == "test.txt"
    assert cit["text_preview"] == "Life is beautiful."

@patch("app.services.groq_client.is_groq_configured", return_value=True)
@patch("app.services.groq_client.Groq")
def test_generate_grounded_answer_prompt(mock_groq_cls, mock_is_groq_configured):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a cited answer [1]."
    mock_client.chat.completions.create.return_value = mock_response
    mock_groq_cls.return_value = mock_client
    
    from app.services.groq_client import generate_grounded_answer
    contexts = [
        {
            "citation_id": 1,
            "document_title": "Doc 1",
            "source_type": "pdf",
            "filename_uri": "doc1.pdf",
            "chunk_index": 0,
            "text": "Context text here."
        }
    ]
    
    answer = generate_grounded_answer("Test question?", contexts)
    assert answer == "This is a cited answer [1]."
    
    mock_client.chat.completions.create.assert_called_once()
    args, kwargs = mock_client.chat.completions.create.call_args
    messages = kwargs["messages"]
    
    system_prompt = messages[0]["content"]
    assert "answer only using the provided context" in system_prompt.lower()
    assert "[1]" in system_prompt
    assert "Doc 1" in system_prompt
    assert "doc1.pdf" in system_prompt
    assert "Context text here." in system_prompt
    assert "say the knowledge base does not contain enough information" in system_prompt.lower()

def test_generate_grounded_answer_empty_contexts():
    from app.services.groq_client import generate_grounded_answer
    with pytest.raises(ValueError, match="No context chunks provided"):
        generate_grounded_answer("test?", [])
