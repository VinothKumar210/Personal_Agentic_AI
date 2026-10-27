from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

SourceType = Literal[
    "pdf",
    "docx",
    "markdown",
    "text",
    "webpage",
    "github_repo",
    "ai_chat",
    "image_ocr",
    "scanned_pdf",
    "web_search_saved",
    "web_clip",
    "deep_research",
    "unknown",
]
DocumentStatus = Literal["pending", "processing", "ready", "failed"]
JobStatus = Literal["queued", "running", "processing", "succeeded", "failed"]

class IngestionJobRead(BaseModel):
    id: UUID
    document_id: Optional[UUID] = None
    job_type: str
    status: JobStatus
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CollectionRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TagRead(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TagCreate(BaseModel):
    name: str

class DocumentBase(BaseModel):
    title: str
    source_type: SourceType
    source_uri: Optional[str] = None
    original_filename: Optional[str] = None
    content_hash: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[DocumentStatus] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None

class DocumentRead(DocumentBase):
    id: UUID
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    collections: List[CollectionRead] = []
    tags: List[TagRead] = []

    model_config = ConfigDict(from_attributes=True)

class DocumentListResponse(BaseModel):
    items: List[DocumentRead]
    total: int

class DocumentChunkRead(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    token_count: Optional[int] = None
    character_count: int
    metadata_json: Optional[str] = None
    embedding_status: str
    embedding_error: Optional[str] = None
    embedded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentChunkListResponse(BaseModel):
    items: List[DocumentChunkRead]
    total: int

class FileUploadResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead
    chunks_created: int
    message: str

class DocumentIndexResponse(BaseModel):
    document_id: UUID
    indexed_count: int
    failed_count: int
    message: str
