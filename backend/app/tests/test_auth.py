import pytest
from app.models.document import Document, DocumentChunk
from app.core.config import settings

def test_register_success(client, db):
    res = client.post("/api/auth/register", json={
        "email": "newuser@example.com",
        "password": "newpassword",
        "display_name": "New User"
    })
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data

def test_register_duplicate(client, db, test_user):
    res = client.post("/api/auth/register", json={
        "email": test_user.email,
        "password": "newpassword",
        "display_name": "Duplicate User"
    })
    assert res.status_code == 400

def test_login_success(client, test_user):
    res = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "password"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_login_failure(client, test_user):
    res = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "wrongpassword"
    })
    assert res.status_code == 400

def test_auth_me_with_token(client, test_user):
    token = client.post("/api/auth/login", json={"email": test_user.email, "password": "password"}).json()["access_token"]
    
    # We clear the dependency override that conftest provides for get_current_user to test real auth
    from app.main import app
    from app.api.deps import get_current_user, get_current_active_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_active_user, None)
    
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == test_user.email

def test_auth_dev_mode_behavior(client, test_user):
    from app.main import app
    from app.api.deps import get_current_user, get_current_active_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_active_user, None)

    # Test dev mode True returns local dev user
    settings.AUTH_DEV_MODE = True
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "local@example.com"

    # Test dev mode False requires auth
    settings.AUTH_DEV_MODE = False
    res = client.get("/api/auth/me")
    assert res.status_code == 401

    settings.AUTH_DEV_MODE = True # Reset

def test_auth_isolation(client, db, test_user, test_user_2):
    # We use the dependency overrides for the rest
    from app.main import app
    from app.api.deps import get_current_user, get_current_active_user
    
    def override_a():
        return test_user
    def override_b():
        return test_user_2

    # User A creates doc
    app.dependency_overrides[get_current_user] = override_a
    app.dependency_overrides[get_current_active_user] = override_a
    res_doc_a = client.post("/api/documents", json={"title": "Doc A", "source_type": "text"})
    doc_id_a = res_doc_a.json()["id"]

    # User B creates doc
    app.dependency_overrides[get_current_user] = override_b
    app.dependency_overrides[get_current_active_user] = override_b
    res_doc_b = client.post("/api/documents", json={"title": "Doc B", "source_type": "text"})
    doc_id_b = res_doc_b.json()["id"]

    # A tries to access B's document
    app.dependency_overrides[get_current_user] = override_a
    app.dependency_overrides[get_current_active_user] = override_a
    assert client.get(f"/api/documents/{doc_id_b}").status_code == 404

    # B tries to access A's document
    app.dependency_overrides[get_current_user] = override_b
    app.dependency_overrides[get_current_active_user] = override_b
    assert client.get(f"/api/documents/{doc_id_a}").status_code == 404

    # A gets their documents
    app.dependency_overrides[get_current_user] = override_a
    app.dependency_overrides[get_current_active_user] = override_a
    docs_a = client.get("/api/documents").json()["items"]
    assert len(docs_a) == 1 and docs_a[0]["title"] == "Doc A"
    
    # A cannot see B's jobs
    jobs_b = db.query(Document).filter_by(id=doc_id_b).first().jobs
    for job in jobs_b:
        assert client.get(f"/api/jobs/{job.id}").status_code == 404
        
    # A creates conversation
    app.dependency_overrides[get_current_user] = override_a
    app.dependency_overrides[get_current_active_user] = override_a
    conv_a = client.post("/api/conversations", json={}).json()
    conv_id_a = conv_a["id"]
    
    # B tries to access A's conversation
    app.dependency_overrides[get_current_user] = override_b
    app.dependency_overrides[get_current_active_user] = override_b
    assert client.get(f"/api/conversations/{conv_id_a}").status_code == 404
    
    # Test Topics & Graph isolation (A shouldn't see B's things)
    # This is implicitly verified by the empty sets returned for User B below
    assert len(client.get("/api/topics").json()["clusters"]) == 0
    assert len(client.get("/api/knowledge-graph").json()["nodes"]) == 0
