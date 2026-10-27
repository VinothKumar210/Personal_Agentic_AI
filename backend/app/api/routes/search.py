from fastapi import APIRouter, Depends, HTTPException
from app.schemas.search import SearchRequest, SearchResponse
from app.services.embedding_service import embed_query
from app.services.vector_service import search_chunks
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("", response_model=SearchResponse)
def search_knowledge(request: SearchRequest, current_user: User = Depends(get_current_user)):
    try:
        query_embedding = embed_query(request.query)
        filters = {"user_id": current_user.id}
        if request.source_type:
            filters["source_type"] = request.source_type
        if request.document_id:
            filters["document_id"] = str(request.document_id)
            
        results = search_chunks(query_embedding, limit=request.limit, filters=filters)
        return SearchResponse(query=request.query, results=results)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Search service unavailable: {str(e)}")
