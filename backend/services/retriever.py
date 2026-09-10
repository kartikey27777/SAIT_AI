import os
from backend.services.qdrant_client import get_qdrant_client
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
from backend.services.embeddings import generate_embedding_single

COLLECTION_NAME = "documents_v2"


def search_documents(query, filename=None, tags=None, limit=5, exclude_tags=None):
    client = get_qdrant_client()

    query_embedding = generate_embedding_single(query)

    must_conditions = []
    must_not_conditions = []

    if filename:
        must_conditions.append(
            FieldCondition(key="file_name", match=MatchValue(value=filename))
        )

    if tags:
        must_conditions.append(
            FieldCondition(key="tags", match=MatchAny(any=tags))
        )

    if exclude_tags:
        must_not_conditions.append(
            FieldCondition(key="tags", match=MatchAny(any=exclude_tags))
        )

    query_filter = Filter(
        must=must_conditions,
        must_not=must_not_conditions,
    ) if (must_conditions or must_not_conditions) else None

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding.tolist(),
        query_filter=query_filter,
        limit=limit
    )

    documents = []
    metadatas = []
    for point in results.points:
        payload = point.payload
        documents.append(payload.get("document", ""))
        metadatas.append({
            "file_name": payload.get("file_name", ""),
            "chunk_id": payload.get("chunk_id", 0),
            "tags": payload.get("tags", []),
            "uploaded_at": payload.get("uploaded_at", "")
        })

    return {
        "documents": documents,
        "metadatas": metadatas
    }


def delete_document(filename: str):
    client = get_qdrant_client()

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="file_name", match=MatchValue(value=filename))]
        )
    )
    return {"deleted": filename}


def list_documents():
    client = get_qdrant_client()

    try:
        all_data = client.scroll(collection_name=COLLECTION_NAME, limit=10000)[0]
    except Exception:
        return []

    if not all_data:
        return []

    file_map = {}
    for point in all_data:
        payload = point.payload
        fname = payload.get("file_name", "unknown")
        if fname not in file_map:
            file_map[fname] = {
                "file_name": fname,
                "chunks": 0,
                "tags": set(),
                "uploaded_at": payload.get("uploaded_at", "")
            }
        file_map[fname]["chunks"] += 1
        file_map[fname]["tags"].update(payload.get("tags", []))

    return [
        {"file_name": v["file_name"], "chunks": v["chunks"], "tags": list(v["tags"]), "uploaded_at": v["uploaded_at"]}
        for v in file_map.values()
    ]