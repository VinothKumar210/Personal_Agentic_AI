from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.schemas.document import DocumentRead, IngestionJobRead

class IngestionJobStatusResponse(BaseModel):
    job: IngestionJobRead
    document: Optional[DocumentRead] = None
    chunks_created: int = 0
    message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
