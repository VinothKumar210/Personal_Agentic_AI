from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.schemas.topics import TopicAnalysisRequest, TopicAnalysisResponse, TopicClusterListResponse, TopicClusterRead
from app.services import topic_service
from app.api.deps import get_current_user
from app.models.user import User
from app.models.document import IngestionJob
from fastapi import BackgroundTasks

router = APIRouter()

@router.post("/auto-cluster")
def trigger_auto_cluster(request: TopicAnalysisRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        job = IngestionJob(
            user_id=current_user.id,
            job_type="topic_clustering",
            status="queued",
            document_id=None
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        from app.services.job_runner import run_ingestion_job
        background_tasks.add_task(
            run_ingestion_job,
            str(job.id),
            "topic_clustering",
            {"min_clusters": request.min_clusters, "max_clusters": request.max_clusters, "min_chunks": request.min_chunks},
            None
        )
        
        return {"job_id": str(job.id), "status": "queued"}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=TopicAnalysisResponse)
def analyze_topics(request: TopicAnalysisRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        clusters, chunks_analyzed, message = topic_service.analyze_topics(db, request, user_id=current_user.id)
        return TopicAnalysisResponse(clusters=clusters, chunks_analyzed=chunks_analyzed, message=message)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("", response_model=TopicClusterListResponse)
def list_topics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clusters = topic_service.list_topic_clusters(db, user_id=current_user.id)
    return TopicClusterListResponse(clusters=clusters)

@router.get("/{cluster_id}", response_model=TopicClusterRead)
def get_topic(cluster_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cluster = topic_service.get_topic_cluster(db, cluster_id, user_id=current_user.id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Topic cluster not found")
    return cluster
