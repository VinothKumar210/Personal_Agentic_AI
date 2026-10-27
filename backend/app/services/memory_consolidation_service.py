import json
import logging
import re
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.memory import PersonalMemory
from app.models.curation import CurationSuggestion
from app.services.embedding_service import embed_texts
from app.services.groq_client import call_groq, parse_json_from_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

PRIVACY_RANK = {
    "public": 1,
    "team": 2,
    "private": 3,
    "sensitive": 4
}

def get_most_restrictive_privacy(privacies: List[str]) -> str:
    if not privacies:
        return "private"
    # Return the privacy string that has the highest rank value
    return max(privacies, key=lambda p: PRIVACY_RANK.get((p or "private").lower(), 3))

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Strip punctuation, lowercase, normalize whitespace
    cleaned = re.sub(r'[^\w\s]', '', text.lower())
    return ' '.join(cleaned.split())

def run_memory_consolidation_analysis(db: Session, user_id: str) -> List[CurationSuggestion]:
    """
    Analyzes active, non-consolidated personal memories for exact duplicates,
    embedding similarity clusters, and potential contradictions/updates using
    layered deterministic heuristics followed by Groq reflection.
    Returns a list of CurationSuggestion models (not committed to DB yet).
    """
    memories = db.query(PersonalMemory).filter(
        PersonalMemory.user_id == user_id,
        PersonalMemory.is_consolidated == False
    ).order_by(PersonalMemory.created_at.asc()).all()

    if len(memories) < 2:
        return []

    suggestions: List[CurationSuggestion] = []
    processed_ids = set()

    # Layer 1: Deterministic Exact/Near-Exact String Duplicate Detection
    norm_map: Dict[str, List[PersonalMemory]] = {}
    for mem in memories:
        norm = normalize_text(mem.content)
        if norm:
            norm_map.setdefault(norm, []).append(mem)

    for norm_text, group in norm_map.items():
        if len(group) >= 2:
            # Create a merge suggestion for this exact group
            source_ids = [m.id for m in group]
            processed_ids.update(source_ids)
            most_restrictive = get_most_restrictive_privacy([m.privacy_level for m in group])
            
            # Select the most detailed content or first
            best_content = max([m.content for m in group], key=len)
            
            sugg = CurationSuggestion(
                user_id=user_id,
                suggestion_type="memory_merge",
                source_ids_json=json.dumps(source_ids),
                proposed_payload_json=json.dumps({
                    "content": best_content,
                    "category": group[0].category,
                    "privacy_level": most_restrictive
                }),
                confidence=1.0,
                explanation="Deterministic exact text match discovered between memory entries.",
                provenance_metadata_json=json.dumps({
                    "sources": [
                        {"id": m.id, "content": m.content, "category": m.category, "privacy_level": m.privacy_level}
                        for m in group
                    ],
                    "privacy_rule": f"Most restrictive ({most_restrictive}) inherited."
                }),
                status="pending"
            )
            suggestions.append(sugg)

    # Layer 2: Vector Embedding Similarity Clustering for remaining items
    remaining = [m for m in memories if m.id not in processed_ids]
    if len(remaining) >= 2:
        try:
            texts = [m.content for m in remaining]
            embeddings = embed_texts(texts)
            
            # Pairwise cosine similarity (embeddings are normalized by embed_texts)
            pairs_to_evaluate: List[Tuple[PersonalMemory, PersonalMemory, float]] = []
            for i in range(len(remaining)):
                for j in range(i + 1, len(remaining)):
                    m1, m2 = remaining[i], remaining[j]
                    # Only evaluate if same category or if both are preferences/facts
                    sim = sum(x * y for x, y in zip(embeddings[i], embeddings[j]))
                    if sim >= 0.78:
                        pairs_to_evaluate.append((m1, m2, sim))
            
            # Layer 3 & Layer 4: Rule-based & Groq Reflection on high-similarity pairs
            for m1, m2, sim in pairs_to_evaluate:
                if m1.id in processed_ids or m2.id in processed_ids:
                    continue
                
                # Call Groq to evaluate candidate pair
                prompt = f"""You are an autonomous memory curation reflection agent.
Analyze the following two personal memory entries for the same user:
Entry 1 (ID: {m1.id}, Category: {m1.category}): "{m1.content}"
Entry 2 (ID: {m2.id}, Category: {m2.category}): "{m2.content}"

Determine whether these two entries:
1. "merge": They express the same or complementary facts/preferences and should be consolidated into one concise summary.
2. "contradiction": They express conflicting preferences or an update over time (e.g., preference shifted from X to Y), and should be synthesized into the current accurate preference.
3. "distinct": They are separate facts that happen to share keywords and should NOT be consolidated.

Return valid JSON in the exact format:
{{
  "action": "merge" | "contradiction" | "distinct",
  "proposed_content": "The unified or updated memory text if action is merge/contradiction",
  "confidence": float between 0.0 and 1.0,
  "explanation": "Brief rationale for the decision"
}}"""
                try:
                    response_text = call_groq(
                        prompt=prompt,
                        model=settings.GROQ_MODEL,
                        temperature=0.1,
                        max_tokens=300
                    )
                    parsed = parse_json_from_llm(response_text)
                    if not isinstance(parsed, dict):
                        continue
                    
                    action = parsed.get("action", "distinct")
                    confidence = float(parsed.get("confidence", 0.0))
                    proposed_content = parsed.get("proposed_content", "").strip()
                    explanation = parsed.get("explanation", f"Similarity {sim:.2f} clustering.")
                    
                    if action in ("merge", "contradiction") and confidence >= 0.75 and proposed_content:
                        most_restrictive = get_most_restrictive_privacy([m1.privacy_level, m2.privacy_level])
                        processed_ids.update([m1.id, m2.id])
                        
                        sugg = CurationSuggestion(
                            user_id=user_id,
                            suggestion_type="memory_merge" if action == "merge" else "memory_contradiction",
                            source_ids_json=json.dumps([m1.id, m2.id]),
                            proposed_payload_json=json.dumps({
                                "content": proposed_content,
                                "category": m1.category,
                                "privacy_level": most_restrictive
                            }),
                            confidence=round(confidence, 2),
                            explanation=explanation,
                            provenance_metadata_json=json.dumps({
                                "sources": [
                                    {"id": m1.id, "content": m1.content, "category": m1.category, "privacy_level": m1.privacy_level},
                                    {"id": m2.id, "content": m2.content, "category": m2.category, "privacy_level": m2.privacy_level}
                                ],
                                "similarity_score": round(sim, 3),
                                "privacy_rule": f"Most restrictive ({most_restrictive}) inherited."
                            }),
                            status="pending"
                        )
                        suggestions.append(sugg)
                except Exception as e:
                    logger.warning(f"Groq reflection failed for memory cluster ({m1.id}, {m2.id}): {e}")
        except Exception as e:
            logger.error(f"Error during vector similarity memory clustering: {e}")

    return suggestions
