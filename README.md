# SAIT AI - AI Document Chat System

SAIT AI is a full-stack Retrieval-Augmented Generation (RAG) system that allows users to upload documents (PDF, DOCX, TXT, images) and chat with an AI that answers questions based on the uploaded content.

## Architecture

┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Open WebUI  │────▶│  FastAPI      │────▶│  Ollama      │
│  (Frontend)  │     │  (Backend)    │     │  (Gemma2:2b) │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ PostgreSQL│ │  Qdrant  │ │  Hugging │
        │ (History) │ │ (Vectors)│ │  Face    │
        └──────────┘ └──────────┘ └──────────┘

## Tech Stack
| Component       | Technology                          |
|-----------------|-------------------------------------|
| Backend         | Python, FastAPI, Uvicorn            |
| LLM             | Ollama, Gemma2:2b                   |
| Embeddings      | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB       | Qdrant                              |
| Database        | PostgreSQL 16                       |
| Frontend        | Open WebUI                          |
| OCR             | Tesseract, PaddleOCR, PyMuPDF       |
| Containerization| Docker, Docker Compose              |

## Features
- Multi-format document upload: PDF, DOCX, TXT, PNG, JPG, CSV, JSON
- OCR support: Extracts text from scanned documents and images
- Semantic search: Finds relevant document chunks using vector embeddings
- Chat history: PostgreSQL-backed session management
- OpenAI-compatible API: Works with any OpenAI SDK client
- Open WebUI integration: Chat interface via Open WebUI pipeline
- Background processing: Concurrent document ingestion with progress tracking
- Caching: In-memory response cache for repeated queries
- Tag-based filtering: Organize and filter documents by tags

## API Endpoints
POST /upload                       - Upload a document for processing
GET  /upload/status/{filename}     - Check processing status
GET  /documents                    - List all uploaded documents
DELETE /documents/{filename}       - Delete a document
POST /chat                         - Send a question
GET  /chat/history/{session_id}    - Get chat history for a session
GET  /chat/sessions                - List all chat sessions
POST /v1/chat/completions          - OpenAI-compatible chat API
GET  /v1/models                    - List available models
GET  /v1/documents                 - List documents (v1 format)
POST /auth/generate-key            - Generate an API key
POST /cache/clear                  - Clear response cache
GET  /                             - Health check

## Environment Variables
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
QDRANT_HOST, QDRANT_PORT
LLAMA_SWAP_HOST, LLM_MODEL
API_KEY

## Docker Resource Limits
PostgreSQL: 512 MB RAM, 1 CPU
Qdrant: 1 GB RAM, 1 CPU
LlamaSwap: 8 GB RAM, 4 CPUs
FastAPI: 6 GB RAM, 4 CPUs