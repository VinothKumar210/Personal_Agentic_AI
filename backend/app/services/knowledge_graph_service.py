import re
import json
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.document import Document, DocumentChunk, KnowledgeNode, KnowledgeEdge, knowledge_node_documents
from app.schemas.knowledge_graph import KnowledgeGraphBuildRequest, KnowledgeGraphResponse

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now", "has", "have", "had", "is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "doing", "would", "could", "ought", "i", "me", "my", "myself", "we", "us", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "this", "that", "these", "those", "am", "as", "at", "by", "for", "in", "of", "on", "to", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very"
}

GENERIC_LABELS = {
    "text", "pdf", "docx", "webpage", "github_repo", "ai_chat", "github", "repo", "document", "file", "page"
}

def normalize_concept(text: str) -> str:
    # lowercase
    text = text.lower()
    # strip punctuation
    text = re.sub(r'[^\w\s-]', ' ', text)
    # collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_valid_concept(concept: str) -> bool:
    if not concept:
        return False
    if len(concept) <= 2:
        return False
    if len(concept) > 60:
        return False
    if concept.isdigit() or re.match(r'^-?\d+(?:\.\d+)?$', concept):
        return False
    if concept in STOPWORDS:
        return False
    if concept in GENERIC_LABELS:
        return False
    
    # check if it's entirely composed of stopwords or numbers
    words = concept.split()
    if all(w in STOPWORDS or w.isdigit() for w in words):
        return False
        
    return True

def extract_concepts_from_text(text: str) -> list[str]:
    # Extract unigrams, bigrams, and trigrams simply using regex words
    words = re.findall(r'\b[A-Za-z0-9_-]+\b', text)
    
    concepts = []
    
    # single terms
    for w in words:
        norm = normalize_concept(w)
        if is_valid_concept(norm):
            concepts.append(norm)
            
    # bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        norm = normalize_concept(bigram)
        if is_valid_concept(norm):
            concepts.append(norm)
            
    # trigrams
    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
        norm = normalize_concept(trigram)
        if is_valid_concept(norm):
            concepts.append(norm)
            
    return list(set(concepts))

def build_graph(db: Session, request: KnowledgeGraphBuildRequest, user_id: str) -> KnowledgeGraphResponse:
    # Delete old graph first
    nodes_to_delete = db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user_id).all()
    node_ids = [n.id for n in nodes_to_delete]
    
    if node_ids:
        # Delete related documents association
        db.execute(knowledge_node_documents.delete().where(knowledge_node_documents.c.node_id.in_(node_ids)))
        
        # Delete edges where this user's nodes are source or target
        db.query(KnowledgeEdge).filter(
            (KnowledgeEdge.source_node_id.in_(node_ids)) | 
            (KnowledgeEdge.target_node_id.in_(node_ids))
        ).delete(synchronize_session=False)
        
        # Delete the nodes themselves
        db.query(KnowledgeNode).filter(KnowledgeNode.id.in_(node_ids)).delete(synchronize_session=False)
        
    db.flush()
    
    chunks = db.query(DocumentChunk).join(Document).filter(Document.status == "ready", Document.user_id == user_id).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()
    
    if not chunks:
        db.commit()
        return KnowledgeGraphResponse(nodes=[], edges=[], node_count=0, edge_count=0, message="No document chunks available.")
        
    # extract concepts per chunk
    # we want to map concept -> documents and concept -> frequency
    concept_freq = Counter()
    concept_docs = defaultdict(set)
    
    chunk_concepts = [] # List of (chunk, [concepts])
    
    for chunk in chunks:
        extracted = extract_concepts_from_text(chunk.text)
        chunk_concepts.append((chunk, extracted))
        for concept in extracted:
            concept_freq[concept] += 1
            concept_docs[concept].add(chunk.document_id)
            
    # filter by min_frequency
    filtered_concepts = [c for c, freq in concept_freq.items() if freq >= request.min_frequency]
    
    if not filtered_concepts:
        db.commit()
        return KnowledgeGraphResponse(nodes=[], edges=[], node_count=0, edge_count=0, message="No concepts found meeting the minimum frequency.")
        
    # Sort concepts by frequency desc, then label asc
    filtered_concepts.sort(key=lambda c: (-concept_freq[c], c))
    
    # Limit to max nodes
    top_concepts = filtered_concepts[:request.max_nodes]
    top_concepts_set = set(top_concepts)
    
    # create edges based on co-occurrence
    edge_weights = Counter() # (nodeA, nodeB) -> weight
    edge_evidence = {} # (nodeA, nodeB) -> evidence dict
    
    # group chunks by document for window analysis
    docs_chunks = defaultdict(list)
    for chunk, concepts in chunk_concepts:
        # filter concepts to only top ones
        valid_concepts = [c for c in concepts if c in top_concepts_set]
        docs_chunks[chunk.document_id].append((chunk, valid_concepts))
        
    for doc_id, c_list in docs_chunks.items():
        # c_list is ordered by chunk_index
        for i, (chunk_a, concepts_a) in enumerate(c_list):
            for j in range(i, min(len(c_list), i + request.cooccurrence_window + 1)):
                chunk_b, concepts_b = c_list[j]
                
                # Pair concepts
                for ca in concepts_a:
                    for cb in concepts_b:
                        if ca != cb:
                            # sort to avoid A-B and B-A duplicates
                            pair = tuple(sorted([ca, cb]))
                            edge_weights[pair] += 1
                            if pair not in edge_evidence:
                                # snippet from chunk_a
                                snippet = chunk_a.text[:100] + "..." if len(chunk_a.text) > 100 else chunk_a.text
                                edge_evidence[pair] = {
                                    "document_id": doc_id,
                                    "chunk_id": chunk_a.id,
                                    "example_text": snippet
                                }
    
    # Create nodes
    concept_to_node = {}
    new_nodes = []
    
    for concept in top_concepts:
        node = KnowledgeNode(
            label=concept,
            frequency=concept_freq[concept],
            user_id=user_id
        )
        # Assign documents
        # For associations, we could do it after adding to db or just append doc models if we had them.
        # But we only have doc_ids in concept_docs. Let's just create nodes first.
        new_nodes.append(node)
        concept_to_node[concept] = node
        
    db.add_all(new_nodes)
    db.flush()
    
    # Create node-document associations
    node_doc_inserts = []
    for concept, node in concept_to_node.items():
        for doc_id in concept_docs[concept]:
            node_doc_inserts.append({"node_id": node.id, "document_id": doc_id})
            
    if node_doc_inserts:
        db.execute(knowledge_node_documents.insert(), node_doc_inserts)
        
    # Create edges
    new_edges = []
    
    # Deterministic order for edges
    sorted_pairs = sorted(edge_weights.keys())
    
    for pair in sorted_pairs:
        weight = edge_weights[pair]
        evidence = edge_evidence[pair]
        
        nodeA = concept_to_node[pair[0]]
        nodeB = concept_to_node[pair[1]]
        
        edge = KnowledgeEdge(
            source_node_id=nodeA.id,
            target_node_id=nodeB.id,
            relation_type="co_occurs_with",
            weight=float(weight),
            evidence_json=json.dumps(evidence),
            user_id=user_id
        )
        new_edges.append(edge)
        
    db.add_all(new_edges)
    db.commit()
    
    for n in new_nodes:
        db.refresh(n)
    for e in new_edges:
        db.refresh(e)
        
    return KnowledgeGraphResponse(
        nodes=new_nodes,
        edges=new_edges,
        node_count=len(new_nodes),
        edge_count=len(new_edges),
        message="Knowledge graph foundation built successfully."
    )

def get_graph(db: Session, user_id: str) -> KnowledgeGraphResponse:
    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.user_id == user_id).order_by(KnowledgeNode.frequency.desc(), KnowledgeNode.label.asc()).all()
    edges = db.query(KnowledgeEdge).filter(KnowledgeEdge.user_id == user_id).order_by(KnowledgeEdge.source_node_id.asc(), KnowledgeEdge.target_node_id.asc(), KnowledgeEdge.relation_type.asc()).all()
    
    return KnowledgeGraphResponse(
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
        message="Knowledge graph retrieved."
    )

def get_node(db: Session, node_id: str, user_id: str) -> KnowledgeNode | None:
    return db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id, KnowledgeNode.user_id == user_id).first()
