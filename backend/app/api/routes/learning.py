from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.learning import (
    LearningProfileCreate,
    LearningProfileRead,
    LearningPathRequest,
    LearningPathResponse
)
from app.services import learning_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/profiles", response_model=LearningProfileRead)
def create_profile(profile: LearningProfileCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return learning_service.create_learning_profile(db, profile, user_id=current_user.id)

@router.get("/profiles", response_model=List[LearningProfileRead])
def list_profiles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return learning_service.list_learning_profiles(db, user_id=current_user.id)

@router.get("/profiles/{profile_id}", response_model=LearningProfileRead)
def get_profile(profile_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = learning_service.get_learning_profile(db, profile_id, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile = learning_service.get_learning_profile(db, profile_id, user_id=current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    learning_service.delete_learning_profile(db, profile_id, user_id=current_user.id)
    return {"message": "Profile deleted successfully"}

@router.post("/analyze", response_model=LearningPathResponse)
def analyze_path(request: LearningPathRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    profile, recommendations, strengths, gaps, message = learning_service.analyze_learning_path(db, request, user_id=current_user.id)
    return LearningPathResponse(
        profile=profile,
        recommendations=recommendations,
        strengths=strengths,
        gaps=gaps,
        message=message
    )
