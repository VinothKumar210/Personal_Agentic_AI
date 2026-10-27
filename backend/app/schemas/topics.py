from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class TopicAnalysisRequest(BaseModel):
    min_clusters: int = Field(default=2, ge=1)
    max_clusters: int = Field(default=8, ge=1, le=20)
    min_chunks: int = Field(default=5, ge=1)
    
class TopicClusterRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    keywords_json: Optional[str] = None
    document_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TopicAnalysisResponse(BaseModel):
    clusters: List[TopicClusterRead]
    chunks_analyzed: int
    message: str

class TopicClusterListResponse(BaseModel):
    clusters: List[TopicClusterRead]
