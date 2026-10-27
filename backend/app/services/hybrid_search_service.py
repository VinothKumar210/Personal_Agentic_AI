import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.document import DocumentChunk, Document
from app.services.vector_service import search_chunks
from app.services.reranking_service import rerank_chunks
from app.core.config import settings

logger = logging.getLogger(__name__)

def sparse_keyword_search(query: str, db: Session, user_id: str, limit: int = 20, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Performs BM25 keyword search over text chunks belonging to user_id stored in PostgreSQL.
    """
    try:
        q = db.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id).filter(
            Document.user_id == user_id
        )
        if filters:
            if filters.get("source_type"):
                q = q.filter(Document.source_type == filters["source_type"])
            if filters.get("document_id"):
                q = q.filter(DocumentChunk.document_id == str(filters["document_id"]))
                
        # Limit to 2000 chunks for in-memory BM25 scoring speed
        rows = q.limit(2000).all()
        if not rows:
            return []
            
        query_tokens = [w.lower().strip(".,!?\"'()[]{}") for w in query.split() if len(w) > 1]
        if not query_tokens:
            return []
            
        corpus = []
        for chunk, _ in rows:
            tokens = [w.lower().strip(".,!?\"'()[]{}") for w in chunk.text.split() if len(w) > 1]
            corpus.append(tokens)
            
        scores = []
        try:
            from rank_bm25 import BM25Okapi
            bm25 = BM25Okapi(corpus)
            doc_scores = list(bm25.get_scores(query_tokens))
            if any(s > 0 for s in doc_scores):
                scores = doc_scores
            else:
                for tokens in corpus:
                    token_set = set(tokens)
                    score = sum(1 for qt in query_tokens if qt in token_set)
                    scores.append(float(score))
        except Exception as e:
            logger.debug(f"rank_bm25 fallback to basic overlap: {e}")
            for tokens in corpus:
                token_set = set(tokens)
                score = sum(1 for qt in query_tokens if qt in token_set)
                scores.append(float(score))
                
        scored_results = []
        for (chunk, doc), score in zip(rows, scores):
            if score > 0.0:
                scored_results.append({
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_title": doc.title,
                    "source_type": doc.source_type,
                    "original_filename": doc.original_filename,
                    "source_uri": doc.source_uri,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "sparse_score": float(score)
                })
                
        scored_results.sort(key=lambda x: x["sparse_score"], reverse=True)
        return scored_results[:limit]
    except Exception as e:
        logger.warning(f"Sparse keyword search error: {e}")
        return []

def hybrid_search_and_rerank(
    query: str,
    query_embedding: List[float],
    db: Optional[Session],
    user_id: str,
    limit: int = 5,
    filters: Optional[Dict[str, Any]] = None,
    dense_results: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Runs hybrid search combining dense vector search (ChromaDB) and sparse keyword search (BM25)
    using Reciprocal Rank Fusion (RRF), followed by Cross-Encoder reranking.
    """
    search_filters = {"user_id": user_id}
    if filters:
        if filters.get("source_type"):
            search_filters["source_type"] = filters["source_type"]
        if filters.get("document_id"):
            search_filters["document_id"] = str(filters["document_id"])

    # 1. Dense Search
    if dense_results is None:
        dense_results = []
        try:
            dense_results = search_chunks(query_embedding, limit=20, filters=search_filters)
        except Exception as e:
            logger.error(f"Dense vector search failed in hybrid search: {e}")

    # 2. Sparse Search
    sparse_results = []
    if db is not None:
        try:
            sparse_results = sparse_keyword_search(query, db, user_id, limit=20, filters=search_filters)
        except Exception as e:
            logger.error(f"Sparse search failed in hybrid search: {e}")

    if not dense_results and not sparse_results:
        return []
    if not sparse_results:
        candidate_pool = dense_results[:15]
        return rerank_chunks(query, candidate_pool, top_k=limit)
    if not dense_results:
        candidate_pool = sparse_results[:15]
        return rerank_chunks(query, candidate_pool, top_k=limit)

    # 3. Reciprocal Rank Fusion (RRF)
    k = getattr(settings, "RRF_K_PARAM", 60)
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict[str, Any]] = {}

    for rank, item in enumerate(dense_results):
        cid = item.get("chunk_id") or item.get("id") or str(rank)
        chunk_map[cid] = item
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for rank, item in enumerate(sparse_results):
        cid = item.get("chunk_id") or item.get("id") or f"sparse_{rank}"
        if cid not in chunk_map:
            chunk_map[cid] = item
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for cid in chunk_map:
        chunk_map[cid]["rrf_score"] = rrf_scores[cid]

    sorted_candidates = sorted(chunk_map.values(), key=lambda x: x.get("rrf_score", 0.0), reverse=True)
    candidate_pool = sorted_candidates[:15]

    # 4. Cross-Encoder Reranking
    return rerank_chunks(query, candidate_pool, top_k=limit)
