import json
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID
from datetime import datetime
from app.schemas.rag import RagCitation

class ConversationCreate(BaseModel):
    title: Optional[str] = None

class ConversationRead(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    items: List[ConversationRead]
    total: int

class ChatMessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    citations: List[RagCitation] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageCreate(BaseModel):
    content: str
    limit: int = Field(default=6, ge=1, le=12)
    source_type: Optional[str] = None
    document_id: Optional[UUID] = None
    confidence_mode: str = Field(default="balanced")
    fallback_action: Optional[str] = None
    research_mode: bool = Field(default=False)
    max_iterations: int = Field(default=2, ge=1, le=3)

    @field_validator('content')
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Content cannot be blank')
        return v

class ChatAnswerResponse(BaseModel):
    conversation: ConversationRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
