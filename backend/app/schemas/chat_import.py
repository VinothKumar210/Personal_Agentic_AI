from pydantic import BaseModel
from app.schemas.document import DocumentRead, IngestionJobRead

class ChatImportResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead
    chunks_created: int
    detected_format: str
    message: str
