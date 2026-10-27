import re
from typing import List, Tuple, Dict, Optional

def detect_language(file_path: str) -> str:
    path_lower = file_path.lower()
    if path_lower.endswith(".py"):
        return "python"
    elif any(path_lower.endswith(ext) for ext in [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]):
        return "javascript_typescript"
    elif path_lower.endswith(".go"):
        return "go"
    elif path_lower.endswith(".rs"):
        return "rust"
    elif path_lower.endswith(".java"):
        return "java"
    return "generic"

def _split_oversized_chunk(text: str, header: str, max_chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """Splits a large block of code into chunks of max_chunk_size with overlap, preserving the header."""
    lines = text.splitlines()
    chunks = []
    current_lines = []
    current_len = len(header) + 2

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chunk_size and current_lines:
            chunk_body = "\n".join(current_lines)
            chunks.append(f"{header}\n\n{chunk_body}")
            
            # calculate overlap lines from the end of current_lines
            overlap_lines = []
            overlap_len = 0
            for l in reversed(current_lines):
                if overlap_len + len(l) + 1 <= overlap:
                    overlap_lines.insert(0, l)
                    overlap_len += len(l) + 1
                else:
                    break
            current_lines = overlap_lines
            current_len = len(header) + 2 + sum(len(l) + 1 for l in current_lines)
        
        current_lines.append(line)
        current_len += line_len

    if current_lines:
        chunk_body = "\n".join(current_lines)
        chunks.append(f"{header}\n\n{chunk_body}")

    return chunks if chunks else [f"{header}\n\n{text}"]

def _chunk_python(lines: List[str], file_path: str, max_chunk_size: int, overlap: int) -> List[str]:
    blocks = []
    current_scope = "Top Level"
    current_block_lines = []
    current_class = None

    scope_regex = re.compile(r'^(\s*)(?:(?:async\s+)?def|class)\s+([a-zA-Z0-9__]+)')

    for line in lines:
        match = scope_regex.match(line)
        if match:
            indent, name = match.group(1), match.group(2)
            if not indent:  # Top-level class or function
                if current_block_lines:
                    blocks.append((current_scope, "\n".join(current_block_lines).strip()))
                    current_block_lines = []
                if line.lstrip().startswith("class "):
                    current_class = name
                    current_scope = f"Class {name}"
                else:
                    current_class = None
                    current_scope = f"Function {name}"
            elif len(indent) == 4 and current_class and line.lstrip().startswith("def "):
                # Method inside a class
                if current_block_lines and len("\n".join(current_block_lines)) > max_chunk_size:
                    blocks.append((current_scope, "\n".join(current_block_lines).strip()))
                    current_block_lines = []
                current_scope = f"Class {current_class} -> Method {name}"
        
        current_block_lines.append(line)

    if current_block_lines:
        blocks.append((current_scope, "\n".join(current_block_lines).strip()))

    results = []
    for scope, text in blocks:
        if not text.strip():
            continue
        header = f"File: {file_path} | Scope: {scope}" if file_path else f"Scope: {scope}"
        if len(text) + len(header) + 2 <= max_chunk_size:
            results.append(f"{header}\n\n{text}")
        else:
            results.extend(_split_oversized_chunk(text, header, max_chunk_size, overlap))
    
    return results

def _chunk_brace_language(lines: List[str], file_path: str, max_chunk_size: int, overlap: int, lang: str) -> List[str]:
    blocks = []
    current_scope = "Top Level"
    current_block_lines = []
    brace_depth = 0
    scope_at_depth_0 = "Top Level"

    # Regex patterns for functions, classes, interfaces, structs, methods across JS/TS/Go/Rust/Java
    if lang == "javascript_typescript":
        scope_regex = re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const)\s+([a-zA-Z0-9_]+)')
    elif lang == "go":
        scope_regex = re.compile(r'^\s*(?:func|type)\s+(?:\([^)]+\)\s+)?([a-zA-Z0-9_]+)')
    elif lang == "rust":
        scope_regex = re.compile(r'^\s*(?:pub\s+)?(?:async\s+)?(?:fn|struct|enum|impl|trait)\s+([a-zA-Z0-9_]+)')
    elif lang == "java":
        scope_regex = re.compile(r'^\s*(?:public|private|protected|static|final|\s)*\s+(?:class|interface|enum|record|void|[a-zA-Z0-9_<>[\]]+)\s+([a-zA-Z0-9_]+)\s*\(')
    else:
        scope_regex = re.compile(r'^\s*(?:function|class|def|func|fn)\s+([a-zA-Z0-9_]+)')

    for line in lines:
        if brace_depth == 0:
            match = scope_regex.match(line)
            if match and "{" in line:
                if current_block_lines:
                    blocks.append((scope_at_depth_0, "\n".join(current_block_lines).strip()))
                    current_block_lines = []
                name = match.group(1)
                scope_at_depth_0 = f"Definition: {name}"
                current_scope = scope_at_depth_0

        current_block_lines.append(line)
        open_count = line.count("{")
        close_count = line.count("}")
        brace_depth += (open_count - close_count)
        if brace_depth < 0:
            brace_depth = 0

        if brace_depth == 0 and open_count > 0 and close_count > 0:
            # single line block or closed block at depth 0
            pass
        elif brace_depth == 0 and close_count > 0 and current_block_lines:
            # Block just closed at top level
            blocks.append((scope_at_depth_0, "\n".join(current_block_lines).strip()))
            current_block_lines = []
            scope_at_depth_0 = "Top Level"
            current_scope = "Top Level"

    if current_block_lines:
        blocks.append((scope_at_depth_0, "\n".join(current_block_lines).strip()))

    results = []
    for scope, text in blocks:
        if not text.strip():
            continue
        header = f"File: {file_path} | Scope: {scope}" if file_path else f"Scope: {scope}"
        if len(text) + len(header) + 2 <= max_chunk_size:
            results.append(f"{header}\n\n{text}")
        else:
            results.extend(_split_oversized_chunk(text, header, max_chunk_size, overlap))
            
    return results

def chunk_code_file(text: str, file_path: str = "", max_chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """
    Intelligent block chunker for source code.
    Extracts functions, classes, and structs based on language syntax rules.
    Falls back to deterministic line/paragraph split if generic or oversized.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines()
    lang = detect_language(file_path)

    if lang == "python":
        return _chunk_python(lines, file_path, max_chunk_size, overlap)
    elif lang in ["javascript_typescript", "go", "rust", "java"]:
        return _chunk_brace_language(lines, file_path, max_chunk_size, overlap, lang)
    else:
        # Generic split
        header = f"File: {file_path}" if file_path else "Code File"
        if len(text) + len(header) + 2 <= max_chunk_size:
            return [f"{header}\n\n{text.strip()}"]
        return _split_oversized_chunk(text.strip(), header, max_chunk_size, overlap)
