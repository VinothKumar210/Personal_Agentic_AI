import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.db.base import Base
from app.main import app
from app.db.session import get_db
from app.core.config import settings
import tempfile

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def override_storage_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings.STORAGE_DIR = tmp_dir
        yield tmp_dir

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)



@pytest.fixture(scope="function")
def test_user(db):
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        id="dev-user-id",
        email="test1@example.com",
        hashed_password=get_password_hash("password"),
        display_name="Test User 1",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def test_user_2(db):
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        id="test-user-2",
        email="test2@example.com",
        hashed_password=get_password_hash("password"),
        display_name="Test User 2",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture(scope="function")
def client(db, test_user):
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    from app.api.deps import get_current_user, get_current_active_user
    
    def override_get_current_user():
        return test_user
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_active_user] = override_get_current_user
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_background_tasks():
    with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
        yield mock_add_task
