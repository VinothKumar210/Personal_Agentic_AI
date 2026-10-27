from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.api_key import ApiKey, utc_now
from app.services.auth_service import get_or_create_dev_user
import logging
import hashlib

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

def get_current_user(
    db: Session = Depends(get_db),
    token: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        if settings.AUTH_DEV_MODE:
            logger.info("No token provided, using dev user due to AUTH_DEV_MODE=True")
            return get_or_create_dev_user(db)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

    try:
        payload = jwt.decode(token.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
        
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

class ScopedApiKeyAuth:
    def __init__(self, required_scopes: list[str] = None):
        self.required_scopes = required_scopes or []

    def __call__(
        self,
        db: Session = Depends(get_db),
        token: HTTPAuthorizationCredentials = Depends(security)
    ) -> User:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated (API Key required)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        raw_key = token.credentials
        hashed = hash_api_key(raw_key)
        
        db_key = db.query(ApiKey).filter(
            ApiKey.hashed_key == hashed,
            ApiKey.revoked_at.is_(None)
        ).first()
        
        if not db_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key",
            )
            
        key_scopes = set(s.strip() for s in db_key.scopes.split(",") if s.strip())
        for req_scope in self.required_scopes:
            if req_scope not in key_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API Key missing required scope: {req_scope}",
                )
                
        # Update last_used
        db_key.last_used_at = utc_now()
        db.commit()
        
        user = db.query(User).filter(User.id == db_key.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user for API Key")
            
        return user
