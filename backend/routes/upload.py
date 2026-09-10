from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from typing import Optional, List
from pathlib import Path
import shutil
import traceback
import time
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.services.auth import get_api_key

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"

_processing_status = {}
_upload_semaphore = threading.Semaphore(3)
_upload_executor = ThreadPoolExecutor(max_workers=3)


def _process_with_semaphore(file_path: str, filename: str, tag_list: list):
    _upload_semaphore.acquire()
    try:
        _process_file_background_inner(file_path, filename, tag_list)
    finally:
        _upload_semaphore.release()


def _process_file_background_inner(file_path: str, filename: str, tag_list: list):
    start = time.time()
    try:
        _processing_status[filename] = {"status": "processing", "progress": "extracting text"}

        from backend.services.ocr import extract_text
        text = extract_text(file_path)
        print(f"[{filename}] Text extracted in {time.time()-start:.1f}s, length={len(text)}")

        _processing_status[filename] = {"status": "processing", "progress": "chunking"}
        from backend.services.chunking import create_chunks
        chunks = create_chunks(text)
        print(f"[{filename}] Chunked into {len(chunks)} chunks in {time.time()-start:.1f}s")

        _processing_status[filename] = {"status": "processing", "progress": "generating embeddings"}
        from backend.services.embeddings import generate_embeddings
        embeddings = generate_embeddings(chunks)
        print(f"[{filename}] Embeddings generated in {time.time()-start:.1f}s")

        _processing_status[filename] = {"status": "processing", "progress": "storing in qdrant"}
        from backend.services.store_vectors import store_chunks
        store_chunks(chunks, embeddings, filename, tags=tag_list)

        elapsed = time.time() - start
        _processing_status[filename] = {"status": "done", "chunks": len(chunks), "time": f"{elapsed:.1f}s"}
        print(f"[{filename}] DONE in {elapsed:.1f}s - {len(chunks)} chunks stored")

    except Exception as e:
        elapsed = time.time() - start
        _processing_status[filename] = {"status": "error", "error": str(e), "time": f"{elapsed:.1f}s"}
        print(f"[{filename}] ERROR after {elapsed:.1f}s: {e}")
        traceback.print_exc()


@router.post("/upload", dependencies=[Depends(get_api_key)])
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
):
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOAD_DIR / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        tag_list = [t.strip() for t in tags.split(",")] if tags else []

        background_tasks.add_task(
            _process_with_semaphore,
            str(file_path),
            file.filename,
            tag_list
        )

        return {
            "message": "File uploaded. Processing in background.",
            "filename": file.filename,
            "tags": tag_list
        }

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@router.get("/upload/status/{filename}")
async def upload_status(filename: str):
    return _processing_status.get(filename, {"status": "unknown"})