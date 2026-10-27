import json
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentChunk, utc_now
from app.services.chunking_service import chunk_text
from app.services.embedding_service import embed_texts
from app.services.vector_service import index_chunks

def create_chunks_for_document(db: Session, document: Document, text: str) -> list[DocumentChunk]:
    """
    Chunks the provided text and persists DocumentChunk objects to the database.
    Does not commit the transaction, allows caller to orchestrate.
    """
    if not text or not text.strip():
        raise ValueError("Extracted text is empty.")
        
    chunks = chunk_text(text)
    chunk_objects = []
    
    for i, chunk_str in enumerate(chunks):
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=i,
            text=chunk_str,
            character_count=len(chunk_str)
        )
        db.add(chunk)
        chunk_objects.append(chunk)
        
    return chunk_objects

def create_code_chunks_for_document(db: Session, document: Document, chunk_records: list[dict]) -> list[DocumentChunk]:
    """
    Creates DocumentChunk objects for structured code chunks (from GitHub repo or code files).
    Stores per-file metadata (file_path, sha, language) inside metadata_json.
    Computes unique chunk_index starting from max existing chunk_index + 1.
    """
    if not chunk_records:
        return []
        
    max_idx_row = db.query(DocumentChunk.chunk_index).filter(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index.desc()).first()
    start_idx = (max_idx_row[0] + 1) if max_idx_row and max_idx_row[0] is not None else 0
        
    chunk_objects = []
    for i, rec in enumerate(chunk_records):
        text = rec.get("text", "")
        if not text.strip():
            continue
            
        meta = {
            "file_path": rec.get("file_path", ""),
            "sha": rec.get("sha", ""),
            "language": rec.get("language", "generic")
        }
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=start_idx + i,
            text=text,
            character_count=len(text),
            metadata_json=json.dumps(meta)
        )
        db.add(chunk)
        chunk_objects.append(chunk)
        
    return chunk_objects

def index_document_chunks(db: Session, document_id: str, only_unindexed: bool = False) -> dict:
    """
    Embeds and indexes chunks for a document.
    If only_unindexed is True, embeds only chunks whose embedding_status != 'indexed'.
    Returns a dict with statistics.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return None
        
    query = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)
    if only_unindexed:
        query = query.filter(DocumentChunk.embedding_status != "indexed")
    chunks = query.all()
    
    if not chunks:
        total_indexed = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id, DocumentChunk.embedding_status == "indexed").count()
        return {"document_id": doc.id, "indexed_count": total_indexed, "failed_count": 0, "message": f"All {total_indexed} chunks up-to-date"}
        
    texts = [c.text for c in chunks]
    indexed_count = 0
    failed_count = 0
    
    try:
        embeddings = embed_texts(texts)
        chunks_data = []
        for c in chunks:
            original_file = doc.original_filename
            if c.metadata_json:
                try:
                    meta = json.loads(c.metadata_json)
                    if meta.get("file_path"):
                        original_file = meta["file_path"]
                except Exception:
                    pass
            chunks_data.append({
                "id": str(c.id),
                "text": c.text,
                "document_id": str(doc.id),
                "chunk_index": c.chunk_index,
                "document_title": doc.title,
                "source_type": doc.source_type,
                "original_filename": original_file,
                "source_uri": doc.source_uri,
                "user_id": doc.user_id
            })
            
        index_chunks(chunks_data, embeddings)
        
        for c in chunks:
            c.embedding_status = "indexed"
            c.embedding_error = None
            c.embedded_at = utc_now()
            indexed_count += 1
            
        db.commit()
        return {"document_id": doc.id, "indexed_count": indexed_count, "failed_count": failed_count, "message": f"Successfully indexed {indexed_count} chunks"}
    except Exception as e:
        for c in chunks:
            c.embedding_status = "failed"
            c.embedding_error = str(e)
            failed_count += 1
            
        db.commit()
        return {"document_id": doc.id, "indexed_count": 0, "failed_count": failed_count, "message": f"Failed to index chunks: {str(e)}"}
