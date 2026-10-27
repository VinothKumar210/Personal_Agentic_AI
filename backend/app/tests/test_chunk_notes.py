import pytest
from app.models.document import Document, DocumentChunk, ChunkNote
from app.services.export_service import build_export_bundle
from app.services.restore_service import restore_export_bundle

def test_create_list_delete_notes(client, db, test_user):
    # 1. Create a document and chunk
    doc = Document(
        id="doc-note-1",
        user_id=test_user.id,
        title="Note Taking Guide",
        source_type="text",
        status="completed"
    )
    db.add(doc)
    
    chunk = DocumentChunk(
        id="chunk-note-1",
        document_id="doc-note-1",
        chunk_index=0,
        text="This is important information to remember.",
        character_count=40
    )
    db.add(chunk)
    db.commit()

    # 2. Add note via endpoint
    res = client.post(
        f"/api/documents/doc-note-1/chunks/chunk-note-1/notes",
        json={"note_text": "Key takeaway: remember this."}
    )
    assert res.status_code == 201, res.text
    note_data = res.json()
    assert note_data["note_text"] == "Key takeaway: remember this."
    note_id = note_data["id"]

    # 3. List notes for document
    res_list = client.get("/api/documents/doc-note-1/notes")
    assert res_list.status_code == 200
    notes = res_list.json()
    assert len(notes) == 1
    assert notes[0]["id"] == note_id

    # 4. Delete note
    res_del = client.delete(f"/api/documents/notes/{note_id}")
    assert res_del.status_code == 204

    # 5. Verify deletion
    res_list2 = client.get("/api/documents/doc-note-1/notes")
    assert len(res_list2.json()) == 0

def test_note_user_isolation(client, db, test_user, test_user_2):
    doc = Document(
        id="doc-iso-1",
        user_id=test_user.id,
        title="Secret Doc",
        source_type="text",
        status="completed"
    )
    db.add(doc)
    chunk = DocumentChunk(
        id="chunk-iso-1",
        document_id="doc-iso-1",
        chunk_index=0,
        text="Confidential text.",
        character_count=18
    )
    db.add(chunk)
    note = ChunkNote(
        id="note-iso-1",
        user_id=test_user.id,
        document_id="doc-iso-1",
        chunk_id="chunk-iso-1",
        note_text="My private note."
    )
    db.add(note)
    db.commit()

    # User 2 tries to delete note
    from app.api.deps import get_current_user
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: test_user_2

    res_del = client.delete("/api/documents/notes/note-iso-1")
    assert res_del.status_code == 404

    # Restore default user
    app.dependency_overrides.clear()

def test_export_restore_notes(db, test_user):
    doc = Document(
        id="doc-exp-1",
        user_id=test_user.id,
        title="Export Doc",
        source_type="text",
        status="completed"
    )
    db.add(doc)
    chunk = DocumentChunk(
        id="chunk-exp-1",
        document_id="doc-exp-1",
        chunk_index=0,
        text="Export chunk text.",
        character_count=18
    )
    db.add(chunk)
    note = ChunkNote(
        id="note-exp-1",
        user_id=test_user.id,
        document_id="doc-exp-1",
        chunk_id="chunk-exp-1",
        note_text="Exported note."
    )
    db.add(note)
    db.commit()

    bundle = build_export_bundle(db, test_user)
    assert len(bundle.chunk_notes) == 1
    assert bundle.chunk_notes[0].note_text == "Exported note."
    assert bundle.manifest.counts["chunk_notes"] == 1

    # Restore in replace mode
    res = restore_export_bundle(db, test_user, bundle, mode="replace")
    assert res.mode == "replace"
    assert res.counts["chunk_notes"] == 1
    
    # Verify in DB
    restored_notes = db.query(ChunkNote).filter(ChunkNote.user_id == test_user.id).all()
    assert len(restored_notes) == 1
    assert restored_notes[0].note_text == "Exported note."
