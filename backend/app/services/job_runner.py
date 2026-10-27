import logging
import json
from sqlalchemy.orm import Session
from typing import Any, Dict

from app.db.session import SessionLocal
from app.models.document import Document, IngestionJob, DocumentChunk, utc_now
from app.services.ingestion_pipeline import create_chunks_for_document, create_code_chunks_for_document, index_document_chunks
from app.services.extraction_service import extract_text
from app.services.web_ingestion_service import fetch_webpage, extract_readable_text, derive_title
from app.services.github_ingestion_service import fetch_repository_tree, filter_ingestable_files, build_repository_text, chunk_repository_files
from app.services.chat_import_service import extract_chat_text
from app.services.ocr_service import extract_ocr_text

logger = logging.getLogger(__name__)

def run_ingestion_job(job_id: str, kind: str, payload: Dict[str, Any], db: Session = None) -> None:
    created_session = db is None
    session = db or SessionLocal()
    try:
        job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
            
        if kind == "deep_research":
            from app.services.deep_research_job import run_deep_research_job
            return run_deep_research_job(job_id, payload, session)

        if kind == "topic_clustering":
            from app.services.topic_service import run_auto_clustering_job
            return run_auto_clustering_job(job_id, payload, session)

        doc = session.query(Document).filter(Document.id == job.document_id).first()
        if not doc:
            logger.error(f"Document {job.document_id} not found for job {job_id}")
            job.status = "failed"
            job.message = "Associated document not found"
            session.commit()
            return

        job.status = "processing"
        session.commit()

        # Check existing chunks and build existing sha map for github_repo delta sync
        existing_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        existing_sha_map = {}
        existing_chunks_by_path = {}
        if kind == "github_repo" and existing_chunks:
            for c in existing_chunks:
                if c.metadata_json:
                    try:
                        meta = json.loads(c.metadata_json)
                        fp = meta.get("file_path")
                        sh = meta.get("sha")
                        if fp:
                            if sh:
                                existing_sha_map[fp] = sh
                            existing_chunks_by_path.setdefault(fp, []).append(c)
                    except Exception:
                        pass

        if kind != "github_repo":
            # Clean existing chunks before re-processing for non-repo docs
            session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            session.commit()

        combined_text = ""
        chunk_records = []
        unchanged_paths = []

        if kind == "file_upload":
            file_path = payload.get("file_path")
            source_type = payload.get("source_type")
            combined_text = extract_text(file_path, source_type)
            if not combined_text.strip():
                raise ValueError("Extracted text is empty.")

        elif kind == "webpage":
            url = payload.get("url")
            html, final_url = fetch_webpage(url)
            combined_text = extract_readable_text(html)
            if not combined_text.strip():
                raise ValueError("Failed to extract readable text from webpage.")
            if doc.title == url:
                derived_title = derive_title(html, url)
                if derived_title:
                    doc.title = derived_title

        elif kind == "github_repo":
            owner = payload.get("owner")
            repo = payload.get("repo")
            tree = fetch_repository_tree(owner, repo)
            ingestable_files = filter_ingestable_files(tree)
            if not ingestable_files:
                raise ValueError("No ingestable files found in the repository.")
            
            chunk_records, files_ingested, unchanged_paths = chunk_repository_files(owner, repo, ingestable_files, existing_sha_map=existing_sha_map)
            if not chunk_records and not unchanged_paths:
                raise ValueError("Failed to extract readable text from repository files.")
                
            deleted_chunk_ids = []
            for fp, c_list in existing_chunks_by_path.items():
                if fp not in unchanged_paths:
                    for c in c_list:
                        deleted_chunk_ids.append(str(c.id))
                        session.delete(c)
            if deleted_chunk_ids:
                from app.services.vector_service import delete_chunks_by_ids
                delete_chunks_by_ids(deleted_chunk_ids)
            session.commit()

        elif kind == "ai_chat":
            file_path = payload.get("file_path")
            filename = payload.get("filename")
            with open(file_path, "rb") as f:
                content = f.read()
            combined_text, _ = extract_chat_text(filename, content)
            if not combined_text.strip():
                raise ValueError("Failed to extract readable chat history.")

        elif kind == "ocr":
            file_path = payload.get("file_path")
            filename = payload.get("filename")
            content_type = payload.get("content_type")
            with open(file_path, "rb") as f:
                content = f.read()
            combined_text, _ = extract_ocr_text(filename, content_type, content)
            if not combined_text.strip():
                raise ValueError("OCR extraction yielded no text.")

        elif kind == "web_search_saved":
            combined_text = payload.get("content", "")
            if not combined_text.strip():
                raise ValueError("Web search result content is empty.")

        else:
            raise ValueError(f"Unknown job kind: {kind}")

        # Create fresh chunks
        if kind == "github_repo":
            chunks = create_code_chunks_for_document(session, doc, chunk_records)
            only_unindexed = True
        else:
            chunks = create_chunks_for_document(session, doc, combined_text)
            only_unindexed = False
        
        # Mark Document ready but job succeeded temporarily for indexing check
        doc.status = "ready"
        job.status = "succeeded"
        job.completed_at = utc_now()
        session.commit()

        # Index chunks
        index_result = index_document_chunks(session, str(doc.id), only_unindexed=only_unindexed)
        
        if index_result and index_result["failed_count"] > 0:
            job.message = f"Extraction succeeded but indexing failed: {index_result['message']}"
        else:
            if kind == "github_repo":
                job.message = f"Successfully ingested files and indexed {index_result['indexed_count'] if index_result else len(chunks)} chunks."
            else:
                job.message = f"Successfully processed and indexed {index_result['indexed_count'] if index_result else len(chunks)} chunks."
        
        session.commit()

        # Trigger auto-tagging if configured
        from app.core.config import settings
        if settings.AUTO_TAG_ON_INGESTION and kind != "github_repo": # Might skip github repos due to size
            try:
                from app.services.tagging_service import generate_tags_for_document
                tags = generate_tags_for_document(session, str(doc.id), str(doc.user_id))
                if tags:
                    tag_names = ", ".join([t.name for t in tags])
                    job.message += f" Auto-tagged: {tag_names}."
                    session.commit()
            except Exception as tag_err:
                logger.warning(f"Auto-tagging failed for document {doc.id}: {tag_err}")
                job.message += f" (Auto-tagging failed: {tag_err})"
                session.commit()

    except Exception as e:
        session.rollback()
        # Ensure job exists to update
        job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            doc = session.query(Document).filter(Document.id == job.document_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = utc_now()
            session.commit()
        logger.exception(f"Background job {job_id} failed.")
    finally:
        if created_session:
            session.close()
