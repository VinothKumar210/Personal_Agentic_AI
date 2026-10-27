from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class KnowledgeNodeRead(BaseModel):
    id: UUID
    label: str
    node_type: str
    description: Optional[str] = None
    aliases_json: Optional[str] = None
    frequency: int
    is_pruned: bool = False
    pruned_reason: Optional[str] = None
    confidence_score: float = 1.0
    last_reflected_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    document_ids: List[str] = []

    model_config = {"from_attributes": True}

class KnowledgeEdgeRead(BaseModel):
    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relation_type: str
    weight: float
    evidence_json: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class KnowledgeGraphResponse(BaseModel):
    nodes: List[KnowledgeNodeRead]
    edges: List[KnowledgeEdgeRead]
    node_count: int
    edge_count: int
    message: str

class KnowledgeGraphBuildRequest(BaseModel):
    min_frequency: int = Field(default=2, ge=1)
    max_nodes: int = Field(default=100, ge=1, le=500)
    cooccurrence_window: int = Field(default=2, ge=1, le=10)
