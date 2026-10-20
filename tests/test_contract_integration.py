"""Integration contract tests: the response shape the frontend actually reads.

The frontend (arena/1d3241c4-pharmasure) was written against a coverage
vocabulary the backend did not emit, so its coverage panel rendered "not
reported" for every field. These tests pin the reconciled contract.

Every expected key here was taken from the frontend's own mappers in
frontend/src/services/api.ts and its reader in
frontend/src/components/CoverageStatus.tsx — not invented.

Run:  venv/bin/python -m pytest tests/test_contract_integration.py -v
"""
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.pipeline as pipeline
from src import coverage, live_retrieval as lr
from src.app import app

client = TestClient(app)

KNOWN_DISEASE = "Alzheimer disease"


def _first_uncovered_disease() -> str:
    """A disease that resolves with candidates but has no local literature."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    passages = json.load(open(os.path.join(root, "data", "passages.json")))
    local = {coverage.normalize_disease_key(p.get("disease")) for p in passages}
    diseases = json.load(open(os.path.join(root, "data", "disease_lookup.json")))
    candidates = json.load(open(os.path.join(root, "data", "candidates.json")))
    for did, info in diseases.items():
        name = info.get("n")
        if not name or coverage.normalize_disease_key(name) in local:
            continue
        if candidates.get(did, {}).get("c"):
            return str(name)
    pytest.skip("no uncovered disease available")
    raise AssertionError("unreachable")


def _first_no_candidate_disease() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    diseases = json.load(open(os.path.join(root, "data", "disease_lookup.json")))
    candidates = json.load(open(os.path.join(root, "data", "candidates.json")))
    for did, info in diseases.items():
        name = info.get("n")
        if name and not candidates.get(did, {}).get("c"):
            return str(name)
    pytest.skip("no candidate-less disease available")
    raise AssertionError("unreachable")

# Keys the frontend reads (from api.ts mappers / CoverageStatus.tsx).
FE_COVERAGE_KEYS = {
    "disease_resolution_status", "graph_candidate_status", "literature_status",
    "source_mode", "provider", "retrieval_status", "retrieved_record_count",
    "distinct_pmid_count", "retrieved_at", "provider_message",
}
FE_CANDIDATE_KEYS = {"rank", "kg_score", "drug", "direction", "evidence",
                     "literature_coverage", "reason", "claims", "evidence_audit"}
FE_PASSAGE_KEYS = {"id", "text", "source", "pmid", "year", "pub_type", "title",
                   "source_url", "provenance", "retrieval_score", "study_weight"}

# Values CoverageStatus.tsx switches on. A value outside these sets silently
# falls through to a generic "not reported" label.
VALID_SOURCE_MODE = {"local", "live", "mixed", "unknown"}
VALID_LITERATURE_STATUS = {"available", "none", "insufficient", "unavailable", "unknown"}
VALID_GRAPH_STATUS = {"available", "none", "unavailable"}
VALID_RESOLUTION = {"resolved", "unresolved"}
ERROR_RETRIEVAL_STATUS = {"rate_limited", "timeout", "unavailable", "failed"}


@pytest.fixture(autouse=True)
def _disable_live_retrieval(monkeypatch):
    """Keep the local-path assertions offline; the live path is tested separately."""
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "0")


@pytest.fixture(scope="module")
def local_result():
    return pipeline.run_pipeline(KNOWN_DISEASE)


# --------------------------------------------------------------------------- #
# Coverage block
# --------------------------------------------------------------------------- #

def test_coverage_block_has_every_key_the_frontend_reads(local_result):
    cov = local_result["coverage"]
    missing = FE_COVERAGE_KEYS - set(cov)
    assert not missing, f"frontend reads these but backend omits them: {sorted(missing)}"


def test_coverage_vocabulary_is_within_the_frontends_switch_sets(local_result):
    cov = local_result["coverage"]
    assert cov["source_mode"] in VALID_SOURCE_MODE
    assert cov["literature_status"] in VALID_LITERATURE_STATUS
    assert cov["graph_candidate_status"] in VALID_GRAPH_STATUS
    assert cov["disease_resolution_status"] in VALID_RESOLUTION


def test_local_path_reports_local_source_mode(local_result):
    cov = local_result["coverage"]
    assert cov["disease_resolution_status"] == "resolved"
    assert cov["graph_candidate_status"] == "available"
    assert cov["literature_status"] == "available"
    assert cov["source_mode"] == "local"
    assert cov["provider"] is None, "no provider is used on the local path"
    assert cov["retrieval_status"] == "not_attempted"


def test_original_count_fields_are_retained(local_result):
    """Additive change: existing consumers must keep working."""
    cov = local_result["coverage"]
    assert "local_passage_count" in cov
    assert "local_literature_available" in cov
    assert "retrieved_passage_count" in cov
    assert cov["local_literature_available"] is True


def test_top_level_message_is_present_on_success(local_result):
    assert isinstance(local_result.get("message"), str)
    assert local_result["message"], "frontend reads message; it must not be empty on success"


# --------------------------------------------------------------------------- #
# Candidate block
# --------------------------------------------------------------------------- #

def test_candidate_has_every_key_the_frontend_reads(local_result):
    for candidate in local_result["results"]:
        missing = FE_CANDIDATE_KEYS - set(candidate)
        assert not missing, f"{candidate.get('drug')} omits {sorted(missing)}"


def test_kg_score_is_the_graph_score(local_result):
    for candidate in local_result["results"]:
        summary = candidate["evidence_summary"]
        assert candidate["kg_score"] == summary["graph_score"]


def test_literature_coverage_matches_evidence_summary(local_result):
    """The two views must agree; a mismatch would show conflicting coverage."""
    allowed = {"available", "insufficient", "none"}
    for candidate in local_result["results"]:
        lc = candidate["literature_coverage"]
        es = candidate["evidence_summary"]
        assert lc["status"] in allowed, f"frontend switch does not know {lc['status']!r}"
        assert lc["source_record_count"] == es["passage_count"]
        assert lc["distinct_pmid_count"] == es["distinct_pmid_count"]
        # status must not contradict the evidence it describes
        if lc["status"] == "available":
            assert es["verification"]["verified"] > 0
        if es["passage_count"] == 0:
            assert lc["status"] == "none"
        assert lc["verification_status"] in {"verified", "needs_review", "not_assessed"}


# --------------------------------------------------------------------------- #
# Passage block
# --------------------------------------------------------------------------- #

def test_passage_has_every_key_the_frontend_reads(local_result):
    for passage in local_result["passages"]:
        missing = FE_PASSAGE_KEYS - set(passage)
        assert not missing, f"passage {passage.get('id')} omits {sorted(missing)}"


def test_passage_provenance_is_reported(local_result):
    for passage in local_result["passages"]:
        assert passage["provenance"] in {"local_corpus", "live_retrieval"}


def test_source_url_is_derived_from_a_real_pmid_only(local_result):
    for passage in local_result["passages"]:
        url = passage["source_url"]
        if passage["pmid"]:
            assert url == f"https://pubmed.ncbi.nlm.nih.gov/{passage['pmid']}/"
        else:
            assert url is None, "no URL may be invented without an identifier"


def test_local_passage_title_is_not_fabricated(local_result):
    """The corpus stores no separate title, so it must stay null."""
    for passage in local_result["passages"]:
        assert passage["title"] is None


# --------------------------------------------------------------------------- #
# Abstention paths carry the same coverage contract
# --------------------------------------------------------------------------- #

def test_no_candidates_reports_graph_status_none():
    result = pipeline.run_pipeline(_first_no_candidate_disease())
    cov = result["coverage"]
    assert result["status"] == "no_candidates"
    assert cov["disease_resolution_status"] == "resolved"
    assert cov["graph_candidate_status"] == "none"
    assert cov["literature_status"] == "none"
    assert FE_COVERAGE_KEYS <= set(cov)


def test_unresolved_disease_reports_unresolved_not_a_false_negative():
    result = pipeline.run_pipeline("Dengue fever")
    cov = result["coverage"]
    assert result["status"] == "unsupported_disease"
    assert cov["disease_resolution_status"] == "unresolved"
    # "unavailable" means not assessed. Reporting "none" here would claim the
    # graph was consulted and came back empty, which is not what happened.
    assert cov["graph_candidate_status"] == "unavailable"
    assert cov["literature_status"] == "unknown"


def test_abstention_paths_also_carry_the_passage_and_message_contract():
    result = pipeline.run_pipeline("Dengue fever")
    assert isinstance(result.get("message"), str) and result["message"]
    assert result["passages"] == []


# --------------------------------------------------------------------------- #
# Provider failure must be visibly an error, not a clean negative
# --------------------------------------------------------------------------- #

def test_provider_failure_lands_in_the_frontends_error_set(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "1")

    class Boom:
        name = "europepmc"
        def search(self, q, l, t):
            raise lr.ProviderTimeout("timed out after 10s")

    monkeypatch.setattr(lr, "get_provider", lambda name=None: Boom())
    monkeypatch.setattr(lr, "_CACHE", lr.TTLCache(ttl_s=60))

    result = pipeline.run_pipeline(_first_uncovered_disease())

    cov = result["coverage"]
    assert result["status"] == "provider_unavailable"
    assert cov["literature_status"] == "unavailable"
    assert cov["retrieval_status"] in ERROR_RETRIEVAL_STATUS, (
        "a provider outage must trigger the frontend's error styling, not read as "
        "'no literature exists'"
    )
    assert cov["provider_message"], "the provider's own message should be surfaced"
    assert "Traceback" not in json.dumps(result)


def test_successful_but_empty_retrieval_is_not_in_the_error_set(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "1")

    class Empty:
        name = "europepmc"
        def search(self, q, l, t):
            return []

    monkeypatch.setattr(lr, "get_provider", lambda name=None: Empty())
    monkeypatch.setattr(lr, "_CACHE", lr.TTLCache(ttl_s=60))

    result = pipeline.run_pipeline(_first_uncovered_disease())

    cov = result["coverage"]
    assert result["status"] == "no_relevant_evidence"
    assert cov["retrieval_status"] not in ERROR_RETRIEVAL_STATUS
    assert cov["literature_status"] == "none"


def test_live_success_reports_live_source_mode(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "1")
    from src import kg

    disease = _first_uncovered_disease()
    resolved = kg.resolve_disease(disease)
    assert resolved is not None
    drug = kg.get_candidates(resolved["id"], top_n=10)["candidates"][0]["drug_name"]

    class Fake:
        name = "europepmc"
        def search(self, q, l, t):
            return [lr.LiveRecord(
                source_id="99000002", provider="europepmc",
                title=f"{drug} cohort study",
                abstract=f"We treated patients with {drug} and measured the outcome.",
                year=2025, url="https://pubmed.ncbi.nlm.nih.gov/99000002/",
                journal="J Test", pub_types=("Journal Article",),
                retrieved_at="2026-10-20T00:00:00+00:00", provider_rank=0)]

    monkeypatch.setattr(lr, "get_provider", lambda name=None: Fake())
    monkeypatch.setattr(lr, "_CACHE", lr.TTLCache(ttl_s=60))

    result = pipeline.run_pipeline(disease)
    cov = result["coverage"]
    assert result["status"] == "ok"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_LIVE
    assert cov["source_mode"] == "live"
    assert cov["provider"] == "europepmc"
    assert cov["retrieved_record_count"] == 1
    # retrieved_at is the moment of retrieval, and must agree with the
    # live_retrieval provenance block rather than being a second, drifting value.
    assert cov["retrieved_at"]
    assert cov["retrieved_at"] == result["live_retrieval"]["retrieved_at"]
    # Live provenance must survive into the passage the frontend links from.
    passage = result["passages"][0]
    assert passage["provenance"] == "live_retrieval"
    assert passage["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/99000002/"
    assert passage["title"] == f"{drug} cohort study"


# --------------------------------------------------------------------------- #
# Cache contract versioning
# --------------------------------------------------------------------------- #

def test_cached_entries_are_stamped_with_the_contract_version(tmp_path):
    """save_demo_cache must stamp the contract version on every entry.

    Writes to a temp path: this function's default target is the real
    data/demo_cache.json, so calling it without a path from a test would destroy
    the shipped demo cache.
    """
    saved = pipeline._demo_cache
    target = tmp_path / "cache.json"
    try:
        pipeline.save_demo_cache({KNOWN_DISEASE.lower(): {"status": "ok"}}, str(target))
        assert (pipeline._demo_cache[KNOWN_DISEASE.lower()]
                ["response_contract_version"]) == coverage.RESPONSE_CONTRACT_VERSION
        # The real cache on disk must be untouched.
        assert json.loads(target.read_text())["alzheimer disease"][
            "response_contract_version"] == coverage.RESPONSE_CONTRACT_VERSION
    finally:
        pipeline._demo_cache = saved


def test_stale_contract_cache_entry_is_not_served(monkeypatch):
    """A cached payload from an older contract must not be served as current."""
    saved = pipeline._demo_cache
    try:
        pipeline._demo_cache = {
            coverage.normalize_disease_key(KNOWN_DISEASE): {
                "status": "ok",
                "query": KNOWN_DISEASE,
                "disease": {"id": "MONDO:0004975", "name": KNOWN_DISEASE},
                "results": [], "known_indications": [], "passages": [],
                "timings_ms": {},
                "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
                "response_contract_version": "ancient-contract-v0",
            }
        }
        result = pipeline.run_pipeline(KNOWN_DISEASE)
    finally:
        pipeline._demo_cache = saved
    assert result.get("from_cache") is not True
    # And the freshly computed response does carry the current contract.
    assert FE_COVERAGE_KEYS <= set(result["coverage"])


def test_current_contract_cache_entry_is_served():
    saved = pipeline._demo_cache
    try:
        pipeline._demo_cache = {
            coverage.normalize_disease_key(KNOWN_DISEASE): {
                "status": "ok",
                "query": KNOWN_DISEASE,
                "message": "cached",
                "disease": {"id": "MONDO:0004975", "name": KNOWN_DISEASE},
                "results": [], "known_indications": [], "passages": [],
                "coverage": {k: None for k in FE_COVERAGE_KEYS},
                "timings_ms": {},
                "corpus_schema_version": coverage.CORPUS_SCHEMA_VERSION,
                "response_contract_version": coverage.RESPONSE_CONTRACT_VERSION,
            }
        }
        result = pipeline.run_pipeline(KNOWN_DISEASE)
    finally:
        pipeline._demo_cache = saved
    assert result.get("from_cache") is True


def test_save_demo_cache_refuses_to_silently_drop_entries(tmp_path):
    """A shrinking overwrite is refused unless explicitly allowed."""
    target = tmp_path / "cache.json"
    target.write_text(json.dumps({"alzheimer disease": {"status": "ok"},
                                  "asthma": {"status": "ok"}}))
    saved = pipeline._demo_cache
    try:
        with pytest.raises(ValueError, match="refusing to drop"):
            pipeline.save_demo_cache({"alzheimer disease": {"status": "ok"}}, str(target))
        # Unchanged on disk after the refusal.
        on_disk = json.loads(target.read_text())
        assert "asthma" in on_disk
        # Explicit opt-in still works.
        pipeline.save_demo_cache({"alzheimer disease": {"status": "ok"}}, str(target),
                                 allow_shrink=True)
        assert "asthma" not in json.loads(target.read_text())
    finally:
        pipeline._demo_cache = saved


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #

def test_api_query_returns_the_contract():
    resp = client.post("/api/query", json={"query": KNOWN_DISEASE})
    assert resp.status_code == 200
    data = resp.json()
    assert FE_COVERAGE_KEYS <= set(data["coverage"])
    assert FE_CANDIDATE_KEYS <= set(data["results"][0])
    assert FE_PASSAGE_KEYS <= set(data["passages"][0])
    text = json.dumps(data)
    assert "NaN" not in text and "Infinity" not in text


def test_api_never_leaks_internal_error_text(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "1")

    class Boom:
        name = "europepmc"
        def search(self, q, l, t):
            raise lr.ProviderHTTPError("Europe PMC server error (HTTP 503)")

    monkeypatch.setattr(lr, "get_provider", lambda name=None: Boom())
    monkeypatch.setattr(lr, "_CACHE", lr.TTLCache(ttl_s=60))

    resp = client.post("/api/query", json={"query": _first_uncovered_disease()})
    assert resp.status_code == 200
    assert "Traceback" not in resp.text
    assert "src/live_retrieval.py" not in resp.text
