import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def run_startup_checks():
    logger.info("Running startup checks...")
    
    # Ensure storage directories exist
    originals_dir = os.path.join(settings.STORAGE_DIR, "originals")
    try:
        os.makedirs(originals_dir, exist_ok=True)
        logger.info(f"Storage directory confirmed: {settings.STORAGE_DIR}")
    except Exception as e:
        logger.error(f"Failed to create storage directory {settings.STORAGE_DIR}: {e}")
        # We do not hard-fail here, but log the error

    # Check Groq configuration
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key":
        logger.info(f"Groq is configured. Model: {settings.GROQ_MODEL}")
    else:
        logger.warning("Groq is NOT configured. RAG and Chat endpoints may return 503 errors.")

    # Log Chroma configuration
    if settings.CHROMA_API_KEY:
        logger.info(f"Chroma Cloud configured. Tenant: {settings.CHROMA_TENANT}, Database: {settings.CHROMA_DATABASE}")
    else:
        logger.info(f"Chroma DB configured at {settings.CHROMA_HOST}:{settings.CHROMA_PORT}")

    # Log Auth Dev Mode
    if settings.AUTH_DEV_MODE:
        logger.warning("AUTH_DEV_MODE is enabled. The system is operating in single-user dev mode without strict security.")
    else:
        logger.info("AUTH_DEV_MODE is disabled. Strict authentication is enforced.")

    logger.info("Startup checks completed.")
