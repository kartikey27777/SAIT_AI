import os
from sentence_transformers import SentenceTransformer
import numpy as np

cache_dir = os.path.join(os.sep, "root", ".cache", "huggingface", "hub")
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            cache_folder=cache_dir,
        )
        _model.encode(["warmup"], show_progress_bar=False)
    return _model


def generate_embeddings(chunks):
    model = get_model()
    embeddings = model.encode(
        chunks,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings


def generate_embedding_single(text):
    model = get_model()
    return model.encode(
        [text],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]