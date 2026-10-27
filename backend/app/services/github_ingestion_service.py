import re
import httpx
import logging
from typing import Tuple, List, Dict, Optional
from app.core.config import settings
from app.services.code_chunker import chunk_code_file, detect_language

logger = logging.getLogger(__name__)

def _get_github_headers(pat: Optional[str] = None) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = pat or settings.GITHUB_PAT
    if token and token.strip():
        headers["Authorization"] = f"token {token.strip()}"
    return headers

def parse_github_repo_url(url: str) -> Tuple[str, str]:
    url = url.strip().rstrip("/")
    if not url.startswith("https://github.com/"):
        raise ValueError("Unsupported URL scheme or domain. Only https://github.com/ is allowed.")
    
    parts = url[len("https://github.com/"):].split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL format. Expected https://github.com/{owner}/{repo}")
    
    if len(parts) > 2:
        if parts[2] == "tree" or parts[2] == "blob":
            raise ValueError("Branch/path-scoped URLs are not supported in this phase. Please provide the root repository URL.")
        raise ValueError("Invalid GitHub repository URL format. Too many path segments.")
        
    owner, repo = parts[0], parts[1]
    if not owner or not repo:
        raise ValueError("Owner or repository name cannot be empty.")
        
    return owner, repo

def list_user_repositories(pat: Optional[str] = None) -> List[Dict]:
    """Lists accessible public and private repositories for the authenticated GitHub user."""
    token = pat or settings.GITHUB_PAT
    if not token or not token.strip():
        raise ValueError("GitHub PAT or authentication required to list repositories.")
        
    api_url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    headers = _get_github_headers(token)
    
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(api_url, headers=headers)
            if response.status_code == 401:
                raise ValueError("Invalid GitHub Personal Access Token (401 Unauthorized).")
            response.raise_for_status()
            repos = response.json()
            return [
                {
                    "name": r.get("name"),
                    "full_name": r.get("full_name"),
                    "private": r.get("private", False),
                    "html_url": r.get("html_url"),
                    "description": r.get("description"),
                    "default_branch": r.get("default_branch", "main")
                }
                for r in repos if isinstance(r, dict)
            ]
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to list GitHub repositories: {str(e)}")

def fetch_repository_tree(owner: str, repo: str) -> List[Dict]:
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    headers = _get_github_headers()
    
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(api_url, headers=headers)
            if response.status_code == 404:
                raise ValueError("Repository not found or is not accessible with current credentials.")
            if response.status_code == 403 and "rate limit" in response.text.lower():
                raise RuntimeError("GitHub API rate limit exceeded.")
            response.raise_for_status()
            
            data = response.json()
            if data.get("truncated"):
                logger.warning(f"GitHub API returned truncated tree for {owner}/{repo}. Some files may be missing.")
                
            return data.get("tree", [])
    except httpx.TimeoutException:
        raise RuntimeError("Request to fetch repository tree timed out.")
    except httpx.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching repository tree: {str(e)}")

def filter_ingestable_files(tree: List[Dict]) -> List[Dict]:
    allowed_exts = [ext.strip() for ext in settings.GITHUB_ALLOWED_EXTENSIONS.split(",")]
    
    ignored_paths = [
        ".git/", "node_modules/", "dist/", "build/", ".next/", 
        "venv/", ".venv/", "__pycache__/", "coverage/", "target/", ".cache/"
    ]
    
    excluded_filenames = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", 
        "poetry.lock", "Pipfile.lock"
    }
    
    ingestable = []
    
    for item in tree:
        if item.get("type") != "blob":
            continue
            
        path = item.get("path", "")
        if not path:
            continue
            
        # Check ignored paths
        if any(ignored in path for ignored in ignored_paths):
            continue
            
        # Check filename exclusions
        filename = path.split("/")[-1]
        if filename in excluded_filenames:
            continue
            
        # Check extensions
        if not any(path.endswith(ext) for ext in allowed_exts):
            continue
            
        # Check size limit (if size is present in tree API)
        size = item.get("size", 0)
        if size > settings.GITHUB_MAX_FILE_BYTES:
            continue
            
        ingestable.append(item)
        if len(ingestable) >= settings.GITHUB_MAX_FILES:
            break
            
    return ingestable

def fetch_file_text(owner: str, repo: str, path: str) -> str:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
    headers = _get_github_headers()
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(raw_url, headers=headers)
            response.raise_for_status()
            text = response.content.decode("utf-8", errors="replace")
            
            non_ws_count = len(text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
            if non_ws_count < 10:
                return ""
                
            return text
    except Exception as e:
        logger.warning(f"Failed to fetch {path}: {str(e)}")
        return ""

def build_repository_text(owner: str, repo: str, files: List[Dict]) -> Tuple[str, int]:
    combined = []
    files_ingested = 0
    
    for item in files:
        path = item.get("path")
        text = fetch_file_text(owner, repo, path)
        if text:
            combined.append(f"\n\n--- FILE: {path} ---\n\n{text}")
            files_ingested += 1
            
    return "".join(combined), files_ingested

def chunk_repository_files(
    owner: str, 
    repo: str, 
    files: List[Dict], 
    existing_sha_map: Optional[Dict[str, str]] = None
) -> Tuple[List[Dict], int, List[str]]:
    """
    Fetches and chunks repository files intelligently using code_chunker.py.
    Returns structured chunk dicts including per-file metadata (file_path, language, sha),
    the total files ingested/retained count, and a list of unchanged file paths skipped via delta sync.
    """
    chunk_records = []
    files_ingested = 0
    unchanged_paths = []
    
    for item in files:
        path = item.get("path", "")
        sha = item.get("sha", "")
        if not path:
            continue
            
        if existing_sha_map and path in existing_sha_map and sha and existing_sha_map[path] == sha:
            unchanged_paths.append(path)
            files_ingested += 1
            continue
            
        text = fetch_file_text(owner, repo, path)
        if not text:
            continue
            
        files_ingested += 1
        language = detect_language(path)
        file_chunks = chunk_code_file(text, file_path=path)
        
        for c_text in file_chunks:
            if c_text.strip():
                chunk_records.append({
                    "text": c_text.strip(),
                    "file_path": path,
                    "sha": sha,
                    "language": language
                })
                
    return chunk_records, files_ingested, unchanged_paths
