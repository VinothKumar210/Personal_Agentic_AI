from unittest.mock import patch

from app.models.document import Document, DocumentChunk, Tag
from app.services.tagging_service import normalize_tag_name, display_case, generate_tags_for_document

def test_normalize_tag_name():
    assert normalize_tag_name("Machine Learning") == "machine learning"
    assert normalize_tag_name(" AI ") == "ai"
    assert normalize_tag_name("A.I.") == "ai"

def test_display_case():
    assert display_case("machine learning") == "Machine Learning"
    assert display_case(" artificial intelligence ") == "Artificial Intelligence"
    assert display_case("a.i.") == "AI"

def test_generate_tags_reuses_normalized_existing_tags(db):
    doc = Document(user_id="dev-user-id", title="AI Notes", source_type="text", status="ready")
    existing = Tag(user_id="dev-user-id", name="AI")
    db.add_all([doc, existing])
    db.flush()
    db.add(DocumentChunk(document_id=doc.id, chunk_index=0, text="Artificial intelligence and LLM retrieval notes.", character_count=56))
    db.commit()
    db.refresh(doc)
    db.refresh(existing)

    with patch("app.services.tagging_service.groq_client.generate_completion", return_value='{"tags": ["A.I.", "LLM"]}'):
        tags = generate_tags_for_document(db, doc.id, "dev-user-id")

    assert [tag.name for tag in tags] == ["AI", "LLM"]
    assert db.query(Tag).filter(Tag.user_id == "dev-user-id", Tag.name == "AI").count() == 1
    assert db.query(Tag).filter(Tag.user_id == "dev-user-id", Tag.name == "LLM").count() == 1
