from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

TargetRole = Literal["llm_engineer", "backend_engineer", "full_stack_ai_engineer"]

class LearningProfileCreate(BaseModel):
    goal_title: str
    target_role: Optional[TargetRole] = None
    current_level: Optional[str] = None
    focus_keywords: List[str] = Field(default_factory=list)

class LearningRecommendationRead(BaseModel):
    id: UUID
    profile_id: Optional[UUID]
    title: str
    description: Optional[str]
    priority: int
    reason: Optional[str]
    evidence_json: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class LearningProfileRead(BaseModel):
    id: UUID
    goal_title: str
    target_role: Optional[TargetRole]
    current_level: Optional[str]
    focus_keywords_json: Optional[str]
    created_at: datetime
    updated_at: datetime
    recommendations: List[LearningRecommendationRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}

class LearningPathRequest(BaseModel):
    profile_id: Optional[UUID] = None
    target_role: Optional[TargetRole] = None
    max_recommendations: int = Field(default=8, ge=1, le=20)

class LearningPathResponse(BaseModel):
    profile: Optional[LearningProfileRead] = None
    recommendations: List[LearningRecommendationRead]
    strengths: List[str]
    gaps: List[str]
    message: str
