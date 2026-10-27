from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID

class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=25)
    source_type: Optional[str] = None
    document_id: Optional[UUID] = None

    @field_validator('query')
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Query cannot be blank or whitespace-only')
        return v

class SearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_type: str
    original_filename: Optional[str] = None
    source_uri: Optional[str] = None
    chunk_index: int
    text: str
    score: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
