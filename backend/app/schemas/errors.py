from pydantic import BaseModel
from typing import Optional, List, Any

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    errors: Optional[List[Any]] = None
