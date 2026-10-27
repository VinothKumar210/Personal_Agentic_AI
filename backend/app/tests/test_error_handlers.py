import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_404_error_format():
    response = client.get("/api/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["code"] == "HTTP_ERROR"
    assert data["detail"] == "Not Found"

def test_422_validation_error_format():
    # Login without payload
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Validation failed"
    assert data["code"] == "VALIDATION_ERROR"
    assert "errors" in data
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) > 0

# Note: Testing 500 error is harder because we have to mock an unhandled exception inside a route,
# which TestClient usually catches and bubbles up if not configured correctly.
# But we can create a temporary route on the app.

@pytest.fixture
def fault_client():
    @app.get("/api/test-500")
    def trigger_error():
        raise ValueError("Simulated internal crash")
    
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

def test_500_generic_error_format(fault_client: TestClient):
    response = fault_client.get("/api/test-500")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal server error"
    assert data["code"] == "INTERNAL_ERROR"
    assert "Simulated internal crash" not in data["detail"] # Must not leak traceback

