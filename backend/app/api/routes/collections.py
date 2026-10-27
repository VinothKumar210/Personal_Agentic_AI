from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.schemas.document import CollectionCreate, CollectionRead, DocumentRead
from app.services import document_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()
@router.post("", response_model=CollectionRead)
def create_collection(collection_in: CollectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return document_service.create_collection(db, collection_in, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.get("", response_model=List[CollectionRead])
def get_collections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return document_service.list_collections(db, user_id=current_user.id, skip=skip, limit=limit)

@router.post("/{collection_id}/documents/{document_id}", response_model=DocumentRead)
def attach_document_to_collection(collection_id: str, document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    collection = document_service.get_collection(db, collection_id, user_id=current_user.id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    document = document_service.get_document(db, document_id, user_id=current_user.id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return document_service.attach_document_to_collection(db, document, collection)
