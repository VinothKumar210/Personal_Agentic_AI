# Agentic Personal Knowledge Assistant

This project is the foundational architecture for a local-first personal AI knowledge assistant.

Currently implemented:
- **FastAPI backend** scaffold
- **Next.js frontend** dashboard shell
- **PostgreSQL** and **ChromaDB** integrations via Docker Compose
- `/api/health` diagnostic endpoint
- **Metadata Database Schema**: SQLAlchemy models for Users, Documents, Jobs, Collections, Tags.
- **Authentication & Ownership**: Core isolation with JWT-based Auth. Every resource belongs to a specific user.
- **Document Library UI**: Create and view metadata records.
- **File Upload & Text Extraction**: Upload `.pdf`, `.docx`, `.md`, and `.txt` files.
- **Chunking**: Deterministic overlapping text chunking.
- **Local Embeddings & ChromaDB Indexing**: Generates embeddings locally using `BAAI/bge-small-en-v1.5` and tracks chunk index status.
- **Semantic Search**: Retrieval-only semantic search over uploaded chunks via ChromaDB.
- **Document Summaries**: Groq-powered bulleted summaries grounded purely in extracted chunks.
- **Collection Summaries**: Groq-powered summaries across multiple associated documents (backend only).
- **Multi-Turn Chat Memory**: Persistent chat interface where recent history informs the retrieval context. Final generative answers are strictly grounded in retrieved chunks, preventing hallucination.

- **Topic Clustering**: Aggregates chunks into clusters based on overlapping metadata and concepts, storing relationships in SQLite/PostgreSQL.
- **Learning Path Planner**: Heuristically analyzes your stored knowledge base against predefined role maps (e.g., `llm_engineer`) to visualize strengths and output prioritized learning gaps. No external APIs or agents are used for this.
- **Interactive Force-Directed Knowledge Graph & Concept Explorer**: High-performance HTML5 Canvas visualizer with 60fps spring-physics simulation, concept node search, frequency filtering, and click-to-inspect Concept Node Inspector Drawer displaying co-occurrence relationships and direct links to associated source documents.
- **Asynchronous Processing Pipeline**: Ingestion and indexing queue local background processing using FastAPI BackgroundTasks.
- **Production Readiness & Hardening**: Strict environment configuration bounds, startup directory/database verification, standardized error schemas, and robust health checks.
- **Export, Backup, and Restore**: Full data portability supporting JSON export bundles and dry-run, merge, or replace restore modes with zero secrets or raw file exposure.
- **Response Streaming (SSE) & Hybrid Search**: Live Server-Sent Events token streaming and Reciprocal Rank Fusion (BM25 lexical + dense semantic embeddings) with cross-encoder reranking.
- **Interactive Document Workspace & Inline Notes**: Dedicated dual-pane modal supporting real-time SSE Q&A grounded exclusively in a single document and persistent, chunk-level personal annotations that export/restore seamlessly.


### 5. AI Chat & Querying
- **RAG Question Answering**: Query your processed documents using FAISS/ChromaDB.
- **Future: Agent Workflows**: Will delegate multi-step web research to specialized agents (planning phase).
- **Future: Neo4j/NetworkX Integration**: The current knowledge graph foundation works locally in PostgreSQL. Advanced force-directed graphs and ontology modeling are planned for future phases.

*Note: The first indexing event will download the local embedding model. The test suite correctly mocks this to prevent network calls during testing. Local OCR is implemented for images and scanned PDFs. Topic Clustering is implemented using deterministic offline analysis. Agents, LangGraph, advanced GitHub features, and Neo4j knowledge graphs are still NOT implemented. Live AI chat sync, shared-chat URL scraping, and provider account imports/APIs are still NOT implemented. Groq is actively required to run Q&A responses and summaries.*

**Warning:** Embedding Runtime limitation: Local embeddings require `sentence-transformers` and its heavy `torch` (PyTorch) dependencies. The first installation and model download may be quite large. If developing natively on Windows with Python 3.13, PyTorch wheel installations frequently fail or experience extremely slow connection timeouts. The recommended and fully supported installation environment is the provided Docker Compose runtime using Python 3.11.

## Authentication and Security

A basic authentication and ownership layer is implemented to safely support user-specific knowledge bases in a local-first application. 
- All resources (documents, collections, summaries, tags, chats, graphs) are strictly scoped to the authenticated user.
- **Dev Mode**: When `AUTH_DEV_MODE=True` in `.env`, all unauthenticated local requests map to a shared dev user (`local@example.com`). This is intended **only** for single-user local development.
- **Production Mode**: In production or multi-user deployments, you must set `AUTH_DEV_MODE=False` and define a strong `JWT_SECRET_KEY`.

## API Endpoints

### Auth
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Authenticate via JSON format to receive a JWT access token

### Documents
- `POST /api/documents/upload` - Upload file, extract text, chunk, and index locally
- `POST /api/sources/webpage` - Ingest a webpage (one-URL static HTML ingestion)
- `POST /api/sources/github-repo` - Ingest a public GitHub repository (source code files)
- `POST /api/sources/ai-chat` - Import exported AI chat files (JSON, MD, TXT)
- `POST /api/sources/ocr` - Ingest images and scanned PDFs using local OCR
- `GET /api/documents` - List documents
- `GET /api/documents/{id}` - Get document details
- `PATCH /api/documents/{id}` - Update document metadata
- `DELETE /api/documents/{id}` - Delete document
- `POST /api/documents/{id}/index` - Re-index document chunks
- `GET /api/jobs/{job_id}` - Check the status of a background ingestion job

### Summaries
- `POST /api/documents/{id}/summary` - Generate Groq-powered document summary based only on chunks
- `POST /api/collections/{id}/summary` - Generate Groq-powered collection summary based only on chunks

### Collections & Tags
- `POST /api/collections` - Create a collection
- `POST /api/tags` - Create a tag
- `POST /api/collections/{collection_id}/documents/{document_id}` - Add document to collection
- `POST /api/documents/{document_id}/tags/{tag_id}` - Tag a document

### Retrieval & Chat
- `POST /api/search` - Semantic search against vector index
- `POST /api/rag/answer` - One-shot Q&A grounded in retrieved context
- `POST /api/conversations` - Create a new chat session
- `POST /api/conversations/{id}/messages` - Send a message and get a grounded response

### Learning Path
- `POST /api/learning/profiles` - Create a learning profile
- `GET /api/learning/profiles` - List learning profiles
- `GET /api/learning/profiles/{id}` - Get learning profile
- `DELETE /api/learning/profiles/{id}` - Delete learning profile
- `POST /api/learning/analyze` - Analyze learning path and generate heuristic recommendations

### Knowledge Graph
- `GET /api/knowledge-graph` - Get the current user's local knowledge graph
- `POST /api/knowledge-graph/build` - Build or rebuild local co-occurrence knowledge graph
- `GET /api/knowledge-graph/nodes/{node_id}/documents` - Retrieve all source documents associated with a concept node

## Limitations & Future Work

The system currently focuses on core architecture and local vector capabilities.

**Implemented:**
- File uploads (PDF, DOCX, TXT, MD) - Note: Normal PDF upload uses embedded text extraction.
- Webpage URL Ingestion (static HTML only)
- Public GitHub Repository Ingestion (single-branch, text/code extraction)
- AI Chat File Import (JSON, MD, TXT exports only; no live API sync or web scraping)
- Image and Scanned Document OCR Ingestion (local OCR for images and scanned/image-heavy PDFs)
- Local sentence-transformers embeddings
- Local Chroma vector store
- Semantic search
- Document and Collection summaries (Groq)
- One-shot RAG Q&A (Groq)
- Multi-turn Chat Memory (Groq)
- Topic Clustering
- Learning Path / Skill-Gap Analysis
- Interactive Force-Directed Knowledge Graph & Concept Explorer

**Not yet implemented:**
- Advanced web crawling and browser-rendered (JavaScript) ingestion
- Private repository ingestion (auth)
- GitHub commit history, issues, PRs
- Code execution or agentic deep code analysis
- Live AI chat sync, shared-chat URL scraping, provider account imports/APIs
- Neo4j graph database integration and advanced ontology/entity extraction
- Advanced Agents / LangGraph / LangChain

## Prerequisites
- Docker and Docker Compose
- Node.js (if developing frontend locally without Docker)
- Python 3.11+ (if developing backend locally without Docker)

## Setup Instructions

### 1. Prerequisites
- **Docker and Docker Compose** (Highly Recommended)
- **Python 3.11+** (for local backend development)
- **Node.js 20+** (for local frontend development)
- **System Dependencies for OCR**: If `OCR_ENABLED=true`, you must have `tesseract` and `poppler-utils` installed on your system.

### 2. Environment Variables
Copy the environment variables example file:
```bash
cp .env.example .env
```
Update the `.env` file with your actual API keys:
- Set `GROQ_API_KEY` to your Groq API key
- (Optional) Set `AUTH_DEV_MODE=False` if you wish to require strict authentication locally
- (Optional) Set `JWT_SECRET_KEY` to a secure random string for JWT token generation

### 3. Local Quickstart (Without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Unix: source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/create_dev_user.py
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Or to build: npm run build
```

**Running Tests:**
```bash
cd backend
pytest app/tests
```

## Migration Notes
- **Migration 001-008:** Metadata, Document chunks, summaries, chat memory, topics, learning paths, knowledge graphs.
- **Migration 009:** Added `users` table and enforced ownership across all metadata schemas.
- **Migration 010:** Enforced unique constraints for Collections and Tags based on user ownership.

## Troubleshooting

- **Chroma Unavailable**: If Chroma is not running, vector embeddings will fail. Make sure Chroma is running natively or via Docker Compose on port 8000.
- **Groq API Key Missing**: Generative functions like Q&A and Summaries will return 503 Service Unavailable if `GROQ_API_KEY` is not provided.
- **Torch / Sentence-Transformers Install Issues**: The `bge-small-en-v1.5` model requires PyTorch. If you encounter installation timeouts (especially on Windows / Python 3.13), use the provided Docker Compose environment which guarantees compatible dependencies.
- **Docker CLI Missing**: Ensure Docker Desktop is running.
- **OCR Binaries Missing**: If you receive errors about "TesseractNotFoundError" or "pdf2image poppler not installed", install Tesseract-OCR and Poppler via your system package manager (e.g. `brew install tesseract poppler` on Mac, or Windows installers).

## Export, Backup, and Restore
The Personal Knowledge Assistant provides full local data portability for authenticated users:
- **Export Backup (`GET /api/export`)**: Downloads a JSON bundle (`knowledge-backup-YYYY-MM-DD.json`) containing all your database-backed records and text chunks. Note that password hashes, API keys, JWT secrets, raw uploaded files, and Chroma embeddings are strictly excluded for security and portability.
- **Restore Backup (`POST /api/restore`)**: Restores a JSON bundle into the current authenticated user's account. Supported modes:
  - **`dry_run`**: Validates the bundle schema and previews record counts without making any database changes.
  - **`merge`**: Inserts new records, skips duplicates using stable identity (e.g., collection name, tag name, or document title + source uri), and automatically generates new UUIDs if ID collisions occur while preserving all relationship links.
  - **`replace`**: Safely wipes the current authenticated user's restorable records before importing the backup bundle. Other users' data remains completely untouched. Restored document chunks are set to `embedding_status="pending"` for re-indexing.

## Usage

- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Backend Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

## Current Limitations
To keep the foundation clean, secure, and local-first, the following features are intentionally NOT implemented in the current release:
- **No OAuth or External Identity Providers**: Authentication uses local email/password with JWT access tokens.
- **No Team Accounts or Multi-Tenant Sharing**: All resources belong strictly to individual users without team sharing or collaborative permissions.
- **No Cloud Sync or Scheduled Backups**: Backups are manual JSON exports downloaded locally; automatic cloud storage or cron scheduling is not implemented.
- **No Raw File Backup**: Export bundles include database metadata and extracted text chunks only; original raw binary files are not exported.
- **No Chroma Embedding Export**: Vector embeddings are re-indexed locally upon restore (`embedding_status="pending"`) rather than exported in the bundle.

## Future Phases (Not Yet Implemented)
- Neo4j graph database integration and advanced ontology/entity extraction
- Agentic Workflows (autonomous research and multi-step ingestion agents)
- Advanced Web Crawling, private GitHub repos, GitHub issues/PRs/commit history, live AI chat sync, and shared-chat scraping
