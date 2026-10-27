from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    chroma: str
    groq_configured: bool
    storage: str
    auth_dev_mode: bool
    embedding_model: str
    chroma_collection: str
