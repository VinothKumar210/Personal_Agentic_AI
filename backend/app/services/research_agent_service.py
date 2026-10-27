"""
Autonomous Multi-Step Research Agent Service.

Breaks complex questions into targeted sub-queries, retrieves evidence
from multiple sources in parallel, self-corrects weak queries, and
synthesizes a comprehensive grounded answer with a transparent audit trail.
"""
import json
import uuid
import logging
from typing import Any, Dict, Generator, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.rag import RagAnswerResponse, RagCitation, RagQuestionRequest
from app.services.rag_service import evaluate_rag_confidence
from app.services.embedding_service import embed_query
from app.services.vector_service import search_chunks
from app.services.groq_client import is_groq_configured
from app.services.memory_service import gate_personal_memory_chunks, search_personal_memories

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured audit trail record
# ---------------------------------------------------------------------------

class ResearchStepRecord(BaseModel):
    """One step in the autonomous research audit trail."""
    iteration: int
    query: str
    target_sources: List[str]
    source_counts: Dict[str, int] = Field(default_factory=dict)
    status: str = "pending"  # pending | retrieved | rewritten | failed
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 1. Query Decomposition
# ---------------------------------------------------------------------------

DECOMPOSE_SYSTEM_PROMPT = """\
You are a research planner. Given a complex user question, break it into \
2-4 focused sub-queries that together cover the full scope of the question.

For each sub-query, specify which sources to search:
- "code": search indexed code chunks (functions, classes, files)
- "documents": search uploaded PDFs, text files, and notes
- "personal_memory": search user's personal memory/profile items
- "web": search the public web (only if the question explicitly asks for \
external/web information or comparisons with public standards)

IMPORTANT: Only include "web" when the user's question explicitly requires \
external information. Do NOT add "web" speculatively.

Respond ONLY with a JSON array. Each element must have:
  {"query": "...", "target_sources": ["code", "documents", ...]}

Example response:
[
  {"query": "How does the JWT authentication middleware work?", "target_sources": ["code"]},
  {"query": "What are the privacy rules for personal memories?", "target_sources": ["code", "personal_memory"]}
]
"""


def decompose_query(question: str) -> List[Dict[str, Any]]:
    """
    Use Groq LLM to decompose a complex question into targeted sub-queries
    with source routing.
    """
    if not is_groq_configured():
        # Fallback: single query targeting all local sources
        return [{"query": question, "target_sources": ["code", "documents", "personal_memory"]}]

    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": DECOMPOSE_SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        # Handle both {"queries": [...]} and direct [...] formats
        if isinstance(parsed, list):
            sub_queries = parsed
        elif isinstance(parsed, dict) and "queries" in parsed:
            sub_queries = parsed["queries"]
        else:
            # Try to extract any list value
            for v in parsed.values():
                if isinstance(v, list):
                    sub_queries = v
                    break
            else:
                sub_queries = [{"query": question, "target_sources": ["code", "documents"]}]

        # Validate structure
        validated = []
        for sq in sub_queries[:4]:
            q = sq.get("query", question) if isinstance(sq, dict) else str(sq)
            ts = sq.get("target_sources", ["code", "documents"]) if isinstance(sq, dict) else ["code", "documents"]
            validated.append({"query": q, "target_sources": ts})

        return validated if validated else [{"query": question, "target_sources": ["code", "documents"]}]

    except Exception as e:
        logger.warning(f"Query decomposition failed: {e}. Falling back to single query.")
        return [{"query": question, "target_sources": ["code", "documents", "personal_memory"]}]


# ---------------------------------------------------------------------------
# 2. Parallel Retrieval Execution
# ---------------------------------------------------------------------------

def _retrieve_local_chunks(query: str, db: Session, user_id: str, limit: int, filters: dict) -> List[Dict[str, Any]]:
    """Retrieve from vector store + hybrid reranking."""
    query_embedding = embed_query(query)
    dense_results = search_chunks(query_embedding, limit=limit * 3, filters=filters)
    try:
        from app.services.hybrid_search_service import hybrid_search_and_rerank
        results = hybrid_search_and_rerank(query, query_embedding, db, user_id, limit=limit, filters=filters, dense_results=dense_results)
    except Exception:
        results = dense_results[:limit]
    return gate_personal_memory_chunks(db, results, user_id)


def _retrieve_personal_memories(query: str, db: Session, user_id: str, limit: int) -> List[Dict[str, Any]]:
    """Retrieve from personal memory store with privacy enforcement."""
    return search_personal_memories(db, user_id, query, limit=limit)


def _retrieve_web(query: str, limit: int) -> List[Dict[str, Any]]:
    """Retrieve from Tavily web search, returning ephemeral chunks with stable UUIDs."""
    from app.services.tavily_client import search_web_ephemeral
    raw = search_web_ephemeral(query, max_results=limit)
    # Replace random UUIDs with stable UUIDv5 based on URL
    for chunk in raw:
        url = chunk.get("source_uri", "")
        if url:
            stable_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
            chunk["chunk_id"] = stable_id
            chunk["document_id"] = stable_id
    return raw


def execute_research_step(
    db: Session,
    sub_query: str,
    target_sources: List[str],
    user_id: str,
    limit: int = 6,
    web_allowed: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Execute parallel retrieval across specified sources for a single sub-query.
    Returns (collected_chunks, source_counts).
    """
    collected: List[Dict[str, Any]] = []
    source_counts: Dict[str, int] = {}
    futures = {}

    filters = {"user_id": user_id}

    with ThreadPoolExecutor(max_workers=4) as executor:
        # Local code/document chunks
        if "code" in target_sources or "documents" in target_sources:
            futures[executor.submit(_retrieve_local_chunks, sub_query, db, user_id, limit, filters)] = "local"

        # Personal memory
        if "personal_memory" in target_sources:
            futures[executor.submit(_retrieve_personal_memories, sub_query, db, user_id, limit)] = "personal_memory"

        # Web (only if explicitly targeted AND web is allowed by caller)
        if "web" in target_sources and web_allowed:
            futures[executor.submit(_retrieve_web, sub_query, limit)] = "web"

        for future in as_completed(futures):
            source_label = futures[future]
            try:
                results = future.result()
                source_counts[source_label] = len(results)
                collected.extend(results)
            except Exception as e:
                logger.warning(f"Retrieval from {source_label} failed for query '{sub_query[:50]}': {e}")
                source_counts[source_label] = 0

    return collected, source_counts


# ---------------------------------------------------------------------------
# 3. Self-Reflection & Query Rewriting
# ---------------------------------------------------------------------------

REFLECT_SYSTEM_PROMPT = """\
You are a research agent reviewing retrieval results. The original question \
was not answered well by the sub-queries below. Analyze why and rewrite \
ONLY the weak sub-queries with broader terminology, synonyms, or \
alternative phrasings to improve retrieval.

CRITICAL RULES:
- Do NOT change target_sources. Keep the same source routing as the original.
- Do NOT add "web" to any sub-query that did not originally have it.
- Only rewrite queries that had weak or zero results.
- Return a JSON array of rewritten sub-queries with the same structure.

Respond ONLY with a JSON array:
[{"query": "...", "target_sources": ["..."]}]
"""


def reflect_and_correct(
    question: str,
    sub_queries: List[Dict[str, Any]],
    collected_chunks: List[Dict[str, Any]],
    iteration: int,
    max_iterations: int,
    confidence_mode: str = "balanced"
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Evaluate collected evidence. If confidence gating fails and iterations
    remain, rewrite weak sub-queries using LLM.

    Returns (sufficient, rewritten_sub_queries, reason).
    """
    passed, best_sim, ev_summary, _ = evaluate_rag_confidence(collected_chunks, confidence_mode)

    if passed:
        return (True, sub_queries, f"Confidence check passed ({ev_summary})")

    if iteration >= max_iterations:
        return (False, sub_queries, f"Max iterations ({max_iterations}) reached. {ev_summary}")

    # Attempt LLM-driven query rewriting
    if not is_groq_configured():
        return (False, sub_queries, f"Groq not configured for self-correction. {ev_summary}")

    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)

    context_summary = (
        f"Original question: {question}\n"
        f"Sub-queries attempted: {json.dumps(sub_queries)}\n"
        f"Results: {len(collected_chunks)} chunks retrieved, "
        f"best similarity: {best_sim*100:.1f}%. {ev_summary}"
    )

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": REFLECT_SYSTEM_PROMPT},
                {"role": "user", "content": context_summary}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        if isinstance(parsed, list):
            rewritten = parsed
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    rewritten = v
                    break
            else:
                rewritten = sub_queries
        else:
            rewritten = sub_queries

        # Enforce source safety: never allow newly-injected "web"
        safe_rewritten = []
        original_sources_map = {sq["query"]: set(sq["target_sources"]) for sq in sub_queries}
        all_original_sources = set()
        for sq in sub_queries:
            all_original_sources.update(sq["target_sources"])

        for rq in rewritten[:4]:
            q = rq.get("query", "") if isinstance(rq, dict) else str(rq)
            ts = rq.get("target_sources", list(all_original_sources)) if isinstance(rq, dict) else list(all_original_sources)
            # Remove "web" if it wasn't in any original sub-query
            if "web" not in all_original_sources and "web" in ts:
                ts = [s for s in ts if s != "web"]
            safe_rewritten.append({"query": q, "target_sources": ts})

        reason = f"Self-corrected: rewrote {len(safe_rewritten)} sub-queries to widen search bounds. {ev_summary}"
        return (False, safe_rewritten, reason)

    except Exception as e:
        logger.warning(f"Self-correction failed: {e}")
        return (False, sub_queries, f"Self-correction LLM call failed: {e}. {ev_summary}")


# ---------------------------------------------------------------------------
# 4. Research Answer Synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """\
You are an expert research assistant synthesizing a comprehensive answer \
from evidence collected across multiple retrieval steps.

System behavior:
- Answer using ONLY the provided evidence chunks.
- Cite sources inline using bracketed citation IDs like [1], [2].
- If the evidence is contradictory, acknowledge both sides.
- Structure your answer clearly with headers and bullet points when helpful.
- Keep the answer thorough but concise.
- If any aspect of the question is not covered by evidence, explicitly note it.

Evidence Chunks:
{context_block}
"""


def _deduplicate_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate chunks by chunk_id, keeping the highest-scoring version."""
    seen = {}
    for c in chunks:
        cid = c.get("chunk_id", id(c))
        existing = seen.get(cid)
        if existing is None or c.get("score", 0) > existing.get("score", 0):
            seen[cid] = c
    return list(seen.values())


def synthesize_research_answer(
    question: str,
    collected_chunks: List[Dict[str, Any]],
    research_steps: List[ResearchStepRecord],
    confidence_mode: str = "balanced"
) -> Tuple[str, str, List[RagCitation], List[Dict[str, Any]]]:
    """
    Deduplicate collected evidence, assign citation IDs, and synthesize
    a comprehensive answer using Groq.

    Returns (answer_text, status, citations, contexts).
    """
    deduped = _deduplicate_chunks(collected_chunks)

    # Final confidence check on the merged evidence
    passed, best_sim, ev_summary, _ = evaluate_rag_confidence(deduped, confidence_mode)

    if not deduped or not passed:
        return (
            "The autonomous research agent examined your codebase and memories "
            "across multiple iterations but found insufficient evidence answering "
            "this question.",
            "insufficient_knowledge",
            [],
            []
        )

    # Build contexts and citations
    contexts = []
    citations = []
    for idx, res in enumerate(deduped):
        citation_id = idx + 1
        contexts.append({
            "citation_id": citation_id,
            "document_title": res.get("document_title", "Unknown"),
            "source_type": res.get("source_type", "unknown"),
            "filename_uri": res.get("source_uri") or res.get("original_filename") or "unknown",
            "chunk_index": res.get("chunk_index", 0),
            "text": res.get("text", "")
        })
        citations.append(RagCitation(
            citation_id=citation_id,
            chunk_id=res.get("chunk_id", str(uuid.uuid4())),
            document_id=res.get("document_id", str(uuid.uuid4())),
            document_title=res.get("document_title", "Unknown"),
            source_type=res.get("source_type", "unknown"),
            original_filename=res.get("original_filename"),
            source_uri=res.get("source_uri"),
            chunk_index=res.get("chunk_index", 0),
            text_preview=(res.get("text", "")[:150] + "...") if len(res.get("text", "")) > 150 else res.get("text", "")
        ))

    # Synthesize answer via Groq
    if not is_groq_configured():
        return (
            "Groq API key is not configured. Cannot synthesize research answer.",
            "insufficient_knowledge",
            [],
            []
        )

    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for ctx in contexts:
        ctx_str = (
            f"[{ctx['citation_id']}]\n"
            f"Document: {ctx['document_title']}\n"
            f"Source type: {ctx['source_type']}\n"
            f"Filename/URI: {ctx['filename_uri']}\n"
            f"Chunk index: {ctx['chunk_index']}\n"
            f"Text:\n{ctx['text']}\n"
        )
        context_strings.append(ctx_str)
    context_block = "\n---\n".join(context_strings)

    system_prompt = SYNTHESIS_SYSTEM_PROMPT.replace("{context_block}", context_block)

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0
    )

    answer = response.choices[0].message.content
    return (answer, "answered", citations, contexts)


def _stream_synthesis_tokens(question: str, contexts: List[Dict[str, Any]]):
    """Stream tokens for the synthesis step."""
    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for ctx in contexts:
        ctx_str = (
            f"[{ctx['citation_id']}]\n"
            f"Document: {ctx['document_title']}\n"
            f"Source type: {ctx['source_type']}\n"
            f"Filename/URI: {ctx['filename_uri']}\n"
            f"Chunk index: {ctx['chunk_index']}\n"
            f"Text:\n{ctx['text']}\n"
        )
        context_strings.append(ctx_str)
    context_block = "\n---\n".join(context_strings)
    system_prompt = SYNTHESIS_SYSTEM_PROMPT.replace("{context_block}", context_block)

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        temperature=0.0,
        stream=True
    )
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content


# ---------------------------------------------------------------------------
# 5. Orchestrator: run_autonomous_research (non-streaming)
# ---------------------------------------------------------------------------

def run_autonomous_research(
    db: Session,
    request: RagQuestionRequest,
    user_id: str
) -> RagAnswerResponse:
    """
    Orchestrate the full autonomous research loop:
    decompose → retrieve → reflect → (rewrite → retrieve)* → synthesize.
    """
    max_iterations = request.max_iterations
    confidence_mode = request.confidence_mode
    research_steps: List[ResearchStepRecord] = []
    all_chunks: List[Dict[str, Any]] = []

    # Determine if web was requested
    web_allowed = request.fallback_action in ("search_web", "autonomous_research")

    # Step 1: Decompose
    sub_queries = decompose_query(request.question)

    # If web wasn't explicitly allowed but decomposition targeted it, strip it
    if not web_allowed:
        for sq in sub_queries:
            sq["target_sources"] = [s for s in sq["target_sources"] if s != "web"]

    for iteration in range(1, max_iterations + 1):
        # Step 2: Execute retrieval for each sub-query
        for sq in sub_queries:
            chunks, source_counts = execute_research_step(
                db, sq["query"], sq["target_sources"], user_id,
                limit=request.limit, web_allowed=web_allowed
            )
            step = ResearchStepRecord(
                iteration=iteration,
                query=sq["query"],
                target_sources=sq["target_sources"],
                source_counts=source_counts,
                status="retrieved",
                reason=f"Retrieved {len(chunks)} chunks"
            )
            research_steps.append(step)
            all_chunks.extend(chunks)

        # Step 3: Reflect and correct
        sufficient, rewritten_queries, reason = reflect_and_correct(
            request.question, sub_queries, all_chunks, iteration, max_iterations, confidence_mode
        )

        if sufficient:
            break

        if iteration < max_iterations:
            # Record the rewrite step
            for rq in rewritten_queries:
                research_steps.append(ResearchStepRecord(
                    iteration=iteration,
                    query=rq["query"],
                    target_sources=rq["target_sources"],
                    source_counts={},
                    status="rewritten",
                    reason=reason
                ))
            sub_queries = rewritten_queries

    # Step 4: Synthesize
    steps_dicts = [s.model_dump() for s in research_steps]
    answer, status, citations, contexts = synthesize_research_answer(
        request.question, all_chunks, research_steps, confidence_mode
    )

    return RagAnswerResponse(
        question=request.question,
        answer=answer,
        citations=citations,
        status=status,
        confidence_mode=confidence_mode,
        best_similarity=None,
        fallback_options=[] if status == "answered" else ["search_web", "general_model"],
        evidence_summary=f"Research completed in {len(set(s.iteration for s in research_steps))} iteration(s) with {len(_deduplicate_chunks(all_chunks))} unique evidence chunks.",
        research_steps=steps_dicts
    )


# ---------------------------------------------------------------------------
# 6. Orchestrator: stream_autonomous_research (SSE streaming)
# ---------------------------------------------------------------------------

def stream_autonomous_research(
    db: Session,
    request: RagQuestionRequest,
    user_id: str
) -> Generator[str, None, None]:
    """
    Stream the autonomous research process as SSE events:
    - event: research_step  (progress updates)
    - event: citations      (final citations)
    - event: token          (streamed answer tokens)
    - event: done           (completion)
    """
    max_iterations = request.max_iterations
    confidence_mode = request.confidence_mode
    research_steps: List[ResearchStepRecord] = []
    all_chunks: List[Dict[str, Any]] = []

    web_allowed = request.fallback_action in ("search_web", "autonomous_research")

    # Step 1: Decompose
    sub_queries = decompose_query(request.question)
    if not web_allowed:
        for sq in sub_queries:
            sq["target_sources"] = [s for s in sq["target_sources"] if s != "web"]

    yield f"event: research_step\ndata: {json.dumps({'type': 'decomposition', 'sub_queries': sub_queries})}\n\n"

    for iteration in range(1, max_iterations + 1):
        for sq in sub_queries:
            chunks, source_counts = execute_research_step(
                db, sq["query"], sq["target_sources"], user_id,
                limit=request.limit, web_allowed=web_allowed
            )
            step = ResearchStepRecord(
                iteration=iteration,
                query=sq["query"],
                target_sources=sq["target_sources"],
                source_counts=source_counts,
                status="retrieved",
                reason=f"Retrieved {len(chunks)} chunks"
            )
            research_steps.append(step)
            all_chunks.extend(chunks)

            yield f"event: research_step\ndata: {json.dumps(step.model_dump())}\n\n"

        sufficient, rewritten_queries, reason = reflect_and_correct(
            request.question, sub_queries, all_chunks, iteration, max_iterations, confidence_mode
        )

        if sufficient:
            yield f"event: research_step\ndata: {json.dumps({'type': 'reflection', 'iteration': iteration, 'status': 'sufficient', 'reason': reason})}\n\n"
            break

        if iteration < max_iterations:
            yield f"event: research_step\ndata: {json.dumps({'type': 'reflection', 'iteration': iteration, 'status': 'rewriting', 'reason': reason})}\n\n"
            for rq in rewritten_queries:
                research_steps.append(ResearchStepRecord(
                    iteration=iteration,
                    query=rq["query"],
                    target_sources=rq["target_sources"],
                    source_counts={},
                    status="rewritten",
                    reason=reason
                ))
            sub_queries = rewritten_queries

    # Synthesize
    deduped = _deduplicate_chunks(all_chunks)
    passed, best_sim, ev_summary, _ = evaluate_rag_confidence(deduped, confidence_mode)

    if not deduped or not passed:
        msg = (
            "The autonomous research agent examined your codebase and memories "
            "across multiple iterations but found insufficient evidence answering "
            "this question."
        )
        steps_dicts = [s.model_dump() for s in research_steps]
        yield f"event: citations\ndata: {json.dumps({'citations': []})}\n\n"
        yield f"event: action_required\ndata: {json.dumps({'status': 'insufficient_knowledge', 'confidence_mode': confidence_mode, 'best_similarity': best_sim, 'fallback_options': ['search_web', 'general_model'], 'evidence_summary': ev_summary, 'research_steps': steps_dicts})}\n\n"
        yield f"event: token\ndata: {json.dumps({'token': msg})}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': 'insufficient_knowledge'})}\n\n"
        return

    # Build citations
    contexts = []
    citations = []
    for idx, res in enumerate(deduped):
        citation_id = idx + 1
        contexts.append({
            "citation_id": citation_id,
            "document_title": res.get("document_title", "Unknown"),
            "source_type": res.get("source_type", "unknown"),
            "filename_uri": res.get("source_uri") or res.get("original_filename") or "unknown",
            "chunk_index": res.get("chunk_index", 0),
            "text": res.get("text", "")
        })
        citations.append(RagCitation(
            citation_id=citation_id,
            chunk_id=res.get("chunk_id", str(uuid.uuid4())),
            document_id=res.get("document_id", str(uuid.uuid4())),
            document_title=res.get("document_title", "Unknown"),
            source_type=res.get("source_type", "unknown"),
            original_filename=res.get("original_filename"),
            source_uri=res.get("source_uri"),
            chunk_index=res.get("chunk_index", 0),
            text_preview=(res.get("text", "")[:150] + "...") if len(res.get("text", "")) > 150 else res.get("text", "")
        ).model_dump(mode="json"))

    yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"

    if not is_groq_configured():
        yield f"event: error\ndata: {json.dumps({'detail': 'GROQ_API_KEY is missing or invalid.'})}\n\n"
        return

    try:
        for token in _stream_synthesis_tokens(request.question, contexts):
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
        steps_dicts = [s.model_dump() for s in research_steps]
        yield f"event: done\ndata: {json.dumps({'status': 'success', 'research_steps': steps_dicts})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
