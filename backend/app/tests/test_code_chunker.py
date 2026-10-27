import pytest
from app.services.code_chunker import detect_language, chunk_code_file

def test_detect_language():
    assert detect_language("app/main.py") == "python"
    assert detect_language("frontend/src/App.tsx") == "javascript_typescript"
    assert detect_language("pkg/server/handler.go") == "go"
    assert detect_language("src/lib.rs") == "rust"
    assert detect_language("com/example/Main.java") == "java"
    assert detect_language("README.md") == "generic"

def test_chunk_python_functions_and_classes():
    code = """
class UserService:
    def __init__(self):
        self.users = []

    def add_user(self, name: str):
        self.users.append(name)
        return True

def standalone_helper():
    print("Helper function")
"""
    chunks = chunk_code_file(code, file_path="app/services/user.py", max_chunk_size=1000)
    assert len(chunks) >= 2
    assert any("Scope: Class UserService" in c for c in chunks)
    assert any("Scope: Function standalone_helper" in c for c in chunks)

def test_chunk_javascript_typescript_blocks():
    code = """
export async function fetchUserData(userId: string) {
    const res = await fetch(`/api/users/${userId}`);
    return res.json();
}

class AuthController {
    constructor() {
        this.token = null;
    }
}
"""
    chunks = chunk_code_file(code, file_path="src/api.ts", max_chunk_size=1000)
    assert len(chunks) >= 2
    assert any("Scope: Definition: fetchUserData" in c for c in chunks)
    assert any("Scope: Definition: AuthController" in c for c in chunks)

def test_chunk_generic_fallback_and_oversized():
    long_text = "line\n" * 500
    chunks = chunk_code_file(long_text, file_path="data/config.txt", max_chunk_size=200, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert "File: data/config.txt" in c
        assert len(c) <= 300  # allow small margin for header + line lengths
