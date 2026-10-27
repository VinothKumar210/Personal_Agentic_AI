import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, DateTime, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

document_collections = Table(
    "document_collections",
    Base.metadata,
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", String, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
)

document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_uri = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    jobs = relationship("IngestionJob", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    collections = relationship("Collection", secondary=document_collections, back_populates="documents")
    tags = relationship("Tag", secondary=document_tags, back_populates="documents")
    assignments = relationship("ClusterAssignment", back_populates="document", cascade="all, delete-orphan")

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    job_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    document = relationship("Document", back_populates="jobs")

class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uix_collection_user_name'),)
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    documents = relationship("Document", secondary=document_collections, back_populates="collections")

class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint('user_id', 'name', name='uix_tag_user_name'),)
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    documents = relationship("Document", secondary=document_tags, back_populates="tags")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint('document_id', 'chunk_index', name='uix_document_chunk_index'),)
    
    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=False)
    metadata_json = Column(Text, nullable=True)
    embedding_status = Column(String, nullable=False, default="pending", index=True)
    embedding_error = Column(Text, nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    document = relationship("Document", back_populates="chunks")
    assignments = relationship("ClusterAssignment", back_populates="chunk", cascade="all, delete-orphan")
    notes = relationship("ChunkNote", back_populates="chunk", cascade="all, delete-orphan")

class TopicCluster(Base):
    __tablename__ = "topic_clusters"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    keywords_json = Column(Text, nullable=True)
    document_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    assignments = relationship("ClusterAssignment", back_populates="cluster", cascade="all, delete-orphan")

class ClusterAssignment(Base):
    __tablename__ = "cluster_assignments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    cluster_id = Column(String, ForeignKey("topic_clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True, index=True)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    cluster = relationship("TopicCluster", back_populates="assignments")
    document = relationship("Document", back_populates="assignments")
    chunk = relationship("DocumentChunk", back_populates="assignments")

class LearningProfile(Base):
    __tablename__ = "learning_profiles"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_title = Column(String, nullable=False)
    target_role = Column(String, nullable=True)
    current_level = Column(String, nullable=True)
    focus_keywords_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    recommendations = relationship("LearningRecommendation", back_populates="profile", cascade="all, delete-orphan")

class LearningRecommendation(Base):
    __tablename__ = "learning_recommendations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(String, ForeignKey("learning_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=3)
    reason = Column(Text, nullable=True)
    evidence_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    profile = relationship("LearningProfile", back_populates="recommendations")

knowledge_node_documents = Table(
    "knowledge_node_documents",
    Base.metadata,
    Column("node_id", String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", String, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
)

class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String, nullable=False)
    node_type = Column(String, nullable=False, default="concept")
    description = Column(Text, nullable=True)
    aliases_json = Column(Text, nullable=True)
    frequency = Column(Integer, nullable=False, default=1)
    is_pruned = Column(Boolean, nullable=False, default=False)
    pruned_reason = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False, default=1.0)
    last_reflected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    documents = relationship("Document", secondary=knowledge_node_documents)

    @property
    def document_ids(self) -> list[str]:
        return [str(d.id) for d in self.documents]

class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String, nullable=False, default="related_to")
    weight = Column(Float, nullable=False, default=1.0)
    evidence_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    source_node = relationship("KnowledgeNode", foreign_keys=[source_node_id])
    target_node = relationship("KnowledgeNode", foreign_keys=[target_node_id])

class ChunkNote(Base):
    __tablename__ = "chunk_notes"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    note_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    
    chunk = relationship("DocumentChunk", back_populates="notes")

