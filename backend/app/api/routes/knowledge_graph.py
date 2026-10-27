from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge_graph import (
    KnowledgeGraphBuildRequest,
    KnowledgeGraphResponse,
    KnowledgeNodeRead
)
from app.schemas.document import DocumentRead
from app.services import knowledge_graph_service
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/build", response_model=KnowledgeGraphResponse)
def build_knowledge_graph(request: KnowledgeGraphBuildRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return knowledge_graph_service.build_graph(db, request, user_id=current_user.id)

@router.get("", response_model=KnowledgeGraphResponse)
def get_knowledge_graph(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return knowledge_graph_service.get_graph(db, user_id=current_user.id)

@router.get("/nodes/{node_id}", response_model=KnowledgeNodeRead)
def get_knowledge_node(node_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    node = knowledge_graph_service.get_node(db, node_id, user_id=current_user.id)
    if not node:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    return node

@router.get("/nodes/{node_id}/documents", response_model=List[DocumentRead])
def get_knowledge_node_documents(node_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    node = knowledge_graph_service.get_node(db, node_id, user_id=current_user.id)
    if not node:
        raise HTTPException(status_code=404, detail="Knowledge node not found")
    return node.documents

