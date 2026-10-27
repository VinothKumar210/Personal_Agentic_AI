import pytest
from fastapi.testclient import TestClient
from app.models.document import Document, DocumentChunk, Collection, Tag
from app.models.chat import Conversation, ChatMessage
from app.models.user import User

def test_export_returns_user_records_only(client, db, test_user, test_user_2):
    # Create records for test_user
    doc1 = Document(id="doc-user-1", user_id=test_user.id, title="User 1 Doc", source_type="file", status="completed", content_hash="hash1")
    col1 = Collection(id="col-user-1", user_id=test_user.id, name="User 1 Col")
    tag1 = Tag(id="tag-user-1", user_id=test_user.id, name="User 1 Tag")
    doc1.collections.append(col1)
    doc1.tags.append(tag1)
    chunk1 = DocumentChunk(id="chunk-user-1", document_id="doc-user-1", chunk_index=0, text="hello world", character_count=11, embedding_status="indexed")
    
    # Create record for test_user_2
    doc2 = Document(id="doc-user-2", user_id=test_user_2.id, title="User 2 Doc", source_type="file", status="completed", content_hash="hash2")
    
    db.add_all([doc1, col1, tag1, chunk1, doc2])
    db.commit()

    res = client.get("/api/export")
    assert res.status_code == 200
    data = res.json()
    
    assert data["manifest"]["user_email"] == test_user.email
    assert data["manifest"]["counts"]["documents"] == 1
    assert data["manifest"]["counts"]["collections"] == 1
    assert data["manifest"]["counts"]["tags"] == 1
    assert data["manifest"]["counts"]["chunks"] == 1
    
    doc_ids = [d["id"] for d in data["documents"]]
    assert "doc-user-1" in doc_ids
    assert "doc-user-2" not in doc_ids
    
    # Ensure no secrets or raw file paths exist in the serialized bundle string
    bundle_str = str(data)
    assert "hashed_password" not in bundle_str
    assert "storage/originals" not in bundle_str

def test_dry_run_restore(client, db, test_user):
    res = client.get("/api/export")
    bundle = res.json()
    
    restore_res = client.post("/api/restore?mode=dry_run", json={"mode": "dry_run", "bundle": bundle})
    assert restore_res.status_code == 200
    r_data = restore_res.json()
    assert r_data["mode"] == "dry_run"
    assert r_data["skipped_records"] == 0
    assert r_data["remapped_ids"] == 0
    assert "No data was modified" in r_data["message"]

def test_merge_restore_remaps_and_skips(client, db, test_user):
    # Ensure Col 1 and Tag 1 exist
    col = Collection(id="col-merge-1", user_id=test_user.id, name="Merge Col")
    tag = Tag(id="tag-merge-1", user_id=test_user.id, name="Merge Tag")
    doc = Document(id="doc-merge-1", user_id=test_user.id, title="Merge Doc", source_type="file", status="completed")
    db.add_all([col, tag, doc])
    db.commit()
    
    res = client.get("/api/export")
    bundle = res.json()
    
    # Modify bundle doc title so it doesn't match by stable identity (title+source_type)
    # but keep same ID "doc-merge-1" which will collide in DB and trigger remapping
    for d in bundle["documents"]:
        if d["id"] == "doc-merge-1":
            d["title"] = "Modified Title For Merge"
            
    restore_res = client.post("/api/restore?mode=merge", json={"mode": "merge", "bundle": bundle})
    assert restore_res.status_code == 200
    r_data = restore_res.json()
    
    # Collection and Tag should be skipped due to same name (stable identity)
    assert r_data["skipped_records"] >= 2
    # Document should be remapped to a new ID due to collision on doc-merge-1
    assert r_data["remapped_ids"] >= 1
    
    # Check that the modified doc exists in DB with new ID
    new_docs = db.query(Document).filter(Document.title == "Modified Title For Merge", Document.user_id == test_user.id).all()
    assert len(new_docs) == 1
    assert new_docs[0].id != "doc-merge-1"

def test_replace_restore_deletes_current_user_only(client, db, test_user, test_user_2):
    # Setup test_user doc and chunk
    doc1 = Document(id="doc-rep-1", user_id=test_user.id, title="User 1 Replace Doc", source_type="file", status="completed")
    chunk1 = DocumentChunk(id="chunk-rep-1", document_id="doc-rep-1", chunk_index=0, text="replace chunk", character_count=13, embedding_status="indexed")
    
    # Setup test_user_2 doc
    doc2 = Document(id="doc-rep-2", user_id=test_user_2.id, title="User 2 Safe Doc", source_type="file", status="completed")
    
    db.add_all([doc1, chunk1, doc2])
    db.commit()
    
    # Export bundle for test_user
    res = client.get("/api/export")
    bundle = res.json()
    
    # Now execute replace mode restore
    restore_res = client.post("/api/restore?mode=replace", json={"mode": "replace", "bundle": bundle})
    assert restore_res.status_code == 200
    
    # Verify User 2's document was NOT touched
    user2_doc = db.query(Document).filter(Document.id == "doc-rep-2").first()
    assert user2_doc is not None
    assert user2_doc.title == "User 2 Safe Doc"
    
    # Verify User 1's chunk was restored with embedding_status="pending"
    restored_chunk = db.query(DocumentChunk).filter(DocumentChunk.text == "replace chunk").first()
    assert restored_chunk is not None
    assert restored_chunk.embedding_status == "pending"

def test_restore_malformed_bundle(client):
    res = client.post("/api/restore?mode=dry_run", json={"mode": "dry_run", "bundle": {"manifest": "invalid"}})
    assert res.status_code in [400, 422]
