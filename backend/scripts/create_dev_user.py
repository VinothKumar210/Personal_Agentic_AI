import sys
import os
import argparse

# Add the parent directory to Python path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.db.base import Base  # To initialize models properly and avoid circular imports
from app.models.user import User
from app.services.auth_service import get_password_hash

def create_or_update_dev_user(password: str = "password"):
    db: Session = SessionLocal()
    try:
        email = settings.DEFAULT_DEV_USER_EMAIL
        user = db.query(User).filter(User.email == email).first()
        
        hashed_password = get_password_hash(password)
        
        if user:
            print(f"User {email} already exists. Updating password...")
            user.hashed_password = hashed_password
        else:
            print(f"Creating new dev user: {email}")
            user = User(
                id="dev-user-id", # Keep it consistent for dev
                email=email,
                hashed_password=hashed_password,
                display_name="Dev User",
                is_active=True
            )
            db.add(user)
            
        db.commit()
        print(f"[OK] Dev user {email} is ready.")
    except Exception as e:
        print(f"[ERROR] Failed to create or update dev user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update the default dev user.")
    parser.add_argument("--password", type=str, default="password", help="Password for the dev user")
    args = parser.parse_args()
    
    create_or_update_dev_user(args.password)
