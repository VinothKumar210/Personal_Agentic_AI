from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.models.user import User
from app.models.flashcard import Flashcard, FlashcardReview, generate_uuid, utc_now
from app.models.document import Document
from app.schemas.flashcard import FlashcardCreate, FlashcardRead, FlashcardReviewRequest, FlashcardGenerateRequest, FlashcardGenerateResponse
from app.api.deps import get_current_user
from app.services.groq_client import is_groq_configured
from app.core.config import settings
import json

router = APIRouter()

def calculate_sm2(quality: int, repetitions: int, previous_interval: int, previous_ease: float) -> tuple[int, int, float]:
    """
    Calculates next review interval based on SuperMemo-2 algorithm.
    quality: 1-4 (1=Again, 2=Hard, 3=Good, 4=Easy)
    """
    # Adjust 1-4 scale to SM-2's 0-5 expected scale roughly
    sm2_q = 0
    if quality == 1: sm2_q = 1
    elif quality == 2: sm2_q = 3
    elif quality == 3: sm2_q = 4
    elif quality == 4: sm2_q = 5
    else: sm2_q = 0
        
    if sm2_q < 3:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = int(round(previous_interval * previous_ease))
            
    ease = previous_ease + (0.1 - (5 - sm2_q) * (0.08 + (5 - sm2_q) * 0.02))
    ease = max(1.3, ease)
    
    return interval, repetitions, ease

@router.post("/generate", response_model=FlashcardGenerateResponse)
def generate_flashcards(
    req: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate draft flashcards for a specific document on demand.
    """
    if not is_groq_configured():
        raise HTTPException(status_code=500, detail="Groq API Key not configured")
        
    doc = db.query(Document).filter(
        Document.id == req.document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Get chunks text
    from app.models.document import DocumentChunk
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index).limit(10).all()
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no chunks")
        
    text_content = "\n".join([c.text for c in chunks])
    
    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    prompt = f"""
    You are an expert educator. Based on the following text, extract 3-5 key concepts and turn them into flashcards.
    Provide the response ONLY as a JSON object with a "flashcards" array.
    Each flashcard must have "front" and "back" keys.
    Text: {text_content[:4000]}
    """
    
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "flashcards" in parsed:
            cards = parsed["flashcards"]
        elif isinstance(parsed, list):
            cards = parsed
        else:
            # try to extract list
            cards = next(iter(parsed.values())) if parsed else []
    except:
        cards = []
        
    drafts = []
    for c in cards:
        if isinstance(c, dict) and "front" in c and "back" in c:
            fc = Flashcard(
                user_id=current_user.id,
                document_id=doc.id,
                front=c["front"],
                back=c["back"],
                status="draft"
            )
            db.add(fc)
            drafts.append(fc)
            
    db.commit()
    for d in drafts:
        db.refresh(d)
        
    return FlashcardGenerateResponse(drafts=[FlashcardRead.model_validate(d) for d in drafts])

@router.post("/{card_id}/approve", response_model=FlashcardRead)
def approve_flashcard(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(Flashcard).filter(Flashcard.id == card_id, Flashcard.user_id == current_user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
        
    card.status = "active"
    card.next_review_date = utc_now()
    db.commit()
    db.refresh(card)
    return card

@router.get("/due", response_model=List[FlashcardRead])
def get_due_flashcards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cards = db.query(Flashcard).filter(
        Flashcard.user_id == current_user.id,
        Flashcard.status == "active",
        Flashcard.next_review_date <= utc_now()
    ).all()
    return cards

@router.post("/{card_id}/review")
def review_flashcard(
    card_id: str,
    req: FlashcardReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    card = db.query(Flashcard).filter(Flashcard.id == card_id, Flashcard.user_id == current_user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    if card.status != "active":
        raise HTTPException(status_code=400, detail="Only active flashcards can be reviewed")
        
    if req.score < 1 or req.score > 4:
        raise HTTPException(status_code=400, detail="Score must be between 1 and 4")
        
    interval, reps, ease = calculate_sm2(
        req.score, 
        card.repetition_count, 
        card.interval_days, 
        card.ease_factor
    )
    
    card.interval_days = interval
    card.repetition_count = reps
    card.ease_factor = ease
    card.next_review_date = utc_now() + timedelta(days=interval)
    
    review = FlashcardReview(
        flashcard_id=card.id,
        user_id=current_user.id,
        score=req.score
    )
    db.add(review)
    db.commit()
    
    return {"status": "success", "next_review_date": card.next_review_date}
