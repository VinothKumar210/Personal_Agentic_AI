import json
import re
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.document import Document, DocumentChunk, TopicCluster, LearningProfile, LearningRecommendation
from app.schemas.learning import LearningProfileCreate, LearningPathRequest

ROLE_MAPS = {
    "llm_engineer": {
        "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "embeddings": ["embedding", "embeddings", "vector representation"],
        "vector_database": ["vector db", "vector database", "chroma", "faiss"],
        "chunking": ["chunking", "text splitting"],
        "prompt_engineering": ["prompt engineering", "prompting", "system prompt"],
        "evaluation": ["evaluation", "evals", "metrics"],
        "agents": ["agent", "agents", "agentic workflow"],
        "langchain_langgraph": ["langchain", "langgraph"],
        "fine_tuning": ["fine-tuning", "finetuning", "lora", "qlora"],
        "deployment": ["docker", "deployment", "deploy", "production"],
        "monitoring": ["monitoring", "observability", "logs", "metrics"],
        "security": ["security", "guardrails", "jailbreak"]
    },
    "backend_engineer": {
        "apis": ["api", "apis", "rest", "graphql"],
        "database_design": ["database design", "schema", "normalization", "sql"],
        "authentication": ["auth", "authentication", "authorization", "jwt"],
        "caching": ["caching", "redis", "memcached"],
        "queues": ["queue", "queues", "celery", "rabbitmq", "kafka"],
        "testing": ["testing", "pytest", "unit test", "integration test"],
        "deployment": ["docker", "deployment", "deploy", "production", "ci/cd"],
        "observability": ["monitoring", "observability", "logs", "metrics"]
    },
    "full_stack_ai_engineer": {
        "frontend": ["frontend", "react", "nextjs", "vue", "ui"],
        "backend": ["backend", "api", "fastapi", "express", "django"],
        "apis": ["api", "apis", "rest", "graphql"],
        "embeddings": ["embedding", "embeddings", "vector representation"],
        "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "vector_search": ["vector search", "vector db", "vector database", "chroma", "faiss"],
        "auth": ["auth", "authentication", "authorization", "jwt"],
        "deployment": ["docker", "deployment", "deploy", "production", "vercel"],
        "ux": ["ux", "user experience", "design"],
        "testing": ["testing", "pytest", "jest", "cypress", "unit test"]
    }
}

def create_learning_profile(db: Session, data: LearningProfileCreate, user_id: str) -> LearningProfile:
    # validate role if present
    if data.target_role and data.target_role not in ROLE_MAPS:
        raise HTTPException(status_code=422, detail=f"Unknown target_role: {data.target_role}")
        
    profile = LearningProfile(
        goal_title=data.goal_title,
        target_role=data.target_role,
        current_level=data.current_level,
        focus_keywords_json=json.dumps(data.focus_keywords) if data.focus_keywords else "[]",
        user_id=user_id
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

def list_learning_profiles(db: Session, user_id: str) -> List[LearningProfile]:
    return db.query(LearningProfile).filter(LearningProfile.user_id == user_id).order_by(LearningProfile.created_at.desc()).all()

def get_learning_profile(db: Session, profile_id: str, user_id: str) -> LearningProfile | None:
    return db.query(LearningProfile).filter(LearningProfile.id == profile_id, LearningProfile.user_id == user_id).first()

def delete_learning_profile(db: Session, profile_id: str, user_id: str):
    profile = get_learning_profile(db, profile_id, user_id)
    if profile:
        db.delete(profile)
        db.commit()

def extract_evidence(db: Session, profile: LearningProfile | None, user_id: str) -> str:
    parts = []
    
    # Get ready documents
    docs = db.query(Document).filter(Document.status == "ready", Document.user_id == user_id).all()
    for doc in docs:
        parts.append(doc.title)
        if doc.source_type:
            parts.append(doc.source_type)
            
    # Get chunks
    chunks = db.query(DocumentChunk).join(Document).filter(Document.status == "ready", Document.user_id == user_id).all()
    for chunk in chunks:
        parts.append(chunk.text)
        
    # Get topics
    topics = db.query(TopicCluster).filter(TopicCluster.user_id == user_id).all()
    for topic in topics:
        if topic.keywords_json:
            try:
                kw = json.loads(topic.keywords_json)
                parts.extend(kw)
            except:
                pass
                
    # Get profile focus keywords
    if profile and profile.focus_keywords_json:
        try:
            kw = json.loads(profile.focus_keywords_json)
            parts.extend(kw)
        except:
            pass
            
    return " ".join(parts).lower()

def has_sufficient_evidence(db: Session, profile: LearningProfile | None, user_id: str) -> bool:
    # Check chunks
    chunks = db.query(DocumentChunk).join(Document).filter(Document.status == "ready", Document.user_id == user_id).all()
    if any(chunk.text and chunk.text.strip() for chunk in chunks):
        return True
        
    # Check topics
    topics = db.query(TopicCluster).filter(TopicCluster.user_id == user_id).all()
    for topic in topics:
        if topic.keywords_json:
            try:
                kw = json.loads(topic.keywords_json)
                if any(k.strip() for k in kw):
                    return True
            except:
                pass
                
    # Check profile
    if profile and profile.focus_keywords_json:
        try:
            kw = json.loads(profile.focus_keywords_json)
            if any(k.strip() for k in kw):
                return True
        except:
            pass
            
    return False

def analyze_learning_path(db: Session, request: LearningPathRequest, user_id: str) -> Tuple[LearningProfile|None, List[LearningRecommendation], List[str], List[str], str]:
    if not request.profile_id and not request.target_role:
        raise HTTPException(status_code=422, detail="Must provide profile_id or target_role")
        
    profile = None
    target_role = request.target_role
    
    if request.profile_id:
        profile = get_learning_profile(db, str(request.profile_id), user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        if not target_role:
            target_role = profile.target_role

    if target_role not in ROLE_MAPS:
        raise HTTPException(status_code=422, detail=f"Unknown target_role: {target_role}")
        
    full_text = extract_evidence(db, profile, user_id)
    role_map = ROLE_MAPS[target_role]
    
    strengths = []
    gaps = []
    recommendations_data = []
    
    # Match keywords
    matched_any_evidence = has_sufficient_evidence(db, profile, user_id)
        
    if not matched_any_evidence:
        return profile, [], [], list(role_map.keys()), "insufficient knowledge base evidence"
        
    for concept, synonyms in role_map.items():
        found = False
        for syn in synonyms:
            # simple substring match or regex for word boundaries
            pattern = r'\b' + re.escape(syn.lower()) + r'\b'
            if re.search(pattern, full_text):
                found = True
                break
                
        if found:
            strengths.append(concept)
        else:
            gaps.append(concept)
            recommendations_data.append({
                "title": f"Learn {concept.replace('_', ' ').title()}",
                "description": f"Target role '{target_role}' requires knowledge of {concept}, but it is missing from your stored knowledge.",
                "priority": 1 if len(gaps) <= 3 else 3,
                "reason": f"Required for {target_role}",
                "evidence_json": json.dumps({
                    "missing_concept": concept,
                    "matched_strengths": strengths,
                    "source": "heuristic"
                })
            })
            
    if profile:
        db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == profile.id).delete()
    else:
        db.query(LearningRecommendation).filter(LearningRecommendation.profile_id == None).delete()
        
    new_recs = []
    for rec_data in recommendations_data[:request.max_recommendations]:
        rec = LearningRecommendation(
            profile_id=profile.id if profile else None,
            user_id=user_id,
            title=rec_data["title"],
            description=rec_data["description"],
            priority=rec_data["priority"],
            reason=rec_data["reason"],
            evidence_json=rec_data["evidence_json"]
        )
        db.add(rec)
        new_recs.append(rec)
        
    db.commit()
    for rec in new_recs:
        db.refresh(rec)
            
    message = f"Found {len(strengths)} strengths and {len(gaps)} gaps."
    return profile, new_recs, strengths, gaps, message
