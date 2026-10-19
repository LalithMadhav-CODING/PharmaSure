"""Integration tests for the PharmaSure API, pipeline, and frontend delivery.

NOTE ON MAINTENANCE: six assertions in this file were stale and failing *before*
the evidence-audit work began (baseline recorded: 6 failed, 2 passed). They
asserted behaviour the product had intentionally moved away from:

  * the product was renamed Telemedicon -> PharmaSure
  * disease resolution now returns the canonical EveryCure/MONDO name
    ("Alzheimer disease"), not the user's typographic form ("Alzheimer's disease")
  * every disease is now resolvable, so "unsupported" only applies to queries the
    knowledge graph genuinely cannot resolve
  * the corpus grew from 5 demo diseases to 842 passages across 113 diseases, so
    per-disease counts changed

They are corrected here to the intended current behaviour. No assertion was
weakened to make a failing implementation pass — where the implementation was at
fault (a missing `supported_diseases` field and a hardcoded `corpus_size`), the
endpoint was fixed instead.

Run:  venv/bin/python -m pytest tests/test_api_integration.py -v
"""
import re

import pytest
from fastapi.testclient import TestClient

from src.app import app

client = TestClient(app)

# Canonical names as returned by disease resolution.
ALZHEIMER = "Alzheimer disease"


def _norm(text: str) -> str:
    """Whitespace/quote-insensitive comparison, mirroring src/verify.py."""
    t = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


# =========================================================================== #
# Existing contract
# =========================================================================== #

def test_health_endpoint():
    """GET /api/health exposes status, real corpus size and supported diseases."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["corpus_size"], int)
    assert data["corpus_size"] > 0
    # Reported size must be the real corpus, not a hardcoded literal.
    assert data["corpus_size"] != 7500
    assert "supported_diseases" in data
    assert "Alzheimer's disease" in data["supported_diseases"]
    assert "Parkinson's disease" in data["supported_diseases"]
    assert "Multiple myeloma" in data["supported_diseases"]


def test_query_alzheimers():
    """POST /api/query returns ranked candidates with verifiable citations."""
    response = client.post("/api/query", json={"query": "Alzheimer's disease"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # Resolution returns the canonical KG name, not the user's typographic form.
    assert data["disease"]["name"] == ALZHEIMER
    assert len(data["results"]) == 10
    assert len(data["known_indications"]) == 13
    assert data.get("from_cache") is True

    ranks = [c["rank"] for c in data["results"]]
    assert ranks == list(range(1, 11))

    # Directions come from the model; only assert the ones the cache produces.
    directions = {c["direction"] for c in data["results"]}
    assert directions <= {"Positive", "Negative", "Mixed", "Uncertain"}
    assert "Positive" in directions

    tiers = {c["evidence"]["tier"] for c in data["results"]}
    assert tiers <= {"Strong", "Moderate", "Preliminary"}
    assert len(tiers) > 1, "evidence scores should not all land in one tier"

    for c in data["results"]:
        assert 0.0 <= c["evidence"]["score"] <= 1.0
        # Candidates with no matching passage legitimately have zero support.
        assert c["evidence"]["support"] >= 0
        assert len(c["reason"]) > 10

    # Citation ids must map to returned passages, and verified quotes must be
    # genuinely present in the cited passage (whitespace-insensitive).
    passages_by_id = {str(p["id"]): p for p in data["passages"]}
    for c in data["results"]:
        for claim in c["claims"]:
            assert "text" in claim
            assert claim["verification_status"] in ["verified", "needs_review"]
            cids = claim.get("citations") or claim.get("citation_ids") or []
            for cid in cids:
                assert str(cid) in passages_by_id
            if claim["verification_status"] == "verified" and cids:
                passage = passages_by_id[str(cids[0])]
                assert _norm(claim["quote"]) in _norm(passage["text"])


def test_all_demo_queries():
    """All demo queries return ok with 10 candidates and their real known counts."""
    queries = [
        ("Parkinson's disease", 10, 27),
        ("Multiple myeloma", 10, 13),
        ("Type 2 diabetes", 10, 40),
        ("Asthma", 10, 27),
    ]
    for q, expected_cands, expected_known in queries:
        resp = client.post("/api/query", json={"query": q})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok", f"Query {q} failed: {data}"
        assert len(data["results"]) == expected_cands, f"{q}: candidate count"
        assert len(data["known_indications"]) == expected_known, f"{q}: known count"


def test_unsupported_disease():
    """A query the knowledge graph cannot resolve reports unsupported_disease."""
    response = client.post("/api/query", json={"query": "Dengue fever"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unsupported_disease"
    assert "Could not resolve" in data["message"]
    assert len(data["results"]) == 0


def test_insufficient_evidence():
    """A resolvable disease with no candidate drugs abstains explicitly."""
    # Resolves in the KG, but has no candidate set.
    response = client.post("/api/query", json={"query": "Xanthomatous hypophysitis"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_evidence"
    assert len(data["results"]) == 0


def test_empty_query_validation():
    """Empty or missing query strings are rejected with 400."""
    assert client.post("/api/query", json={"query": ""}).status_code == 400
    assert client.post("/api/query", json={}).status_code == 400
    assert client.post("/api/query", json={"query": "   "}).status_code == 400


def test_frontend_delivery():
    """Frontend HTML is served at / with the current product name."""
    response = client.get("/")
    assert response.status_code == 200
    assert "PharmaSure" in response.text
    assert '<div id="root">' in response.text


def test_legacy_gradio_mounted():
    """The legacy Gradio console is preserved at /gradio."""
    assert client.get("/gradio/").status_code == 200


def test_runtime_config_endpoint():
    """Runtime config exposes a same-origin apiBase and a proxy target."""
    response = client.get("/config.json")
    assert response.status_code == 200
    data = response.json()
    assert "apiBase" in data and "proxyTarget" in data


# =========================================================================== #
# Evidence audit — API integration (spec §6.6)
# =========================================================================== #

def _ok_payload(query="Alzheimer's disease"):
    resp = client.post("/api/query", json={"query": query})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    return data


def test_query_response_carries_audit_summary():
    data = _ok_payload()
    summary = data.get("evidence_audit_summary")
    assert summary is not None
    assert summary.get("version")
    assert summary.get("method") == "leave_one_independent_study_out"
    assert "audited" in summary


def test_every_candidate_carries_an_evidence_audit():
    data = _ok_payload()
    for candidate in data["results"]:
        assert "evidence_audit" in candidate, candidate.get("drug")
        assert candidate["evidence_audit"].get("status")


def test_audit_is_complete_when_multiple_study_units_exist():
    data = _ok_payload()
    audits = [c["evidence_audit"] for c in data["results"]]
    complete = [a for a in audits if a["status"] == "complete"]
    assert complete, "at least one candidate should have an auditable evidence set"
    for a in complete:
        assert a["counterfactuals"], "a complete audit must expose its scenarios"
        assert a["stability"]["successful_counterfactuals"] >= 2


def test_audit_status_is_explicit_when_data_is_insufficient():
    data = _ok_payload()
    for a in (c["evidence_audit"] for c in data["results"]):
        if a["status"] != "complete":
            # Must state why, never silently omit.
            assert a.get("reason") or a.get("warnings")


def test_audit_preserves_the_baseline_score_exactly():
    data = _ok_payload()
    for c in data["results"]:
        audit = c["evidence_audit"]
        assert audit["baseline"]["evidence_score"] == pytest.approx(
            c["evidence"]["score"], abs=1e-6
        )


def test_audit_rank_is_distinct_from_the_displayed_rank():
    data = _ok_payload()
    for c in data["results"]:
        audit = c["evidence_audit"]
        assert audit["baseline"]["displayed_kg_rank"] == c["rank"]
        assert "evidence_rank" in audit["baseline"]
        assert audit["ranking_scope"] == "evidence_rank_over_retrieved_candidates"


def test_audit_does_not_change_the_existing_candidate_contract():
    data = _ok_payload()
    for c in data["results"]:
        assert {"rank", "drug", "direction", "evidence", "reason", "claims"} <= set(c)


def test_audit_does_not_change_existing_evidence_scores():
    """The audit must be additive: scoring behaviour is untouched."""
    data = _ok_payload()
    for c in data["results"]:
        breakdown = c["evidence"].get("breakdown")
        assert breakdown is not None
        recomputed = (
            0.25 * breakdown["relevance"]
            + 0.35 * breakdown["support"]
            + 0.40 * breakdown["study_quality"]
        )
        assert c["evidence"]["score"] == pytest.approx(recomputed, abs=0.002)


def test_audit_counterfactual_deltas_are_consistent():
    data = _ok_payload()
    for c in data["results"]:
        audit = c["evidence_audit"]
        baseline = audit["baseline"]["evidence_score"]
        for cf in audit["counterfactuals"]:
            if cf["status"] != "ok":
                continue
            assert cf["score_delta"] == pytest.approx(baseline - cf["counterfactual_score"], abs=1e-6)
            assert cf["rank_delta"] == cf["counterfactual_rank"] - audit["baseline"]["evidence_rank"]


def test_audit_source_links_are_valid_pubmed_urls():
    data = _ok_payload()
    seen = 0
    for c in data["results"]:
        for src in c["evidence_audit"].get("sources", []):
            if src.get("pubmed_url"):
                seen += 1
                assert re.fullmatch(r"https://pubmed\.ncbi\.nlm\.nih\.gov/\d+/", src["pubmed_url"])
                assert src["pubmed_url"].endswith(f"/{src['pmid']}/")
    assert seen > 0, "expected at least one source with a PubMed link"


def test_audit_sources_reference_returned_passages():
    data = _ok_payload()
    passage_ids = {str(p["id"]) for p in data["passages"]}
    for c in data["results"]:
        for src in c["evidence_audit"].get("sources", []):
            assert str(src["passage_id"]) in passage_ids


def test_audit_states_that_independence_is_unverified():
    data = _ok_payload()
    audits = [c["evidence_audit"] for c in data["results"]]
    assert any(
        a["study_counts"].get("study_independence_verified") is False
        for a in audits
        if a.get("study_counts")
    )
    assert any("independence cannot be verified" in w for a in audits for w in a.get("warnings", []))


def test_audit_does_not_claim_clinical_validity():
    data = _ok_payload()
    blob = str(data).lower()
    for forbidden in ("clinically proven", "clinically validated", "state of the art",
                      "first of its kind", "probability of efficacy"):
        assert forbidden not in blob


def test_legacy_cached_response_without_audit_does_not_crash():
    """A cache entry predating the audit must degrade explicitly, not error."""
    import src.pipeline as pipeline

    saved = pipeline._demo_cache
    try:
        pipeline._demo_cache = {
            "legacy test disease": {
                "status": "ok",
                "query": "legacy test disease",
                "disease": {"id": "MONDO:9", "name": "Legacy disease"},
                "results": [{"rank": 1, "drug": "DrugX",
                             "evidence": {"score": 0.1, "tier": "Preliminary",
                                          "support": 0, "best_study_type": "none"},
                             "reason": "legacy", "claims": [], "direction": "Uncertain"}],
                "known_indications": [],
                "passages": [],
                "timings_ms": {},
            }
        }
        out = pipeline.run_pipeline("legacy test disease")
    finally:
        pipeline._demo_cache = saved

    assert out["status"] == "ok"
    assert out["results"][0]["drug"] == "DrugX"
    # No fabricated audit is presented for a result that never had one.
    assert out["evidence_audit_summary"]["status"] == "unavailable_for_cached_result"


def test_audit_failure_does_not_remove_candidates(monkeypatch):
    """A broken audit layer must leave the baseline candidate results intact.

    The audit is additive: if it raises, every candidate must still be returned
    with its original score, and the failure must be reported explicitly rather
    than swallowed.
    """
    import src.audit as audit_mod
    import src.pipeline as pipeline

    # Serve the demo result from cache so no model call is needed, then break
    # only the audit layer.
    saved = pipeline._demo_cache
    try:
        pipeline._demo_cache = {}
        out = pipeline.run_pipeline("Asthma")
        baseline = [(c["drug"], c["evidence"]["score"]) for c in out["results"]]
        assert baseline, "expected candidate results before breaking the audit"

        def explode(*a, **k):
            raise RuntimeError("induced audit failure")

        monkeypatch.setattr(audit_mod, "attach_audits", explode)
        broken = pipeline.run_pipeline("Asthma")

        assert broken["status"] == "ok"
        assert [(c["drug"], c["evidence"]["score"]) for c in broken["results"]] == baseline
        assert broken["evidence_audit_summary"]["status"].startswith("failed")
    finally:
        pipeline._demo_cache = saved


def test_api_does_not_expose_secrets_or_paths():
    data = _ok_payload()
    blob = str(data)
    for forbidden in ("GEMINI_API_KEY", "/home/", "tailscale", "OLLAMA", "sk-"):
        assert forbidden not in blob
