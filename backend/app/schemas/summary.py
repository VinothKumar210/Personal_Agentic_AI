from pydantic import BaseModel, Field
from typing import Literal
from uuid import UUID

class DocumentSummaryRequest(BaseModel):
    max_chunks: int = Field(default=20, ge=1, le=50)

class CollectionSummaryRequest(BaseModel):
    max_documents: int = Field(default=20, ge=1, le=50)
    max_chunks_per_document: int = Field(default=10, ge=1, le=30)

class SummaryResponse(BaseModel):
    target_type: Literal["document", "collection"]
    target_id: UUID
    title: str
    summary: str
    chunks_used: int
    documents_used: int
    message: str
