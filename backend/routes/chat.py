from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json

from backend.services.rag import ask_question, ask_question_streaming, ask_with_context, build_rag_context
from backend.services.retriever import delete_document, list_documents
from backend.database.chat_history import save_message, get_history, list_sessions_with_titles, delete_chat_session
from backend.services.auth import get_api_key

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    filename: Optional[str] = None
    tags: Optional[List[str]] = None
    context: Optional[str] = None
    exclude_tags: Optional[List[str]] = None


class ChatContextRequest(BaseModel):
    question: str
    context: str
    filename: str = "uploaded_document"
    session_id: Optional[str] = None


class HistoryRequest(BaseModel):
    session_id: str
    limit: int = 20


@router.post("/chat", dependencies=[Depends(get_api_key)])
async def chat(request: ChatRequest):
    if request.context:
        result = await ask_with_context(
            request.question,
            request.context,
            request.filename or "uploaded_document",
        )
        return {
            "question": request.question,
            "answer": result["answer"],
            "sources": result["sources"]
        }

    session_id = request.session_id or str(uuid.uuid4())

    save_message(session_id, "user", request.question)

    history = get_history(session_id, limit=10)
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[:-1]])

    result = await ask_question(
        request.question,
        history_context=history_text,
        filename=request.filename,
        tags=request.tags,
        exclude_tags=request.exclude_tags,
    )

    save_message(session_id, "assistant", result["answer"])

    return {
        "session_id": session_id,
        "question": request.question,
        "answer": result["answer"],
        "sources": result["sources"]
    }


@router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str, limit: int = 20):
    return {"session_id": session_id, "messages": get_history(session_id, limit)}


@router.get("/chat/sessions")
async def get_sessions():
    return {"sessions": list_sessions_with_titles()}


@router.delete("/chat/session/{session_id}", dependencies=[Depends(get_api_key)])
async def delete_session(session_id: str):
    return delete_chat_session(session_id)


@router.get("/documents")
async def get_documents():
    return {"documents": list_documents()}


@router.delete("/documents/{filename}", dependencies=[Depends(get_api_key)])
async def delete_doc(filename: str):
    return delete_document(filename)


class ChatStreamRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    filename: Optional[str] = None
    tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None


@router.post("/chat/stream", dependencies=[Depends(get_api_key)])
async def chat_stream(request: ChatStreamRequest):
    session_id = request.session_id or str(uuid.uuid4())

    save_message(session_id, "user", request.question)

    history = get_history(session_id, limit=10)
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[:-1]])

    async def generate():
        messages, metadatas = build_rag_context(
            request.question,
            history_context=history_text,
            filename=request.filename,
            tags=request.tags,
            exclude_tags=request.exclude_tags,
        )

        if messages is None:
            yield json.dumps({"t": "s", "sources": []}) + "\n"
            yield json.dumps({"t": "t", "c": "No documents have been uploaded yet. Please upload a document first (PDF, DOCX, TXT, images, etc.)."}) + "\n"
            return

        yield json.dumps({"t": "s", "sources": metadatas}) + "\n"

        full_answer = ""
        async for token in ask_question_streaming(
            request.question,
            history_context=history_text,
            filename=request.filename,
            tags=request.tags,
            _prebuilt=(messages, metadatas),
        ):
            full_answer += token
            yield json.dumps({"t": "t", "c": token}) + "\n"
        save_message(session_id, "assistant", full_answer)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Session-Id": session_id},
    )


@router.post("/chat/context", dependencies=[Depends(get_api_key)])
async def chat_context(request: ChatContextRequest):
    result = await ask_with_context(
        request.question,
        request.context,
        request.filename,
    )

    return {
        "question": request.question,
        "answer": result["answer"],
        "sources": result["sources"]
    }