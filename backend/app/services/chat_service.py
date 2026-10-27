import json
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.chat import Conversation, ChatMessage
from app.schemas.chat import ConversationCreate, ChatMessageCreate, ChatMessageRead
from app.schemas.rag import RagCitation
from app.services.embedding_service import embed_query
from app.services.vector_service import search_chunks
from app.services.groq_client import generate_grounded_answer, is_groq_configured

def _parse_citations(message: ChatMessage) -> list[RagCitation]:
    if message.role == "user" or not message.citations_json:
        return []
    try:
        data = json.loads(message.citations_json)
        return [RagCitation(**c) for c in data]
    except Exception:
        return []

def _parse_metadata(message: ChatMessage) -> dict | None:
    if not message.metadata_json:
        return None
    try:
        return json.loads(message.metadata_json)
    except Exception:
        return None

def _to_message_read(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        citations=_parse_citations(message),
        metadata=_parse_metadata(message),
        created_at=message.created_at
    )

def create_conversation(request: ConversationCreate, db: Session, user_id: str) -> Conversation:
    conv = Conversation(title=request.title, user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

def list_conversations(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    total = db.query(Conversation).filter(Conversation.user_id == user_id).count()
    items = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(desc(Conversation.updated_at)).offset(skip).limit(limit).all()
    return items, total

def get_conversation(conversation_id: str, db: Session, user_id: str) -> Conversation:
    return db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == user_id).first()

def delete_conversation(conversation_id: str, db: Session, user_id: str) -> bool:
    conv = get_conversation(conversation_id, db, user_id)
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True

def list_messages(conversation_id: str, db: Session) -> list[ChatMessageRead]:
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at).all()
    return [_to_message_read(m) for m in messages]

def build_contextual_query(latest_message: str, recent_messages: list[ChatMessage]) -> str:
    if not recent_messages:
        return latest_message
    
    context_str = "Conversation context:\n"
    for m in recent_messages:
        role = "User" if m.role == "user" else "Assistant"
        context_str += f"{role}: {m.content}\n"
    context_str += f"\nLatest question:\n{latest_message}"
    return context_str

def add_user_message_and_answer(conversation_id: str, request: ChatMessageCreate, db: Session, user_id: str):
    conv = get_conversation(conversation_id, db, user_id)
    if not conv:
        raise ValueError("Conversation not found")
        
    recent_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(desc(ChatMessage.created_at)).limit(4).all()
    recent_messages = list(reversed(recent_messages))

    user_msg = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.content
    )
    db.add(user_msg)
    
    if not conv.title:
        conv.title = request.content[:60]

    db.commit()
    db.refresh(user_msg)

    query_str = build_contextual_query(request.content, recent_messages)

    # Delegate to autonomous research if requested
    if request.research_mode or request.fallback_action == "autonomous_research":
        from app.services.research_agent_service import run_autonomous_research
        from app.schemas.rag import RagQuestionRequest
        rag_req = RagQuestionRequest(
            question=request.content,
            limit=request.limit,
            source_type=request.source_type,
            document_id=request.document_id,
            confidence_mode=request.confidence_mode,
            fallback_action=request.fallback_action,
            research_mode=True,
            max_iterations=request.max_iterations
        )
        rag_resp = run_autonomous_research(db, rag_req, user_id)
        research_meta = {"research_steps": rag_resp.research_steps} if rag_resp.research_steps else None
        assistant_msg = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=rag_resp.answer,
            citations_json=json.dumps([c.model_dump(mode="json") for c in rag_resp.citations]),
            metadata_json=json.dumps(research_meta) if research_meta else None
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)
        return conv, _to_message_read(user_msg), _to_message_read(assistant_msg)

    if request.fallback_action == "search_web":
        try:
            from app.services.tavily_client import get_ephemeral_web_contexts
            _, contexts, citations_obj = get_ephemeral_web_contexts(request.content, max_results=request.limit)
            citations = [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in citations_obj]
        except Exception as e:
            raise RuntimeError(f"Tavily web search failed: {str(e)}")
    elif request.fallback_action == "general_model":
        contexts = []
        citations = []
    else:
        try:
            query_embedding = embed_query(query_str)
            filters = {}
            if request.source_type:
                filters["source_type"] = request.source_type
            if request.document_id:
                filters["document_id"] = str(request.document_id)
                
            filters["user_id"] = user_id
            dense_results = search_chunks(query_embedding, limit=request.limit * 3, filters=filters)
            from app.services.hybrid_search_service import hybrid_search_and_rerank
            results = hybrid_search_and_rerank(request.content, query_embedding, db, user_id, limit=request.limit, filters=filters, dense_results=dense_results)
        except Exception as e:
            raise RuntimeError(f"Retrieval failed: {str(e)}")

        from app.services.memory_service import gate_personal_memory_chunks
        results = gate_personal_memory_chunks(db, results, user_id)

        from app.services.rag_service import evaluate_rag_confidence
        passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(results, request.confidence_mode)
        if not passed:
            content_text = (
                "The knowledge base does not contain enough information to answer this question."
                if not results else
                f"I reviewed your local documents, but none contained strong evidence answering this query ({ev_summary})."
            )
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=content_text,
                citations_json="[]"
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            return conv, _to_message_read(user_msg), _to_message_read(assistant_msg)

        contexts = []
        citations = []
        for i, r in enumerate(results):
            contexts.append({
                "citation_id": i + 1,
                "document_title": r["document_title"],
                "source_type": r["source_type"],
                "filename_uri": r.get("source_uri") or r.get("original_filename") or "unknown",
                "chunk_index": r["chunk_index"],
                "text": r["text"]
            })
            citations.append(RagCitation(
                citation_id=i + 1,
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                document_title=r["document_title"],
                source_type=r["source_type"],
                original_filename=r.get("original_filename"),
                source_uri=r.get("source_uri"),
                chunk_index=r["chunk_index"],
                text_preview=r["text"][:100] + "..." if len(r["text"]) > 100 else r["text"]
            ).model_dump(mode="json"))

    if not is_groq_configured():
        raise RuntimeError("Groq API key not configured")

    try:
        answer = generate_grounded_answer(request.content, contexts)
    except Exception as e:
        raise RuntimeError(f"Generation failed: {str(e)}")

    assistant_msg = ChatMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        citations_json=json.dumps(citations)
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return conv, _to_message_read(user_msg), _to_message_read(assistant_msg)

def stream_chat_message(conversation_id: str, request: ChatMessageCreate, db: Session, user_id: str):
    conv = get_conversation(conversation_id, db, user_id)
    if not conv:
        yield f"event: error\ndata: {json.dumps({'detail': 'Conversation not found'})}\n\n"
        return

    recent_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(desc(ChatMessage.created_at)).limit(4).all()
    recent_messages = list(reversed(recent_messages))

    user_msg = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.content
    )
    db.add(user_msg)
    if not conv.title:
        conv.title = request.content[:60]
    db.commit()
    db.refresh(user_msg)

    query_str = build_contextual_query(request.content, recent_messages)

    # Delegate to autonomous research streaming if requested
    if request.research_mode or request.fallback_action == "autonomous_research":
        from app.services.research_agent_service import stream_autonomous_research
        from app.schemas.rag import RagQuestionRequest
        rag_req = RagQuestionRequest(
            question=request.content,
            limit=request.limit,
            source_type=request.source_type,
            document_id=request.document_id,
            confidence_mode=request.confidence_mode,
            fallback_action=request.fallback_action,
            research_mode=True,
            max_iterations=request.max_iterations
        )
        answer = ""
        research_steps = None
        citations_data = []
        for event_str in stream_autonomous_research(db, rag_req, user_id):
            yield event_str
            # Capture streamed data for persistence
            if "event: token" in event_str and "data:" in event_str:
                try:
                    data_part = event_str.split("data: ", 1)[1].strip()
                    token_data = json.loads(data_part)
                    answer += token_data.get("token", "")
                except Exception:
                    pass
            elif "event: citations" in event_str and "data:" in event_str:
                try:
                    data_part = event_str.split("data: ", 1)[1].strip()
                    citations_data = json.loads(data_part).get("citations", [])
                except Exception:
                    pass
            elif "event: done" in event_str and "data:" in event_str:
                try:
                    data_part = event_str.split("data: ", 1)[1].strip()
                    done_data = json.loads(data_part)
                    research_steps = done_data.get("research_steps")
                except Exception:
                    pass

        # Persist to DB
        if answer:
            research_meta = {"research_steps": research_steps} if research_steps else None
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                citations_json=json.dumps(citations_data),
                metadata_json=json.dumps(research_meta) if research_meta else None
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            yield f"event: message_saved\ndata: {json.dumps({'message_id': assistant_msg.id})}\n\n"
        return

    if request.fallback_action == "search_web":
        try:
            from app.services.tavily_client import get_ephemeral_web_contexts
            _, contexts, citations_obj = get_ephemeral_web_contexts(request.content, max_results=request.limit)
            citations = [c.model_dump(mode="json") if hasattr(c, "model_dump") else c for c in citations_obj]
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': f'Tavily web search failed: {str(e)}'})}\n\n"
            return
    elif request.fallback_action == "general_model":
        contexts = []
        citations = []
    else:
        try:
            query_embedding = embed_query(query_str)
            filters = {"user_id": user_id}
            if request.source_type:
                filters["source_type"] = request.source_type
            if request.document_id:
                filters["document_id"] = str(request.document_id)
                
            dense_results = search_chunks(query_embedding, limit=request.limit * 3, filters=filters)
            from app.services.hybrid_search_service import hybrid_search_and_rerank
            results = hybrid_search_and_rerank(request.content, query_embedding, db, user_id, limit=request.limit, filters=filters, dense_results=dense_results)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': f'Retrieval failed: {str(e)}'})}\n\n"
            return

        from app.services.memory_service import gate_personal_memory_chunks
        results = gate_personal_memory_chunks(db, results, user_id)

        from app.services.rag_service import evaluate_rag_confidence
        passed, best_sim, ev_summary, fallbacks = evaluate_rag_confidence(results, request.confidence_mode)
        if not passed:
            msg = (
                "The knowledge base does not contain enough information to answer this question."
                if not results else
                f"I reviewed your local documents, but none contained strong evidence answering this query ({ev_summary})."
            )
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=msg,
                citations_json="[]"
            )
            db.add(assistant_msg)
            db.commit()
            db.refresh(assistant_msg)
            yield f"event: citations\ndata: {json.dumps({'citations': []})}\n\n"
            yield f"event: action_required\ndata: {json.dumps({'status': 'insufficient_knowledge', 'confidence_mode': request.confidence_mode, 'best_similarity': best_sim, 'fallback_options': fallbacks, 'evidence_summary': ev_summary})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': 'insufficient_knowledge', 'message_id': assistant_msg.id})}\n\n"
            return

        contexts = []
        citations = []
        for i, r in enumerate(results):
            contexts.append({
                "citation_id": i + 1,
                "document_title": r["document_title"],
                "source_type": r["source_type"],
                "filename_uri": r.get("source_uri") or r.get("original_filename") or "unknown",
                "chunk_index": r["chunk_index"],
                "text": r["text"]
            })
            citations.append(RagCitation(
                citation_id=i + 1,
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                document_title=r["document_title"],
                source_type=r["source_type"],
                original_filename=r.get("original_filename"),
                source_uri=r.get("source_uri"),
                chunk_index=r["chunk_index"],
                text_preview=r["text"][:100] + "..." if len(r["text"]) > 100 else r["text"]
            ).model_dump(mode="json"))

    yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"

    if not is_groq_configured():
        yield f"event: error\ndata: {json.dumps({'detail': 'Groq API key not configured'})}\n\n"
        return

    answer = ""
    try:
        from app.services.groq_client import stream_grounded_answer_tokens
        for token in stream_grounded_answer_tokens(request.content, contexts):
            answer += token
            yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        assistant_msg = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            citations_json=json.dumps(citations)
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)
        yield f"event: done\ndata: {json.dumps({'status': 'success', 'message_id': assistant_msg.id})}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
