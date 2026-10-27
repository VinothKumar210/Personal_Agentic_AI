import pytest
from app.models.document import Document, DocumentChunk, TopicCluster, ClusterAssignment
from app.schemas.topics import TopicAnalysisRequest
from app.services.topic_service import analyze_topics

def test_analyze_no_chunks(db):
    request = TopicAnalysisRequest(min_clusters=2, max_clusters=5, min_chunks=5)
    clusters, chunks_analyzed, message = analyze_topics(db, request, user_id="dev-user-id")
    assert len(clusters) == 0
    assert chunks_analyzed == 0
    assert "not enough" in message.lower()

def test_analyze_creates_clusters_and_replaces(db):
    doc = Document(user_id="dev-user-id", title="Science Doc", source_type="text", status="ready")
    db.add(doc)
    db.flush()
    texts = [
        "quantum physics and mechanics",
        "quantum theory of entanglement",
        "quantum computing applications",
        "biological cells and dna",
        "genetics and dna sequencing",
        "cellular biology structures"
    ]
    for i, t in enumerate(texts):
        chunk = DocumentChunk(document_id=doc.id, chunk_index=i, text=t, character_count=len(t))
        db.add(chunk)
    db.commit()

    request = TopicAnalysisRequest(min_clusters=2, max_clusters=2, min_chunks=5)
    clusters, chunks_analyzed, message = analyze_topics(db, request, user_id="dev-user-id")
    
    assert len(clusters) == 2
    assert chunks_analyzed == 6
    assert db.query(ClusterAssignment).count() == 6
    assert db.query(TopicCluster).count() == 2

def test_trigger_auto_cluster_endpoint(client, db):
    response = client.post("/api/topics/auto-cluster", json={
        "min_clusters": 2,
        "max_clusters": 5,
        "min_chunks": 5
    })
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

def test_list_and_get_topic_clusters(client, db):
    tc = TopicCluster(user_id="dev-user-id", name="Test Cluster", document_count=1, chunk_count=1)
    db.add(tc)
    db.commit()
    db.refresh(tc)
    
    response = client.get("/api/topics")
    assert response.status_code == 200
    data = response.json()
    assert len(data["clusters"]) >= 1
    assert data["clusters"][0]["id"] == tc.id
    
    response = client.get(f"/api/topics/{tc.id}")
    assert response.status_code == 200
    assert response.json()["id"] == tc.id
