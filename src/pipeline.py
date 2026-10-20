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
    from . import embeddings, kg, llm, retrieval, verify, audit, coverage, live_retrieval
except (ImportError, ValueError):
    from src import embeddings, kg, llm, retrieval, verify, audit, coverage, live_retrieval


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


def save_demo_cache(cache: dict, cache_path: str = "data/demo_cache.json",
                    *, allow_shrink: bool = False):
    """Save precomputed demo results to disk.

    Every entry is stamped with the response contract version it was produced
    under. Stamping here rather than at each return path means no response shape
    can reach the cache unstamped, so a later contract change invalidates stale
    entries instead of leaving the frontend reading fields that are gone.

    Refuses to silently DROP entries that already exist on disk. Overwriting the
    shipped demo cache with a smaller one is almost always an accident (a test
    calling this without a path, or a partial rebuild), and the loss is silent —
    the app just gets slower and returns uncached results. Pass
    ``allow_shrink=True`` when a reduction is genuinely intended.
    """
    global _demo_cache

    if not allow_shrink and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                existing = json.load(f) or {}
        except (OSError, ValueError):
            existing = {}
        if isinstance(existing, dict):
            lost = set(existing) - set(cache)
            if lost:
                raise ValueError(
                    f"refusing to drop {len(lost)} existing demo cache entry/entries "
                    f"({sorted(lost)[:3]}). Pass allow_shrink=True if intended."
                )

    cache = {
        key: ({**value, "response_contract_version": coverage.RESPONSE_CONTRACT_VERSION}
              if isinstance(value, dict) else value)
        for key, value in cache.items()
    }
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


def _distinct_pmid_count(passages: list) -> int:
    return len({str(p.get("pmid")) for p in passages if p.get("pmid")})


def _live_retrieval_status(live_outcome) -> str:
    """Map a live-retrieval outcome onto the status vocabulary the frontend reads.

    The frontend treats 'rate_limited', 'timeout', 'unavailable' and 'failed' as
    retrieval errors (amber styling), and everything else as a normal state. A
    provider outage must land in the error set so it is visibly not a clean
    negative result.
    """
    if live_outcome is None:
        return "not_attempted"
    if live_outcome.status == live_retrieval.LIVE_STATUS_FAILED:
        kind = (live_outcome.error or {}).get("kind")
        if kind == "timeout":
            return "timeout"
        if kind == "rate_limited":
            return "rate_limited"
        return "unavailable"
    return live_outcome.status


def _build_coverage(disease: dict, candidates: list, live_outcome, top_passages: list,
                    evidence_scope: str, local_passage_count: int,
                    graph_status: str = "available") -> dict:
    """Assemble the coverage block.

    Emits the semantic vocabulary the frontend reads (disease_resolution_status,
    graph_candidate_status, literature_status, source_mode, provider,
    retrieval_status, retrieved_record_count, distinct_pmid_count, retrieved_at,
    provider_message) alongside the original count fields, which are retained so
    existing consumers keep working. Purely additive.

    Every value here is derived from data the backend already holds; nothing is
    invented. Absent facts stay null rather than being filled with a plausible
    guess.
    """
    live = live_outcome

    if evidence_scope == coverage.EVIDENCE_SCOPE_LOCAL:
        literature_status = "available"
        source_mode = "local"
    elif evidence_scope == coverage.EVIDENCE_SCOPE_LIVE:
        literature_status = "available"
        source_mode = "live"
    else:
        # No candidate-specific evidence was produced. Distinguish "provider
        # never answered" from "provider answered and there is nothing".
        if live is not None and live.status == live_retrieval.LIVE_STATUS_FAILED:
            literature_status = "unavailable"
        else:
            literature_status = "none"
        source_mode = "unknown"

    provider_message = None
    if live is not None:
        if live.status == live_retrieval.LIVE_STATUS_FAILED and live.error:
            # The provider's own error text only — never a stack trace or an
            # internal exception repr.
            provider_message = live.error.get("message")
        elif live.status in (live_retrieval.LIVE_STATUS_NO_RESULTS,
                             live_retrieval.LIVE_STATUS_NO_RELEVANT):
            provider_message = "; ".join(live.limitations) or None

    if live is not None:
        retrieved_record_count = live.records_after_dedup
        distinct_pmid_count = None
        retrieved_at = live.retrieved_at
        provider = live.provider
    else:
        retrieved_record_count = len(top_passages)
        distinct_pmid_count = _distinct_pmid_count(top_passages)
        retrieved_at = None
        provider = None

    return {
        # --- semantic vocabulary read by the frontend ---
        "disease_resolution_status": "resolved",
        "graph_candidate_status": graph_status,
        "literature_status": literature_status,
        "source_mode": source_mode,
        "provider": provider,
        "retrieval_status": _live_retrieval_status(live),
        "retrieved_record_count": retrieved_record_count,
        "distinct_pmid_count": distinct_pmid_count,
        "retrieved_at": retrieved_at,
        "provider_message": provider_message,
        # --- original count fields, retained for compatibility ---
        "local_passage_count": local_passage_count,
        "local_literature_available": local_passage_count > 0,
        "retrieved_passage_count": len(top_passages),
    }


def _abstention_response(disease: dict, candidates: list, known_indications: list,
                         timings: dict, live_outcome) -> dict:
    """Controlled abstention when no candidate-specific evidence can be produced.

    Maps the live-retrieval outcome onto a distinct status so a caller can tell
    "the provider failed" from "the provider succeeded and found nothing relevant"
    from "live retrieval is switched off". Collapsing these would let a provider
    outage read as a real negative result.
    """
    pool = [
        {
            "drug": c.get("drug_name"),
            "graph_rank": i + 1,
            "graph_score": c.get("score"),
            "evidence_status": "no_evidence",
        }
        for i, c in enumerate(candidates)
    ]

    base = {
        "disease": disease,
        "results": [],
        "candidate_pool": pool,
        "known_indications": known_indications,
        "passages": [],
        "coverage": _build_coverage(
            disease, candidates, live_outcome, [],
            coverage.EVIDENCE_SCOPE_NONE, 0, graph_status="available",
        ),
        "timings_ms": timings,
        "from_cache": False,
        "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
    }

    name = disease["name"]

    if live_outcome is None:
        return {
            **base,
            "status": "no_local_evidence",
            "evidence_scope": coverage.EVIDENCE_SCOPE_NONE,
            "live_retrieval": {"status": live_retrieval.LIVE_STATUS_DISABLED,
                               "enabled": False},
            "message": (
                f"'{name}' is recognised by the knowledge graph and has "
                f"{len(candidates)} candidate drugs, but the indexed literature corpus "
                f"contains no abstracts for this disease and live retrieval is "
                f"disabled, so no candidate-specific evidence can be produced. "
                f"Absence of evidence here is not evidence of ineffectiveness."
            ),
        }

    summary = live_outcome.summary()

    if live_outcome.status == live_retrieval.LIVE_STATUS_FAILED:
        return {
            **base,
            "status": "provider_unavailable",
            "evidence_scope": coverage.EVIDENCE_SCOPE_NONE,
            "live_retrieval": summary,
            "message": (
                f"'{name}' has no indexed local literature, and the live literature "
                f"provider ({live_outcome.provider}) could not be reached, so no "
                f"candidate-specific evidence could be produced. This is a retrieval "
                f"failure — it is not evidence that no literature exists."
            ),
        }

    if live_outcome.status == live_retrieval.LIVE_STATUS_NO_RESULTS:
        detail = "the provider responded successfully and returned no records for it"
    else:
        detail = (
            f"the provider returned {live_outcome.records_after_dedup} record(s), but "
            f"none of them name any of the {len(candidates)} graph candidates, so none "
            f"qualify as candidate-specific evidence"
        )

    return {
        **base,
        "status": "no_relevant_evidence",
        "evidence_scope": coverage.EVIDENCE_SCOPE_NONE,
        "live_retrieval": summary,
        "message": (
            f"'{name}' has no indexed local literature; {detail}. This is an "
            f"absence of retrieved evidence, not evidence of ineffectiveness."
        ),
    }


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

    # A cached entry built against an older *response contract* must not be served
    # either: the corpus is unchanged but the payload shape is not, so a stale
    # entry would leave the frontend reading fields that are no longer emitted.
    if hit_key:
        cached_contract = (cache[hit_key] or {}).get("response_contract_version")
        if cached_contract != coverage.RESPONSE_CONTRACT_VERSION:
            hit_key = None

    # A cached entry whose scores were produced by a DIFFERENT scoring function must
    # not be served. The corpus and the payload shape can both be unchanged while
    # the numbers are not, so neither version above catches a re-weighted scorer.
    if hit_key:
        cached_scorer = (cache[hit_key] or {}).get("scoring_function")
        if cached_scorer != audit.SCORING_FUNCTION_ID:
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
            "coverage": {
                # The disease never resolved, so nothing downstream was assessed.
                # Reported explicitly rather than left absent, so the frontend can
                # say "not assessed" instead of inferring a false negative.
                "disease_resolution_status": "unresolved",
                "graph_candidate_status": "unavailable",
                "literature_status": "unknown",
                "source_mode": "unknown",
                "provider": None,
                "retrieval_status": "not_attempted",
                "retrieved_record_count": 0,
                "distinct_pmid_count": 0,
                "retrieved_at": None,
                "provider_message": None,
                "local_passage_count": 0,
                "local_literature_available": False,
                "retrieved_passage_count": 0,
            },
            "timings_ms": timings,
            "from_cache": False,
            "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
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
            "coverage": _build_coverage(
                disease, [], None, [],
                coverage.EVIDENCE_SCOPE_NONE, 0, graph_status="none",
            ),
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
    live_outcome = None
    live_passages_by_drug: dict = {}

    if local_passage_count == 0:
        # No indexed literature for this disease. Before abstaining, try bounded
        # live retrieval so "nothing indexed" does not silently become "nothing
        # to say" — but never let a provider failure masquerade as a real result.
        if live_retrieval.live_retrieval_enabled():
            live_outcome = live_retrieval.retrieve_for_disease(
                disease["name"],
                [c["drug_name"] for c in candidates],
                synonyms=list(disease.get("synonyms") or []),
            )
            if live_outcome.status == live_retrieval.LIVE_STATUS_OK:
                live_passages_by_drug = live_outcome.passages_by_drug
            else:
                return _abstention_response(
                    disease, candidates, known_indications, timings, live_outcome
                )
        else:
            return _abstention_response(
                disease, candidates, known_indications, timings, None
            )

    # Step 3: Select the evidence source.
    #
    # Local corpus evidence takes precedence when it exists. Live retrieval is
    # used only when the corpus holds nothing for this disease; its passages are
    # already bound to specific candidates by the relevance check, so they are
    # never presented as disease-specific evidence for a drug they do not name.
    if live_passages_by_drug:
        evidence_scope = coverage.EVIDENCE_SCOPE_LIVE
        retrieved = [p.copy() for ps in live_passages_by_drug.values() for p in ps]
        retrieved.sort(key=lambda p: (-float(p.get("combined_score") or 0.0),
                                      str(p.get("pmid") or "")))
        top_passages = retrieved[:10]
        timings["embed_ms"] = 0
        timings["retrieve_ms"] = 0
        timings["rerank_ms"] = 0
    else:
        evidence_scope = coverage.EVIDENCE_SCOPE_LOCAL

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
        # either returned an abstention above or is being served from live
        # retrieval. Global-corpus retrieval is deliberately NOT a fallback,
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

    # Passage contract expected by the frontend. Additive.
    #
    # `source_url` is derived from the PMID only when a PMID genuinely exists — a
    # deterministic URL for a real identifier, not a fabricated link. `title` is
    # left null for corpus passages because the indexed corpus stores no separate
    # title field; inventing one would be fabrication.
    for p in top_passages:
        if not p.get("provenance"):
            p["provenance"] = p.get("source_mode") or "local_corpus"
        if not p.get("source_url"):
            if p.get("url"):
                p["source_url"] = p["url"]
            elif p.get("pmid"):
                p["source_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"
            else:
                p["source_url"] = None
        if "title" not in p:
            p["title"] = None

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

        # Claims are read BEFORE scoring: verification is a scored term now, so the
        # score cannot be computed without it.
        claims = llm_cand.get("claims", []) or []
        verified_claims = sum(1 for c in claims if c.get("verification_status") == "verified")
        review_claims = len(claims) - verified_claims

        score_info = retrieval.evidence_score(
            drug_passages, drug_name,
            verified_claims=verified_claims, total_claims=len(claims),
        ) if drug_passages else {
            "score": 0.0, "tier": "Preliminary", "support": 0, "best_study_type": "none",
            "verification": 0.0,
            "breakdown": {
                "verification": 0.0, "verification_role": "multiplier",
                "verified_claims": verified_claims, "total_claims": len(claims),
                "evidence_strength": 0.0,
                "relevance": 0.0, "relevance_weight": 0.35,
                "support": 0.0, "support_weight": 0.35,
                "study_quality": 0.0, "study_quality_weight": 0.30,
            },
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

        # Contract expected by the frontend's coverage panel. Additive: the
        # evidence_summary block above is retained unchanged.
        if verified_claims > 0 and review_claims == 0:
            verification_status = "verified"
        elif claims:
            verification_status = "needs_review"
        else:
            verification_status = "not_assessed"

        if evidence_status == "supported":
            coverage_status = "available"
        elif evidence_status == "no_candidate_specific_evidence":
            coverage_status = "none"
        else:
            coverage_status = "insufficient"

        literature_coverage = {
            "status": coverage_status,
            "source_record_count": len(drug_passages),
            "distinct_pmid_count": len(distinct_pmids),
            "verification_status": verification_status,
        }

        results.append({
            "rank": i + 1,
            "drug": drug_name,
            "kg_score": kg_cand.get("score"),
            "direction": llm_cand.get("direction", "Uncertain"),
            "evidence": score_info,
            "reason": reason,
            "claims": claims,
            "evidence_summary": evidence_summary,
            "literature_coverage": literature_coverage,
        })

    # Step 7b: rank by evidence score.
    #
    # The displayed order is the EVIDENCE order, so a candidate whose quotations
    # actually verified rises and one that scores only on publication metadata
    # falls. The knowledge-graph origin is not lost: it stays in
    # evidence_summary.graph_rank, and the audit still reports it separately as
    # displayed_kg_rank. Ties break on the graph rank, then the drug name, so the
    # ordering is fully deterministic.
    results.sort(key=lambda c: (
        -(c["evidence"].get("score") or 0.0),
        c["evidence_summary"]["graph_rank"],
        c["drug"].lower(),
    ))
    for position, candidate in enumerate(results, start=1):
        candidate["rank"] = position

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
    if evidence_scope == coverage.EVIDENCE_SCOPE_LIVE:
        live_provider = live_outcome.provider if live_outcome is not None else "the live provider"
        message = (
            f"No indexed local literature exists for '{disease['name']}'; evidence "
            f"was retrieved live from {live_provider} and bound to specific "
            f"graph candidates. Live records are not part of the indexed corpus."
        )
    else:
        message = (
            f"Answered from the indexed local corpus "
            f"({local_passage_count} passage(s) for this disease)."
        )

    response = {
        "status": "ok",
        "query": query,
        "message": message,
        "disease": disease,
        "results": results,
        "known_indications": known_indications,
        "passages": top_passages,
        "evidence_scope": evidence_scope,
        "coverage": _build_coverage(
            disease, candidates, live_outcome, top_passages,
            evidence_scope, local_passage_count,
        ),
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
        # Which scorer produced these numbers. Cached entries are checked against
        # it, so re-weighting the scorer cannot serve stale scores.
        "scoring_function": audit.SCORING_FUNCTION_ID,
        "ranking_method": "evidence_score_desc",
    }

    if live_outcome is not None:
        # Provenance: which provider, which query, when, and whether it was cached.
        # Live evidence is never presented as if it were the local corpus.
        response["live_retrieval"] = live_outcome.summary()

    return response


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
