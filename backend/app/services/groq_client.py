from groq import Groq
from app.core.config import settings

def is_groq_configured() -> bool:
    """
    Check if the GROQ API key is configured.
    """
    return bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip() != "your_groq_api_key_here")

def generate_grounded_answer(question: str, contexts: list[dict]) -> str:
    """
    Generate an answer to a question using only the provided context chunks.
    contexts is expected to be a list of dicts with:
    - citation_id: int
    - document_title: str
    - source_type: str
    - filename_uri: str
    - chunk_index: int
    - text: str
    """
    if not contexts:
        raise ValueError("No context chunks provided")

    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for ctx in contexts:
        ctx_str = (
            f"[{ctx['citation_id']}]\n"
            f"Document: {ctx['document_title']}\n"
            f"Source type: {ctx['source_type']}\n"
            f"Filename/URI: {ctx['filename_uri']}\n"
            f"Chunk index: {ctx['chunk_index']}\n"
            f"Text:\n{ctx['text']}\n"
        )
        context_strings.append(ctx_str)
    
    context_block = "\n---\n".join(context_strings)

    system_prompt = (
        "You are an expert AI assistant answering questions based solely on the provided context chunks.\n"
        "System behavior:\n"
        "- Answer only using the provided context chunks.\n"
        "- If the context is insufficient, say the knowledge base does not contain enough information.\n"
        "- Do not invent sources.\n"
        "- Cite sources inline using bracketed citation IDs like [1], [2].\n"
        "- Keep answers concise but useful.\n"
        "- Mention uncertainty when relevant.\n"
        "\nContext Chunks:\n"
        f"{context_block}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.0
    )

    return response.choices[0].message.content

def stream_grounded_answer_tokens(question: str, contexts: list[dict]):
    """
    Stream tokens for an answer to a question using only the provided context chunks.
    """
    if not contexts:
        raise ValueError("No context chunks provided")

    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for ctx in contexts:
        ctx_str = (
            f"[{ctx['citation_id']}]\n"
            f"Document: {ctx['document_title']}\n"
            f"Source type: {ctx['source_type']}\n"
            f"Filename/URI: {ctx['filename_uri']}\n"
            f"Chunk index: {ctx['chunk_index']}\n"
            f"Text:\n{ctx['text']}\n"
        )
        context_strings.append(ctx_str)
    
    context_block = "\n---\n".join(context_strings)

    system_prompt = (
        "You are an expert AI assistant answering questions based solely on the provided context chunks.\n"
        "System behavior:\n"
        "- Answer only using the provided context chunks.\n"
        "- If the context is insufficient, say the knowledge base does not contain enough information.\n"
        "- Do not invent sources.\n"
        "- Cite sources inline using bracketed citation IDs like [1], [2].\n"
        "- Keep answers concise but useful.\n"
        "- Mention uncertainty when relevant.\n"
        "\nContext Chunks:\n"
        f"{context_block}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.0,
        stream=True
    )

    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content

def generate_document_summary(title: str, chunks: list[dict]) -> str:
    """
    Generate a concise bulleted summary of a single document based on its chunks.
    chunks is expected to be a list of dicts with:
    - text: str
    """
    if not chunks:
        raise ValueError("No context chunks provided")

    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for i, chunk in enumerate(chunks):
        context_strings.append(f"[Chunk {i+1}]\n{chunk['text']}")
    
    context_block = "\n---\n".join(context_strings)

    system_prompt = (
        f"You are an expert summarizer. Summarize the document titled '{title}' using ONLY the provided text chunks.\n"
        "Guidelines:\n"
        "- Do not invent facts or bring in outside knowledge.\n"
        "- Mention uncertainty or missing information if the chunks are incomplete.\n"
        "- Use concise bullet points.\n"
        "- Include main topics, key concepts, important details, and possible follow-up questions.\n"
        "\nContext Chunks:\n"
        f"{context_block}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Please summarize this document based on the provided chunks."}
    ]

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.3
    )

    return response.choices[0].message.content

def generate_collection_summary(collection_name: str, document_contexts: list[dict]) -> str:
    """
    Generate a summary of a collection based on chunks from multiple documents.
    document_contexts is a list of dicts with:
    - title: str
    - chunks: list[str]
    """
    if not document_contexts:
        raise ValueError("No context chunks provided")

    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)

    context_strings = []
    for doc in document_contexts:
        chunks_joined = "\n".join(f"- {text}" for text in doc["chunks"])
        context_strings.append(f"Document: {doc['title']}\nChunks:\n{chunks_joined}")
    
    context_block = "\n---\n".join(context_strings)

    system_prompt = (
        f"You are an expert summarizer. Summarize the collection titled '{collection_name}' using ONLY the provided chunks from its documents.\n"
        "Guidelines:\n"
        "- Do not invent facts or bring in outside knowledge.\n"
        "- Mention uncertainty or missing information if the chunks are incomplete.\n"
        "- Use concise bullet points.\n"
        "- Include overall themes, repeated concepts across documents, notable differences if visible, and what the collection appears to be about.\n"
        "\nDocument Chunks:\n"
        f"{context_block}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Please summarize this collection based on the provided document chunks."}
    ]

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.3
    )

    return response.choices[0].message.content

def call_groq(prompt: str, model: str = None, temperature: float = 0.1, max_tokens: int = 500) -> str:
    """
    Calls Groq API with a prompt and returns the raw text response.
    """
    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    model_to_use = model or settings.GROQ_MODEL
    
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    response = client.chat.completions.create(
        model=model_to_use,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"} if "json" in prompt.lower() else None
    )
    return response.choices[0].message.content

def generate_completion(
    prompt: str,
    system_message: str | None = None,
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 500,
    json_mode: bool = False,
) -> str:
    """
    Generate a raw completion from Groq with optional system instructions.
    """
    if not is_groq_configured():
        raise RuntimeError("GROQ API Key is not configured")

    client = Groq(api_key=settings.GROQ_API_KEY)
    model_to_use = model or settings.GROQ_MODEL
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": model_to_use,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content

def parse_json_from_llm(raw_text: str) -> dict:
    """
    Safely extracts and parses JSON object from LLM response text.
    """
    import json
    import re
    if not raw_text:
        return {}
    try:
        return json.loads(raw_text)
    except Exception:
        pass
    # Try finding json inside ```json ... ``` blocks
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Try finding any outer braces
    match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {}
