from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class DiaryEventBase(BaseModel):
    event_date: datetime
    title: str
    description: Optional[str] = None
    category: str = "personal"
    people_json: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    privacy_level: str = "private"
    sentiment: str = "neutral"
    source_span: Optional[str] = None
    confidence_score: float = 1.0

class DiaryEventRead(DiaryEventBase):
    id: str
    user_id: str
    diary_entry_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DiaryEntryCreate(BaseModel):
    entry_date: datetime
    raw_text: str

class DiaryEntryRead(BaseModel):
    id: str
    user_id: str
    entry_date: datetime
    raw_text: str
    extraction_version: str
    created_at: datetime
    updated_at: datetime
    events: List[DiaryEventRead] = Field(default_factory=list)

    class Config:
        from_attributes = True

class DiarySearchRequest(BaseModel):
    query: str
    limit: int = 10
