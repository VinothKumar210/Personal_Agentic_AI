import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

def validate_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")
        
    parsed = urlparse(url)
    if parsed.scheme not in ["http", "https"]:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}. Only http and https are allowed.")
        
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing hostname")
        
    return url

def fetch_webpage(url: str) -> tuple[str, str]:
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "").lower()
            if content_type:
                if "text/html" not in content_type:
                    raise ValueError(f"Unsupported content type: {content_type}")
            else:
                body_lower = response.text[:2000].lower() # check start of body
                if not any(tag in body_lower for tag in ["<html", "<body", "<article", "<main"]):
                    raise ValueError("Unsupported content type: missing content-type and body does not appear to be HTML")
            
            return response.text, str(response.url)
    except httpx.TimeoutException:
        raise RuntimeError(f"Request to {url} timed out.")
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching {url}: {str(e)}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise RuntimeError(f"Failed to fetch webpage: {str(e)}")

def extract_readable_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    
    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        element.decompose()
        
    # Prefer <article>, then <main>, then <body>, then soup
    target = soup.find('article')
    if not target:
        target = soup.find('main')
    if not target:
        target = soup.find('body')
    if not target:
        target = soup
        
    # Get text
    text = target.get_text(separator=" ")
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    non_ws_count = len(text.replace(" ", ""))
    if non_ws_count < 100:
        raise ValueError(f"Extracted text is too short ({non_ws_count} chars). Minimum is 100 non-whitespace characters.")
        
    return text

def derive_title(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
            
    h1 = soup.find('h1')
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
        
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if path:
        return f"{parsed.netloc}/{path}"
    return parsed.netloc

def save_web_result_to_kb(db, user_id: str, title: str, url: str, content: str):
    from app.schemas.document import DocumentCreate
    from app.services import document_service
    from app.models.document import IngestionJob

    doc_in = DocumentCreate(
        title=title or url or "Saved Web Result",
        source_type="web_search_saved",
        source_uri=url
    )
    doc = document_service.create_document_metadata(db, doc_in, user_id=user_id)
    doc.status = "processing"

    job = IngestionJob(
        document_id=doc.id,
        user_id=user_id,
        job_type="web_search_saved_ingestion",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)
    return doc, job

def process_web_clip(db, user_id: str, url: str, title: str | None = None, html_content: str | None = None, selected_text: str | None = None):
    from app.schemas.document import DocumentCreate
    from app.services import document_service
    from app.models.document import IngestionJob
    import uuid
    import os
    from app.core.config import settings

    final_title = title or derive_title(html_content or "", url) or "Clipped Web Page"
    
    doc_in = DocumentCreate(
        title=final_title,
        source_type="web_clip",
        source_uri=url
    )
    doc = document_service.create_document_metadata(db, doc_in, user_id=user_id)
    
    # Store the content on disk for the background job to chunk
    text_content = ""
    if selected_text:
        text_content = selected_text
    elif html_content:
        try:
            text_content = extract_readable_text(html_content)
        except ValueError:
            text_content = html_content # fallback to raw if empty or failed
    else:
        # Fallback to fetching it directly if only URL provided
        html_content, _ = fetch_webpage(url)
        text_content = extract_readable_text(html_content)

    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    temp_file = os.path.join(settings.STORAGE_DIR, f"{doc.id}_clip.txt")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(text_content)
        
    doc.original_filename = temp_file
    doc.status = "processing"

    job = IngestionJob(
        document_id=doc.id,
        user_id=user_id,
        job_type="text_ingestion", # Re-use text ingestion since it's already a txt file now
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Trigger job runner asynchronously
    from app.services.job_runner import run_ingestion_job
    import threading
    payload = {"file_path": temp_file, "source_type": "text"}
    threading.Thread(target=run_ingestion_job, args=(job.id, "file_upload", payload), daemon=True).start()
    
    return job
