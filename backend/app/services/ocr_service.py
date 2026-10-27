import logging
import re
from typing import Tuple, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

def is_image_file(filename: str, content_type: Optional[str] = None) -> bool:
    ext = filename.lower().split(".")[-1]
    valid_exts = {"png", "jpg", "jpeg", "webp", "tif", "tiff"}
    
    if ext in valid_exts:
        return True
        
    if content_type and content_type.startswith("image/"):
        return True
        
    return False

def is_pdf_file(filename: str, content_type: Optional[str] = None) -> bool:
    ext = filename.lower().split(".")[-1]
    if ext == "pdf":
        return True
    if content_type == "application/pdf":
        return True
    return False

def extract_text_from_image_bytes(content: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise RuntimeError("OCR engine is not installed or not available")
        
    import io
    
    try:
        image = Image.open(io.BytesIO(content))
        if image.mode != "RGB":
            image = image.convert("RGB")
            
        text = pytesseract.image_to_string(image, lang=settings.OCR_LANG)
        return text
    except Exception as e:
        logger.error(f"Pytesseract error: {str(e)}")
        raise RuntimeError("OCR engine is not installed or not available")

def extract_text_from_scanned_pdf(content: bytes) -> tuple[str, int]:
    try:
        import pdf2image
        from PIL import Image
        import pytesseract
    except ImportError:
        raise RuntimeError("PDF rendering dependency is not installed or not available")

    try:
        pages = pdf2image.convert_from_bytes(
            content,
            dpi=settings.OCR_DPI,
            first_page=1,
            last_page=settings.OCR_MAX_PAGES
        )
    except Exception as e:
        logger.error(f"pdf2image error: {str(e)}")
        raise RuntimeError("PDF rendering dependency is not installed or not available")
        
    extracted_text = []
    for i, page in enumerate(pages):
        try:
            page_text = pytesseract.image_to_string(page, lang=settings.OCR_LANG)
            extracted_text.append(f"--- OCR PAGE {i+1} ---\n{page_text}")
        except Exception as e:
            logger.error(f"Pytesseract error on page {i+1}: {str(e)}")
            raise RuntimeError("OCR engine is not installed or not available")
            
    return "\n\n".join(extracted_text), len(pages)

def extract_ocr_text(filename: str, content_type: Optional[str], content: bytes) -> Tuple[str, Dict]:
    if not settings.OCR_ENABLED:
        raise ValueError("OCR ingestion is disabled.")
        
    source_kind = "unknown"
    pages_processed = 0
    text = ""
    
    if is_image_file(filename, content_type):
        source_kind = "image"
        text = extract_text_from_image_bytes(content)
        pages_processed = 1
    elif is_pdf_file(filename, content_type):
        source_kind = "scanned_pdf"
        text, pages = extract_text_from_scanned_pdf(content)
        pages_processed = pages
    else:
        raise ValueError("Unsupported file format for OCR.")
        
    non_ws = len(re.sub(r"\s+", "", text))
    if non_ws < settings.OCR_MIN_TEXT_CHARS:
        raise ValueError("Extracted text is too short or empty. Ensure the image/document contains recognizable text.")
        
    metadata = {
        "source_kind": source_kind,
        "pages_processed": pages_processed,
        "ocr_lang": settings.OCR_LANG
    }
    return text, metadata
