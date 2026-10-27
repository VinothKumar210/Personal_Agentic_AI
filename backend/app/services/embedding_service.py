import logging
import threading
from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()

def get_embedding_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info(f"Loading embedding model {settings.EMBEDDING_MODEL_NAME} on device {settings.EMBEDDING_DEVICE}")
                try:
                    from sentence_transformers import SentenceTransformer
                    _temp_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                    if settings.EMBEDDING_DEVICE != "cpu":
                        _temp_model.to(settings.EMBEDDING_DEVICE)
                    _model = _temp_model
                except Exception as e:
                    logger.error(f"Failed to load embedding model: {e}")
                    raise RuntimeError(f"Embedding model initialization failed: {e}")
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    # BGE prefix for passages
    prefixed_texts = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed_texts, normalize_embeddings=True)
    return embeddings.tolist()

def embed_query(query: str) -> list[float]:
    if not query.strip():
        return []
    model = get_embedding_model()
    # BGE prefix for queries
    prefixed_query = f"query: {query}"
    embeddings = model.encode([prefixed_query], normalize_embeddings=True)
    return embeddings[0].tolist()
