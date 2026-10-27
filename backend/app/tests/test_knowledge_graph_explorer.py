from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentChunk, KnowledgeNode
from app.services import knowledge_graph_service

def test_knowledge_graph_explorer_endpoints(client: TestClient, db: Session):
    # Create document and chunks for user
    doc = Document(
        title="AI Engineering Notes",
        original_filename="ai_notes.md",
        source_type="markdown",
        status="ready",
        user_id="dev-user-id"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunk1 = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        text="FastAPI and SQLAlchemy are great for AI backends. Chroma vector database handles embeddings.",
        character_count=85
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        chunk_index=1,
        text="Chroma vector database integrates cleanly with FastAPI for retrieval augmented generation.",
        character_count=88
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    # Build knowledge graph via API
    res = client.post(
        "/api/knowledge-graph/build",
        json={"min_frequency": 1, "max_nodes": 50, "cooccurrence_window": 2}
    )
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert len(data["nodes"]) > 0

    first_node = data["nodes"][0]
    assert "document_ids" in first_node
    assert isinstance(first_node["document_ids"], list)

    node_id = first_node["id"]

    # Test GET /api/knowledge-graph/nodes/{node_id}/documents
    docs_res = client.get(
        f"/api/knowledge-graph/nodes/{node_id}/documents"
    )
    assert docs_res.status_code == 200
    docs_list = docs_res.json()
    assert isinstance(docs_list, list)

def test_knowledge_graph_node_not_found(client: TestClient):
    res = client.get(
        "/api/knowledge-graph/nodes/non-existent-id/documents"
    )
    assert res.status_code == 404
