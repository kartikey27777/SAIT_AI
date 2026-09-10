import os
from backend.services.qdrant_client import get_qdrant_client
from qdrant_client.models import VectorParams, Distance, PointStruct
import uuid
import time

COLLECTION_NAME = "documents_v2"
VECTOR_DIM = 384

def ensure_collection():
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_DIM,
                distance=Distance.COSINE
            )
        )

_collection_ready = False


def store_chunks(chunks, embeddings, filename, tags=None):
    global _collection_ready
    if not _collection_ready:
        ensure_collection()
        _collection_ready = True
    client = get_qdrant_client()

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="file_name", match=MatchValue(value=filename))]
            )
        )
    except Exception:
        pass

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embeddings[i].tolist(),
            payload={
                "file_name": filename,
                "chunk_id": i,
                "document": chunks[i],
                "tags": tags or [],
                "uploaded_at": str(int(time.time()))
            }
        )
        for i in range(len(chunks))
    ]

    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch
        )

    print(f"Stored {len(chunks)} chunks for {filename}")