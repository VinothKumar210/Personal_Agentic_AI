import json
import logging
import re
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.document import Document, Tag, document_tags
from app.services import groq_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert taxonomy and metadata assistant. Your job is to generate 3 to 5 highly relevant tags for a document.

You will be provided with a summary and/or excerpts of the document, as well as a list of existing tags in the user's library.
You MUST follow these rules:
1. Prefer choosing from the existing tags if they accurately describe the document.
2. Only create a new tag if no existing tag is a good fit.
3. Keep tags concise (1-3 words max).
4. Output ONLY a valid JSON object with a "tags" array of strings. No markdown formatting, no explanations.

Example Output:
{"tags": ["Machine Learning", "Python", "Data Science"]}
"""

def normalize_tag_name(name: str) -> str:
    normalized = name.strip().lower()
    normalized = re.sub(r"(?<=\b[a-z])\.(?=[a-z]\b)", "", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def display_case(name: str) -> str:
    normalized = normalize_tag_name(name)
    acronyms = {"ai", "api", "llm", "rag", "ocr", "pdf", "ui", "ux", "jwt"}
    words = []
    for word in normalized.split():
        words.append(word.upper() if word in acronyms else word.capitalize())
    return " ".join(words)

def get_existing_tags(db: Session, user_id: str) -> List[Tag]:
    return db.query(Tag).filter(Tag.user_id == user_id).all()

def generate_tags_for_document(db: Session, document_id: str, user_id: str) -> List[Tag]:
    """Generates and assigns tags to a document using LLM, preferring existing tags."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found.")

    # Build context from summary or chunks
    context = ""
    if doc.summary:
        context += f"Summary:\n{doc.summary}\n\n"
    
    # Get first few chunks if summary is missing or small
    if len(context) < 500:
        chunks = doc.chunks[:3]
        if chunks:
            context += "Excerpts:\n"
            for chunk in chunks:
                context += f"{chunk.text}\n---\n"
                
    if not context.strip():
        logger.warning(f"No content found for document {document_id} to tag.")
        return []

    # Get existing tags to encourage reuse
    existing_tags = get_existing_tags(db, user_id)
    existing_tag_names = [t.name for t in existing_tags]
    
    user_prompt = f"Document Title: {doc.title}\n\n"
    if existing_tag_names:
        user_prompt += f"Existing Tags to choose from:\n{json.dumps(existing_tag_names)}\n\n"
    user_prompt += f"Document Content:\n{context}"

    # Call LLM
    try:
        response_text = groq_client.generate_completion(
            prompt=user_prompt,
            system_message=SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=150,
            json_mode=True
        )
        
        parsed = json.loads(response_text)
        if isinstance(parsed, dict):
            generated_tag_names = parsed.get("tags", [])
        else:
            generated_tag_names = parsed
        if not isinstance(generated_tag_names, list):
            raise ValueError("LLM did not return a tags list")
            
    except Exception as e:
        logger.error(f"Failed to generate tags for document {document_id}: {e}")
        raise e

    # Process and assign tags
    assigned_tags = []
    
    # Mapping for quick lookup by normalized name
    existing_tags_map = {normalize_tag_name(t.name): t for t in existing_tags}
    
    # Get document's current tags to avoid duplicates
    current_doc_tags_map = {normalize_tag_name(t.name): t for t in doc.tags}

    for name in generated_tag_names[:5]: # Limit to 5
        if not isinstance(name, str) or not name.strip():
            continue
            
        norm_name = normalize_tag_name(name)
        if not norm_name:
            continue
            
        # Already attached to doc?
        if norm_name in current_doc_tags_map:
            assigned_tags.append(current_doc_tags_map[norm_name])
            continue
            
        # Exists in db but not on doc?
        if norm_name in existing_tags_map:
            tag = existing_tags_map[norm_name]
        else:
            # Create new tag
            tag = Tag(
                name=display_case(name),
                user_id=user_id
            )
            db.add(tag)
            # Add to map in case LLM returned duplicates in its list
            existing_tags_map[norm_name] = tag
            
        doc.tags.append(tag)
        current_doc_tags_map[norm_name] = tag
        assigned_tags.append(tag)

    db.commit()
    return assigned_tags
