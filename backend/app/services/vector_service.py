import chromadb
from chromadb.config import Settings
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            if settings.CHROMA_API_KEY:
                _chroma_client = chromadb.CloudClient(
                    api_key=settings.CHROMA_API_KEY,
                    tenant=settings.CHROMA_TENANT,
                    database=settings.CHROMA_DATABASE,
                )
            else:
                _chroma_client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            raise
    return _chroma_client

def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

def get_diary_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="diary_events",
        metadata={"hnsw:space": "cosine"}
    )

def index_chunks(chunks_data: list[dict], embeddings: list[list[float]]):
    """
    chunks_data is a list of dicts with:
    - id: str
    - text: str
    - document_id: str
    - chunk_index: int
    - document_title: str
    - source_type: str
    - original_filename: Optional[str]
    - source_uri: Optional[str]
    - user_id: str
    """
    if not chunks_data or not embeddings:
        return

    collection = get_collection()
    
    ids = [c["id"] for c in chunks_data]
    documents = [c["text"] for c in chunks_data]
    
    metadatas = []
    for c in chunks_data:
        meta = {
            "chunk_id": c["id"],
            "document_id": c["document_id"],
            "chunk_index": c["chunk_index"],
            "document_title": c["document_title"],
            "source_type": c["source_type"],
            "user_id": c.get("user_id", "")
        }
        if c.get("original_filename"):
            meta["original_filename"] = c["original_filename"]
        if c.get("source_uri"):
            meta["source_uri"] = c["source_uri"]
        metadatas.append(meta)
        
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

def search_chunks(query_embedding: list[float], limit: int = 8, filters: dict = None) -> list[dict]:
    collection = get_collection()
    
    where = None
    if filters:
        conditions = []
        if "source_type" in filters and filters["source_type"]:
            conditions.append({"source_type": filters["source_type"]})
        if "document_id" in filters and filters["document_id"]:
            conditions.append({"document_id": filters["document_id"]})
        if "user_id" in filters and filters["user_id"]:
            conditions.append({"user_id": filters["user_id"]})
            
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}
            
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where,
        include=["metadatas", "documents", "distances"]
    )
    
    formatted_results = []
    if results and results.get("ids") and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
            sim = max(0.0, 1.0 - dist) if dist is not None else None
            formatted_results.append({
                "chunk_id": results["ids"][0][i],
                "document_id": meta["document_id"],
                "document_title": meta["document_title"],
                "source_type": meta["source_type"],
                "original_filename": meta.get("original_filename"),
                "source_uri": meta.get("source_uri"),
                "chunk_index": meta["chunk_index"],
                "text": results["documents"][0][i],
                "distance": dist,
                "score": sim
            })
            
    return formatted_results

def delete_chunks_by_ids(ids: list[str]):
    if not ids:
        return
    try:
        collection = get_collection()
        collection.delete(ids=ids)
    except Exception as e:
        logger.warning(f"Failed to delete chunk IDs from ChromaDB: {e}")
