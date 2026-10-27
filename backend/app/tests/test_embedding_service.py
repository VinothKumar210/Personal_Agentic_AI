import pytest
import sys
from unittest.mock import patch, MagicMock

# Inject a fake sentence_transformers module
mock_st_module = MagicMock()
sys.modules["sentence_transformers"] = mock_st_module

@pytest.fixture(autouse=True)
def reset_model():
    import app.services.embedding_service as embs
    embs._model = None
    yield
    embs._model = None

def test_embed_texts_empty():
    from app.services.embedding_service import embed_texts
    assert embed_texts([]) == []

def test_embed_query_empty():
    from app.services.embedding_service import embed_query
    assert embed_query("   ") == []

def test_embed_texts_calls_encode():
    import numpy as np
    from app.services.embedding_service import embed_texts
    
    mock_instance = MagicMock()
    mock_instance.encode.return_value = np.array([[0.1, 0.2]])
    mock_st_module.SentenceTransformer.return_value = mock_instance

    result = embed_texts(["hello", "world"])
    
    assert result == [[0.1, 0.2]]
    mock_instance.encode.assert_called_once_with(
        ["passage: hello", "passage: world"], 
        normalize_embeddings=True
    )

def test_embed_query_calls_encode():
    import numpy as np
    from app.services.embedding_service import embed_query
    
    mock_instance = MagicMock()
    mock_instance.encode.return_value = np.array([[0.5, 0.6]])
    mock_st_module.SentenceTransformer.return_value = mock_instance

    result = embed_query("hello")
    
    assert result == [0.5, 0.6]
    mock_instance.encode.assert_called_once_with(
        ["query: hello"], 
        normalize_embeddings=True
    )
