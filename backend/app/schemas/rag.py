from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from uuid import UUID

class RagQuestionRequest(BaseModel):
    question: str
    limit: int = Field(default=6, ge=1, le=12)
    source_type: Optional[str] = None
    document_id: Optional[UUID] = None
    confidence_mode: str = Field(default="balanced", description="strict | balanced | permissive")
    fallback_action: Optional[str] = None
    research_mode: bool = Field(default=False, description="Enable autonomous multi-step research")
    max_iterations: int = Field(default=2, ge=1, le=3, description="Max self-correction iterations for research mode")
    include_sensitive_diary: bool = Field(default=False, description="Include sensitive diary events in search")

    @field_validator('question')
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Question cannot be blank or whitespace-only')
        return v

    @field_validator('confidence_mode')
    @classmethod
    def validate_confidence_mode(cls, v: str) -> str:
        allowed = {"strict", "balanced", "permissive"}
        if v not in allowed:
            raise ValueError(f"confidence_mode must be one of {allowed}")
        return v

class RagCitation(BaseModel):
    citation_id: int
    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_type: str
    original_filename: Optional[str] = None
    source_uri: Optional[str] = None
    chunk_index: int
    text_preview: str

class RagAnswerResponse(BaseModel):
    question: str
    answer: str
    citations: List[RagCitation]
    status: str = Field(default="answered", description="answered | insufficient_knowledge | needs_web_permission")
    confidence_mode: str = Field(default="balanced")
    best_similarity: Optional[float] = None
    fallback_options: List[str] = Field(default_factory=list)
    evidence_summary: Optional[str] = None
    research_steps: Optional[List[Dict[str, Any]]] = None
