from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.db.base import Base

class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    entry_date = Column(DateTime(timezone=True), nullable=False)
    raw_text = Column(Text, nullable=False)
    extraction_version = Column(String(50), default="v1")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    events = relationship("DiaryEvent", back_populates="entry", cascade="all, delete-orphan")


class DiaryEvent(Base):
    __tablename__ = "diary_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    diary_entry_id = Column(String(36), ForeignKey("diary_entries.id", ondelete="CASCADE"), nullable=False)
    
    event_date = Column(DateTime(timezone=True), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), default="personal")
    people_json = Column(JSON, default=list)
    location = Column(String(255), nullable=True)
    privacy_level = Column(String(50), default="private")
    sentiment = Column(String(50), default="neutral")
    source_span = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    entry = relationship("DiaryEntry", back_populates="events")
