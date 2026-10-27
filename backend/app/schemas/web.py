from pydantic import BaseModel
from typing import Optional
from app.schemas.document import DocumentRead, IngestionJobRead

class WebpageIngestRequest(BaseModel):
    url: str
    title: Optional[str] = None

class WebpageIngestResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead
    chunks_created: int
    message: str

class SaveWebResultRequest(BaseModel):
    title: str
    url: str
    content: str
    fetched_date: Optional[str] = None

class SaveWebResultResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead
    message: str
