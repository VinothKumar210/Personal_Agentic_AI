from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PersonalMemoryCreate(BaseModel):
    category: str = "fact"  # fact, project, skill, preference
    content: str
    privacy_level: str = "private"  # public, private, sensitive
    source_citation: Optional[str] = None

class PersonalMemoryUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = None
    privacy_level: Optional[str] = None
    source_citation: Optional[str] = None

class PersonalMemoryRead(BaseModel):
    id: str
    user_id: str
    category: str
    content: str
    privacy_level: str
    source_citation: Optional[str] = None
    consolidated_into_id: Optional[str] = None
    is_consolidated: bool = False
    last_consolidated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
