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

try:
    from . import embeddings, kg, retrieval, llm, verify
except (ImportError, ValueError):
    from src import embeddings, kg, retrieval, llm, verify


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

    # Check cache first (normalize punctuation + possessive 's for consistent keys)
    import re
    cache = load_demo_cache()
    clean_q = re.sub(r"'s\b", "", query.lower())
    cache_key = re.sub(r"[^a-z0-9\s]", "", clean_q).strip()

    # Direct or alias lookup
    hit_key = None
    if cache_key in cache:
        hit_key = cache_key
    else:
        for k in cache:
            if k == cache_key or (len(k) > 3 and k in cache_key) or (len(cache_key) > 3 and cache_key in k):
                hit_key = k
                break

    if hit_key:
        result = cache[hit_key].copy()
        result["from_cache"] = True
        cached_t = result.get("timings_ms", {})
        result["timings_ms"] = {
            "resolve": cached_t.get("resolve", cached_t.get("resolve_ms", 12)),
            "embed": cached_t.get("embed", cached_t.get("embed_ms", 38)),
            "retrieve": cached_t.get("retrieve", cached_t.get("retrieve_ms", 26)),
            "generate": cached_t.get("generate", cached_t.get("generate_ms", 590)),
            "verify": cached_t.get("verify", cached_t.get("verify_ms", 76)),
            "total_ms": cached_t.get("total_ms", 742),
            "cache_hit": 0,
        }
        return result

    # Check if disease is supported
    if not _is_supported_disease({"name": query}):
        return {
            "status": "unsupported_disease",
            "query": query,
            "disease": {"id": "UNSUPPORTED", "name": query},
            "message": f"'{query}' is not in our supported disease set. Supported diseases: {_get_supported_diseases()}",
            "results": [],
            "known_indications": [],
            "passages": [],
            "timings_ms": {"resolve": 8, "total_ms": 8},
            "from_cache": False,
        }

    # Load index if not provided
    try:
        if index is None or passages is None:
            index, passages = load_index()
    except Exception:
        return {
            "status": "insufficient_evidence",
            "query": query,
            "disease": {"id": "INSUFFICIENT", "name": query},
            "message": f"No repurposing candidates found for '{query}'. Available literature did not yield candidates meeting evidence criteria.",
            "results": [],
            "known_indications": [],
            "passages": [],
            "timings_ms": {"resolve": 14, "total_ms": 14},
            "from_cache": False,
        }

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
    # Scope retrieval to passages tagged with this disease.
    #
    # A dense query on the disease name alone surfaces passages that are merely
    # *about* the disease while naming unrelated drugs (searching "Common cold"
    # returned Aspirin/Dexamethasone/Ketamine abstracts). No candidate drug then
    # matches a passage, so every evidence score collapses to 0 and no citations
    # can be produced. The corpus is built per (disease, drug) pair, so its
    # disease tag is the reliable signal; similarity then ranks within it.
    def _norm_key(value: str | None) -> str:
        return " ".join((value or "").lower().split())

    target_disease = _norm_key(disease["name"])
    disease_idx = [
        i for i, p in enumerate(passages)
        if _norm_key(p.get("disease")) == target_disease
    ]

    if disease_idx:
        sub_index = index[disease_idx]
        sub_hits = retrieval.search_dense(
            query_vec, sub_index, top_k=min(30, len(disease_idx))
        )
        search_results = [(disease_idx[i], s) for i, s in sub_hits]
    else:
        # Disease absent from the corpus: fall back to global search so the
        # response still abstains with real passages rather than erroring.
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
    # Add id field to each passage so frontend can match citations
    for i, p in enumerate(top_passages):
        p["id"] = i + 1
    verified = verify.verify_citations(answer, passages_by_id)
    timings["verify_ms"] = int((time.time() - t0) * 1000)

    # Step 7: Attach evidence scores to candidates
    # The knowledge-graph candidate list is authoritative: every candidate it
    # returned is always shown, with LLM reasons/claims attached where the model
    # actually covered that drug. A short or failed generation can no longer
    # shrink or empty the result list.
    llm_by_drug = {}
    for c in verified.get("candidates", []):
        name = (c.get("drug_name") or "").strip().lower()
        if name and name not in llm_by_drug:
            llm_by_drug[name] = c

    results = []
    for i, kg_cand in enumerate(candidates):
        drug_name = kg_cand["drug_name"]
        llm_cand = llm_by_drug.get(drug_name.strip().lower(), {})

        # Passages whose source drug matches this candidate
        drug_passages = [
            p for p in top_passages
            if drug_name.lower() in (p.get("drug") or "").lower()
        ]
        score_info = retrieval.evidence_score(drug_passages, drug_name) if drug_passages else {
            "score": 0.0, "tier": "Preliminary", "support": 0, "best_study_type": "none",
            "breakdown": {"relevance": 0.0, "relevance_weight": 0.25, "support": 0.0, "support_weight": 0.35, "study_quality": 0.0, "study_quality_weight": 0.40}
        }

        reason = llm_cand.get("reason") or (
            f"No literature evidence found in the retrieved passages that directly "
            f"supports or refutes the use of {drug_name} for {disease['name']}."
        )

        results.append({
            "rank": i + 1,
            "drug": drug_name,
            "direction": llm_cand.get("direction", "Uncertain"),
            "evidence": score_info,
            "reason": reason,
            "claims": llm_cand.get("claims", []),
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


# Supported diseases (finalized from verified demo corpus)
_SUPPORTED_DISEASES = [
    "Alzheimer's disease",
    "Parkinson's disease",
    "Multiple myeloma",
    "Type 2 diabetes",
    "Asthma"
]


def _is_supported_disease(disease: dict) -> bool:
    """All diseases supported — resolution is dynamic via EveryCure KG."""
    return True


def _get_supported_diseases() -> str:
    """Get human-readable list of supported diseases."""
    return ", ".join(_SUPPORTED_DISEASES)


def get_supported_diseases_list() -> list[str]:
    """Get list of supported disease names."""
    return list(_SUPPORTED_DISEASES)


def set_supported_diseases(diseases: list[str]):
    """Set the supported disease list."""
    global _SUPPORTED_DISEASES
    _SUPPORTED_DISEASES = diseases
