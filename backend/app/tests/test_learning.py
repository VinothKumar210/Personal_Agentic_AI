import pytest
import json
from app.models.document import LearningProfile, LearningRecommendation, Document, DocumentChunk

def test_create_list_get_delete_profile(client, db):
    # Create profile
    response = client.post("/api/learning/profiles", json={
        "goal_title": "Become a backend wizard",
        "target_role": "backend_engineer",
        "current_level": "beginner",
        "focus_keywords": ["python", "apis"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["goal_title"] == "Become a backend wizard"
    assert data["target_role"] == "backend_engineer"
    profile_id = data["id"]
    
    # List profiles
    response = client.get("/api/learning/profiles")
    assert response.status_code == 200
    assert len(response.json()) >= 1
    
    # Get profile
    response = client.get(f"/api/learning/profiles/{profile_id}")
    assert response.status_code == 200
    assert response.json()["id"] == profile_id
    
    # Delete profile
    response = client.delete(f"/api/learning/profiles/{profile_id}")
    assert response.status_code == 200
    
    # Get profile again should 404
    response = client.get(f"/api/learning/profiles/{profile_id}")
    assert response.status_code == 404

def test_analyze_no_documents_safe_response(client, db):
    response = client.post("/api/learning/analyze", json={
        "target_role": "llm_engineer"
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["strengths"]) == 0
    assert len(data["gaps"]) > 0
    assert len(data["recommendations"]) == 0
    assert "insufficient" in data["message"].lower()

def test_analyze_metadata_only_document_safe_response(client, db):
    # Create a ready document with NO chunks
    doc = Document(user_id="dev-user-id", title="Empty Doc", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    
    response = client.post("/api/learning/analyze", json={
        "target_role": "llm_engineer"
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["strengths"]) == 0
    assert len(data["gaps"]) > 0
    assert len(data["recommendations"]) == 0
    assert "insufficient" in data["message"].lower()

def test_invalid_target_role(client):
    response = client.post("/api/learning/analyze", json={
        "target_role": "fake_role"
    })
    assert response.status_code == 422

def test_analyze_with_chunks_replaces_old_recs(client, db):
    # Add a document with RAG and embeddings
    doc = Document(user_id="dev-user-id", title="LLM Guide", source_type="text", status="ready")
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, text="I learned about RAG and vector database.", character_count=50)
    db.add(chunk)
    db.commit()
    
    # Create profile
    response = client.post("/api/learning/profiles", json={
        "goal_title": "AI master",
        "target_role": "llm_engineer"
    })
    profile_id = response.json()["id"]
    
    # Analyze
    response = client.post("/api/learning/analyze", json={
        "profile_id": profile_id,
        "max_recommendations": 5
    })
    assert response.status_code == 200
    data = response.json()
    assert "rag" in data["strengths"]
    assert "vector_database" in data["strengths"]
    assert "chunking" in data["gaps"]
    
    assert len(data["recommendations"]) > 0
    assert len(data["recommendations"]) <= 5
    
    # Check DB
    recs = db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == profile_id).all()
    assert len(recs) == len(data["recommendations"])
    
    # Verify evidence json
    evidence = json.loads(recs[0].evidence_json)
    assert evidence["source"] == "heuristic"
    assert "matched_strengths" in evidence
    
    # Run analysis again to ensure old recs are deleted
    response2 = client.post("/api/learning/analyze", json={
        "profile_id": profile_id,
        "max_recommendations": 3
    })
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["recommendations"]) <= 3
    
    recs2 = db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == profile_id).all()
    assert len(recs2) <= 3

def test_missing_profile_id_and_target_role(client):
    response = client.post("/api/learning/analyze", json={})
    assert response.status_code == 422

def test_invalid_profile_id(client):
    response = client.post("/api/learning/analyze", json={
        "profile_id": "00000000-0000-0000-0000-000000000000"
    })
    assert response.status_code == 404

def test_profileless_analysis_persistence(client, db):
    # Add enough evidence
    doc = Document(user_id="dev-user-id", title="Backend Guide", source_type="text", status="ready")
    db.add(doc)
    db.flush()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, text="I learned about apis and database design.", character_count=50)
    db.add(chunk)
    db.commit()

    # Analyze backend_engineer with no profile
    response = client.post("/api/learning/analyze", json={
        "target_role": "backend_engineer",
        "max_recommendations": 3
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["recommendations"]) > 0

    # Assert matching LearningRecommendation rows exist with profile_id is None
    recs = db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == None).all()
    assert len(recs) == len(data["recommendations"])

    # Re-run and assert old profile-less recommendations are replaced
    response2 = client.post("/api/learning/analyze", json={
        "target_role": "backend_engineer",
        "max_recommendations": 2
    })
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["recommendations"]) <= 2

    recs2 = db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == None).all()
    assert len(recs2) <= 2

def test_focus_keywords_as_evidence(client, db):
    # Create profile with focus keywords
    response = client.post("/api/learning/profiles", json={
        "goal_title": "AI master",
        "target_role": "llm_engineer",
        "focus_keywords": ["rag", "embeddings"]
    })
    profile_id = response.json()["id"]

    # Analyze that profile (no documents or chunks created)
    response = client.post("/api/learning/analyze", json={
        "profile_id": profile_id,
        "max_recommendations": 5
    })
    assert response.status_code == 200
    data = response.json()
    
    # Expect 'rag' and 'embeddings' in strengths
    assert "rag" in data["strengths"]
    assert "embeddings" in data["strengths"]
    
    # Expect remaining LLM engineer concepts in gaps (like chunking, evaluation, etc)
    assert "chunking" in data["gaps"]
    assert "evaluation" in data["gaps"]
