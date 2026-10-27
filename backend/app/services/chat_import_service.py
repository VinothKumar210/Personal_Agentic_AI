import json
import logging
from typing import Any, Tuple, List, Dict

logger = logging.getLogger(__name__)

def detect_chat_export_format(filename: str, content: bytes) -> str:
    ext = filename.lower().split(".")[-1]
    if ext == "md":
        return "markdown"
    if ext == "txt":
        return "text"
        
    if ext == "json":
        try:
            data = json.loads(content)
            # Detect ChatGPT
            if isinstance(data, dict) and "mapping" in data:
                return "chatgpt_json"
            if isinstance(data, list) and len(data) > 0 and "mapping" in data[0]:
                return "chatgpt_json"
            # Detect Claude
            if isinstance(data, dict) and "chat_messages" in data:
                return "claude_json"
            if isinstance(data, list) and len(data) > 0 and "chat_messages" in data[0]:
                return "claude_json"
            return "generic_json"
        except Exception:
            return "unknown_json"
            
    return "unknown"

def normalize_role_strict(role: str) -> str | None:
    if not role:
        return None
    r = str(role).strip().lower()
    if r in ["user", "human"]:
        return "User"
    if r in ["assistant", "ai", "bot", "model", "claude", "chatgpt", "gemini"]:
        return "Assistant"
    if r in ["system", "developer", "tool"]:
        return "System"
    return None

def format_turn(role: str, text: str) -> str | None:
    normalized = normalize_role_strict(role)
    if not normalized:
        return None
    return f"{normalized}: {text.strip()}"

def extract_chatgpt_json(data: Any) -> str:
    dialogues = []
    
    if not isinstance(data, list):
        data = [data]
        
    for convo in data:
        mapping = convo.get("mapping", {})
        messages = []
        for node_id, node in mapping.items():
            msg = node.get("message")
            if not msg:
                continue
            
            create_time = msg.get("create_time") or 0
            author = msg.get("author", {})
            role = author.get("role", "")
            
            content = msg.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                continue
                
            text = ""
            if isinstance(parts, list):
                text = " ".join([str(p) for p in parts if isinstance(p, str)])
            
            if text.strip() and role:
                messages.append({"role": role, "text": text, "create_time": create_time})
                
        # Sort by create_time to preserve order
        messages.sort(key=lambda x: x["create_time"] if x["create_time"] is not None else 0)
        
        turns = []
        for m in messages:
            turn = format_turn(m["role"], m["text"])
            if turn:
                turns.append(turn)
                
        if turns:
            dialogues.append("\n\n".join(turns))
            
    return "\n\n---\n\n".join(dialogues)

def extract_claude_json(data: Any) -> str:
    dialogues = []
    
    if not isinstance(data, list):
        data = [data]
        
    for convo in data:
        messages = convo.get("chat_messages", [])
        turns = []
        for m in messages:
            sender = m.get("sender")
            text = m.get("text")
            if sender and text and str(text).strip():
                turn = format_turn(sender, text)
                if turn:
                    turns.append(turn)
                
        if turns:
            dialogues.append("\n\n".join(turns))
            
    return "\n\n---\n\n".join(dialogues)

def extract_generic_json(data: Any) -> str:
    messages = []
    
    def traverse(node):
        if isinstance(node, dict):
            # Check if this node is a plausible message
            role_keys = ["role", "sender", "author", "from", "type"]
            text_keys = ["text", "content", "message", "body"]
            
            raw_role = next((node[k] for k in role_keys if k in node and isinstance(node[k], str)), None)
            text = next((node[k] for k in text_keys if k in node and isinstance(node[k], str)), None)
            
            normalized_role = normalize_role_strict(raw_role) if raw_role else None
            
            if normalized_role and text and str(text).strip():
                messages.append({"role": normalized_role, "text": str(text).strip()})
            
            for v in node.values():
                traverse(v)
        elif isinstance(node, list):
            for item in node:
                traverse(item)
                
    traverse(data)
    
    turns = []
    for m in messages:
        turn = format_turn(m["role"], m["text"])
        if turn:
            turns.append(turn)
            
    return "\n\n".join(turns)

def extract_chat_text(filename: str, content: bytes) -> Tuple[str, Dict]:
    format_type = detect_chat_export_format(filename, content)
    
    text = ""
    if format_type == "markdown" or format_type == "text":
        text = content.decode("utf-8", errors="replace")
    elif format_type == "chatgpt_json":
        data = json.loads(content)
        text = extract_chatgpt_json(data)
    elif format_type == "claude_json":
        data = json.loads(content)
        text = extract_claude_json(data)
    elif format_type == "generic_json":
        data = json.loads(content)
        text = extract_generic_json(data)
    else:
        raise ValueError(f"Unable to parse chat file format for {filename}")
        
    # Check minimum length
    non_ws = len(text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
    if non_ws < 100:
        raise ValueError("Extracted chat text is too short or empty (requires at least 100 non-whitespace characters).")
        
    metadata = {
        "detected_format": format_type
    }
    
    return text, metadata
