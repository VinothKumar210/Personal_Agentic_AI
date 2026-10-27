import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

_cross_encoder = None

def get_cross_encoder():
    global _cross_encoder
    if not settings.RERANKING_ENABLED:
        return None
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading CrossEncoder model: {settings.RERANKING_MODEL}")
            _cross_encoder = CrossEncoder(settings.RERANKING_MODEL)
        except Exception as e:
            logger.warning(f"Failed to load CrossEncoder ({settings.RERANKING_MODEL}): {e}. Fallback to unreranked results.")
            return None
    return _cross_encoder

def rerank_chunks(query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Reranks candidate chunks against the query using a Cross-Encoder.
    If reranking is disabled or fails, returns the top_k candidates as-is.
    """
    if not candidates:
        return []
        
    if len(candidates) <= 1 or not settings.RERANKING_ENABLED:
        return candidates[:top_k]

    model = get_cross_encoder()
    if model is None:
        return candidates[:top_k]

    try:
        pairs = [[query, c.get("text", "")] for c in candidates]
        scores = model.predict(pairs)
        
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)
            
        sorted_candidates = sorted(candidates, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return sorted_candidates[:top_k]
    except Exception as e:
        logger.warning(f"Error during cross-encoder prediction: {e}. Returning original ranking.")
        return candidates[:top_k]
