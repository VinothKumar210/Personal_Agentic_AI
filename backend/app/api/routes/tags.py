from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.document import TagCreate, TagRead, DocumentRead
from app.services import document_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("", response_model=TagRead)
def create_tag(tag_in: TagCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return document_service.create_tag(db, tag_in, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("", response_model=List[TagRead])
def get_tags(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return document_service.list_tags(db, user_id=current_user.id, skip=skip, limit=limit)

@router.post("/{tag_id}/documents/{document_id}", response_model=DocumentRead)
def attach_tag_to_document(tag_id: str, document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tag = document_service.get_tag(db, tag_id, user_id=current_user.id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return document_service.attach_tag_to_document(db, document, tag)

@router.delete("/{tag_id}/documents/{document_id}", response_model=DocumentRead)
def detach_tag_from_document(tag_id: str, document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tag = document_service.get_tag(db, tag_id, user_id=current_user.id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document_service.detach_tag_from_document(db, document, tag)
