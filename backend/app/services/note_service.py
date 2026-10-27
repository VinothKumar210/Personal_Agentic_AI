from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.document import Document, DocumentChunk, ChunkNote
from fastapi import HTTPException

def create_chunk_note(
    db: Session,
    user_id: str,
    document_id: str,
    chunk_id: str,
    note_text: str
) -> ChunkNote:
    # Verify chunk exists and belongs to user
    chunk = (
        db.query(DocumentChunk)
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(DocumentChunk.id == chunk_id, Document.user_id == user_id, DocumentChunk.document_id == document_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Document chunk not found or access denied")
        
    note = ChunkNote(
        user_id=user_id,
        document_id=document_id,
        chunk_id=chunk_id,
        note_text=note_text.strip()
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

def list_document_notes(
    db: Session,
    user_id: str,
    document_id: str
) -> List[ChunkNote]:
    return (
        db.query(ChunkNote)
        .filter(ChunkNote.document_id == document_id, ChunkNote.user_id == user_id)
        .order_by(ChunkNote.created_at.desc())
        .all()
    )

def delete_chunk_note(
    db: Session,
    user_id: str,
    note_id: str
) -> bool:
    note = db.query(ChunkNote).filter(ChunkNote.id == note_id, ChunkNote.user_id == user_id).first()
    if not note:
        return False
    db.delete(note)
    db.commit()
    return True
