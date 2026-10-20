"""Phase 5 acceptance tests: live retrieval integrated into the real pipeline.

Verifies the end-to-end wiring: evidence-source precedence, the distinct
abstention statuses, that live passages are never passed off as local corpus
evidence, and that the existing audit still works on the live path.

Run:  venv/bin/python -m pytest tests/test_live_pipeline.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.pipeline as pipeline
from src import coverage, kg, live_retrieval as lr
from src.app import app
from fastapi.testclient import TestClient

client = TestClient(app)

KNOWN_DISEASE = "Alzheimer disease"


def _uncovered_disease_with_candidates() -> str:
    """A disease that resolves with graph candidates but has no local literature."""
    import json as _json

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    passages = _json.load(open(os.path.join(root, "data", "passages.json")))
    local = {coverage.normalize_disease_key(p.get("disease")) for p in passages}
    diseases = _json.load(open(os.path.join(root, "data", "disease_lookup.json")))
    candidates = _json.load(open(os.path.join(root, "data", "candidates.json")))

    for did, info in diseases.items():
        name = info.get("n")
        if not name or coverage.normalize_disease_key(name) in local:
            continue
        if candidates.get(did, {}).get("c"):
            return str(name)
    pytest.skip("no uncovered disease available in this corpus")
    raise AssertionError("unreachable")


def _resolve_and_candidates(disease):
    resolved = kg.resolve_disease(disease)
    assert resolved is not None, f"{disease} should resolve"
    cands = kg.get_candidates(resolved["id"], top_n=10)["candidates"]
    assert cands, f"{disease} should have graph candidates"
    return cands


def _records_for(drug_name, pmid="99000001"):
    return [lr.LiveRecord(
        source_id=pmid, provider="europepmc",
        title=f"{drug_name} in a rare disease cohort",
        abstract=(f"We treated patients with {drug_name} and recorded the outcome. "
                  f"The {drug_name} arm showed a measurable change."),
        year=2025, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        journal="Journal of Rare Disease", pub_types=("Journal Article",),
        retrieved_at="2026-10-20T00:00:00+00:00", provider_rank=0,
    )]


class FakeProvider:
    name = "europepmc"

    def __init__(self, records=None, exc=None):
        self._records = records or []
        self._exc = exc
        self.calls = 0

    def search(self, query, limit, timeout_s):
        self.calls += 1
        if self._exc:
            raise self._exc
        return list(self._records)


@pytest.fixture
def install_provider(monkeypatch):
    """Install a fake provider and a clean live cache for the duration of a test."""
    def _install(provider):
        monkeypatch.setattr(lr, "get_provider", lambda name=None: provider)
        monkeypatch.setattr(lr, "_CACHE", lr.TTLCache(ttl_s=60))
        return provider
    return _install


# --------------------------------------------------------------------------- #
# Precedence: local evidence wins, live is only a fallback
# --------------------------------------------------------------------------- #

def test_local_evidence_takes_precedence_over_live(install_provider):
    provider = install_provider(FakeProvider(_records_for("Galantamine")))
    result = pipeline.run_pipeline(KNOWN_DISEASE)
    assert result["status"] == "ok"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_LOCAL
    assert provider.calls == 0, "live retrieval must not run when local evidence exists"


def test_local_passages_are_not_marked_as_live():
    result = pipeline.run_pipeline(KNOWN_DISEASE)
    for passage in result["passages"]:
        assert passage.get("source_mode") != "live_retrieval"


# --------------------------------------------------------------------------- #
# Live fallback
# --------------------------------------------------------------------------- #

def test_uncovered_disease_uses_live_retrieval(install_provider):
    disease = _uncovered_disease_with_candidates()
    resolved = kg.resolve_disease(disease)
    candidates = kg.get_candidates(resolved["id"], top_n=10)["candidates"]
    drug = candidates[0]["drug_name"]

    provider = install_provider(FakeProvider(_records_for(drug)))
    result = pipeline.run_pipeline(disease)

    assert result["status"] == "ok"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_LIVE
    assert provider.calls == 1
    assert result["passages"], "live evidence should be present"

    for passage in result["passages"]:
        assert passage["source_mode"] == "live_retrieval"
        assert passage["provider"] == "europepmc"
        assert passage["retrieved_at"]

    assert result["live_retrieval"]["provider"] == "europepmc"
    assert result["live_retrieval"]["records_after_dedup"] == 1
    # Local coverage is still reported truthfully as absent.
    assert result["coverage"]["local_literature_available"] is False


def test_live_passages_are_attributable_to_the_matching_candidate(install_provider):
    disease = _uncovered_disease_with_candidates()
    resolved = kg.resolve_disease(disease)
    candidates = kg.get_candidates(resolved["id"], top_n=10)["candidates"]
    drug = candidates[0]["drug_name"]

    install_provider(FakeProvider(_records_for(drug)))
    result = pipeline.run_pipeline(disease)

    for passage in result["passages"]:
        assert passage["drug"] == drug
        assert lr.record_mentions_drug(
            lr.LiveRecord(source_id=passage["pmid"], provider="europepmc",
                          title=passage["title"], abstract=passage["text"],
                          year=passage["year"], url=passage["url"], journal=None),
            passage["drug"],
        )


def test_audit_still_runs_on_the_live_path(install_provider):
    """Phase 3 capability must survive the Phase 5 change."""
    disease = _uncovered_disease_with_candidates()
    resolved = kg.resolve_disease(disease)
    candidates = kg.get_candidates(resolved["id"], top_n=10)["candidates"]
    drug = candidates[0]["drug_name"]

    install_provider(FakeProvider(_records_for(drug)))
    result = pipeline.run_pipeline(disease)

    assert result["evidence_audit_summary"]["method"] == "leave_one_independent_study_out"
    audited = [c for c in result["results"] if c.get("evidence_audit")]
    assert audited, "at least the evidence-bearing candidate should carry an audit"
    for c in audited:
        assert "status" in c["evidence_audit"]


# --------------------------------------------------------------------------- #
# Distinct abstention statuses
# --------------------------------------------------------------------------- #

def test_provider_failure_yields_provider_unavailable(install_provider):
    disease = _uncovered_disease_with_candidates()
    install_provider(FakeProvider(exc=lr.ProviderTimeout("timed out")))
    result = pipeline.run_pipeline(disease)

    assert result["status"] == "provider_unavailable"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_NONE
    assert result["results"] == []
    assert result["passages"] == []
    assert result["live_retrieval"]["error"]["kind"] == "timeout"
    assert "not evidence that no literature exists" in result["message"].lower()


def test_successful_but_irrelevant_retrieval_yields_no_relevant_evidence(install_provider):
    disease = _uncovered_disease_with_candidates()
    install_provider(FakeProvider([lr.LiveRecord(
        source_id="88888888", provider="europepmc", title="Unrelated paper",
        abstract="This abstract never names any candidate drug.",
        year=2024, url="https://pubmed.ncbi.nlm.nih.gov/88888888/",
        journal=None, pub_types=(), retrieved_at="2026-10-20T00:00:00+00:00",
    )]))
    result = pipeline.run_pipeline(disease)

    assert result["status"] == "no_relevant_evidence"
    assert result["results"] == []
    assert result["passages"] == []
    assert result["candidate_pool"], "graph candidates are still reported"


def test_provider_failure_and_no_results_are_distinguishable(install_provider):
    disease = _uncovered_disease_with_candidates()

    install_provider(FakeProvider(exc=lr.ProviderUnavailable("down")))
    failed = pipeline.run_pipeline(disease)

    install_provider(FakeProvider([]))
    empty = pipeline.run_pipeline(disease)

    assert failed["status"] == "provider_unavailable"
    assert empty["status"] == "no_relevant_evidence"
    assert failed["status"] != empty["status"]


def test_live_disabled_restores_the_phase_1_abstention(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "0")
    disease = _uncovered_disease_with_candidates()
    result = pipeline.run_pipeline(disease)

    assert result["status"] == "no_local_evidence"
    assert result["evidence_scope"] == coverage.EVIDENCE_SCOPE_NONE
    assert result["passages"] == [], "no unrelated evidence may be presented"
    assert result["results"] == []
    assert result["live_retrieval"]["status"] == lr.LIVE_STATUS_DISABLED


# --------------------------------------------------------------------------- #
# API integration and serialization
# --------------------------------------------------------------------------- #

def test_health_reports_live_retrieval_readiness():
    data = client.get("/api/health").json()
    assert "live_retrieval_enabled" in data
    assert data["live_retrieval_enabled"] is True
    # The provider name must be reported too: knowing live retrieval is on without
    # knowing which provider serves it is not enough to diagnose a result.
    assert data.get("live_retrieval_provider") == "europepmc"
    # No secrets or provider credentials may appear in health output.
    text = json.dumps(data).lower()
    for secret in ("api_key", "apikey", "token", "password", "secret"):
        assert secret not in text


def test_live_response_is_json_serializable(install_provider):
    disease = _uncovered_disease_with_candidates()
    resolved = kg.resolve_disease(disease)
    drug = kg.get_candidates(resolved["id"], top_n=10)["candidates"][0]["drug_name"]
    install_provider(FakeProvider(_records_for(drug)))

    result = pipeline.run_pipeline(disease)
    text = json.dumps(result)
    assert "NaN" not in text and "Infinity" not in text
    assert "live_retrieval" in text


def test_api_returns_live_status_without_tracebacks(install_provider):
    disease = _uncovered_disease_with_candidates()
    install_provider(FakeProvider(exc=lr.ProviderHTTPError("500")))
    resp = client.post("/api/query", json={"query": disease})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "provider_unavailable"
    assert "Traceback" not in resp.text
    # Internal exception text must not leak to API consumers.
    assert "Europe PMC server error" not in resp.text
