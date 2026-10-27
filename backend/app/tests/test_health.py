import pytest
from unittest.mock import patch

@patch("app.api.routes.health.is_groq_configured")
@patch("app.api.routes.health.check_chroma_health")
def test_health_endpoint(mock_chroma_health, mock_groq_configured, client, db):
    mock_chroma_health.return_value = True
    mock_groq_configured.return_value = True
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    
    assert "service" in data
    assert data["service"] == "backend"
    
    assert "version" in data
    assert isinstance(data["version"], str)
    
    assert "database" in data
    assert data["database"] in ["ok", "unavailable"]
    
    assert "chroma" in data
    assert data["chroma"] in ["ok", "unavailable"]
    
    assert "groq_configured" in data
    assert isinstance(data["groq_configured"], bool)
