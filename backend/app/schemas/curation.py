from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CurationSuggestionCreate(BaseModel):
    suggestion_type: str  # memory_merge, memory_contradiction, graph_bridge, graph_prune
    source_ids: List[str]
    proposed_payload: Dict[str, Any]
    confidence: float = 1.0
    explanation: Optional[str] = None
    provenance_metadata: Dict[str, Any] = {}

class CurationSuggestionRead(BaseModel):
    id: str
    user_id: str
    suggestion_type: str
    source_ids: List[str]
    proposed_payload: Dict[str, Any]
    confidence: float
    explanation: Optional[str] = None
    provenance_metadata: Dict[str, Any]
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CurationLogRead(BaseModel):
    id: str
    user_id: str
    sweep_type: str
    items_processed: int
    items_merged: int
    details: Dict[str, Any]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class KnowledgeBriefingRead(BaseModel):
    id: str
    user_id: str
    title: str
    summary_markdown: str
    highlights: List[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CurationSweepRequest(BaseModel):
    dry_run: bool = True

class CurationSweepResponse(BaseModel):
    sweep_type: str
    items_processed: int
    suggestions_created: int
    details: Dict[str, Any]
    suggestions: List[CurationSuggestionRead] = []
    briefing: Optional[KnowledgeBriefingRead] = None
