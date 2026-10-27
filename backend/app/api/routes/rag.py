from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.schemas.rag import RagQuestionRequest, RagAnswerResponse
from app.services.rag_service import answer_question, stream_grounded_answer
from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()

@router.post("/answer", response_model=RagAnswerResponse)
async def ask_question(
    request: RagQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Delegate to autonomous research if research_mode or fallback_action requests it
        if request.research_mode or request.fallback_action == "autonomous_research":
            from app.services.research_agent_service import run_autonomous_research
            return run_autonomous_research(db, request, user_id=current_user.id)
        response = answer_question(request, user_id=current_user.id, db=db)
        return response
    except RuntimeError as e:
        error_msg = str(e)
        if "GROQ" in error_msg.upper() or "generate answer from Groq" in error_msg:
            raise HTTPException(status_code=503, detail=error_msg)
        elif "Vector search failed" in error_msg or "query embedding" in error_msg:
            raise HTTPException(status_code=503, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)

@router.post("/stream")
async def ask_question_stream(
    request: RagQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Delegate to autonomous research streaming if research_mode or fallback_action requests it
    if request.research_mode or request.fallback_action == "autonomous_research":
        from app.services.research_agent_service import stream_autonomous_research
        return StreamingResponse(
            stream_autonomous_research(db, request, user_id=current_user.id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    return StreamingResponse(
        stream_grounded_answer(request, user_id=current_user.id, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/search-web", response_model=RagAnswerResponse)
async def ask_question_web(
    request: RagQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    request.fallback_action = "search_web"
    try:
        return answer_question(request, user_id=current_user.id, db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/research", response_model=RagAnswerResponse)
async def autonomous_research(
    request: RagQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dedicated endpoint for autonomous multi-step research."""
    from app.services.research_agent_service import run_autonomous_research
    try:
        return run_autonomous_research(db, request, user_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/research/stream")
async def autonomous_research_stream(
    request: RagQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dedicated streaming endpoint for autonomous multi-step research."""
    from app.services.research_agent_service import stream_autonomous_research
    return StreamingResponse(
        stream_autonomous_research(db, request, user_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/deep-research")
async def start_deep_research(
    request: RagQuestionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Starts a long-running deep research job and returns the job ID."""
    from app.models.document import IngestionJob
    from app.services.job_runner import run_ingestion_job
    
    job = IngestionJob(
        user_id=current_user.id,
        job_type="deep_research",
        status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    payload = {"question": request.question}
    background_tasks.add_task(run_ingestion_job, job.id, "deep_research", payload)
    
    # Return job status structure
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "message": "Deep research queued"
    }

@router.get("/jobs/{job_id}")
async def get_rag_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.document import IngestionJob
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id, IngestionJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "message": job.message,
        "error_message": job.error_message,
        "document_id": job.document_id
    }
