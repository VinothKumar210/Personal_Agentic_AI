from typing import Optional
from pydantic import BaseModel
from app.schemas.document import DocumentRead, IngestionJobRead

class OcrIngestResponse(BaseModel):
    document: Optional[DocumentRead] = None
    job: Optional[IngestionJobRead] = None
    chunks_created: int = 0
    source_kind: str
    pages_processed: int = 0
    message: str
