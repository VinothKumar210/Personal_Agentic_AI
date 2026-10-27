from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import hashlib
import secrets

from app.db.session import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyRead, ApiKeyCreateResponse
from app.api.deps import get_current_user

router = APIRouter()

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

@router.post("/", response_model=ApiKeyCreateResponse)
def create_api_key(
    req: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    raw_key = secrets.token_urlsafe(32)
    hashed_key = hash_api_key(raw_key)

    db_key = ApiKey(
        user_id=current_user.id,
        description=req.description,
        scopes=req.scopes,
        hashed_key=hashed_key
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    return ApiKeyCreateResponse(
        id=db_key.id,
        description=db_key.description,
        scopes=db_key.scopes,
        created_at=db_key.created_at,
        last_used_at=db_key.last_used_at,
        revoked_at=db_key.revoked_at,
        raw_key=raw_key,
    )

@router.get("/", response_model=List[ApiKeyRead])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.revoked_at.is_(None)
    ).all()
    return keys

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.api_key import utc_now
    db_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not db_key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    db_key.revoked_at = utc_now()
    db.commit()
