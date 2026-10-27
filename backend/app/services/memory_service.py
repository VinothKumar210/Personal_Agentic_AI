import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.memory import PersonalMemory
from app.schemas.memory import PersonalMemoryCreate, PersonalMemoryUpdate
from app.services.vector_service import index_chunks, delete_chunks_by_ids, search_chunks
from app.services.embedding_service import embed_texts, embed_query

logger = logging.getLogger(__name__)

def index_memory_item(memory: PersonalMemory):
    """
    Indexes a PersonalMemory item into Chroma vector store unless privacy_level == 'sensitive'.
    If sensitive, ensures any existing chunk is deleted from the vector store.
    """
    if memory.privacy_level == "sensitive":
        delete_chunks_by_ids([memory.id])
        return

    try:
        embeddings = embed_texts([memory.content])
        chunk_data = [{
            "id": memory.id,
            "text": memory.content,
            "document_id": memory.id,
            "chunk_index": 0,
            "document_title": f"Personal Memory ({memory.category})",
            "source_type": "personal_memory",
            "original_filename": memory.privacy_level,
            "source_uri": memory.source_citation,
            "user_id": memory.user_id
        }]
        index_chunks(chunk_data, embeddings)
    except Exception as e:
        logger.error(f"Failed to index memory item {memory.id}: {e}")

def create_memory(db: Session, user_id: str, memory_in: PersonalMemoryCreate) -> PersonalMemory:
    memory = PersonalMemory(
        user_id=user_id,
        category=memory_in.category,
        content=memory_in.content,
        privacy_level=memory_in.privacy_level,
        source_citation=memory_in.source_citation
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    index_memory_item(memory)
    return memory

def get_memories(db: Session, user_id: str, category: Optional[str] = None, privacy_level: Optional[str] = None) -> List[PersonalMemory]:
    query = db.query(PersonalMemory).filter(PersonalMemory.user_id == user_id)
    if category:
        query = query.filter(PersonalMemory.category == category)
    if privacy_level:
        query = query.filter(PersonalMemory.privacy_level == privacy_level)
    return query.order_by(PersonalMemory.created_at.desc()).all()

def update_memory(db: Session, user_id: str, memory_id: str, memory_in: PersonalMemoryUpdate) -> Optional[PersonalMemory]:
    memory = db.query(PersonalMemory).filter(PersonalMemory.id == memory_id, PersonalMemory.user_id == user_id).first()
    if not memory:
        return None
    update_data = memory_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(memory, field, val)
    db.commit()
    db.refresh(memory)
    index_memory_item(memory)
    return memory

def delete_memory(db: Session, user_id: str, memory_id: str) -> bool:
    memory = db.query(PersonalMemory).filter(PersonalMemory.id == memory_id, PersonalMemory.user_id == user_id).first()
    if not memory:
        return False
    db.delete(memory)
    db.commit()
    delete_chunks_by_ids([memory_id])
    return True

def search_personal_memories(db: Session, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Searches vector store for relevant personal memories.
    Enforces strict privacy rules:
    - Excludes any 'sensitive' memories.
    - Excludes 'private' memories not belonging to user_id.
    - Includes 'public' memories or 'private' memories belonging to user_id.
    """
    query_emb = embed_query(query)
    if not query_emb:
        return []
        
    raw_results = search_chunks(query_emb, limit=limit * 2, filters={"source_type": "personal_memory"})
    if not raw_results:
        return []
        
    memory_ids = [r["chunk_id"] for r in raw_results]
    db_memories = {m.id: m for m in db.query(PersonalMemory).filter(PersonalMemory.id.in_(memory_ids)).all()}
    
    filtered = []
    for r in raw_results:
        mem = db_memories.get(r["chunk_id"])
        if not mem or mem.privacy_level == "sensitive":
            continue
        if mem.privacy_level == "private" and mem.user_id != user_id:
            continue
            
        r["category"] = mem.category
        r["privacy_level"] = mem.privacy_level
        r["source_citation"] = mem.source_citation
        filtered.append(r)
        if len(filtered) >= limit:
            break
            
    return filtered

def gate_personal_memory_chunks(db: Optional[Session], chunks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """
    Filters retrieved chunks to strictly enforce personal memory privacy rules across all RAG/chat endpoints:
    - Excludes 'sensitive' memories.
    - Excludes 'private' memories belonging to another user.
    - Allows 'public' memories or 'private' memories matching user_id.
    """
    if db is None or not chunks:
        return chunks
        
    mem_ids = [r["chunk_id"] for r in chunks if r.get("source_type") == "personal_memory"]
    if not mem_ids:
        return chunks
        
    mem_map = {m.id: m for m in db.query(PersonalMemory).filter(PersonalMemory.id.in_(mem_ids)).all()}
    gated_results = []
    for r in chunks:
        if r.get("source_type") == "personal_memory":
            mem = mem_map.get(r["chunk_id"])
            if not mem or mem.privacy_level == "sensitive":
                continue
            if mem.privacy_level == "private" and mem.user_id != user_id:
                continue
            r["document_title"] = f"Personal Memory ({mem.category})"
        gated_results.append(r)
    return gated_results
