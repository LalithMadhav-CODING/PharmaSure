"""Ollama embedding client using nomic-embed-text."""
import httpx
import numpy as np

OLLAMA_URL = "http://localhost:11434"
MODEL = "nomic-embed-text"


def embed_texts(texts: list[str], kind: str = "document") -> np.ndarray:
    """Embed texts via Ollama → (N, 768) L2-normalized array."""
    prefix = "search_document:" if kind == "document" else "search_query:"
    vectors = []
    # Batch in groups of 20
    for i in range(0, len(texts), 20):
        batch = texts[i:i+20]
        for text in batch:
            resp = httpx.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": MODEL, "prompt": f"{prefix} {text}"},
                timeout=30,
            )
            resp.raise_for_status()
            vec = np.array(resp.json()["embedding"], dtype=np.float32)
            vectors.append(vec)
    mat = np.array(vectors, dtype=np.float32)
    # L2 normalize
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    return mat / norms


def embed_query(query: str) -> np.ndarray:
    """Embed a single query → (768,) L2-normalized."""
    return embed_texts([query], kind="query")[0]
