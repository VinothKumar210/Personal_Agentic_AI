import logging
import sys

_logging_setup_done = False

def setup_logging():
    global _logging_setup_done
    if _logging_setup_done:
        return logging.getLogger(__name__)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(module)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Silence chatty libraries
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)

    _logging_setup_done = True
    return logging.getLogger(__name__)

logger = setup_logging()