from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class NoteCreate(BaseModel):
    note_text: str = Field(..., description="The annotation or note content")

    @field_validator('note_text')
    @classmethod
    def note_text_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Note text cannot be blank or whitespace-only')
        return v

class NoteRead(BaseModel):
    id: str
    user_id: str
    document_id: str
    chunk_id: str
    note_text: str
    created_at: datetime
    updated_at: datetime
