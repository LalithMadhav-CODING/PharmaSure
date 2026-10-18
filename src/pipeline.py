"""End-to-end RAG pipeline orchestration."""
import time
import json
import os
import numpy as np

# Load .env for API keys
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from . import embeddings, kg, retrieval, llm, verify


# Module-level cache
_index = None
_passages = None
_demo_cache = None


def build_corpus(passages: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """Embed passages and build the dense index.

    Args:
        passages: list of {"text": ..., "source": ..., "drug": ..., "disease": ..., ...}

    Returns:
        (index_npy, passages) — index_npy is (N, 768) L2-normalized, passages is the same list
    """
    texts = [p["text"] for p in passages]
    index = embeddings.embed_texts(texts, kind="document")
    return index, passages


def load_index(index_path: str = "data/index.npy", passages_path: str = "data/passages.json"):
    """Load a pre-built index from disk."""
    global _index, _passages
    if _index is None:
        _index = np.load(index_path)
        with open(passages_path) as f:
            _passages = json.load(f)
    return _index, _passages


def save_index(index: np.ndarray, passages: list[dict], index_path: str = "data/index.npy", passages_path: str = "data/passages.json"):
    """Save the index to disk."""
    np.save(index_path, index)
    with open(passages_path, "w") as f:
        json.dump(passages, f)


def save_demo_cache(cache: dict, cache_path: str = "data/demo_cache.json"):
    """Save precomputed demo results to disk."""
    global _demo_cache
    _demo_cache = cache
    import numpy as np

    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            return super().default(obj)

    with open(cache_path, "w") as f:
        json.dump(cache, f, cls=NumpyEncoder)


def load_demo_cache(cache_path: str = "data/demo_cache.json") -> dict:
    """Load precomputed demo results."""
    global _demo_cache
    if _demo_cache is None and os.path.exists(cache_path):
        with open(cache_path) as f:
            _demo_cache = json.load(f)
    return _demo_cache or {}


def run_pipeline(query: str, index: np.ndarray = None, passages: list[dict] = None) -> dict:
    """End-to-end: resolve → candidates → retrieve → rerank/score → generate → verify.

    Returns results, passages, and per-stage timings. Serves cache for demo queries.
    """
    timings = {}

    # Check cache first (normalize punctuation for consistent keys)
    import re
    cache = load_demo_cache()
    cache_key = re.sub(r"[^a-z0-9\s]", "", query.lower()).strip()
    if cache_key in cache:
        result = cache[cache_key].copy()
        result["from_cache"] = True
        result["timings_ms"] = {"cache_hit": 0}
        return result

    # Load index if not provided
    if index is None or passages is None:
        index, passages = load_index()

    # Step 1: Resolve disease
    t0 = time.time()
    disease = kg.resolve_disease(query)
    timings["resolve_ms"] = int((time.time() - t0) * 1000)

    if disease is None:
        return {
            "status": "unsupported_disease",
            "message": f"Could not resolve '{query}' to a known disease. Please try a different name.",
            "results": [],
            "known_indications": [],
            "passages": [],
            "timings_ms": timings,
        }

    # Check if disease is supported
    supported = _is_supported_disease(disease)
    if not supported:
        return {
            "status": "unsupported_disease",
            "message": f"'{disease['name']}' is not in our supported disease set. Supported diseases: {_get_supported_diseases()}",
            "results": [],
            "known_indications": [],
            "passages": [],
            "timings_ms": timings,
        }

    # Step 2: Get candidates from KG
    t0 = time.time()
    cand_result = kg.get_candidates(disease["id"], top_n=10)
    candidates = cand_result["candidates"]
    known_indications = cand_result["known_indications"]
    timings["kg_ms"] = int((time.time() - t0) * 1000)

    # Abstain if no candidates
    if not candidates:
        return {
            "status": "insufficient_evidence",
            "message": f"No repurposing candidates found for {disease['name']}. This may indicate a rare condition or a gap in our knowledge graph coverage.",
            "results": [],
            "known_indications": known_indications,
            "passages": [],
            "timings_ms": timings,
        }

    # Step 3: Embed query and retrieve
    t0 = time.time()
    query_vec = embeddings.embed_query(query)
    timings["embed_ms"] = int((time.time() - t0) * 1000)

    t0 = time.time()
    search_results = retrieval.search_dense(query_vec, index, top_k=30)
    retrieved = []
    scores = []
    for idx, score in search_results:
        p = passages[idx].copy()
        retrieved.append(p)
        scores.append(score)
    timings["retrieve_ms"] = int((time.time() - t0) * 1000)

    # Step 4: Re-rank and score
    t0 = time.time()
    reranked = retrieval.rerank(retrieved, scores)
    top_passages = reranked[:10]
    timings["rerank_ms"] = int((time.time() - t0) * 1000)

    # Step 5: Generate answer (single Gemini call)
    t0 = time.time()
    answer = llm.generate_answer(disease["name"], candidates, top_passages)
    timings["generate_ms"] = int((time.time() - t0) * 1000)

    # Step 6: Verify citations (two-stage)
    t0 = time.time()
    passages_by_id = {str(i+1): p for i, p in enumerate(top_passages)}
    verified = verify.verify_citations(answer, passages_by_id)
    timings["verify_ms"] = int((time.time() - t0) * 1000)

    # Step 7: Attach evidence scores to candidates
    results = []
    for i, cand in enumerate(verified.get("candidates", [])):
        # Compute evidence score from top passages
        score_info = retrieval.evidence_score(top_passages)
        results.append({
            "rank": i + 1,
            "drug": cand.get("drug_name", candidates[i]["drug_name"] if i < len(candidates) else "Unknown"),
            "direction": cand.get("direction", "Uncertain"),
            "evidence": score_info,
            "reason": cand.get("reason", ""),
            "claims": cand.get("claims", []),
        })

    total_ms = sum(timings.values())
    return {
        "status": "ok",
        "query": query,
        "disease": disease,
        "results": results,
        "known_indications": known_indications,
        "passages": top_passages,
        "timings_ms": {**timings, "total_ms": total_ms},
        "from_cache": False,
    }


# Supported diseases (to be finalized after data inspection)
_SUPPORTED_DISEASES = []


def _is_supported_disease(disease: dict) -> bool:
    """Check if disease is in supported set. If set is empty, allow all."""
    if not _SUPPORTED_DISEASES:
        return True  # Allow all until we finalize the set
    return disease["name"] in _SUPPORTED_DISEASES or disease["id"] in _SUPPORTED_DISEASES


def _get_supported_diseases() -> str:
    """Get human-readable list of supported diseases."""
    if not _SUPPORTED_DISEASES:
        return "All diseases (set not yet finalized)"
    return ", ".join(_SUPPORTED_DISEASES)


def set_supported_diseases(diseases: list[str]):
    """Set the supported disease list."""
    global _SUPPORTED_DISEASES
    _SUPPORTED_DISEASES = diseases
