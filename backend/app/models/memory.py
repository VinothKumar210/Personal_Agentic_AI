import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from app.db.base import Base

def utc_now():
    return datetime.now(timezone.utc)

class PersonalMemory(Base):
    __tablename__ = "personal_memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False, default="fact")  # fact, project, skill, preference
    content = Column(Text, nullable=False)
    privacy_level = Column(String, nullable=False, default="private")  # public, private, sensitive
    source_citation = Column(String, nullable=True)
    consolidated_into_id = Column(String, ForeignKey("personal_memories.id", ondelete="SET NULL"), nullable=True)
    is_consolidated = Column(Boolean, nullable=False, default=False)
    last_consolidated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
