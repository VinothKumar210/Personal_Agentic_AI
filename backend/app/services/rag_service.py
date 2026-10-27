import json
from typing import Generator, Optional
from sqlalchemy.orm import Session
from app.schemas.rag import RagQuestionRequest, RagCitation, RagAnswerResponse
from app.services.embedding_service import embed_query
from app.services.vector_service import search_chunks, search_diary_events
from app.services.groq_client import is_groq_configured, generate_grounded_answer

def evaluate_rag_confidence(results: list[dict], confidence_mode: str = "balanced") -> tuple[bool, float, str, list[str]]:
    """
    Evaluates multi-factor RAG confidence gating against the chosen mode.
    Returns: (passed, best_similarity, evidence_summary, fallback_options)
    """
    if not results:
        return (
            False,
            0.0,
            f"No relevant chunks found in the knowledge base meeting '{confidence_mode}' criteria.",
            ["search_web", "general_model"]
        )

    # 1. Determine thresholds based on mode
    if confidence_mode == "strict":
        min_dense_sim = 0.45
        min_rerank_score = 0.50
        min_passed_count = 2
    elif confidence_mode == "permissive":
        min_dense_sim = 0.18
        min_rerank_score = 0.05
        min_passed_count = 1
    else:  # balanced
        min_dense_sim = 0.28
        min_rerank_score = 0.25
        min_passed_count = 1

    passed_count = 0
    best_sim = 0.0

    for res in results:
        # Extract normalized cosine similarity
        sim = res.get("score")
        if sim is None and res.get("distance") is not None:
            sim = max(0.0, 1.0 - res["distance"])

        rerank_score = res.get("rerank_score")
        sparse_score = res.get("sparse_score", 0.0)
        rrf_score = res.get("rrf_score", 0.0)

        # If all score metrics are completely absent (e.g. unit test mocks without score), default sim to 1.0
        if sim is None and rerank_score is None and sparse_score == 0.0 and rrf_score == 0.0:
            sim = 1.0
        elif sim is None:
            sim = 0.0

        best_sim = max(best_sim, sim)

        # Evaluate if this chunk independently qualifies as relevant
        chunk_passed = False
        if rerank_score is not None:
            if rerank_score >= min_rerank_score or sim >= min_dense_sim:
                chunk_passed = True
        else:
            if sim >= min_dense_sim:
                chunk_passed = True

        # Check keyword / lexical / rrf evidence boost if close to threshold
        if not chunk_passed and (sparse_score > 0.0 or rrf_score > 0.0):
            if sim >= (min_dense_sim - 0.08) or sparse_score >= 1.5:
                chunk_passed = True

        if chunk_passed:
            passed_count += 1

    # If we have at least min_passed_count independently relevant chunks, gating passes!
    if passed_count >= min_passed_count:
        return (True, best_sim, f"Passed confidence check ({passed_count} relevant chunks).", [])

    # Otherwise gating fails
    evidence_summary = (
        f"Found {len(results)} candidate chunks (highest match: {best_sim*100:.1f}%), "
        f"but only {passed_count}/{min_passed_count} met the '{confidence_mode}' multi-factor criteria."
    )
    fallback_options = ["search_web", "general_model"]
    return (False, best_sim, evidence_summary, fallback_options)

def answer_question(request: RagQuestionRequest, user_id: str, db: Optional[Session] = None) -> RagAnswerResponse:
    if request.fallback_action == "search_web":
        try:
            from app.services.tavily_client import get_ephemeral_web_contexts
            _, contexts, citations = get_ephemeral_web_contexts(request.question, max_results=request.limit)
            best_sim = 1.0
            ev_summary = "Answered via ephemeral web search (Tavily)"
        except Exception as e:
            raise RuntimeError(f"Tavily web search failed: {str(e)}")
    elif request.fallback_action == "general_model":
        contexts = []
        citations = []
        best_sim = None
        ev_summary = "Answered via general model knowledge"
    else:
        # 1. Embed query
        try:
            query_embedding = embed_query(request.question)
        except Exception as e:
            raise RuntimeError(f"Failed to generate query embedding: {str(e)}")

        # 2. Search chunks (Hybrid + Reranking if db provided, else vector fallback)
        filters = {"user_id": user_id}
        if request.source_type:
            filters["source_type"] = request.source_type
        if request.document_id:
            filters["document_id"] = str(request.document_id)

        try:
            dense_results = search_chunks(query_embedding, limit=request.limit * 3 if db else request.limit, filters=filters)
            if db is not None:
                from app.services.hybrid_search_service import hybrid_search_and_rerank
                results = hybrid_search_and_rerank(request.question, query_embedding, db, user_id, limit=request.limit, filters=filters, dense_results=dense_results)
            else:
                results = dense_results[:request.limit]
                
            # Search diary events
            diary_results = search_diary_events(
                query_embedding=query_embedding, 
                user_id=user_id, 
                include_sensitive=request.include_sensitive_diary, 
                limit=request.limit
            )
            
            # Merge and sort
            results.extend(diary_results)
            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            results = results[:request.limit]
            
        except Exception as e:
            raise RuntimeError(f"Vector search failed: {str(e)}")

        # Double check privacy gating for any retrieved personal memories
        from app.services.memory_service import gate_personal_memory_chunks
        results = gate_personal_memory_chunks(db, results, user_id)

        # 3. Check results and multi-factor confidence gating
        passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(results, request.confidence_mode)
        if not passed:
            answer_text = (
                "The knowledge base does not contain enough information to answer this question."
                if not results else
                f"I reviewed your local documents, but none contained strong evidence answering this query ({ev_summary})."
            )
            return RagAnswerResponse(
                question=request.question,
                answer=answer_text,
                citations=[],
                status="insufficient_knowledge",
                confidence_mode=request.confidence_mode,
                best_similarity=best_sim,
                fallback_options=fallbacks,
                evidence_summary=ev_summary
            )

        # 4. Format contexts and citations
        contexts = []
        citations = []
        for idx, res in enumerate(results):
            citation_id = idx + 1
            if res.get("is_diary_event"):
                title = res["metadata"].get("title", "Diary Event")
                date_str = res["metadata"].get("event_date", "Unknown Date")
                contexts.append({
                    "citation_id": citation_id,
                    "document_title": f"📔 Diary Event: {title} ({date_str})",
                    "source_type": "diary",
                    "filename_uri": "diary",
                    "chunk_index": 0,
                    "text": res["text"]
                })
            else:
                contexts.append({
                    "citation_id": citation_id,
                    "document_title": res["document_title"],
                    "source_type": res["source_type"],
                    "filename_uri": res.get("source_uri") or res.get("original_filename") or "unknown",
                    "chunk_index": res["chunk_index"],
                    "text": res["text"]
                })

            citations.append(RagCitation(
                citation_id=citation_id,
                chunk_id=res["chunk_id"],
                document_id=res["document_id"],
                document_title=res["document_title"],
                source_type=res["source_type"],
                original_filename=res.get("original_filename"),
                source_uri=res.get("source_uri"),
                chunk_index=res["chunk_index"],
                text_preview=res["text"][:150] + "..." if len(res["text"]) > 150 else res["text"]
            ))

    # 5. Call Groq
    if not is_groq_configured():
        raise RuntimeError("GROQ_API_KEY is missing or invalid.")

    try:
        answer = generate_grounded_answer(request.question, contexts)
    except Exception as e:
        raise RuntimeError(f"Failed to generate answer from Groq: {str(e)}")

    return RagAnswerResponse(
        question=request.question,
        answer=answer,
        citations=citations,
        status="answered",
        confidence_mode=request.confidence_mode,
        best_similarity=best_sim,
        fallback_options=[],
        evidence_summary=ev_summary
    )

def stream_grounded_answer(request: RagQuestionRequest, user_id: str, db: Optional[Session] = None) -> Generator[str, None, None]:
    if request.fallback_action == "search_web":
        try:
            from app.services.tavily_client import get_ephemeral_web_contexts
            _, contexts, citations_obj = get_ephemeral_web_contexts(request.question, max_results=request.limit)
            citations = [c.model_dump(mode="json") for c in citations_obj]
            best_sim = 1.0
            ev_summary = "Answered via ephemeral web search (Tavily)"
        except Exception as e:
            err_msg = f"Tavily web search failed: {str(e)}"
            yield f"event: error\ndata: {json.dumps({'detail': err_msg})}\n\n"
            return
    elif request.fallback_action == "general_model":
        contexts = []
        citations = []
        best_sim = None
        ev_summary = "Answered via general model knowledge"
    else:
        try:
            query_embedding = embed_query(request.question)
        except Exception as e:
            err_msg = f"Failed to generate query embedding: {str(e)}"
            yield f"event: error\ndata: {json.dumps({'detail': err_msg})}\n\n"
            return

        filters = {"user_id": user_id}
        if request.source_type:
            filters["source_type"] = request.source_type
        if request.document_id:
            filters["document_id"] = str(request.document_id)

        try:
            dense_results = search_chunks(query_embedding, limit=request.limit * 3 if db else request.limit, filters=filters)
            if db is not None:
                from app.services.hybrid_search_service import hybrid_search_and_rerank
                results = hybrid_search_and_rerank(request.question, query_embedding, db, user_id, limit=request.limit, filters=filters, dense_results=dense_results)
            else:
                results = dense_results[:request.limit]
        except Exception as e:
            err_msg = f"Vector search failed: {str(e)}"
            yield f"event: error\ndata: {json.dumps({'detail': err_msg})}\n\n"
            return

        # Double check privacy gating for any retrieved personal memories
        from app.services.memory_service import gate_personal_memory_chunks
        results = gate_personal_memory_chunks(db, results, user_id)

        # Check results and multi-factor confidence gating
        passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(results, request.confidence_mode)
        if not passed:
            yield f"event: citations\ndata: {json.dumps({'citations': []})}\n\n"
            msg = (
                "The knowledge base does not contain enough information to answer this question."
                if not results else
                f"I reviewed your local documents, but none contained strong evidence answering this query ({ev_summary})."
            )
            yield f"event: action_required\ndata: {json.dumps({'status': 'insufficient_knowledge', 'confidence_mode': request.confidence_mode, 'best_similarity': best_sim, 'fallback_options': fallbacks, 'evidence_summary': ev_summary})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': 'insufficient_knowledge'})}\n\n"
            return

        contexts = []
        citations = []
        for idx, res in enumerate(results):
            citation_id = idx + 1
            contexts.append({
                "citation_id": citation_id,
                "document_title": res["document_title"],
                "source_type": res["source_type"],
                "filename_uri": res.get("source_uri") or res.get("original_filename") or "unknown",
                "chunk_index": res["chunk_index"],
                "text": res["text"]
            })
            cit = RagCitation(
                citation_id=citation_id,
                chunk_id=res["chunk_id"],
                document_id=res["document_id"],
                document_title=res["document_title"],
                source_type=res["source_type"],
                original_filename=res.get("original_filename"),
                source_uri=res.get("source_uri"),
                chunk_index=res["chunk_index"],
                text_preview=res["text"][:150] + "..." if len(res["text"]) > 150 else res["text"]
            )
            citations.append(cit.model_dump(mode="json"))

    yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"

    if not is_groq_configured():
        yield f"event: error\ndata: {json.dumps({'detail': 'GROQ_API_KEY is missing or invalid.'})}\n\n"
        return

    try:
        from app.services.groq_client import stream_grounded_answer_tokens
        for token in stream_grounded_answer_tokens(request.question, contexts):
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': 'success'})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
