import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.document import (
    Document, DocumentChunk, Collection, Tag,
    TopicCluster, ClusterAssignment, LearningProfile,
    LearningRecommendation, KnowledgeNode, KnowledgeEdge, ChunkNote,
    document_collections, document_tags, knowledge_node_documents,
    IngestionJob
)
from app.models.chat import Conversation, ChatMessage
from app.schemas.export import KnowledgeExportBundle, RestoreResponse

def validate_export_bundle(data: Any) -> KnowledgeExportBundle:
    if isinstance(data, KnowledgeExportBundle):
        return data
    if isinstance(data, dict):
        return KnowledgeExportBundle(**data)
    raise ValueError("Invalid bundle data format")

def restore_export_bundle(db: Session, user: User, bundle: KnowledgeExportBundle, mode: str) -> RestoreResponse:
    if mode not in ["dry_run", "merge", "replace"]:
        raise ValueError(f"Unsupported restore mode: {mode}")

    counts = {
        "documents": len(bundle.documents),
        "chunks": len(bundle.chunks),
        "collections": len(bundle.collections),
        "tags": len(bundle.tags),
        "conversations": len(bundle.conversations),
        "chat_messages": len(bundle.chat_messages),
        "learning_profiles": len(bundle.learning_profiles),
        "learning_recommendations": len(bundle.learning_recommendations),
        "topic_clusters": len(bundle.topic_clusters),
        "knowledge_nodes": len(bundle.knowledge_nodes),
        "knowledge_edges": len(bundle.knowledge_edges),
        "chunk_notes": len(getattr(bundle, 'chunk_notes', []))
    }

    if mode == "dry_run":
        return RestoreResponse(
            mode=mode,
            counts=counts,
            skipped_records=0,
            remapped_ids=0,
            message="Dry run validation successful. No data was modified."
        )

    if mode == "replace":
        # Safe deletion of user's restorable records in reverse foreign-key order
        user_cluster_ids = [r[0] for r in db.query(TopicCluster.id).filter(TopicCluster.user_id == user.id).all()]
        if user_cluster_ids:
            db.query(ClusterAssignment).filter(ClusterAssignment.cluster_id.in_(user_cluster_ids)).delete(synchronize_session=False)
        db.query(TopicCluster).filter(TopicCluster.user_id == user.id).delete(synchronize_session=False)
        db.query(ChunkNote).filter(ChunkNote.user_id == user.id).delete(synchronize_session=False)

        
        db.query(LearningRecommendation).filter(LearningRecommendation.user_id == user.id).delete(synchronize_session=False)
        db.query(LearningProfile).filter(LearningProfile.user_id == user.id).delete(synchronize_session=False)
        
        user_conv_ids = [r[0] for r in db.query(Conversation.id).filter(Conversation.user_id == user.id).all()]
        if user_conv_ids:
            db.query(ChatMessage).filter(ChatMessage.conversation_id.in_(user_conv_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.user_id == user.id).delete(synchronize_session=False)
        
        db.query(KnowledgeEdge).filter(KnowledgeEdge.user_id == user.id).delete(synchronize_session=False)
        
        user_node_ids = [r[0] for r in db.query(KnowledgeNode.id).filter(KnowledgeNode.user_id == user.id).all()]
        if user_node_ids:
            db.execute(knowledge_node_documents.delete().where(knowledge_node_documents.c.node_id.in_(user_node_ids)))
        db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user.id).delete(synchronize_session=False)
        
        user_doc_ids = [r[0] for r in db.query(Document.id).filter(Document.user_id == user.id).all()]
        if user_doc_ids:
            db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(user_doc_ids)).delete(synchronize_session=False)
            db.execute(document_collections.delete().where(document_collections.c.document_id.in_(user_doc_ids)))
            db.execute(document_tags.delete().where(document_tags.c.document_id.in_(user_doc_ids)))
        
        db.query(IngestionJob).filter(IngestionJob.user_id == user.id).delete(synchronize_session=False)
        db.query(Document).filter(Document.user_id == user.id).delete(synchronize_session=False)
        db.query(Collection).filter(Collection.user_id == user.id).delete(synchronize_session=False)
        db.query(Tag).filter(Tag.user_id == user.id).delete(synchronize_session=False)
        
        db.flush()
        db.expunge_all()

    id_map: Dict[str, str] = {}
    skipped_records = 0
    remapped_ids = 0

    def get_target_id(model_cls: Any, old_id: str) -> str:
        nonlocal remapped_ids
        if old_id in id_map:
            return id_map[old_id]
        existing = db.query(model_cls).filter(model_cls.id == old_id).first()
        if existing:
            new_id = str(uuid.uuid4())
            id_map[old_id] = new_id
            remapped_ids += 1
            return new_id
        id_map[old_id] = old_id
        return old_id

    # 1. Collections
    for col in bundle.collections:
        existing = db.query(Collection).filter(Collection.user_id == user.id, Collection.name == col.name).first()
        if existing:
            id_map[col.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(Collection, col.id)
            new_col = Collection(
                id=target_id,
                user_id=user.id,
                name=col.name,
                description=col.description,
                summary=col.summary
            )
            db.add(new_col)
            db.flush()

    # 2. Tags
    for tag in bundle.tags:
        existing = db.query(Tag).filter(Tag.user_id == user.id, Tag.name == tag.name).first()
        if existing:
            id_map[tag.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(Tag, tag.id)
            new_tag = Tag(
                id=target_id,
                user_id=user.id,
                name=tag.name
            )
            db.add(new_tag)
            db.flush()

    # 3. Documents
    for doc in bundle.documents:
        query = db.query(Document).filter(Document.user_id == user.id, Document.title == doc.title, Document.source_type == doc.source_type)
        if doc.source_uri:
            query = query.filter(Document.source_uri == doc.source_uri)
        existing = query.first()
        if not existing and doc.content_hash:
            existing = db.query(Document).filter(Document.user_id == user.id, Document.content_hash == doc.content_hash).first()
        
        if existing:
            id_map[doc.id] = str(existing.id)
            skipped_records += 1
            for cid in doc.collection_ids:
                mapped_cid = id_map.get(cid)
                if mapped_cid:
                    col_obj = db.query(Collection).filter(Collection.id == mapped_cid, Collection.user_id == user.id).first()
                    if col_obj and col_obj not in existing.collections:
                        existing.collections.append(col_obj)
            for tid in doc.tag_ids:
                mapped_tid = id_map.get(tid)
                if mapped_tid:
                    tag_obj = db.query(Tag).filter(Tag.id == mapped_tid, Tag.user_id == user.id).first()
                    if tag_obj and tag_obj not in existing.tags:
                        existing.tags.append(tag_obj)
        else:
            target_id = get_target_id(Document, doc.id)
            new_doc = Document(
                id=target_id,
                user_id=user.id,
                title=doc.title,
                source_type=doc.source_type,
                source_uri=doc.source_uri,
                original_filename=doc.original_filename,
                content_hash=doc.content_hash,
                mime_type=doc.mime_type,
                size_bytes=doc.size_bytes,
                status=doc.status,
                summary=doc.summary,
                error_message=doc.error_message
            )
            db.add(new_doc)
            db.flush()
            for cid in doc.collection_ids:
                mapped_cid = id_map.get(cid)
                if mapped_cid:
                    col_obj = db.query(Collection).filter(Collection.id == mapped_cid, Collection.user_id == user.id).first()
                    if col_obj and col_obj not in new_doc.collections:
                        new_doc.collections.append(col_obj)
            for tid in doc.tag_ids:
                mapped_tid = id_map.get(tid)
                if mapped_tid:
                    tag_obj = db.query(Tag).filter(Tag.id == mapped_tid, Tag.user_id == user.id).first()
                    if tag_obj and tag_obj not in new_doc.tags:
                        new_doc.tags.append(tag_obj)

    # 4. Chunks
    for chunk in bundle.chunks:
        doc_id = id_map.get(chunk.document_id)
        if not doc_id:
            skipped_records += 1
            continue
        existing = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id, DocumentChunk.chunk_index == chunk.chunk_index).first()
        if existing:
            id_map[chunk.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(DocumentChunk, chunk.id)
            new_chunk = DocumentChunk(
                id=target_id,
                document_id=doc_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                character_count=chunk.character_count,
                metadata_json=chunk.metadata_json,
                embedding_status="pending",
                embedded_at=None,
                embedding_error=None
            )
            db.add(new_chunk)
            db.flush()

    # 5. Conversations
    for conv in bundle.conversations:
        existing = db.query(Conversation).filter(Conversation.user_id == user.id, Conversation.id == conv.id).first()
        if existing:
            id_map[conv.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(Conversation, conv.id)
            new_conv = Conversation(
                id=target_id,
                user_id=user.id,
                title=conv.title
            )
            db.add(new_conv)
            db.flush()

    # 6. Chat Messages
    for msg in bundle.chat_messages:
        conv_id = id_map.get(msg.conversation_id)
        if not conv_id:
            skipped_records += 1
            continue
        existing = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv_id, ChatMessage.id == msg.id).first()
        if existing:
            id_map[msg.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(ChatMessage, msg.id)
            new_msg = ChatMessage(
                id=target_id,
                conversation_id=conv_id,
                role=msg.role,
                content=msg.content,
                citations_json=msg.citations_json
            )
            db.add(new_msg)
            db.flush()

    # 7. Learning Profiles
    for profile in bundle.learning_profiles:
        existing = db.query(LearningProfile).filter(LearningProfile.user_id == user.id, LearningProfile.goal_title == profile.goal_title).first()
        if existing:
            id_map[profile.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(LearningProfile, profile.id)
            new_profile = LearningProfile(
                id=target_id,
                user_id=user.id,
                goal_title=profile.goal_title,
                target_role=profile.target_role,
                current_level=profile.current_level,
                focus_keywords_json=profile.focus_keywords_json
            )
            db.add(new_profile)
            db.flush()

    # 8. Learning Recommendations
    for rec in bundle.learning_recommendations:
        profile_id = id_map.get(rec.profile_id) if rec.profile_id else None
        existing = db.query(LearningRecommendation).filter(
            LearningRecommendation.user_id == user.id,
            LearningRecommendation.title == rec.title,
            LearningRecommendation.profile_id == profile_id
        ).first()
        if existing:
            id_map[rec.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(LearningRecommendation, rec.id)
            new_rec = LearningRecommendation(
                id=target_id,
                user_id=user.id,
                profile_id=profile_id,
                title=rec.title,
                description=rec.description,
                priority=rec.priority,
                reason=rec.reason,
                evidence_json=rec.evidence_json,
                status=rec.status
            )
            db.add(new_rec)
            db.flush()

    # 9. Topic Clusters
    for cluster in bundle.topic_clusters:
        existing = db.query(TopicCluster).filter(TopicCluster.user_id == user.id, TopicCluster.name == cluster.name).first()
        if existing:
            id_map[cluster.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(TopicCluster, cluster.id)
            new_cluster = TopicCluster(
                id=target_id,
                user_id=user.id,
                name=cluster.name,
                description=cluster.description,
                keywords_json=cluster.keywords_json,
                document_count=cluster.document_count,
                chunk_count=cluster.chunk_count
            )
            db.add(new_cluster)
            db.flush()
        
        target_cluster_id = id_map[cluster.id]
        for assignment in cluster.assignments:
            doc_id = id_map.get(assignment.document_id)
            if not doc_id:
                continue
            chunk_id = id_map.get(assignment.chunk_id) if assignment.chunk_id else None
            existing_a = db.query(ClusterAssignment).filter(
                ClusterAssignment.cluster_id == target_cluster_id,
                ClusterAssignment.document_id == doc_id,
                ClusterAssignment.chunk_id == chunk_id
            ).first()
            if not existing_a:
                new_a = ClusterAssignment(
                    id=get_target_id(ClusterAssignment, assignment.id),
                    cluster_id=target_cluster_id,
                    document_id=doc_id,
                    chunk_id=chunk_id,
                    score=assignment.score
                )
                db.add(new_a)
                db.flush()

    # 10. Knowledge Graph Nodes
    for node in bundle.knowledge_nodes:
        existing = db.query(KnowledgeNode).filter(
            KnowledgeNode.user_id == user.id,
            KnowledgeNode.label == node.label,
            KnowledgeNode.node_type == node.node_type
        ).first()
        if existing:
            id_map[node.id] = str(existing.id)
            skipped_records += 1
            for did in node.document_ids:
                mapped_did = id_map.get(did)
                if mapped_did:
                    doc_obj = db.query(Document).filter(Document.id == mapped_did, Document.user_id == user.id).first()
                    if doc_obj and doc_obj not in existing.documents:
                        existing.documents.append(doc_obj)
        else:
            target_id = get_target_id(KnowledgeNode, node.id)
            new_node = KnowledgeNode(
                id=target_id,
                user_id=user.id,
                label=node.label,
                node_type=node.node_type,
                description=node.description,
                aliases_json=node.aliases_json,
                frequency=node.frequency
            )
            db.add(new_node)
            db.flush()
            for did in node.document_ids:
                mapped_did = id_map.get(did)
                if mapped_did:
                    doc_obj = db.query(Document).filter(Document.id == mapped_did, Document.user_id == user.id).first()
                    if doc_obj and doc_obj not in new_node.documents:
                        new_node.documents.append(doc_obj)

    # 11. Knowledge Graph Edges
    for edge in bundle.knowledge_edges:
        src_id = id_map.get(edge.source_node_id)
        tgt_id = id_map.get(edge.target_node_id)
        if not src_id or not tgt_id:
            skipped_records += 1
            continue
        existing = db.query(KnowledgeEdge).filter(
            KnowledgeEdge.user_id == user.id,
            KnowledgeEdge.source_node_id == src_id,
            KnowledgeEdge.target_node_id == tgt_id,
            KnowledgeEdge.relation_type == edge.relation_type
        ).first()
        if existing:
            id_map[edge.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(KnowledgeEdge, edge.id)
            new_edge = KnowledgeEdge(
                id=target_id,
                user_id=user.id,
                source_node_id=src_id,
                target_node_id=tgt_id,
                relation_type=edge.relation_type,
                weight=edge.weight,
                evidence_json=edge.evidence_json
            )
            db.add(new_edge)
            db.flush()

    # 12. Chunk Notes
    for note in getattr(bundle, 'chunk_notes', []):
        doc_id = id_map.get(note.document_id)
        chk_id = id_map.get(note.chunk_id)
        if not doc_id or not chk_id:
            skipped_records += 1
            continue
        existing = db.query(ChunkNote).filter(
            ChunkNote.user_id == user.id,
            ChunkNote.chunk_id == chk_id,
            ChunkNote.note_text == note.note_text
        ).first()
        if existing:
            id_map[note.id] = str(existing.id)
            skipped_records += 1
        else:
            target_id = get_target_id(ChunkNote, note.id)
            new_note = ChunkNote(
                id=target_id,
                user_id=user.id,
                document_id=doc_id,
                chunk_id=chk_id,
                note_text=note.note_text
            )
            db.add(new_note)
            db.flush()

    db.commit()

    return RestoreResponse(
        mode=mode,
        counts=counts,
        skipped_records=skipped_records,
        remapped_ids=remapped_ids,
        message=f"Successfully restored knowledge base in '{mode}' mode."
    )

