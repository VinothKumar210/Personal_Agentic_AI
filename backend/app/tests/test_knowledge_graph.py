import pytest
from app.models.document import Document, DocumentChunk, KnowledgeNode, KnowledgeEdge

def test_build_graph_no_chunks(client):
    response = client.post("/api/knowledge-graph/build", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert "No document chunks" in data["message"]
    assert len(data["nodes"]) == 0
    assert len(data["edges"]) == 0

def test_build_graph_with_chunks(client, db):
    # Add ready document and chunks
    doc1 = Document(user_id="dev-user-id", title="AI Research", source_type="text", status="ready")
    db.add(doc1)
    db.commit()
    
    # We add concepts that should be extracted
    # Stopwords like "The", "is", "a", "and" should be ignored
    text1 = "Retrieval Augmented Generation is a powerful technique for AI models."
    text2 = "AI models benefit from Retrieval Augmented Generation and vector databases."
    
    chunk1 = DocumentChunk(document_id=doc1.id, chunk_index=0, text=text1, character_count=len(text1))
    chunk2 = DocumentChunk(document_id=doc1.id, chunk_index=1, text=text2, character_count=len(text2))
    
    db.add_all([chunk1, chunk2])
    db.commit()

    response = client.post("/api/knowledge-graph/build", json={
        "min_frequency": 2, # 'Retrieval Augmented Generation', 'AI models' will appear twice
        "max_nodes": 10
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] > 0
    
    # Verify nodes
    node_labels = [n["label"] for n in data["nodes"]]
    # Should contain "retrieval augmented generation" and "ai models" because they appear in both chunks
    assert "retrieval augmented generation" in node_labels
    assert "ai models" in node_labels
    
    # Stopwords should not be nodes
    assert "the" not in node_labels
    assert "is" not in node_labels
    
    # Verify edges
    assert data["edge_count"] > 0
    edges = data["edges"]
    
    # Check if retrieval augmented generation and ai models co-occur
    # We find their IDs
    rag_id = next(n["id"] for n in data["nodes"] if n["label"] == "retrieval augmented generation")
    ai_id = next(n["id"] for n in data["nodes"] if n["label"] == "ai models")
    
    # Look for edge between them
    found_edge = False
    for e in edges:
        if (e["source_node_id"] == rag_id and e["target_node_id"] == ai_id) or \
           (e["source_node_id"] == ai_id and e["target_node_id"] == rag_id):
            found_edge = True
            break
            
    assert found_edge

def test_get_graph(client, db):
    response = client.get("/api/knowledge-graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data

def test_get_missing_node(client):
    response = client.get("/api/knowledge-graph/nodes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_invalid_max_nodes(client):
    response = client.post("/api/knowledge-graph/build", json={
        "max_nodes": 1000 # limit is 500
    })
    assert response.status_code == 422

def test_rebuild_replaces_graph(client, db):
    # build twice and ensure total nodes in DB is same as returned
    response1 = client.post("/api/knowledge-graph/build", json={"min_frequency": 2})
    assert response1.status_code == 200
    count1 = response1.json()["node_count"]
    
    response2 = client.post("/api/knowledge-graph/build", json={"min_frequency": 2})
    assert response2.status_code == 200
    count2 = response2.json()["node_count"]
    
    assert count1 == count2
    
    # check DB directly
    db_nodes = db.query(KnowledgeNode).count()
    assert db_nodes == count2

def test_rebuild_clears_graph_when_empty(client, db):
    # First ensure we have a graph
    doc = Document(user_id="dev-user-id", title="AI", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    chunk = DocumentChunk(document_id=doc.id, chunk_index=0, text="AI works.", character_count=9)
    chunk2 = DocumentChunk(document_id=doc.id, chunk_index=1, text="AI works.", character_count=9)
    db.add_all([chunk, chunk2])
    db.commit()
    
    res1 = client.post("/api/knowledge-graph/build", json={"min_frequency": 2})
    assert res1.json()["node_count"] > 0
    
    # Now make the document not ready
    doc.status = "processing"
    db.commit()
    
    res2 = client.post("/api/knowledge-graph/build", json={"min_frequency": 2})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["node_count"] == 0
    assert data2["edge_count"] == 0
    
    # Check DB
    assert db.query(KnowledgeNode).count() == 0
    assert db.query(KnowledgeEdge).count() == 0

def test_edge_aggregation(client, db):
    # Create repeated co-occurrences of the same terms
    doc = Document(user_id="dev-user-id", title="Testing Aggregation", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    
    text = "Machine learning and deep learning."
    chunk1 = DocumentChunk(document_id=doc.id, chunk_index=0, text=text, character_count=len(text))
    chunk2 = DocumentChunk(document_id=doc.id, chunk_index=1, text=text, character_count=len(text))
    db.add_all([chunk1, chunk2])
    db.commit()
    
    res = client.post("/api/knowledge-graph/build", json={
        "min_frequency": 2,
        "cooccurrence_window": 2
    })
    
    edges = res.json()["edges"]
    # We expect one edge between "machine learning" and "deep learning", with weight > 1
    # Find edge
    found = False
    target_edge_weight = 0
    for e in edges:
        # Check relation between the two
        nodeA = next((n for n in res.json()["nodes"] if n["id"] == e["source_node_id"]), None)
        nodeB = next((n for n in res.json()["nodes"] if n["id"] == e["target_node_id"]), None)
        
        if nodeA and nodeB:
            labels = {nodeA["label"], nodeB["label"]}
            if "machine learning" in labels and "deep learning" in labels:
                found = True
                target_edge_weight = e["weight"]
                break
                
    assert found, "Expected edge between machine learning and deep learning not found."
    assert target_edge_weight > 1.0, "Expected weight > 1.0 for aggregated edge."
    
    # We at least ensure that the total edges is correct and no duplicates exist.
    edge_pairs = set()
    for e in edges:
        pair = tuple(sorted([e["source_node_id"], e["target_node_id"]]))
        assert pair not in edge_pairs, "Duplicate edge found!"
        edge_pairs.add(pair)

def test_min_frequency_filtering(client, db):
    doc = Document(user_id="dev-user-id", title="Frequency Filter", source_type="text", status="ready")
    db.add(doc)
    db.commit()
    
    # "RepeatedConcept" appears twice, "RareConcept" appears once
    text1 = "RepeatedConcept RareConcept"
    text2 = "RepeatedConcept"
    
    chunk1 = DocumentChunk(document_id=doc.id, chunk_index=0, text=text1, character_count=len(text1))
    chunk2 = DocumentChunk(document_id=doc.id, chunk_index=1, text=text2, character_count=len(text2))
    db.add_all([chunk1, chunk2])
    db.commit()
    
    res = client.post("/api/knowledge-graph/build", json={
        "min_frequency": 2,
        "max_nodes": 10
    })
    
    assert res.status_code == 200
    data = res.json()
    
    node_labels = [n["label"] for n in data["nodes"]]
    assert "repeatedconcept" in node_labels, "Expected repeated concept to appear."
    assert "rareconcept" not in node_labels, "Expected rare concept to be filtered out."

def test_invalid_cooccurrence_window(client):
    res = client.post("/api/knowledge-graph/build", json={"cooccurrence_window": 0})
    assert res.status_code == 422
    
    res2 = client.post("/api/knowledge-graph/build", json={"cooccurrence_window": 11})
    assert res2.status_code == 422
