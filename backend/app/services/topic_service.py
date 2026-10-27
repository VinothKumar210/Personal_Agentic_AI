import json
import re
from typing import List, Tuple
from sqlalchemy.orm import Session
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans

from app.models.document import DocumentChunk, TopicCluster, ClusterAssignment, Document, IngestionJob, utc_now
from app.schemas.topics import TopicAnalysisRequest
from app.services import groq_client

# Basic English stopwords
STOPWORDS = set([
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
])

def extract_candidate_keywords(text: str) -> List[str]:
    # Lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    
    # Remove stopwords, keep length >= 3
    keywords = [w for w in words if w not in STOPWORDS and len(w) >= 3 and not w.isdigit()]
    return keywords

def build_chunk_feature_text(chunk: DocumentChunk) -> str:
    parts = []
    if chunk.document and chunk.document.title:
        parts.append(chunk.document.title)
    if chunk.document and chunk.document.source_type:
        parts.append(chunk.document.source_type)
    parts.append(chunk.text)
    return " ".join(parts)

def analyze_topics(db: Session, request: TopicAnalysisRequest, user_id: str) -> Tuple[List[TopicCluster], int, str]:
    if request.max_clusters < request.min_clusters:
        raise ValueError("max_clusters cannot be less than min_clusters")

    # 1. Fetch chunks from ready documents
    # Using deterministic sort to ensure repeatable test results
    chunks = db.query(DocumentChunk).join(Document).filter(
        Document.status == "ready", Document.user_id == user_id
    ).order_by(DocumentChunk.id).all()
    
    num_chunks = len(chunks)
    if num_chunks < request.min_chunks:
        return [], num_chunks, f"Not enough chunks for analysis (found {num_chunks}, minimum required is {request.min_chunks})"

    if num_chunks < request.min_clusters:
        return [], num_chunks, f"Not enough chunks for minimum clusters (found {num_chunks}, minimum clusters requested is {request.min_clusters})"
        
    # 2. Determine cluster count
    n_clusters = min(request.max_clusters, num_chunks)
    n_clusters = max(n_clusters, request.min_clusters)
    
    # 3. Build features
    texts = [build_chunk_feature_text(c) for c in chunks]
    
    vectorizer = TfidfVectorizer(
        stop_words=list(STOPWORDS), 
        max_features=1000, 
        min_df=1, 
        max_df=0.9, 
        token_pattern=r'(?u)\b[a-zA-Z]{3,}\b'
    )
    
    try:
        X = vectorizer.fit_transform(texts)
    except ValueError as e:
        msg = str(e).lower()
        if "empty vocabulary" in msg or "empty" in msg or "no terms remain" in msg or "after pruning" in msg:
            return [], num_chunks, "Not enough meaningful terms for topic analysis."
        raise e
    
    # 4. Cluster
    # Use deterministic random state
    kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    kmeans.fit(X)
    
    labels = kmeans.labels_
    
    # Get top terms per cluster
    feature_names = vectorizer.get_feature_names_out()
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    
    # 5. Clear old assignments and clusters
    clusters_to_delete = db.query(TopicCluster).filter(TopicCluster.user_id == user_id).all()
    cluster_ids = [c.id for c in clusters_to_delete]
    if cluster_ids:
        db.query(ClusterAssignment).filter(ClusterAssignment.cluster_id.in_(cluster_ids)).delete(synchronize_session=False)
        db.query(TopicCluster).filter(TopicCluster.id.in_(cluster_ids)).delete(synchronize_session=False)
    
    # 6. Save new clusters and assignments
    new_clusters = []
    for i in range(n_clusters):
        top_indices = order_centroids[i, :10]
        top_keywords = [feature_names[ind] for ind in top_indices if kmeans.cluster_centers_[i, ind] > 0]
        
        
        # Name the cluster with LLM
        cluster_name = f"Cluster {i+1}"
        cluster_description = ""
        
        if top_keywords:
            # Fallback name in case LLM fails
            cluster_name = " / ".join(top_keywords[:3]).title()
            
            # Use Groq to generate a human-readable name and description
            try:
                # Find some chunks that belong to this cluster for context
                sample_chunks = []
                for j, label in enumerate(labels):
                    if label == i:
                        sample_chunks.append(chunks[j].text)
                        if len(sample_chunks) >= 3:
                            break
                            
                prompt = f"Top Keywords: {', '.join(top_keywords)}\n\nSample Excerpts:\n"
                for excerpt in sample_chunks:
                    prompt += f"- {excerpt}\n"
                    
                response_text = groq_client.generate_completion(
                    prompt=prompt,
                    system_message="You are a data analyst summarizing document clusters. Based on the keywords and sample excerpts provided, output ONLY a JSON object with two string fields: 'name' (a concise, 2-4 word topic label) and 'description' (a 1-sentence summary of what this cluster is about). Do not include markdown blocks.",
                    temperature=0.2,
                    max_tokens=100,
                    json_mode=True
                )
                
                name_data = json.loads(response_text)
                if isinstance(name_data, dict):
                    if name_data.get('name'):
                        cluster_name = name_data['name']
                    if name_data.get('description'):
                        cluster_description = name_data['description']
            except Exception as e:
                # Fallback to TF-IDF keywords if LLM fails
                pass
            
        cluster_docs = set()
        cluster_chunk_count = 0
        
        # Find which chunks belong to this cluster
        assignments = []
        for j, label in enumerate(labels):
            if label == i:
                chunk = chunks[j]
                cluster_chunk_count += 1
                cluster_docs.add(chunk.document_id)
                assignments.append((chunk.document_id, chunk.id))
                
        # Only create cluster if it has chunks
        if cluster_chunk_count > 0:
            tc = TopicCluster(
                name=cluster_name,
                description=cluster_description,
                keywords_json=json.dumps(top_keywords),
                document_count=len(cluster_docs),
                chunk_count=cluster_chunk_count,
                user_id=user_id
            )
            db.add(tc)
            db.flush() # get tc.id
            
            for doc_id, chunk_id in assignments:
                ca = ClusterAssignment(
                    cluster_id=tc.id,
                    document_id=doc_id,
                    chunk_id=chunk_id
                )
                db.add(ca)
            
            new_clusters.append(tc)
            
    db.commit()
    for tc in new_clusters:
        db.refresh(tc)
        
    # Sort deterministically
    new_clusters.sort(key=lambda x: x.name)
    return new_clusters, num_chunks, "Analysis completed successfully"

def list_topic_clusters(db: Session, user_id: str) -> List[TopicCluster]:
    return db.query(TopicCluster).filter(TopicCluster.user_id == user_id).order_by(TopicCluster.created_at.desc()).all()

def get_topic_cluster(db: Session, cluster_id: str, user_id: str) -> TopicCluster | None:
    return db.query(TopicCluster).filter(TopicCluster.id == cluster_id, TopicCluster.user_id == user_id).first()

def run_auto_clustering_job(job_id: str, payload: dict, session: Session) -> None:
    """Background job runner for topic clustering."""
    try:
        job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return
            
        job.status = "processing"
        session.commit()
        
        request = TopicAnalysisRequest(
            min_clusters=payload.get("min_clusters", 2),
            max_clusters=payload.get("max_clusters", 8),
            min_chunks=payload.get("min_chunks", 5)
        )
        
        clusters, num_chunks, message = analyze_topics(session, request, job.user_id)
        
        job.status = "succeeded"
        job.message = f"Analyzed {num_chunks} chunks. Generated {len(clusters)} clusters."
        job.completed_at = utc_now()
        session.commit()
        
    except Exception as e:
        session.rollback()
        job = session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = utc_now()
            session.commit()
