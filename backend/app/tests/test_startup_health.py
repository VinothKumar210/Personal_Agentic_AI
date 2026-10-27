import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import Settings
from app.services.startup_checks import run_startup_checks

@pytest.fixture
def mock_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

def test_startup_creates_directories(monkeypatch, mock_storage):
    monkeypatch.setattr("app.services.startup_checks.settings.STORAGE_DIR", mock_storage)
    
    run_startup_checks()
    
    originals_dir = os.path.join(mock_storage, "originals")
    assert os.path.isdir(originals_dir)

def test_health_endpoint_success(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "storage" in data
    assert "auth_dev_mode" in data
    assert "embedding_model" in data
    assert "chroma_collection" in data
    assert data["status"] == "ok"

def test_config_validation_auth_dev_mode_secret():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY must be changed from default when AUTH_DEV_MODE is False"):
        Settings(
            AUTH_DEV_MODE=False,
            JWT_SECRET_KEY="supersecretkey_change_me_in_production",
            DATABASE_URL="sqlite:///:memory:"
        )

def test_config_validation_auth_dev_mode_success():
    s = Settings(
        AUTH_DEV_MODE=False,
        JWT_SECRET_KEY="a_strong_production_secret",
        DATABASE_URL="sqlite:///:memory:"
    )
    assert s.JWT_SECRET_KEY == "a_strong_production_secret"
