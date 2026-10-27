from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ApiKeyCreate(BaseModel):
    description: Optional[str] = None
    scopes: str = ""  # Comma separated scopes, e.g., "capture_page,search"

class ApiKeyRead(BaseModel):
    id: str
    description: Optional[str] = None
    scopes: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreateResponse(ApiKeyRead):
    raw_key: str  # Only returned once on creation
