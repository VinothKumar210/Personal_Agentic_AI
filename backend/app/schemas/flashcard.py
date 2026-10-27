from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class FlashcardBase(BaseModel):
    front: str
    back: str

class FlashcardCreate(FlashcardBase):
    document_id: str

class FlashcardRead(FlashcardBase):
    id: str
    document_id: str
    status: str
    next_review_date: datetime
    ease_factor: float
    interval_days: int
    repetition_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FlashcardReviewRequest(BaseModel):
    score: int # 1=Again, 2=Hard, 3=Good, 4=Easy

class FlashcardGenerateRequest(BaseModel):
    document_id: str

class FlashcardGenerateResponse(BaseModel):
    drafts: List[FlashcardRead]
