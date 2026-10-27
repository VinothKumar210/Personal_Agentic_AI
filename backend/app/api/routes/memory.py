from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.memory import PersonalMemoryCreate, PersonalMemoryUpdate, PersonalMemoryRead
from app.services import memory_service

router = APIRouter()

class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5

@router.get("", response_model=List[PersonalMemoryRead])
def list_memories(
    category: Optional[str] = Query(None),
    privacy_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    memories = memory_service.get_memories(db, user_id=current_user.id, category=category, privacy_level=privacy_level)
    return memories

@router.post("", response_model=PersonalMemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory_item(
    memory_in: PersonalMemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if memory_in.privacy_level not in ["public", "team", "private", "sensitive"]:
        raise HTTPException(status_code=422, detail="Invalid privacy_level. Must be public, team, private, or sensitive.")
    memory = memory_service.create_memory(db, user_id=current_user.id, memory_in=memory_in)
    return memory

@router.put("/{memory_id}", response_model=PersonalMemoryRead)
@router.patch("/{memory_id}", response_model=PersonalMemoryRead)
def update_memory_item(
    memory_id: str,
    memory_in: PersonalMemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if memory_in.privacy_level and memory_in.privacy_level not in ["public", "team", "private", "sensitive"]:
        raise HTTPException(status_code=422, detail="Invalid privacy_level. Must be public, team, private, or sensitive.")
    memory = memory_service.update_memory(db, user_id=current_user.id, memory_id=memory_id, memory_in=memory_in)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return memory

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory_item(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = memory_service.delete_memory(db, user_id=current_user.id, memory_id=memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return None

@router.post("/search")
def search_memories(
    request: MemorySearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = memory_service.search_personal_memories(db, user_id=current_user.id, query=request.query, limit=request.limit)
    return {"results": results}
