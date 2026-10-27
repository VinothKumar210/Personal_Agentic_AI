import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    status = Column(String, default="draft", nullable=False) # draft, active, suspended
    
    # SM-2 fields
    next_review_date = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    ease_factor = Column(Float, default=2.5, nullable=False)
    interval_days = Column(Integer, default=0, nullable=False)
    repetition_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User")
    document = relationship("Document")

class FlashcardReview(Base):
    __tablename__ = "flashcard_reviews"

    id = Column(String, primary_key=True, default=generate_uuid)
    flashcard_id = Column(String, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    score = Column(Integer, nullable=False) # 1=Again, 2=Hard, 3=Good, 4=Easy
    reviewed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    flashcard = relationship("Flashcard")
