import re
from typing import List

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """
    Chunks text deterministically preserving paragraphs where possible.
    Target size is chunk_size, with an overlap of overlap.
    """
    if not text.strip():
        return []

    # Normalize newlines
    text = text.replace('\r\n', '\n')
    
    # Split by double newline to get paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = []
    current_len = 0

    def add_current_chunk():
        nonlocal current_chunk, current_len
        if current_chunk:
            chunk_text_str = "\n\n".join(current_chunk)
            if chunk_text_str.strip():
                chunks.append(chunk_text_str)
            
            # Start new chunk with overlap
            overlap_chunk = []
            overlap_len = 0
            for p in reversed(current_chunk):
                if overlap_len + len(p) <= overlap:
                    overlap_chunk.insert(0, p)
                    overlap_len += len(p) + 2
                else:
                    break
            
            current_chunk = overlap_chunk
            current_len = sum(len(p) for p in current_chunk) + (len(current_chunk) - 1) * 2 if current_chunk else 0

    for p in paragraphs:
        if current_len + len(p) > chunk_size and current_len > 0:
            add_current_chunk()
            
        if len(p) > chunk_size:
            # Simple split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', p)
            for s in sentences:
                if current_len + len(s) > chunk_size and current_len > 0:
                    add_current_chunk()
                
                if len(s) > chunk_size:
                    # Split by arbitrary length if a single sentence is too big
                    for i in range(0, len(s), chunk_size - overlap):
                        part = s[i:i + chunk_size]
                        if current_len + len(part) > chunk_size and current_len > 0:
                            add_current_chunk()
                        current_chunk.append(part)
                        current_len += len(part) + 2
                else:
                    current_chunk.append(s)
                    current_len += len(s) + 2
        else:
            current_chunk.append(p)
            current_len += len(p) + 2

    if current_chunk:
        chunk_text_str = "\n\n".join(current_chunk)
        if chunk_text_str.strip():
            chunks.append(chunk_text_str)

    # Clean up empty chunks and duplicates
    final_chunks = []
    for c in chunks:
        c = c.strip()
        if c and (not final_chunks or final_chunks[-1] != c):
            final_chunks.append(c)

    return final_chunks
