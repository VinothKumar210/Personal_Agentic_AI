from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate
from app.core.security import get_password_hash, verify_password
from app.core.config import settings

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        display_name=user_in.display_name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_or_create_dev_user(db: Session) -> User:
    email = settings.DEFAULT_DEV_USER_EMAIL
    user = get_user_by_email(db, email)
    if not user:
        hashed_password = get_password_hash("password")
        user = User(
            email=email,
            hashed_password=hashed_password,
            display_name="Local Dev",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
