import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.curation import CurationSuggestion, CurationLog, KnowledgeBriefing
from app.models.memory import PersonalMemory
from app.models.document import KnowledgeNode, KnowledgeEdge
from app.schemas.memory import PersonalMemoryCreate
from app.services.memory_service import create_memory, delete_memory, index_memory_item
from app.services.vector_service import delete_chunks_by_ids
from app.services.memory_consolidation_service import run_memory_consolidation_analysis
from app.services.graph_reflection_service import run_graph_reflection_analysis

logger = logging.getLogger(__name__)

def utc_now():
    return datetime.now(timezone.utc)

def execute_curation_sweep(db: Session, user_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Executes a complete curation & reflection sweep across memories and graph nodes.
    Defaults to dry_run=True (creating reviewable suggestions in curation_suggestions).
    """
    logger.info(f"Starting curation sweep for user {user_id} (dry_run={dry_run})")
    
    # 1. Run consolidation & reflection analysis
    memory_suggs = run_memory_consolidation_analysis(db, user_id)
    graph_suggs = run_graph_reflection_analysis(db, user_id)
    
    all_suggs = memory_suggs + graph_suggs
    for s in all_suggs:
        db.add(s)
    db.commit()
    for s in all_suggs:
        db.refresh(s)

    # Counts breakdown
    counts = {
        "memory_merge": sum(1 for s in all_suggs if s.suggestion_type == "memory_merge"),
        "memory_contradiction": sum(1 for s in all_suggs if s.suggestion_type == "memory_contradiction"),
        "graph_bridge": sum(1 for s in all_suggs if s.suggestion_type == "graph_bridge"),
        "graph_prune": sum(1 for s in all_suggs if s.suggestion_type == "graph_prune")
    }

    # 2. Synthesize a Knowledge Briefing digest
    summary_lines = [
        f"# Knowledge Curation Briefing ({utc_now().strftime('%Y-%m-%d')})",
        "",
        "During our automated reflection sweep across your personal memories and knowledge graph, we discovered:",
        f"- **{counts['memory_merge']}** exact or high-similarity memory clusters to merge.",
        f"- **{counts['memory_contradiction']}** potential preference updates or contradictions.",
        f"- **{counts['graph_bridge']}** inferred cross-document conceptual bridges.",
        f"- **{counts['graph_prune']}** isolated or low-relevance nodes recommended for soft pruning.",
        "",
        "### Top Highlights"
    ]
    
    highlights: List[Dict[str, Any]] = []
    for s in all_suggs[:5]:
        summary_lines.append(f"- **{s.suggestion_type.replace('_', ' ').title()}**: {s.explanation} *(Confidence: {int(s.confidence * 100)}%)*")
        highlights.append({
            "id": s.id,
            "type": s.suggestion_type,
            "explanation": s.explanation,
            "confidence": s.confidence
        })

    summary_markdown = "\n".join(summary_lines)
    briefing = KnowledgeBriefing(
        user_id=user_id,
        title=f"Curation Digest: {len(all_suggs)} Suggestions Discovered",
        summary_markdown=summary_markdown,
        highlights_json=json.dumps(highlights)
    )
    db.add(briefing)

    # 3. Log curation event
    log = CurationLog(
        user_id=user_id,
        sweep_type="dry_run" if dry_run else "auto",
        items_processed=len(all_suggs),
        items_merged=0,
        details_json=json.dumps(counts),
        status="completed"
    )
    db.add(log)
    db.commit()
    db.refresh(briefing)
    db.refresh(log)

    return {
        "sweep_type": "dry_run" if dry_run else "auto",
        "items_processed": len(all_suggs),
        "suggestions_created": len(all_suggs),
        "details": counts,
        "suggestions": all_suggs,
        "briefing": briefing
    }

def apply_suggestion(db: Session, suggestion_id: str, user_id: str) -> CurationSuggestion:
    sugg = db.query(CurationSuggestion).filter(
        CurationSuggestion.id == suggestion_id,
        CurationSuggestion.user_id == user_id
    ).first()

    if not sugg:
        raise ValueError(f"Suggestion {suggestion_id} not found.")
    if sugg.status not in ("pending", "approved"):
        raise ValueError(f"Cannot apply suggestion with status '{sugg.status}'. Must be pending or approved.")

    payload = sugg.proposed_payload
    source_ids = sugg.source_ids

    if sugg.suggestion_type in ("memory_merge", "memory_contradiction"):
        # Create consolidated memory (which auto-indexes via create_memory)
        new_mem = create_memory(db, user_id, PersonalMemoryCreate(
            content=payload["content"],
            category=payload.get("category", "fact"),
            privacy_level=payload.get("privacy_level", "private"),
            source_citation=f"consolidated:{sugg.id}"
        ))
        # Mark sources as consolidated and remove them from active vector store
        for sid in source_ids:
            src = db.query(PersonalMemory).filter(PersonalMemory.id == sid, PersonalMemory.user_id == user_id).first()
            if src:
                src.is_consolidated = True
                src.consolidated_into_id = new_mem.id
                src.last_consolidated_at = utc_now()
                delete_chunks_by_ids([src.id])

    elif sugg.suggestion_type == "graph_bridge":
        edge = KnowledgeEdge(
            user_id=user_id,
            source_node_id=payload["source_node_id"],
            target_node_id=payload["target_node_id"],
            relation_type=payload.get("relation_type", "inferred_bridge:related_to"),
            weight=payload.get("weight", 0.8),
            evidence_json=payload.get("evidence_json", "{}")
        )
        db.add(edge)

    elif sugg.suggestion_type == "graph_prune":
        for nid in source_ids:
            node = db.query(KnowledgeNode).filter(KnowledgeNode.id == nid, KnowledgeNode.user_id == user_id).first()
            if node:
                node.is_pruned = True
                node.pruned_reason = payload.get("pruned_reason", "Soft pruned during background curation.")
                node.confidence_score = payload.get("confidence_score", 0.3)
                node.last_reflected_at = utc_now()

    sugg.status = "applied"
    sugg.reviewed_at = utc_now()
    db.commit()
    db.refresh(sugg)
    return sugg

def rollback_suggestion(db: Session, suggestion_id: str, user_id: str) -> CurationSuggestion:
    sugg = db.query(CurationSuggestion).filter(
        CurationSuggestion.id == suggestion_id,
        CurationSuggestion.user_id == user_id
    ).first()

    if not sugg:
        raise ValueError(f"Suggestion {suggestion_id} not found.")
    if sugg.status != "applied":
        raise ValueError(f"Cannot rollback suggestion with status '{sugg.status}'. Must be applied.")

    payload = sugg.proposed_payload
    source_ids = sugg.source_ids

    if sugg.suggestion_type in ("memory_merge", "memory_contradiction"):
        # Find and delete the target consolidated memory
        cons_mem = db.query(PersonalMemory).filter(
            PersonalMemory.source_citation == f"consolidated:{sugg.id}",
            PersonalMemory.user_id == user_id
        ).first()
        if cons_mem:
            delete_memory(db, user_id, cons_mem.id)

        # Restore source memories
        for sid in source_ids:
            src = db.query(PersonalMemory).filter(PersonalMemory.id == sid, PersonalMemory.user_id == user_id).first()
            if src:
                src.is_consolidated = False
                src.consolidated_into_id = None
                src.last_consolidated_at = None
                index_memory_item(src)

    elif sugg.suggestion_type == "graph_bridge":
        edge = db.query(KnowledgeEdge).filter(
            KnowledgeEdge.user_id == user_id,
            KnowledgeEdge.source_node_id == payload.get("source_node_id"),
            KnowledgeEdge.target_node_id == payload.get("target_node_id"),
            KnowledgeEdge.relation_type == payload.get("relation_type", "inferred_bridge:related_to")
        ).first()
        if edge:
            db.delete(edge)

    elif sugg.suggestion_type == "graph_prune":
        for nid in source_ids:
            node = db.query(KnowledgeNode).filter(KnowledgeNode.id == nid, KnowledgeNode.user_id == user_id).first()
            if node:
                node.is_pruned = False
                node.pruned_reason = None
                node.confidence_score = 1.0

    sugg.status = "rolled_back"
    sugg.reviewed_at = utc_now()
    db.commit()
    db.refresh(sugg)
    return sugg
