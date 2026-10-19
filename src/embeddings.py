"""Ollama embedding client using nomic-embed-text."""
import time

import httpx
import numpy as np

OLLAMA_URL = "http://localhost:11434"
MODEL = "nomic-embed-text"

# nomic-embed-text rejects inputs past its context window with HTTP 500.
# Passage text is truncated to this many characters; the head of an abstract
# carries the signal that matters for retrieval.
MAX_CHARS = 6000
_RETRY_LIMITS = (MAX_CHARS, 4000, 2000, 1000, 500)


def _embed_one(prefix: str, text: str) -> np.ndarray:
    """Embed a single string, shrinking the input if Ollama rejects it."""
    body = (text or "").strip()
    last_err = None
    for limit in _RETRY_LIMITS:
        try:
            resp = httpx.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": MODEL, "prompt": f"{prefix} {body[:limit]}"},
                timeout=60,
            )
            resp.raise_for_status()
            return np.array(resp.json()["embedding"], dtype=np.float32)
        except Exception as exc:  # noqa: BLE001 - retry with a smaller window
            last_err = exc
            time.sleep(0.3)
    raise RuntimeError(f"embedding failed for input of {len(body)} chars: {last_err}")


def embed_texts(texts: list[str], kind: str = "document") -> np.ndarray:
    """Embed texts via Ollama → (N, 768) L2-normalized array."""
    prefix = "search_document:" if kind == "document" else "search_query:"
    vectors = [
        _embed_one(prefix, text)
        for i in range(0, len(texts), 20)
        for text in texts[i:i + 20]
    ]
    mat = np.array(vectors, dtype=np.float32)
    # L2 normalize
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    return mat / norms


def embed_query(query: str) -> np.ndarray:
    """Embed a single query → (768,) L2-normalized."""
    return embed_texts([query], kind="query")[0]
