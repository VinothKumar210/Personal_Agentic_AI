import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean
from app.db.base import Base

def utc_now():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

class CurationSuggestion(Base):
    __tablename__ = "curation_suggestions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_type = Column(String, nullable=False)  # memory_merge, memory_contradiction, graph_bridge, graph_prune
    source_ids_json = Column(Text, nullable=False, default="[]")
    proposed_payload_json = Column(Text, nullable=False, default="{}")
    confidence = Column(Float, nullable=False, default=1.0)
    explanation = Column(Text, nullable=True)
    provenance_metadata_json = Column(Text, nullable=False, default="{}")
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected, applied, rolled_back
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def source_ids(self) -> list:
        try:
            return json.loads(self.source_ids_json or "[]")
        except Exception:
            return []

    @property
    def proposed_payload(self) -> dict:
        try:
            return json.loads(self.proposed_payload_json or "{}")
        except Exception:
            return {}

    @property
    def provenance_metadata(self) -> dict:
        try:
            return json.loads(self.provenance_metadata_json or "{}")
        except Exception:
            return {}


class CurationLog(Base):
    __tablename__ = "curation_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sweep_type = Column(String, nullable=False, default="dry_run")
    items_processed = Column(Integer, nullable=False, default=0)
    items_merged = Column(Integer, nullable=False, default=0)
    details_json = Column(Text, nullable=True, default="{}")
    status = Column(String, nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except Exception:
            return {}


class KnowledgeBriefing(Base):
    __tablename__ = "knowledge_briefings"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    summary_markdown = Column(Text, nullable=False)
    highlights_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    @property
    def highlights(self) -> list:
        try:
            return json.loads(self.highlights_json or "[]")
        except Exception:
            return []
