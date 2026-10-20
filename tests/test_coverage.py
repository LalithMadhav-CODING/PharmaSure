"""Phase 1 acceptance tests: disease coverage and evidence boundaries.

These pin the behaviour that stops the system presenting unrelated literature as
disease-specific evidence, and that keeps the knowledge-graph vocabulary distinct
from local literature coverage.

Run:  venv/bin/python -m pytest tests/test_coverage.py -v
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

import src.pipeline as pipeline
from src import coverage, audit
from src.app import app

client = TestClient(app)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

KNOWN_DISEASE = "Alzheimer disease"


@pytest.fixture(autouse=True)
def _disable_live_retrieval(monkeypatch):
    """Pin the LOCAL evidence boundary these tests are about.

    Live retrieval is enabled by default in production. Leaving it on here would
    (a) make this suite depend on network availability, which the plan forbids,
    and (b) change the abstention status under test, since an uncovered disease
    would be answered by the provider rather than abstaining locally.

    The live path has its own coverage in tests/test_live_retrieval.py and
    tests/test_live_pipeline.py.
    """
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "0")


def _first_uncovered_disease() -> str:
    """A disease the graph resolves, with candidates, but absent from the corpus."""
    passages = json.load(open(os.path.join(DATA, "passages.json")))
    local = {coverage.normalize_disease_key(p.get("disease")) for p in passages}
    diseases = json.load(open(os.path.join(DATA, "disease_lookup.json")))
    candidates = json.load(open(os.path.join(DATA, "candidates.json")))
    for did, info in diseases.items():
        name = info.get("n")
        if not name:
            continue
        if coverage.normalize_disease_key(name) in local:
            continue
        if not candidates.get(did, {}).get("c"):
            continue
        return str(name)
    pytest.skip("no uncovered disease available in this corpus")
    raise AssertionError("unreachable")


def _first_no_candidate_disease() -> str:
    """A disease the graph resolves but has no candidates for."""
    diseases = json.load(open(os.path.join(DATA, "disease_lookup.json")))
    candidates = json.load(open(os.path.join(DATA, "candidates.json")))
    for did, info in diseases.items():
        name = info.get("n")
        if name and not candidates.get(did, {}).get("c"):
            return str(name)
    pytest.skip("no candidate-less disease available")
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- #
# Coverage module
# --------------------------------------------------------------------------- #

def test_coverage_metadata_computed_from_real_data():
    cov = coverage.coverage_metadata()
    passages = json.load(open(os.path.join(DATA, "passages.json")))
    diseases = json.load(open(os.path.join(DATA, "disease_lookup.json")))

    assert cov["local_abstract_count"] == len(passages)
    assert cov["kg_disease_count"] == len(diseases)
    # The whole point: these two numbers must not be conflated.
    assert cov["local_literature_disease_count"] < cov["kg_disease_count"]
    assert cov["corpus_schema_version"]
    assert cov["live_retrieval_enabled"] is False


def test_normalize_disease_key_is_canonical_not_substring():
    assert coverage.normalize_disease_key("Alzheimer's disease") == coverage.normalize_disease_key("Alzheimer disease")
    assert coverage.normalize_disease_key("  Type 2  DIABETES ") == "type 2 diabetes"
    # Distinct diseases must NOT normalise to the same key.
    assert coverage.normalize_disease_key("type 1 diabetes") != coverage.normalize_disease_key("type 2 diabetes")


def test_local_literature_check_is_exact():
    assert coverage.has_local_literature(KNOWN_DISEASE) is True
    assert coverage.local_passage_count(KNOWN_DISEASE) > 0
    assert coverage.has_local_literature("Zygodactyly type 4") is False
    assert coverage.local_passage_count("Zygodactyly type 4") == 0
    assert coverage.has_local_literature(None) is False


# --------------------------------------------------------------------------- #
# Evidence boundary — the critical Phase 1 requirement
# --------------------------------------------------------------------------- #

def test_uncovered_disease_does_not_receive_unrelated_passages():
    """A disease with no local literature must not be given foreign passages."""
    disease = _first_uncovered_disease()
    result = pipeline.run_pipeline(disease)

    assert result["status"] == "no_local_evidence"
    assert result["passages"] == [], "no passages may be presented as evidence"
    assert result["results"] == [], "no evidence-backed candidates may be returned"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_NONE


def test_uncovered_disease_still_reports_candidate_availability():
    """Candidate availability is a separate fact from literature availability."""
    disease = _first_uncovered_disease()
    result = pipeline.run_pipeline(disease)

    pool = result.get("candidate_pool") or []
    assert pool, "graph candidates should still be surfaced"
    # The per-candidate status states the candidate has no evidence. The *reason*
    # for that absence lives in the top-level status, because with live retrieval
    # the reason can be a provider outage, an empty search, or absent local
    # coverage — pinning the candidate's status to one reason would be wrong.
    assert all(c["evidence_status"] == "no_evidence" for c in pool)
    assert all("graph_rank" in c for c in pool)
    # Graph score must be present and must not be dressed up as evidence.
    assert all("graph_score" in c for c in pool)
    assert result["status"] in {
        "no_local_evidence", "no_relevant_evidence", "provider_unavailable",
    }


def test_uncovered_disease_message_does_not_claim_ineffectiveness():
    disease = _first_uncovered_disease()
    result = pipeline.run_pipeline(disease)
    msg = result["message"].lower()
    assert "not evidence of ineffectiveness" in msg or "absence of evidence" in msg
    for forbidden in ("ineffective", "no treatment exists", "does not work"):
        assert forbidden not in msg.replace("not evidence of ineffectiveness", "")


def test_known_disease_still_works_after_coverage_gate():
    result = pipeline.run_pipeline(KNOWN_DISEASE)
    assert result["status"] == "ok"
    # Candidates with no verified evidence are not displayed, so the count is driven
    # by corpus coverage rather than a fixed list length.
    assert len(result["results"]) >= 1
    assert all(c["evidence"]["score"] > 0 for c in result["results"])
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_LOCAL
    assert result["coverage"]["local_literature_available"] is True
    assert result["coverage"]["local_passage_count"] > 0


def test_returned_passages_belong_to_the_requested_disease():
    """Every passage in a successful response must be tagged with that disease."""
    result = pipeline.run_pipeline(KNOWN_DISEASE)
    target = coverage.normalize_disease_key(KNOWN_DISEASE)
    for passage in result["passages"]:
        assert coverage.normalize_disease_key(passage.get("disease")) == target


# --------------------------------------------------------------------------- #
# Distinct, controlled statuses
# --------------------------------------------------------------------------- #

def test_the_four_outcomes_are_distinct():
    covered = pipeline.run_pipeline(KNOWN_DISEASE)
    uncovered = pipeline.run_pipeline(_first_uncovered_disease())
    unresolved = pipeline.run_pipeline("Dengue fever")
    no_cands = pipeline.run_pipeline(_first_no_candidate_disease())

    statuses = {
        covered["status"],
        uncovered["status"],
        unresolved["status"],
        no_cands["status"],
    }
    assert statuses == {"ok", "no_local_evidence", "unsupported_disease", "no_candidates"}


def test_no_candidates_is_not_reported_as_insufficient_evidence():
    result = pipeline.run_pipeline(_first_no_candidate_disease())
    assert result["status"] == "no_candidates"
    assert result["results"] == []
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_NONE


def test_unsupported_disease_still_reports_unresolved():
    result = pipeline.run_pipeline("Dengue fever")
    assert result["status"] == "unsupported_disease"
    assert "Could not resolve" in result["message"]


# --------------------------------------------------------------------------- #
# Health endpoint
# --------------------------------------------------------------------------- #

def test_health_separates_graph_from_literature_coverage():
    data = client.get("/api/health").json()
    assert data["kg_disease_count"] > data["local_literature_disease_count"]
    assert data["local_abstract_count"] > 0
    assert data["local_literature_disease_count"] == 113
    assert data["corpus_size"] == data["local_abstract_count"]
    assert data["corpus_schema_version"]


def test_health_does_not_claim_all_diseases_are_supported():
    data = client.get("/api/health").json()
    assert data["all_diseases_supported"] is False


def test_health_declares_live_retrieval_state():
    data = client.get("/api/health").json()
    assert data["live_retrieval_enabled"] is False
    assert "demo_supported_diseases" in data


# --------------------------------------------------------------------------- #
# Cache identity — must not leak across diseases
# --------------------------------------------------------------------------- #

def _with_fake_cache(entry_key, entry):
    saved = pipeline._demo_cache
    pipeline._demo_cache = {entry_key: entry}
    return saved


def _restore(saved):
    pipeline._demo_cache = saved


def test_cache_does_not_leak_across_diseases():
    """'diabetes' must NOT be answered with the 'type 2 diabetes' cached result."""
    entry = {
        "status": "ok", "query": "type 2 diabetes",
        "disease": {"id": "MONDO:1", "name": "Type 2 diabetes mellitus"},
        "results": [], "known_indications": [], "passages": [], "timings_ms": {},
    }
    saved = _with_fake_cache("type 2 diabetes", entry)
    try:
        out = pipeline.run_pipeline("diabetes")
    finally:
        _restore(saved)
    assert out.get("from_cache") is not True
    assert out.get("disease", {}).get("name") != "Type 2 diabetes mellitus"


def test_cache_does_not_leak_on_substring_query():
    entry = {
        "status": "ok", "query": "asthma",
        "disease": {"id": "MONDO:2", "name": "Asthma"},
        "results": [], "known_indications": [], "passages": [], "timings_ms": {},
    }
    saved = _with_fake_cache("asthma", entry)
    try:
        out = pipeline.run_pipeline("asthma and copd overlap syndrome")
    finally:
        _restore(saved)
    assert out.get("from_cache") is not True


def test_cache_hit_uses_canonical_identity():
    """Typographic variants of the same disease SHOULD hit the same entry."""
    entry = {
        "status": "ok", "query": "alzheimer disease",
        "disease": {"id": "MONDO:0004975", "name": "Alzheimer disease"},
        "results": [], "known_indications": [], "passages": [],
        "timings_ms": {},
        "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
        # Must carry the current response contract, or the entry is correctly
        # treated as stale and this stops testing canonical-identity matching.
        "response_contract_version": coverage.RESPONSE_CONTRACT_VERSION,
        "scoring_function": audit.SCORING_FUNCTION_ID,
    }
    saved = _with_fake_cache("alzheimer disease", entry)
    try:
        out = pipeline.run_pipeline("Alzheimer's disease")
    finally:
        _restore(saved)
    assert out.get("from_cache") is True
    assert out["disease"]["name"] == "Alzheimer disease"


def test_stale_cache_version_is_not_served():
    entry = {
        "status": "ok", "query": "alzheimer disease",
        "disease": {"id": "MONDO:0004975", "name": "Alzheimer disease"},
        "results": [], "known_indications": [], "passages": [],
        "timings_ms": {},
        "corpus_schema_version": "ancient-corpus-v0",
    }
    saved = _with_fake_cache("alzheimer disease", entry)
    try:
        out = pipeline.run_pipeline("Alzheimer's disease")
    finally:
        _restore(saved)
    assert out.get("from_cache") is not True, "a stale-version cache entry must not be served"


# --------------------------------------------------------------------------- #
# Controlled errors, never tracebacks
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": "   "}, {"query": 123}])
def test_malformed_inputs_return_controlled_errors(payload):
    resp = client.post("/api/query", json=payload)
    assert resp.status_code in (400, 422)
    assert "Traceback" not in resp.text


def test_invalid_json_returns_400():
    resp = client.post("/api/query", content=b"not json",
                       headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert "Traceback" not in resp.text


def test_responses_are_json_serializable_with_finite_numbers():
    for q in (KNOWN_DISEASE, "Dengue fever"):
        data = client.post("/api/query", json={"query": q}).json()
        text = json.dumps(data)  # raises if not serializable
        assert "NaN" not in text and "Infinity" not in text
