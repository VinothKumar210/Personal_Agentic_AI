from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.chat import (
    ConversationCreate,
    ConversationRead,
    ConversationListResponse,
    ChatMessageCreate,
    ChatMessageRead,
    ChatAnswerResponse
)
from app.services import chat_service
from typing import List
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/conversations", tags=["chat"])

@router.post("", response_model=ConversationRead)
def create_conversation(request: ConversationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = chat_service.create_conversation(request, db, user_id=current_user.id)
    return ConversationRead.model_validate(conv)

@router.get("", response_model=ConversationListResponse)
def list_conversations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items, total = chat_service.list_conversations(db, user_id=current_user.id, skip=skip, limit=limit)
    return ConversationListResponse(
        items=[ConversationRead.model_validate(c) for c in items],
        total=total
    )

@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = chat_service.get_conversation(conversation_id, db, user_id=current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conv)

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = chat_service.delete_conversation(conversation_id, db, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None

@router.get("/{conversation_id}/messages", response_model=List[ChatMessageRead])
def get_messages(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = chat_service.get_conversation(conversation_id, db, user_id=current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat_service.list_messages(conversation_id, db)

@router.post("/{conversation_id}/messages", response_model=ChatAnswerResponse)
def create_message(conversation_id: str, request: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        conv, user_msg, asst_msg = chat_service.add_user_message_and_answer(conversation_id, request, db, user_id=current_user.id)
        return ChatAnswerResponse(
            conversation=ConversationRead.model_validate(conv),
            user_message=user_msg,
            assistant_message=asst_msg
        )
    except ValueError as e:
        if "Conversation not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/{conversation_id}/messages/stream")
def create_message_stream(conversation_id: str, request: ChatMessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        chat_service.stream_chat_message(conversation_id, request, db, user_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

