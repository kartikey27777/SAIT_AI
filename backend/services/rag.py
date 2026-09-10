import os
import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
from backend.services.retriever import search_documents

LLAMA_SWAP_HOST = os.environ.get("LLAMA_SWAP_HOST", "http://localhost:8080")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2:1.5b")

_cache = {}
CACHE_TTL = 300

_executor = ThreadPoolExecutor(max_workers=4)

MAX_CONTEXT_CHARS = 2000


def _call_llm_sync(messages):
    response = httpx.post(
        f"{LLAMA_SWAP_HOST}/v1/chat/completions",
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.6,
            "max_tokens": 256,
        },
        headers={"Authorization": "Bearer no-key"},
        timeout=600.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _build_rag_context(question, history_context="", filename=None, tags=None, exclude_tags=None):
    results = search_documents(question, filename=filename, tags=tags, limit=5, exclude_tags=exclude_tags)

    if not results["documents"]:
        return None, []

    context = "\n\n".join(results["documents"])
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "..."

    system_prompt = (
        "You are SAIT AI, a helpful assistant. Answer the question using the context below. "
        "Give detailed, well-explained answers. Use bullet points or paragraphs as needed. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    return messages, results["metadatas"]


def build_rag_context(question, history_context="", filename=None, tags=None, exclude_tags=None):
    return _build_rag_context(question, history_context, filename, tags, exclude_tags)


async def ask_question(question, history_context="", filename=None, tags=None, exclude_tags=None):
    cache_key = f"{question}:{filename}:{tags}:{exclude_tags}"

    if cache_key in _cache:
        cached = _cache[cache_key]
        if time.time() - cached["time"] < CACHE_TTL:
            return cached["result"]

    messages, metadatas = _build_rag_context(question, history_context, filename, tags, exclude_tags)

    if messages is None:
        return {
            "answer": "No documents have been uploaded yet. Please upload a document first (PDF, DOCX, TXT, images, etc.).",
            "sources": []
        }

    try:
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(_executor, _call_llm_sync, messages)
    except Exception as e:
        try:
            answer = _call_llm_sync(messages)
        except Exception as e2:
            answer = f"Error calling LLM: {str(e2)}"

    result = {
        "answer": answer,
        "sources": metadatas
    }

    _cache[cache_key] = {"result": result, "time": time.time()}

    if len(_cache) > 1000:
        oldest_keys = sorted(_cache.keys(), key=lambda k: _cache[k]["time"])[:500]
        for k in oldest_keys:
            del _cache[k]

    return result


async def ask_question_streaming(question, history_context="", filename=None, tags=None, _prebuilt=None, exclude_tags=None):
    if _prebuilt:
        messages, metadatas = _prebuilt
    else:
        messages, metadatas = _build_rag_context(question, history_context, filename, tags, exclude_tags)

    if messages is None:
        yield "No documents have been uploaded yet. Please upload a document first (PDF, DOCX, TXT, images, etc.)."
        return

    import httpx as _httpx
    async with _httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream(
            "POST",
            f"{LLAMA_SWAP_HOST}/v1/chat/completions",
            json={
                "model": LLM_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": 0.6,
                "max_tokens": 256,
            },
            headers={"Authorization": "Bearer no-key"},
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                except json.JSONDecodeError:
                    continue


async def ask_with_context(question, context, filename):
    if not context or not context.strip():
        return {
            "answer": "No document content was provided.",
            "sources": []
        }

    trimmed_context = context[:MAX_CONTEXT_CHARS] + "..." if len(context) > MAX_CONTEXT_CHARS else context

    system_prompt = (
        "You are SAIT AI, a helpful assistant. Answer the question using the context below. "
        "Give detailed, well-explained answers. Use bullet points or paragraphs as needed. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{trimmed_context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    try:
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(_executor, _call_llm_sync, messages)
    except Exception as e:
        try:
            answer = _call_llm_sync(messages)
        except Exception as e2:
            answer = f"Error calling LLM: {str(e2)}"

    return {
        "answer": answer,
        "sources": [{"file_name": filename}]
    }