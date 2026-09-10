import os
import threading
from qdrant_client import QdrantClient

_client = None
_lock = threading.Lock()


def get_qdrant_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = QdrantClient(
                    host=os.environ.get("QDRANT_HOST", "localhost"),
                    port=int(os.environ.get("QDRANT_PORT", 6333)),
                    timeout=30
                )
    return _client