import logging
from sqlalchemy.orm import Session
from app.models.document import Document, IngestionJob, utc_now
from app.schemas.document import DocumentCreate
from app.schemas.rag import RagQuestionRequest
from app.services import document_service
from app.services.research_agent_service import run_autonomous_research

logger = logging.getLogger(__name__)

def run_deep_research_job(job_id: str, payload: dict, session: Session):
    job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    job.status = "processing"
    session.commit()

    question = payload.get("question")
    user_id = job.user_id

    try:
        req = RagQuestionRequest(
            question=question,
            max_iterations=3, # Caps
            limit=5,
            fallback_action="autonomous_research",
            confidence_mode="balanced"
        )
        
        # We need to enforce caps. The autonomous research internally respects max_iterations and limit.
        response = run_autonomous_research(session, req, user_id)
        
        # Save as Markdown
        report_content = f"# Deep Research Report: {question}\n\n{response.answer}\n\n## References\n"
        for citation in response.citations:
            report_content += f"- [{citation.citation_id}] {citation.document_title} ({citation.source_type})\n"
            
        doc_in = DocumentCreate(
            title=f"Deep Research: {question[:50]}",
            source_type="deep_research",
            source_uri=None
        )
        doc = document_service.create_document_metadata(session, doc_in, user_id=user_id)
        
        # Save text directly
        import os
        from app.core.config import settings
        os.makedirs(settings.STORAGE_DIR, exist_ok=True)
        temp_file = os.path.join(settings.STORAGE_DIR, f"{doc.id}_research.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        doc.original_filename = temp_file
        doc.status = "ready"
        job.document_id = doc.id
        
        # Re-use ingestion_pipeline to chunk and index the markdown report
        from app.services.ingestion_pipeline import create_chunks_for_document, index_document_chunks
        chunks = create_chunks_for_document(session, doc, report_content)
        index_result = index_document_chunks(session, str(doc.id))
        
        job.status = "succeeded"
        job.message = f"Research complete. Generated report and indexed {len(chunks)} chunks."
        job.completed_at = utc_now()
        session.commit()

    except Exception as e:
        session.rollback()
        job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = utc_now()
            session.commit()
        logger.exception(f"Deep Research job {job_id} failed.")
