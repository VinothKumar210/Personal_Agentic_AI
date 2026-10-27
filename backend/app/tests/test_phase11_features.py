from datetime import timedelta
from unittest.mock import patch

from app.models.document import Document, IngestionJob, utc_now
from app.models.flashcard import Flashcard


def test_document_schema_accepts_phase11_source_types(client):
    for source_type in ("deep_research", "web_clip"):
        response = client.post(
            "/api/documents",
            json={"title": f"Phase 11 {source_type}", "source_type": source_type},
        )

        assert response.status_code == 200
        assert response.json()["source_type"] == source_type


def test_job_status_supports_processing_jobs_without_document(client, db):
    job = IngestionJob(
        user_id="dev-user-id",
        document_id=None,
        job_type="deep_research",
        status="processing",
        message="Researching sources",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "processing"
    assert data["document"] is None
    assert data["chunks_created"] == 0
    assert data["message"] == "Researching sources"


def test_api_key_scope_and_revocation_for_clip_endpoint(client, db):
    create_response = client.post(
        "/api/apikeys/",
        json={"description": "Clipper", "scopes": "capture_page"},
    )
    assert create_response.status_code == 200
    raw_key = create_response.json()["raw_key"]

    list_response = client.get("/api/apikeys/")
    assert list_response.status_code == 200
    assert "raw_key" not in list_response.json()[0]

    doc = Document(
        user_id="dev-user-id",
        title="Clipped Page",
        source_type="web_clip",
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job = IngestionJob(
        user_id="dev-user-id",
        document_id=doc.id,
        job_type="text_ingestion",
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    with patch("app.api.routes.ingest.process_web_clip", return_value=job):
        clip_response = client.post(
            "/api/ingest/clip",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={"url": "https://example.com", "title": "Example", "selected_text": "Example text"},
        )
    assert clip_response.status_code == 200
    assert clip_response.json()["id"] == job.id

    key_id = create_response.json()["id"]
    revoke_response = client.delete(f"/api/apikeys/{key_id}")
    assert revoke_response.status_code == 204

    revoked_response = client.post(
        "/api/ingest/clip",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"url": "https://example.com", "title": "Example"},
    )
    assert revoked_response.status_code == 401


def test_api_key_missing_scope_is_forbidden(client):
    create_response = client.post(
        "/api/apikeys/",
        json={"description": "Search only", "scopes": "search"},
    )
    assert create_response.status_code == 200

    response = client.post(
        "/api/ingest/clip",
        headers={"Authorization": f"Bearer {create_response.json()['raw_key']}"},
        json={"url": "https://example.com", "title": "Example"},
    )

    assert response.status_code == 403


def test_flashcard_due_excludes_drafts_and_review_requires_active(client, db):
    doc = Document(user_id="dev-user-id", title="Study Doc", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    draft = Flashcard(
        user_id="dev-user-id",
        document_id=doc.id,
        front="Draft question?",
        back="Draft answer",
        status="draft",
        next_review_date=utc_now() - timedelta(days=1),
    )
    active = Flashcard(
        user_id="dev-user-id",
        document_id=doc.id,
        front="Active question?",
        back="Active answer",
        status="active",
        next_review_date=utc_now() - timedelta(days=1),
    )
    db.add_all([draft, active])
    db.commit()
    db.refresh(draft)
    db.refresh(active)

    due_response = client.get("/api/flashcards/due")
    assert due_response.status_code == 200
    assert [card["id"] for card in due_response.json()] == [active.id]

    draft_review = client.post(f"/api/flashcards/{draft.id}/review", json={"score": 3})
    assert draft_review.status_code == 400

    active_review = client.post(f"/api/flashcards/{active.id}/review", json={"score": 4})
    assert active_review.status_code == 200
    assert active_review.json()["status"] == "success"


def test_start_deep_research_queues_background_job(client, mock_background_tasks):
    response = client.post(
        "/api/rag/deep-research",
        json={"question": "Produce a report about my indexed material."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_type"] == "deep_research"
    assert data["status"] == "queued"
    mock_background_tasks.assert_called_once()

    status_response = client.get(f"/api/rag/jobs/{data['id']}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"
