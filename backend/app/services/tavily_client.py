import httpx
from typing import List, Dict, Any
import uuid
from app.core.config import settings
from app.schemas.rag import RagCitation

def search_web_ephemeral(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using Tavily API without persisting results to DB.
    Returns formatted results as ephemeral dicts ready for citations and LLM context.
    """
    if not settings.TAVILY_API_KEY or not settings.TAVILY_API_KEY.strip():
        raise ValueError("TAVILY_API_KEY is not configured")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.TAVILY_API_KEY.strip(),
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "search_depth": "basic"
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise RuntimeError(f"Tavily web search error: {str(e)}")

    raw_results = data.get("results", [])
    ephemeral_chunks = []
    for idx, item in enumerate(raw_results):
        title = item.get("title") or f"Web Result #{idx+1}"
        url_str = item.get("url") or ""
        content = item.get("content") or ""
        
        ephemeral_chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "document_title": title,
            "source_type": "web_tavily",
            "original_filename": None,
            "source_uri": url_str,
            "chunk_index": idx + 1,
            "text": content,
            "score": item.get("score", 1.0)
        })

    return ephemeral_chunks

def format_tavily_citations(ephemeral_chunks: List[Dict[str, Any]]) -> List[RagCitation]:
    """
    Format ephemeral chunks or raw dicts into Pydantic RagCitation objects.
    """
    citations = []
    for idx, res in enumerate(ephemeral_chunks):
        citation_id = idx + 1
        text_content = res.get("text") or res.get("content", "")
        citations.append(RagCitation(
            citation_id=citation_id,
            chunk_id=str(res.get("chunk_id") or uuid.uuid4()),
            document_id=str(res.get("document_id") or uuid.uuid4()),
            document_title=res.get("document_title") or res.get("title", f"Web Result #{citation_id}"),
            source_type=res.get("source_type", "web_tavily"),
            original_filename=res.get("original_filename"),
            source_uri=res.get("source_uri") or res.get("url", ""),
            chunk_index=res.get("chunk_index", citation_id),
            text_preview=text_content[:150] + "..." if len(text_content) > 150 else text_content
        ))
    return citations

def get_ephemeral_web_contexts(query: str, max_results: int = 5):
    ephemeral_chunks = search_web_ephemeral(query, max_results=max_results)
    contexts = []
    for idx, res in enumerate(ephemeral_chunks):
        contexts.append({
            "citation_id": idx + 1,
            "document_title": res["document_title"],
            "source_type": "web_tavily",
            "filename_uri": res.get("source_uri") or "unknown",
            "chunk_index": res["chunk_index"],
            "text": res["text"]
        })
    citations = format_tavily_citations(ephemeral_chunks)
    return ephemeral_chunks, contexts, citations

