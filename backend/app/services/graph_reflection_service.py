import json
import logging
from typing import List, Dict, Any, Tuple, Set
from sqlalchemy.orm import Session
from app.models.document import KnowledgeNode, KnowledgeEdge
from app.models.curation import CurationSuggestion
from app.services.embedding_service import embed_texts
from app.services.groq_client import call_groq, parse_json_from_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

def run_graph_reflection_analysis(db: Session, user_id: str) -> List[CurationSuggestion]:
    """
    Analyzes active, non-pruned KnowledgeGraphNodes to discover:
    1. Soft pruning candidates (isolated nodes with zero edges and low frequency).
    2. Semantic bridge candidates between disconnected or conceptually related nodes across documents.
    Returns a list of reviewable CurationSuggestion models (not committed to DB yet).
    """
    nodes = db.query(KnowledgeNode).filter(
        KnowledgeNode.user_id == user_id,
        KnowledgeNode.is_pruned == False
    ).all()

    if not nodes:
        return []

    edges = db.query(KnowledgeEdge).filter(
        KnowledgeEdge.user_id == user_id
    ).all()

    # Build adjacency set to quickly check degree and existing connections
    connected_pairs: Set[Tuple[str, str]] = set()
    node_degree: Dict[str, int] = {n.id: 0 for n in nodes}

    for edge in edges:
        s, t = str(edge.source_node_id), str(edge.target_node_id)
        connected_pairs.add((s, t))
        connected_pairs.add((t, s))
        if s in node_degree:
            node_degree[s] += 1
        if t in node_degree:
            node_degree[t] += 1

    suggestions: List[CurationSuggestion] = []

    # 1. Soft Pruning Suggestions
    for node in nodes:
        if node_degree.get(node.id, 0) == 0 and node.frequency <= 1:
            sugg = CurationSuggestion(
                user_id=user_id,
                suggestion_type="graph_prune",
                source_ids_json=json.dumps([node.id]),
                proposed_payload_json=json.dumps({
                    "node_id": node.id,
                    "is_pruned": True,
                    "pruned_reason": "Zero-degree isolated concept node with low co-occurrence frequency.",
                    "confidence_score": 0.3
                }),
                confidence=0.88,
                explanation=f"Isolated node '{node.label}' has 0 connected edges and only appeared once across documents.",
                provenance_metadata_json=json.dumps({
                    "id": node.id,
                    "label": node.label,
                    "node_type": node.node_type,
                    "frequency": node.frequency,
                    "action": "soft_prune"
                }),
                status="pending"
            )
            suggestions.append(sugg)

    # 2. Semantic Bridge Discovery (evaluate top frequency/connected nodes not directly linked)
    active_nodes = [n for n in nodes if node_degree.get(n.id, 0) > 0 or n.frequency >= 2]
    # Cap at top 40 nodes by frequency to keep embedding computation/comparisons bounded
    active_nodes.sort(key=lambda n: n.frequency, reverse=True)
    candidate_nodes = active_nodes[:40]

    if len(candidate_nodes) >= 2:
        try:
            texts = [f"{n.label}: {n.description or ''}" for n in candidate_nodes]
            embeddings = embed_texts(texts)

            for i in range(len(candidate_nodes)):
                for j in range(i + 1, len(candidate_nodes)):
                    n1, n2 = candidate_nodes[i], candidate_nodes[j]
                    if (n1.id, n2.id) in connected_pairs:
                        continue

                    # Dot product of normalized vectors
                    sim = sum(x * y for x, y in zip(embeddings[i], embeddings[j]))
                    if sim >= 0.76:
                        # Prompt Groq to evaluate semantic bridge
                        prompt = f"""You are an autonomous knowledge graph reflection agent.
Evaluate whether a cross-document conceptual bridge exists between these two nodes in a knowledge base:
Node A (ID: {n1.id}, Label: '{n1.label}', Type: {n1.node_type}): "{n1.description or 'No description'}"
Node B (ID: {n2.id}, Label: '{n2.label}', Type: {n2.node_type}): "{n2.description or 'No description'}"

Determine if linking these two nodes adds valuable structural context to the knowledge graph.
Return valid JSON in the exact format:
{{
  "should_bridge": boolean,
  "relation_type": string describing the relation (e.g. "conceptually_related", "depends_on", "implements", "part_of"),
  "weight": float between 0.0 and 1.0 representing edge strength,
  "confidence": float between 0.0 and 1.0,
  "explanation": "Brief reasoning explaining why these concepts bridge across documents"
}}"""
                        try:
                            resp = call_groq(
                                prompt=prompt,
                                model=settings.GROQ_MODEL,
                                temperature=0.1,
                                max_tokens=250
                            )
                            parsed = parse_json_from_llm(resp)
                            if not isinstance(parsed, dict):
                                continue

                            if parsed.get("should_bridge") is True and float(parsed.get("confidence", 0.0)) >= 0.72:
                                rel_type = str(parsed.get("relation_type", "conceptually_related")).strip()
                                weight = float(parsed.get("weight", 0.8))
                                explanation = str(parsed.get("explanation", f"Semantic similarity {sim:.2f}")).strip()
                                conf = float(parsed.get("confidence", 0.8))

                                sugg = CurationSuggestion(
                                    user_id=user_id,
                                    suggestion_type="graph_bridge",
                                    source_ids_json=json.dumps([n1.id, n2.id]),
                                    proposed_payload_json=json.dumps({
                                        "source_node_id": n1.id,
                                        "target_node_id": n2.id,
                                        "relation_type": f"inferred_bridge:{rel_type}",
                                        "weight": round(weight, 2),
                                        "evidence_json": json.dumps({
                                            "reason": explanation,
                                            "inferred_by": "graph_reflection_service",
                                            "similarity": round(sim, 3)
                                        })
                                    }),
                                    confidence=round(conf, 2),
                                    explanation=explanation,
                                    provenance_metadata_json=json.dumps({
                                        "source_node": {"id": n1.id, "label": n1.label, "type": n1.node_type},
                                        "target_node": {"id": n2.id, "label": n2.label, "type": n2.node_type},
                                        "similarity_score": round(sim, 3),
                                        "action": "inferred_bridge"
                                    }),
                                    status="pending"
                                )
                                suggestions.append(sugg)
                        except Exception as e:
                            logger.warning(f"Groq reflection failed for graph bridge ({n1.id}, {n2.id}): {e}")
        except Exception as e:
            logger.error(f"Error during graph reflection embedding comparison: {e}")

    return suggestions
