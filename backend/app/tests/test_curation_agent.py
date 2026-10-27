import pytest
from unittest.mock import patch, MagicMock
from app.models.memory import PersonalMemory
from app.models.document import KnowledgeNode
from app.models.curation import CurationSuggestion, KnowledgeBriefing
from app.services.memory_consolidation_service import get_most_restrictive_privacy

def test_strict_privacy_rank_function():
    assert get_most_restrictive_privacy(["public", "team", "private", "sensitive"]) == "sensitive"
    assert get_most_restrictive_privacy(["public", "team", "private"]) == "private"
    assert get_most_restrictive_privacy(["public", "team"]) == "team"
    assert get_most_restrictive_privacy(["public", "public"]) == "public"
    assert get_most_restrictive_privacy([]) == "private"

@patch("app.services.memory_service.index_chunks")
@patch("app.services.memory_service.embed_texts")
@patch("app.services.memory_consolidation_service.embed_texts")
def test_default_dry_run_curation_sweep(mock_cons_embed, mock_mem_embed, mock_index, client, db):
    mock_mem_embed.return_value = [[0.1] * 384]
    mock_cons_embed.return_value = [[0.1] * 384, [0.1] * 384]

    # Create two exact duplicate personal memories with different privacy levels
    m1 = client.post("/api/memory", json={
        "category": "preference",
        "content": "I always use PostgreSQL for production databases.",
        "privacy_level": "team",
        "source_citation": "doc 1"
    }).json()

    m2 = client.post("/api/memory", json={
        "category": "preference",
        "content": "I always use postgresql for production databases!",
        "privacy_level": "private",
        "source_citation": "doc 2"
    }).json()

    # Trigger curation sweep (defaults to dry_run=True)
    sweep_resp = client.post("/api/curation/sweep", json={"dry_run": True})
    assert sweep_resp.status_code == 200
    data = sweep_resp.json()
    assert data["sweep_type"] == "dry_run"
    assert data["suggestions_created"] >= 1
    assert data["details"]["memory_merge"] >= 1

    # Verify suggestion was created with pending status and inherited most restrictive privacy (private > team)
    suggestions = client.get("/api/curation/suggestions?status=pending").json()
    assert len(suggestions) >= 1
    merge_sugg = next(s for s in suggestions if s["suggestion_type"] == "memory_merge")
    assert merge_sugg["confidence"] == 1.0
    assert merge_sugg["proposed_payload"]["privacy_level"] == "private"
    assert set(merge_sugg["source_ids"]) == {m1["id"], m2["id"]}

    # Verify original source memories remain unmodified and not consolidated during dry_run
    db.expire_all()
    orig1 = db.query(PersonalMemory).filter_by(id=m1["id"]).first()
    orig2 = db.query(PersonalMemory).filter_by(id=m2["id"]).first()
    assert orig1.is_consolidated is False
    assert orig2.is_consolidated is False

    # Verify KnowledgeBriefing was created
    briefings = client.get("/api/curation/briefings").json()
    assert len(briefings) >= 1
    assert "Knowledge Curation Briefing" in briefings[0]["summary_markdown"]

@patch("app.services.memory_service.index_chunks")
@patch("app.services.memory_service.delete_chunks_by_ids")
@patch("app.services.memory_service.embed_texts")
@patch("app.services.memory_consolidation_service.embed_texts")
def test_approve_apply_and_rollback_suggestion(mock_cons_embed, mock_mem_embed, mock_delete, mock_index, client, db):
    mock_mem_embed.return_value = [[0.1] * 384]
    mock_cons_embed.return_value = [[0.1] * 384, [0.1] * 384]

    # Create two duplicate memories to merge
    m1 = client.post("/api/memory", json={
        "category": "fact",
        "content": "Our default API port is 8000.",
        "privacy_level": "public"
    }).json()
    m2 = client.post("/api/memory", json={
        "category": "fact",
        "content": "Our default api port is 8000!",
        "privacy_level": "team"
    }).json()

    # Trigger sweep to get suggestion
    sweep_resp = client.post("/api/curation/sweep", json={"dry_run": True})
    assert sweep_resp.status_code == 200
    suggestions = client.get("/api/curation/suggestions?status=pending").json()
    sugg = suggestions[0]
    sugg_id = sugg["id"]

    # 1. Approve suggestion
    approve_resp = client.post(f"/api/curation/suggestions/{sugg_id}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 2. Apply suggestion
    apply_resp = client.post(f"/api/curation/suggestions/{sugg_id}/apply")
    assert apply_resp.status_code == 200
    assert apply_resp.json()["status"] == "applied"

    # Verify target consolidated memory created and sources marked consolidated
    db.expire_all()
    cons_mem = db.query(PersonalMemory).filter_by(source_citation=f"consolidated:{sugg_id}").first()
    assert cons_mem is not None
    assert cons_mem.privacy_level == "team" # inherited more restrictive (team > public)

    src1 = db.query(PersonalMemory).filter_by(id=m1["id"]).first()
    src2 = db.query(PersonalMemory).filter_by(id=m2["id"]).first()
    assert src1.is_consolidated is True
    assert src1.consolidated_into_id == cons_mem.id
    assert src2.is_consolidated is True
    assert src2.consolidated_into_id == cons_mem.id

    # 3. Rollback suggestion
    rollback_resp = client.post(f"/api/curation/suggestions/{sugg_id}/rollback")
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["status"] == "rolled_back"

    # Verify consolidated memory deleted and sources restored
    db.expire_all()
    restored_cons = db.query(PersonalMemory).filter_by(id=cons_mem.id).first()
    assert restored_cons is None

    src1_after = db.query(PersonalMemory).filter_by(id=m1["id"]).first()
    src2_after = db.query(PersonalMemory).filter_by(id=m2["id"]).first()
    assert src1_after.is_consolidated is False
    assert src1_after.consolidated_into_id is None
    assert src2_after.is_consolidated is False
    assert src2_after.consolidated_into_id is None

def test_graph_reflection_soft_pruning_suggestion(client, db):
    # Create an isolated KnowledgeNode with 0 connected edges and frequency=1
    node = KnowledgeNode(
        id="test-node-isolated",
        user_id="dev-user-id",
        label="isolated-temp-concept",
        node_type="concept",
        frequency=1,
        is_pruned=False
    )
    db.add(node)
    db.commit()

    # Run curation sweep
    sweep_resp = client.post("/api/curation/sweep", json={"dry_run": True})
    assert sweep_resp.status_code == 200
    
    suggestions = client.get("/api/curation/suggestions?suggestion_type=graph_prune").json()
    assert len(suggestions) >= 1
    prune_sugg = next(s for s in suggestions if "test-node-isolated" in s["source_ids"])
    assert prune_sugg["suggestion_type"] == "graph_prune"
    assert prune_sugg["status"] == "pending"

    # Approve and Apply soft pruning
    client.post(f"/api/curation/suggestions/{prune_sugg['id']}/approve")
    client.post(f"/api/curation/suggestions/{prune_sugg['id']}/apply")

    db.expire_all()
    pruned_node = db.query(KnowledgeNode).filter_by(id="test-node-isolated").first()
    assert pruned_node.is_pruned is True
    assert "Zero-degree isolated concept node" in pruned_node.pruned_reason
