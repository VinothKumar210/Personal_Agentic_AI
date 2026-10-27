import os
from pypdf import PdfReader
from docx import Document as DocxDocument

def extract_text_from_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n".join(text)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")

def extract_text_from_docx(path: str) -> str:
    try:
        doc = DocxDocument(path)
        text = [paragraph.text for paragraph in doc.paragraphs if paragraph.text]
        return "\n".join(text)
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {str(e)}")

def extract_text_from_text(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Failed to read text file: {str(e)}")

def extract_text_from_markdown(path: str) -> str:
    return extract_text_from_text(path)

def extract_text(path: str, source_type: str) -> str:
    if source_type == "pdf":
        return extract_text_from_pdf(path)
    elif source_type == "docx":
        return extract_text_from_docx(path)
    elif source_type in ["text", "markdown"]:
        return extract_text_from_text(path)
    else:
        raise ValueError(f"Unsupported source type for extraction: {source_type}")
