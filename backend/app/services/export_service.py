from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.document import (
    Document, DocumentChunk, Collection, Tag,
    TopicCluster, ClusterAssignment, LearningProfile,
    LearningRecommendation, KnowledgeNode, KnowledgeEdge, ChunkNote
)
from app.models.chat import Conversation, ChatMessage
from app.schemas.export import (
    ExportManifest, ExportDocument, ExportChunk, ExportCollection,
    ExportTag, ExportConversation, ExportChatMessage, ExportLearningProfile,
    ExportLearningRecommendation, ExportTopicCluster, ExportClusterAssignment,
    ExportKnowledgeNode, ExportKnowledgeEdge, ExportChunkNote, KnowledgeExportBundle
)

def format_dt(dt: any) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat()
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    return str(dt)

def build_export_bundle(db: Session, user: User) -> KnowledgeExportBundle:
    # 1. Collections & Tags
    collections = db.query(Collection).filter(Collection.user_id == user.id).all()
    cols_export = [
        ExportCollection(
            id=str(c.id),
            name=c.name,
            description=c.description,
            summary=c.summary,
            created_at=format_dt(c.created_at),
            updated_at=format_dt(c.updated_at)
        )
        for c in collections
    ]

    tags = db.query(Tag).filter(Tag.user_id == user.id).all()
    tags_export = [
        ExportTag(
            id=str(t.id),
            name=t.name,
            created_at=format_dt(t.created_at),
            updated_at=format_dt(t.updated_at)
        )
        for t in tags
    ]

    # 2. Documents & Chunks
    documents = db.query(Document).filter(Document.user_id == user.id).all()
    doc_ids = [d.id for d in documents]
    
    docs_export = []
    for d in documents:
        docs_export.append(
            ExportDocument(
                id=str(d.id),
                title=d.title,
                source_type=d.source_type,
                source_uri=d.source_uri,
                original_filename=d.original_filename,
                content_hash=d.content_hash,
                mime_type=d.mime_type,
                size_bytes=d.size_bytes,
                status=d.status,
                summary=d.summary,
                error_message=d.error_message,
                created_at=format_dt(d.created_at),
                updated_at=format_dt(d.updated_at),
                collection_ids=[str(c.id) for c in d.collections],
                tag_ids=[str(t.id) for t in d.tags]
            )
        )

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(doc_ids)).all() if doc_ids else []
    chunks_export = [
        ExportChunk(
            id=str(ch.id),
            document_id=str(ch.document_id),
            chunk_index=ch.chunk_index,
            text=ch.text,
            token_count=ch.token_count,
            character_count=ch.character_count,
            metadata_json=ch.metadata_json,
            created_at=format_dt(ch.created_at),
            updated_at=format_dt(ch.updated_at)
        )
        for ch in chunks
    ]

    # 3. Conversations & Chat Messages
    conversations = db.query(Conversation).filter(Conversation.user_id == user.id).all()
    conv_ids = [c.id for c in conversations]
    convs_export = [
        ExportConversation(
            id=str(c.id),
            title=c.title,
            created_at=format_dt(c.created_at),
            updated_at=format_dt(c.updated_at)
        )
        for c in conversations
    ]

    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id.in_(conv_ids)).all() if conv_ids else []
    msgs_export = [
        ExportChatMessage(
            id=str(m.id),
            conversation_id=str(m.conversation_id),
            role=m.role,
            content=m.content,
            citations_json=m.citations_json,
            created_at=format_dt(m.created_at)
        )
        for m in messages
    ]

    # 4. Learning Profiles & Recommendations
    profiles = db.query(LearningProfile).filter(LearningProfile.user_id == user.id).all()
    profiles_export = [
        ExportLearningProfile(
            id=str(p.id),
            goal_title=p.goal_title,
            target_role=p.target_role,
            current_level=p.current_level,
            focus_keywords_json=p.focus_keywords_json,
            created_at=format_dt(p.created_at),
            updated_at=format_dt(p.updated_at)
        )
        for p in profiles
    ]

    recs = db.query(LearningRecommendation).filter(LearningRecommendation.user_id == user.id).all()
    recs_export = [
        ExportLearningRecommendation(
            id=str(r.id),
            profile_id=str(r.profile_id) if r.profile_id else None,
            title=r.title,
            description=r.description,
            priority=r.priority,
            reason=r.reason,
            evidence_json=r.evidence_json,
            status=r.status,
            created_at=format_dt(r.created_at),
            updated_at=format_dt(r.updated_at)
        )
        for r in recs
    ]

    # 5. Topic Clusters & Assignments
    clusters = db.query(TopicCluster).filter(TopicCluster.user_id == user.id).all()
    clusters_export = []
    for cl in clusters:
        assigns_export = [
            ExportClusterAssignment(
                id=str(a.id),
                document_id=str(a.document_id),
                chunk_id=str(a.chunk_id) if a.chunk_id else None,
                score=a.score,
                created_at=format_dt(a.created_at)
            )
            for a in cl.assignments
        ]
        clusters_export.append(
            ExportTopicCluster(
                id=str(cl.id),
                name=cl.name,
                description=cl.description,
                keywords_json=cl.keywords_json,
                document_count=cl.document_count,
                chunk_count=cl.chunk_count,
                created_at=format_dt(cl.created_at),
                updated_at=format_dt(cl.updated_at),
                assignments=assigns_export
            )
        )

    # 6. Knowledge Graph Nodes & Edges
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user.id).all()
    nodes_export = [
        ExportKnowledgeNode(
            id=str(kn.id),
            label=kn.label,
            node_type=kn.node_type,
            description=kn.description,
            aliases_json=kn.aliases_json,
            frequency=kn.frequency,
            created_at=format_dt(kn.created_at),
            updated_at=format_dt(kn.updated_at),
            document_ids=[str(d.id) for d in kn.documents]
        )
        for kn in nodes
    ]

    edges = db.query(KnowledgeEdge).filter(KnowledgeEdge.user_id == user.id).all()
    edges_export = [
        ExportKnowledgeEdge(
            id=str(ke.id),
            source_node_id=str(ke.source_node_id),
            target_node_id=str(ke.target_node_id),
            relation_type=ke.relation_type,
            weight=ke.weight,
            evidence_json=ke.evidence_json,
            created_at=format_dt(ke.created_at)
        )
        for ke in edges
    ]

    notes = db.query(ChunkNote).filter(ChunkNote.user_id == user.id).all()
    notes_export = [
        ExportChunkNote(
            id=str(n.id),
            document_id=str(n.document_id),
            chunk_id=str(n.chunk_id),
            note_text=n.note_text,
            created_at=format_dt(n.created_at),
            updated_at=format_dt(n.updated_at)
        )
        for n in notes
    ]

    counts = {
        "documents": len(docs_export),
        "chunks": len(chunks_export),
        "collections": len(cols_export),
        "tags": len(tags_export),
        "conversations": len(convs_export),
        "chat_messages": len(msgs_export),
        "learning_profiles": len(profiles_export),
        "learning_recommendations": len(recs_export),
        "topic_clusters": len(clusters_export),
        "knowledge_nodes": len(nodes_export),
        "knowledge_edges": len(edges_export),
        "chunk_notes": len(notes_export)
    }

    manifest = ExportManifest(
        export_version="1.0",
        exported_at=datetime.now(timezone.utc).isoformat(),
        app_version="0.1.0",
        user_email=user.email,
        counts=counts
    )

    return KnowledgeExportBundle(
        manifest=manifest,
        documents=docs_export,
        chunks=chunks_export,
        collections=cols_export,
        tags=tags_export,
        conversations=convs_export,
        chat_messages=msgs_export,
        learning_profiles=profiles_export,
        learning_recommendations=recs_export,
        topic_clusters=clusters_export,
        knowledge_nodes=nodes_export,
        knowledge_edges=edges_export,
        chunk_notes=notes_export
    )

