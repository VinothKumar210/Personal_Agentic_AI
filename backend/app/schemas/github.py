from pydantic import BaseModel
from typing import Optional
from app.schemas.document import DocumentRead, IngestionJobRead

class GithubRepoIngestRequest(BaseModel):
    repo_url: str
    title: Optional[str] = None

class GithubRepoIngestResponse(BaseModel):
    document: DocumentRead
    job: IngestionJobRead
    files_ingested: int
    chunks_created: int
    message: str

class GithubRepoRead(BaseModel):
    name: str
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    default_branch: str
