import pytest
import uuid
from unittest.mock import patch, MagicMock

@patch("app.services.groq_client.Groq")
def test_generate_document_summary_empty(mock_groq):
    from app.services.groq_client import generate_document_summary
    with pytest.raises(ValueError, match="No context chunks provided"):
        generate_document_summary("Title", [])
    mock_groq.assert_not_called()

@patch("app.services.groq_client.Groq")
def test_generate_collection_summary_empty(mock_groq):
    from app.services.groq_client import generate_collection_summary
    with pytest.raises(ValueError, match="No context chunks provided"):
        generate_collection_summary("Col", [])
    mock_groq.assert_not_called()

def test_collection_summary_400_no_chunks(client, db):
    from app.models.document import Collection, Document
    col_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    col = Collection(user_id="dev-user-id", id=col_id, name="Col with doc")
    doc = Document(user_id="dev-user-id", id=doc_id, title="Empty Doc", source_type="txt", status="ready")
    col.documents.append(doc)
    db.add(col)
    db.add(doc)
    db.commit()
    
    response = client.post(f"/api/collections/{col_id}/summary", json={})
    assert response.status_code == 400
    assert "no chunks" in response.json()["detail"].lower()

def test_document_summary_404(client):
    doc_id = str(uuid.uuid4())
    response = client.post(f"/api/documents/{doc_id}/summary", json={})
    assert response.status_code == 404

def test_document_summary_400_no_chunks(client, db):
    from app.models.document import Document
    doc_id = str(uuid.uuid4())
    doc = Document(user_id="dev-user-id", id=doc_id, title="Empty", source_type="txt", status="ready")
    db.add(doc)
    db.commit()
    
    response = client.post(f"/api/documents/{doc_id}/summary", json={})
    assert response.status_code == 400
    assert "no chunks" in response.json()["detail"].lower()

@patch("app.services.summary_service.generate_document_summary")
def test_document_summary_success(mock_generate, client, db):
    mock_generate.return_value = "This is a summary"
    
    from app.models.document import Document, DocumentChunk
    doc_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    doc = Document(user_id="dev-user-id", id=doc_id, title="Full", source_type="txt", status="ready")
    chunk = DocumentChunk(id=chunk_id, document_id=doc_id, chunk_index=0, text="hello", character_count=5)
    db.add(doc)
    db.add(chunk)
    db.commit()

    response = client.post(f"/api/documents/{doc_id}/summary", json={})
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "This is a summary"
    assert data["target_type"] == "document"
    
    db.refresh(doc)
    assert doc.summary == "This is a summary"

def test_collection_summary_404(client):
    col_id = str(uuid.uuid4())
    response = client.post(f"/api/collections/{col_id}/summary", json={})
    assert response.status_code == 404

def test_collection_summary_400_no_docs(client, db):
    from app.models.document import Collection
    col_id = str(uuid.uuid4())
    col = Collection(user_id="dev-user-id", id=col_id, name="Empty Col")
    db.add(col)
    db.commit()
    
    response = client.post(f"/api/collections/{col_id}/summary", json={})
    assert response.status_code == 400
    assert "no associated documents" in response.json()["detail"].lower()

@patch("app.services.summary_service.generate_collection_summary")
def test_collection_summary_success(mock_generate, client, db):
    mock_generate.return_value = "Col summary"
    
    from app.models.document import Document, DocumentChunk, Collection
    col_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    col = Collection(user_id="dev-user-id", id=col_id, name="Full Col")
    doc = Document(user_id="dev-user-id", id=doc_id, title="Doc 3", source_type="txt", status="ready")
    col.documents.append(doc)
    chunk = DocumentChunk(id=chunk_id, document_id=doc_id, chunk_index=0, text="world", character_count=5)
    
    db.add(col)
    db.add(doc)
    db.add(chunk)
    db.commit()

    response = client.post(f"/api/collections/{col_id}/summary", json={})
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Col summary"
    assert data["target_type"] == "collection"
    
    db.refresh(col)
    assert col.summary == "Col summary"
