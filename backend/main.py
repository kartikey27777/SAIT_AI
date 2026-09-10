import os
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_API_KEY"] = ""
os.environ["LLAMA_SWAP_HOST"] = os.environ.get("LLAMA_SWAP_HOST", "http://localhost:8080")
os.environ["DO_NOT_TRACK"] = "1"

import uuid
import time
import json
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from backend.routes.upload import router as upload_router
from backend.routes.chat import router as chat_router
from backend.routes.website import router as website_router
from backend.services.auth import get_api_key, generate_api_key

app = FastAPI()


@app.on_event("startup")
async def _warmup():
    import threading
    def _load():
        try:
            from backend.services.embeddings import get_model
            get_model()
            print("[startup] Embedding model loaded")
        except Exception as e:
            print(f"[startup] Embedding model warmup failed: {e}")
    threading.Thread(target=_load, daemon=True).start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Session-Id"],
)

app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(website_router)


@app.get("/")
def home():
    return {
        "message": "SAIT AI is running"
    }


@app.post("/auth/generate-key")
def create_api_key():
    key = generate_api_key()
    return {"api_key": key, "usage": "Add header: X-API-Key: <key>"}


@app.post("/cache/clear")
def clear_cache():
    from backend.services.rag import _cache
    _cache.clear()
    return {"message": "Cache cleared"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "sait-ai",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "sait-ai",
            }
        ],
    }


@app.get("/v1/documents")
def list_documents_v1():
    from backend.services.retriever import list_documents as list_docs
    docs = list_docs()
    return {
        "documents": [{"file_name": d["file_name"], "chunks": d["chunks"]} for d in docs],
        "total": sum(d["chunks"] for d in docs),
    }


class OpenAIChatRequest(BaseModel):
    model: str = "sait-ai"
    messages: list
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


@app.post("/v1/chat/completions", dependencies=[Depends(get_api_key)])
async def openai_chat_completions(request: OpenAIChatRequest):
    from fastapi.responses import StreamingResponse
    from backend.services.rag import ask_question

    user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        user_message = request.messages[-1].get("content", "") if request.messages else ""

    result = await ask_question(user_message)

    chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if request.stream:
        async def generate():
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": result["answer"]},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

            done = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created,
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["answer"],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }