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
    from . import embeddings, kg, retrieval, llm, verify, audit, coverage
except (ImportError, ValueError):
    from src import embeddings, kg, retrieval, llm, verify, audit, coverage


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

    # Check cache first.
    #
    # Identity is the disease's CANONICAL name, not a substring. The previous
    # implementation accepted any cache key that was a substring of the query or
    # vice versa, so a query for one disease could be answered with another
    # disease's cached result (e.g. "diabetes" -> the "type 2 diabetes" entry).
    cache = load_demo_cache()
    cache_key = coverage.normalize_disease_key(query)
    normalized_cache = {coverage.normalize_disease_key(k): k for k in cache}
    hit_key = normalized_cache.get(cache_key)

    # A cached entry produced from a different corpus/scoring version must not be
    # served as if it were current.
    if hit_key:
        cached_version = (cache[hit_key] or {}).get("corpus_schema_version")
        if cached_version and cached_version != coverage.CORPUS_SCHEMA_VERSION:
            hit_key = None

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
            "audit": cached_t.get("audit", cached_t.get("audit_ms", 0)),
            "total_ms": cached_t.get("total_ms", 742),
            "cache_hit": 0,
        }
        # Cached entries are only served as-is when they were produced by this
        # audit version; otherwise the caller sees an explicit "unavailable"
        # audit rather than a stale one presented as current.
        result.setdefault("evidence_audit_summary", {
            "version": audit.AUDIT_VERSION,
            "status": "unavailable_for_cached_result",
            "note": "Cached result predates the evidence audit.",
        })
        return result

    # NOTE: there is deliberately no "is this disease supported" gate before
    # resolution. Support is not a static list — it is decided from the resolved
    # canonical identity plus what the local corpus actually covers (see below).

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

    # Step 2: Get candidates from KG
    t0 = time.time()
    cand_result = kg.get_candidates(disease["id"], top_n=10)
    candidates = cand_result["candidates"]
    known_indications = cand_result["known_indications"]
    timings["kg_ms"] = int((time.time() - t0) * 1000)

    # Resolved, but the knowledge graph proposes nothing for it. This is a
    # distinct outcome from "not resolved" and from "no literature": the
    # vocabulary recognises the disease, but there is no candidate to evaluate.
    if not candidates:
        return {
            "status": "no_candidates",
            "evidence_scope": coverage.EVIDENCE_SCOPE_NONE,
            "message": (
                f"'{disease['name']}' was recognised, but the EveryCure knowledge "
                f"graph contains no repurposing candidates for it. This is a gap in "
                f"graph coverage, not evidence that no treatment exists."
            ),
            "disease": disease,
            "results": [],
            "candidate_pool": [],
            "known_indications": known_indications,
            "passages": [],
            "timings_ms": timings,
            "from_cache": False,
            "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
        }

    # Step 2b: Evidence boundary (coverage gate).
    #
    # The graph can propose candidates for a disease the local corpus has never
    # seen. In that case there is NO disease-specific evidence, and answering
    # with passages retrieved from unrelated diseases would be fabrication —
    # a real PMID does not make an off-topic abstract into evidence.
    #
    # So: report coverage honestly, return no evidence-backed candidates, and
    # still surface candidate availability (which is a separate fact).
    local_passage_count = coverage.local_passage_count(disease["name"])
    if local_passage_count == 0:
        return {
            "status": "no_local_evidence",
            "evidence_scope": coverage.EVIDENCE_SCOPE_NONE,
            "message": (
                f"'{disease['name']}' is recognised by the knowledge graph and has "
                f"{len(candidates)} candidate drugs, but the indexed literature corpus "
                f"contains no abstracts for this disease, so no candidate-specific "
                f"evidence can be produced. Absence of evidence here is not evidence "
                f"of ineffectiveness."
            ),
            "disease": disease,
            "results": [],
            "candidate_pool": [
                {
                    "drug": c.get("drug_name"),
                    "graph_rank": i + 1,
                    "graph_score": c.get("score"),
                    "evidence_status": "no_local_evidence",
                }
                for i, c in enumerate(candidates)
            ],
            "known_indications": known_indications,
            "passages": [],
            "coverage": {
                "local_passage_count": 0,
                "local_literature_available": False,
            },
            "timings_ms": timings,
            "from_cache": False,
            "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
        }

    # Step 3: Embed query and retrieve
    t0 = time.time()
    query_vec = embeddings.embed_query(query)
    timings["embed_ms"] = int((time.time() - t0) * 1000)

    t0 = time.time()
    # Retrieval is scoped to passages tagged with this disease.
    #
    # A dense query on the disease name alone surfaces passages that are merely
    # *about* the disease while naming unrelated drugs (searching "Common cold"
    # returned Aspirin/Dexamethasone/Ketamine abstracts). No candidate drug then
    # matches a passage, so every evidence score collapses to 0 and no citations
    # can be produced. The corpus is built per (disease, drug) pair, so its
    # disease tag is the reliable signal; similarity then ranks within it.
    target_disease = coverage.normalize_disease_key(disease["name"])
    disease_idx = [
        i for i, p in enumerate(passages)
        if coverage.normalize_disease_key(p.get("disease")) == target_disease
    ]

    # disease_idx cannot be empty here: a disease with no local literature
    # returned above. Global-corpus retrieval is deliberately NOT a fallback,
    # because those passages are not evidence for this disease.
    sub_index = index[disease_idx]
    sub_hits = retrieval.search_dense(
        query_vec, sub_index, top_k=min(30, len(disease_idx))
    )
    search_results = [(disease_idx[i], s) for i, s in sub_hits]

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

        # --- Phase 2: explicit candidate-specific evidence record -------------
        # Ties the candidate to its provenance, the evidence actually retrieved
        # for THIS candidate, and an explicit status. Nothing here is inferred
        # from free-form generated text.
        distinct_pmids = sorted({
            str(p.get("pmid")) for p in drug_passages if p.get("pmid")
        })
        claims = llm_cand.get("claims", []) or []
        verified_claims = sum(1 for c in claims if c.get("verification_status") == "verified")
        review_claims = len(claims) - verified_claims

        if not drug_passages:
            evidence_status = "no_candidate_specific_evidence"
        elif not claims:
            evidence_status = "evidence_retrieved_no_verified_claims"
        elif verified_claims == 0:
            evidence_status = "evidence_unverified"
        else:
            evidence_status = "supported"

        limitations = []
        if not drug_passages:
            limitations.append(
                "No retrieved passage is associated with this candidate, so its "
                "evidence score is zero. This reflects corpus coverage, not "
                "evidence of ineffectiveness."
            )
        if drug_passages and not distinct_pmids:
            limitations.append("Retrieved passages carry no PMID; provenance is incomplete.")
        if review_claims:
            limitations.append(f"{review_claims} claim(s) did not pass verbatim verification.")
        if len(distinct_pmids) == 1 and drug_passages:
            limitations.append(
                "All evidence for this candidate comes from a single PMID; it is one "
                "study unit, not independent corroboration."
            )

        evidence_summary = {
            "candidate_source": "everycure_knowledge_graph",
            "graph_rank": i + 1,
            "graph_score": kg_cand.get("score"),
            "drug_id": kg_cand.get("drug_id"),
            "evidence_status": evidence_status,
            "passage_count": len(drug_passages),
            "distinct_pmid_count": len(distinct_pmids),
            "pmids": distinct_pmids,
            "best_study_type": score_info.get("best_study_type"),
            "verification": {
                "claims": len(claims),
                "verified": verified_claims,
                "needs_review": review_claims,
            },
            "limitations": limitations,
        }

        results.append({
            "rank": i + 1,
            "drug": drug_name,
            "direction": llm_cand.get("direction", "Uncertain"),
            "evidence": score_info,
            "reason": reason,
            "claims": claims,
            "evidence_summary": evidence_summary,
        })

    # Step 8: Citation-level counterfactual evidence audit (additive).
    # Pure deterministic recomputation over the evidence already retrieved: no LLM
    # call and no re-embedding, so it cannot alter the baseline scores above.
    # The audit is an additive layer — if it fails, the baseline candidate
    # results must still be returned intact (spec §6.6.13).
    t0 = time.time()
    try:
        audit_summary = audit.attach_audits(results, top_passages, disease)
        audit_state = "computed"
    except Exception as exc:  # noqa: BLE001
        audit_summary = {
            "audited": 0, "complete": 0,
            "not_auditable": 0, "failed": len(results),
        }
        audit_state = f"failed:{type(exc).__name__}"
    timings["audit_ms"] = int((time.time() - t0) * 1000)

    total_ms = sum(timings.values())
    return {
        "status": "ok",
        "query": query,
        "disease": disease,
        "results": results,
        "known_indications": known_indications,
        "passages": top_passages,
        "evidence_scope": coverage.EVIDENCE_SCOPE_LOCAL,
        "coverage": {
            "local_passage_count": local_passage_count,
            "local_literature_available": True,
            "retrieved_passage_count": len(top_passages),
        },
        "evidence_audit_summary": {
            "version": audit.AUDIT_VERSION,
            "method": audit.AUDIT_METHOD,
            "scoring_function": audit.SCORING_FUNCTION_ID,
            "status": audit_state,
            **audit_summary,
        },
        "timings_ms": {**timings, "total_ms": total_ms},
        "from_cache": False,
        "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
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
    """Deprecated gate. Retained for callers; coverage is decided in run_pipeline.

    This used to return True unconditionally, which meant an always-true
    "supported" predicate. Real support is now a function of (a) whether the
    disease resolves to a canonical identity and (b) whether the local corpus
    holds literature for it — see ``src/coverage.py`` and the ``no_candidates`` /
    ``no_local_evidence`` statuses in ``run_pipeline``.
    """
    return coverage.has_local_literature((disease or {}).get("name"))


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
