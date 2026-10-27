import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator, model_validator, Field
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "Agentic Personal Knowledge Assistant API"
    API_VERSION: str = "0.1.0"
    APP_ENV: str = "local"
    
    # Authentication
    JWT_SECRET_KEY: str = "supersecretkey_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    AUTH_DEV_MODE: bool = True
    DEFAULT_DEV_USER_EMAIL: str = "local@example.com"
    
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                pass
        return v
    
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@postgres:5432/knowledge_assistant"
    
    CHROMA_HOST: str = "chroma"
    CHROMA_PORT: int = 8000
    CHROMA_API_KEY: str = ""
    CHROMA_TENANT: str = ""
    CHROMA_DATABASE: str = ""
    
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    TAVILY_API_KEY: str = ""
    
    # OCR Ingestion
    OCR_ENABLED: bool = True
    OCR_LANG: str = "eng"
    OCR_DPI: int = Field(default=200, ge=100, le=400)
    OCR_MAX_PAGES: int = Field(default=10, ge=1, le=50)
    OCR_MIN_TEXT_CHARS: int = Field(default=100, ge=1, le=1000)
    
    # Embedding Configuration
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DEVICE: str = "cpu"
    CHROMA_COLLECTION_NAME: str = "knowledge_chunks"
    STORAGE_DIR: str = "./storage"

    # Reranking & Hybrid Search
    RERANKING_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKING_ENABLED: bool = True
    RRF_K_PARAM: int = 60

    # GitHub Ingestion
    GITHUB_MAX_FILES: int = Field(default=50, ge=1, le=500)
    GITHUB_MAX_FILE_BYTES: int = Field(default=300000, ge=1000, le=2_000_000)
    GITHUB_ALLOWED_EXTENSIONS: str = ".py,.js,.ts,.tsx,.jsx,.md,.txt,.json,.yaml,.yml,.toml,.css,.html,.go,.rs,.java"
    GITHUB_PAT: str = ""

    # Automation
    AUTO_TAG_ON_INGESTION: bool = True

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        # Check JWT_SECRET_KEY
        if not self.AUTH_DEV_MODE:
            if self.JWT_SECRET_KEY == "supersecretkey_change_me_in_production":
                raise ValueError("JWT_SECRET_KEY must be changed from default when AUTH_DEV_MODE is False")
        
        # Check DATABASE_URL
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be configured")
            
        # Normalize STORAGE_DIR
        self.STORAGE_DIR = os.path.abspath(self.STORAGE_DIR)
        
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
