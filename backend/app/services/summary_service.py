from sqlalchemy.orm import Session
from app.models.document import Document, Collection, DocumentChunk
from app.schemas.summary import DocumentSummaryRequest, CollectionSummaryRequest, SummaryResponse
from app.services.groq_client import generate_document_summary, generate_collection_summary

def summarize_document(document_id: str, request: DocumentSummaryRequest, db: Session, user_id: str) -> SummaryResponse:
    # Fetch document
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise ValueError(f"Document not found: {document_id}")
        
    # Fetch chunks
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).limit(request.max_chunks).all()
    
    if not chunks:
        raise ValueError("Document has no chunks to summarize")

    chunk_dicts = [{"text": c.text} for c in chunks]

    # Call Groq
    try:
        summary_text = generate_document_summary(doc.title, chunk_dicts)
    except Exception as e:
        raise RuntimeError(f"Failed to generate summary: {str(e)}")

    # Save to DB
    doc.summary = summary_text
    db.commit()

    return SummaryResponse(
        target_type="document",
        target_id=doc.id,
        title=doc.title,
        summary=summary_text,
        chunks_used=len(chunks),
        documents_used=1,
        message="Document summary generated successfully."
    )


def summarize_collection(collection_id: str, request: CollectionSummaryRequest, db: Session, user_id: str) -> SummaryResponse:
    # Fetch collection
    collection = db.query(Collection).filter(Collection.id == collection_id, Collection.user_id == user_id).first()
    if not collection:
        raise ValueError(f"Collection not found: {collection_id}")

    docs = collection.documents[:request.max_documents]
    if not docs:
        raise ValueError("Collection has no associated documents to summarize")

    document_contexts = []
    total_chunks_used = 0

    for doc in docs:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index).limit(request.max_chunks_per_document).all()
        if chunks:
            document_contexts.append({
                "title": doc.title,
                "chunks": [c.text for c in chunks]
            })
            total_chunks_used += len(chunks)

    if not document_contexts:
        raise ValueError("Associated documents have no chunks to summarize")

    # Call Groq
    try:
        summary_text = generate_collection_summary(collection.name, document_contexts)
    except Exception as e:
        raise RuntimeError(f"Failed to generate summary: {str(e)}")

    # Save to DB
    collection.summary = summary_text
    db.commit()

    return SummaryResponse(
        target_type="collection",
        target_id=collection.id,
        title=collection.name,
        summary=summary_text,
        chunks_used=total_chunks_used,
        documents_used=len(document_contexts),
        message="Collection summary generated successfully."
    )
