import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.diary import DiaryEntry, DiaryEvent
from app.services.groq_client import generate_completion
from app.services.vector_service import get_diary_collection
from app.services.embedding_service import get_embeddings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise AI memory extraction engine. 
The user is providing a daily diary entry. Your task is to extract structured life events from the text.
For each distinct event or activity, output a JSON object.

Output ONLY a JSON array of event objects. No conversational text.

Each event object must have these fields:
- "title": A short, clear summary (e.g. "Visited doctor for headache")
- "description": Additional context from the text, or null.
- "category": One of [health, social, work, learning, finance, travel, family, personal, task, other].
- "people": A list of names of people involved. Normalize names (lowercase, no titles) where possible.
- "location": A location if mentioned, or null.
- "privacy_level": Either "private" or "sensitive". (health, finance, family, and emotional entries MUST be "sensitive").
- "sentiment": Either "positive", "neutral", or "negative".
- "source_span": The exact sentence or substring from the raw entry that generated this event.

Example Output:
[
  {
    "title": "Met friend Vinoth at a cafe",
    "description": null,
    "category": "social",
    "people": ["vinoth"],
    "location": "cafe",
    "privacy_level": "private",
    "sentiment": "positive",
    "source_span": "Later I met my friend Vinoth at a cafe."
  }
]
"""

async def process_diary_entry(db: Session, user_id: str, entry_date: datetime, raw_text: str):
    # 1. Save raw entry
    entry = DiaryEntry(
        user_id=user_id,
        entry_date=entry_date,
        raw_text=raw_text,
        extraction_version="v1"
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # 2. Extract structured events with Groq
    prompt = f"Today's date is {entry_date.strftime('%Y-%m-%d')}.\n\nDiary Entry:\n{raw_text}"
    
    events_created = []
    
    try:
        completion = await generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.1
        )
        
        # Parse JSON array
        # Try to find array brackets in case there's markdown
        start_idx = completion.find('[')
        end_idx = completion.rfind(']')
        if start_idx != -1 and end_idx != -1:
            json_str = completion[start_idx:end_idx+1]
        else:
            json_str = completion
            
        extracted_events = json.loads(json_str)
        
        for item in extracted_events:
            privacy = item.get("privacy_level", "private").lower()
            if privacy not in ["private", "sensitive"]:
                privacy = "private"
                
            sentiment = item.get("sentiment", "neutral").lower()
            if sentiment not in ["positive", "neutral", "negative"]:
                sentiment = "neutral"
                
            event = DiaryEvent(
                user_id=user_id,
                diary_entry_id=entry.id,
                event_date=entry_date,
                title=item.get("title", "Unknown Event"),
                description=item.get("description"),
                category=item.get("category", "personal"),
                people_json=item.get("people", []),
                location=item.get("location"),
                privacy_level=privacy,
                sentiment=sentiment,
                source_span=item.get("source_span"),
                confidence_score=1.0
            )
            db.add(event)
            events_created.append(event)
            
    except Exception as e:
        logger.error(f"Failed to extract diary events for entry {entry.id}: {e}")
        # Fallback to raw entry event
        fallback_event = DiaryEvent(
            user_id=user_id,
            diary_entry_id=entry.id,
            event_date=entry_date,
            title="Diary Entry",
            description=raw_text[:200] + "..." if len(raw_text) > 200 else raw_text,
            category="personal",
            privacy_level="sensitive",
            confidence_score=0.1,
            source_span=raw_text
        )
        db.add(fallback_event)
        events_created.append(fallback_event)

    db.commit()
    
    # Refresh all to get IDs
    for event in events_created:
        db.refresh(event)

    # 3. Index events in Chroma
    try:
        await index_diary_events(events_created)
    except Exception as e:
        logger.error(f"Failed to index diary events into Chroma: {e}")
        
    return entry, events_created

async def index_diary_events(events: list[DiaryEvent]):
    if not events:
        return
        
    collection = get_diary_collection()
    
    # We will embed a string combining category, title, description
    texts_to_embed = []
    for event in events:
        text = f"[{event.category}] {event.title}"
        if event.description:
            text += f": {event.description}"
        texts_to_embed.append(text)
        
    embeddings = await get_embeddings(texts_to_embed)
    
    ids = [e.id for e in events]
    metadatas = []
    for event in events:
        metadatas.append({
            "user_id": event.user_id,
            "event_date": event.event_date.isoformat(),
            "category": event.category,
            "privacy_level": event.privacy_level,
            "people": ",".join(event.people_json) if event.people_json else "",
            "diary_entry_id": event.diary_entry_id
        })
        
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=texts_to_embed
    )
