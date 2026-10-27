import chromadb
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_chroma_client():
    try:
        if settings.CHROMA_API_KEY:
            client = chromadb.CloudClient(
                api_key=settings.CHROMA_API_KEY,
                tenant=settings.CHROMA_TENANT,
                database=settings.CHROMA_DATABASE,
            )
        else:
            client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Chroma: {e}")
        return None

def check_chroma_health() -> bool:
    try:
        client = get_chroma_client()
        if client:
            client.heartbeat()
            return True
        return False
    except Exception:
        return False
