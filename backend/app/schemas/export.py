from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ExportManifest(BaseModel):
    export_version: str = "1.0"
    exported_at: str
    app_version: str = "0.1.0"
    user_email: str
    counts: Dict[str, int]

class ExportDocument(BaseModel):
    id: str
    title: str
    source_type: str
    source_uri: Optional[str] = None
    original_filename: Optional[str] = None
    content_hash: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    status: str
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    collection_ids: List[str] = []
    tag_ids: List[str] = []

class ExportChunk(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str
    token_count: Optional[int] = None
    character_count: int
    metadata_json: Optional[str] = None
    created_at: str
    updated_at: str

class ExportChunkNote(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    note_text: str
    created_at: str
    updated_at: str

class ExportCollection(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    summary: Optional[str] = None
    created_at: str
    updated_at: str

class ExportTag(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str

class ExportConversation(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str

class ExportChatMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations_json: Optional[str] = None
    created_at: str

class ExportLearningProfile(BaseModel):
    id: str
    goal_title: str
    target_role: Optional[str] = None
    current_level: Optional[str] = None
    focus_keywords_json: Optional[str] = None
    created_at: str
    updated_at: str

class ExportLearningRecommendation(BaseModel):
    id: str
    profile_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    priority: int = 3
    reason: Optional[str] = None
    evidence_json: Optional[str] = None
    status: str = "open"
    created_at: str
    updated_at: str

class ExportClusterAssignment(BaseModel):
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    score: Optional[float] = None
    created_at: str

class ExportTopicCluster(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    keywords_json: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    created_at: str
    updated_at: str
    assignments: List[ExportClusterAssignment] = []

class ExportKnowledgeNode(BaseModel):
    id: str
    label: str
    node_type: str = "concept"
    description: Optional[str] = None
    aliases_json: Optional[str] = None
    frequency: int = 1
    created_at: str
    updated_at: str
    document_ids: List[str] = []

class ExportKnowledgeEdge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    relation_type: str = "related_to"
    weight: float = 1.0
    evidence_json: Optional[str] = None
    created_at: str

class KnowledgeExportBundle(BaseModel):
    manifest: ExportManifest
    documents: List[ExportDocument] = []
    chunks: List[ExportChunk] = []
    collections: List[ExportCollection] = []
    tags: List[ExportTag] = []
    conversations: List[ExportConversation] = []
    chat_messages: List[ExportChatMessage] = []
    learning_profiles: List[ExportLearningProfile] = []
    learning_recommendations: List[ExportLearningRecommendation] = []
    topic_clusters: List[ExportTopicCluster] = []
    knowledge_nodes: List[ExportKnowledgeNode] = []
    knowledge_edges: List[ExportKnowledgeEdge] = []
    chunk_notes: List[ExportChunkNote] = []


class RestoreRequest(BaseModel):
    mode: str = "dry_run"
    bundle: KnowledgeExportBundle

class RestoreResponse(BaseModel):
    mode: str
    counts: Dict[str, int]
    skipped_records: int = 0
    remapped_ids: int = 0
    message: str
