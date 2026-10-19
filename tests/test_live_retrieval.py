"""Phase 5 acceptance tests: bounded live literature retrieval.

Every test uses a fake provider or a fake HTTP client. No test requires network
access, so the suite is deterministic and can run offline.

Run:  venv/bin/python -m pytest tests/test_live_retrieval.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.pipeline as pipeline
from src import coverage, kg, live_retrieval as lr
from src.verify import verify_citations


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

def make_record(pmid=None, title="A study", abstract="Some abstract text.",
                year=2024, pub_types=("Journal Article",)):
    return lr.LiveRecord(
        source_id=pmid, provider="europepmc", title=title, abstract=abstract,
        year=year, url=(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
        journal="J Test", pub_types=pub_types,
        retrieved_at="2026-10-20T00:00:00+00:00", provider_rank=0,
    )


class FakeProvider:
    name = "europepmc"

    def __init__(self, records=None, exc=None):
        self._records = records or []
        self._exc = exc
        self.calls = []

    def search(self, query, limit, timeout_s):
        self.calls.append({"query": query, "limit": limit, "timeout_s": timeout_s})
        if self._exc:
            raise self._exc
        return list(self._records)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


class FakeClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def get(self, url, params=None, timeout=None, headers=None):
        if self._exc:
            raise self._exc
        return self._response


class FakeTimeout(Exception):
    pass


FakeTimeout.__name__ = "ReadTimeout"


# --------------------------------------------------------------------------- #
# Provider responses
# --------------------------------------------------------------------------- #

def test_valid_provider_response_is_parsed():
    payload = {
        "resultList": {"result": [{
            "pmid": "40978128", "title": "A real title",
            "abstractText": "<h4>Background</h4> We studied it.",
            "pubYear": "2025", "journalTitle": "Nature",
            "pubTypeList": {"pubType": ["Journal Article", "Review"]},
        }]}
    }
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(200, payload)))
    records = provider.search("q", 10, 5.0)

    assert len(records) == 1
    r = records[0]
    assert r.source_id == "40978128"
    assert r.title == "A real title"
    # Provider markup must be stripped, or quotation verification breaks.
    assert "<h4>" not in r.abstract
    assert "Background" in r.abstract
    assert r.year == 2025
    assert r.url == "https://pubmed.ncbi.nlm.nih.gov/40978128/"
    assert r.study_type == "review"


def test_empty_result_is_not_an_error():
    provider = lr.EuropePMCProvider(
        client=FakeClient(FakeResponse(200, {"resultList": {"result": []}}))
    )
    assert provider.search("q", 10, 5.0) == []


def test_timeout_raises_provider_timeout():
    provider = lr.EuropePMCProvider(client=FakeClient(exc=FakeTimeout("timed out")))
    with pytest.raises(lr.ProviderTimeout):
        provider.search("q", 10, 5.0)


def test_connection_failure_raises_unavailable():
    provider = lr.EuropePMCProvider(client=FakeClient(exc=OSError("no route to host")))
    with pytest.raises(lr.ProviderUnavailable):
        provider.search("q", 10, 5.0)


@pytest.mark.parametrize("status,expected", [
    (429, lr.ProviderRateLimited),
    (500, lr.ProviderHTTPError),
    (503, lr.ProviderHTTPError),
    (400, lr.ProviderHTTPError),
])
def test_http_errors_map_to_distinct_exceptions(status, expected):
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(status, {})))
    with pytest.raises(expected):
        provider.search("q", 10, 5.0)


@pytest.mark.parametrize("payload", [
    None, [], "a string", {"resultList": "wrong"}, {"resultList": {"result": "wrong"}},
])
def test_malformed_payloads_raise_malformed(payload):
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(200, payload)))
    with pytest.raises(lr.ProviderMalformed):
        provider.search("q", 10, 5.0)


def test_non_json_body_raises_malformed():
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(200, raise_json=True)))
    with pytest.raises(lr.ProviderMalformed):
        provider.search("q", 10, 5.0)


def test_malformed_pmid_is_not_presented_as_real():
    payload = {"resultList": {"result": [
        {"pmid": "not-a-pmid", "title": "T", "abstractText": "A"}
    ]}}
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(200, payload)))
    records = provider.search("q", 10, 5.0)
    assert records[0].source_id is None, "a malformed identifier must not be passed off as real"


def test_record_with_no_usable_text_is_dropped():
    payload = {"resultList": {"result": [{"pmid": "1", "title": "", "abstractText": ""}]}}
    provider = lr.EuropePMCProvider(client=FakeClient(FakeResponse(200, payload)))
    assert provider.search("q", 10, 5.0) == []


# --------------------------------------------------------------------------- #
# Deduplication and identifiers
# --------------------------------------------------------------------------- #

def test_duplicate_pmids_are_one_study_unit():
    records = [
        make_record("111", "First"),
        make_record("111", "Same source again"),
        make_record("222", "Second"),
    ]
    deduped, unidentified = lr.deduplicate(records)
    assert len(deduped) == 2
    assert unidentified == 0


def test_records_without_identifier_are_counted_not_hidden():
    records = [make_record("111", "Has id"), make_record(None, "No id")]
    deduped, unidentified = lr.deduplicate(records)
    assert len(deduped) == 2
    assert unidentified == 1, "unidentifiable records must be reported, not silently merged"


def test_missing_identifier_is_reported_as_a_limitation():
    out = lr.retrieve_for_disease(
        "Test disease", ["Doxepin"],
        provider=FakeProvider([make_record(None, "Doxepin study")]),
        cache=lr.TTLCache(),
    )
    assert out.records_without_identifier == 1
    assert any("no stable identifier" in l for l in out.limitations)


# --------------------------------------------------------------------------- #
# Candidate-specific relevance — the evidence boundary
# --------------------------------------------------------------------------- #

def test_disease_only_paper_is_not_evidence_for_a_candidate():
    """A paper that never names the drug must not become candidate evidence."""
    out = lr.retrieve_for_disease(
        "Test disease", ["Doxepin"],
        provider=FakeProvider([make_record("111", "Unrelated cardiology paper",
                                           "Nothing about the drug here.")]),
        cache=lr.TTLCache(),
    )
    assert out.status == lr.LIVE_STATUS_NO_RELEVANT
    assert out.passages_by_drug == {}


def test_candidate_mention_binds_evidence_to_that_candidate_only():
    out = lr.retrieve_for_disease(
        "Test disease", ["Doxepin", "Triamcinolone"],
        provider=FakeProvider([
            make_record("111", "Doxepin trial", "We gave Doxepin to patients."),
            make_record("222", "Triamcinolone trial", "We gave Triamcinolone."),
        ]),
        cache=lr.TTLCache(),
    )
    assert set(out.passages_by_drug) == {"Doxepin", "Triamcinolone"}
    for drug, passages in out.passages_by_drug.items():
        for p in passages:
            assert lr.record_mentions_drug(
                make_record(p["pmid"], p["title"], p["text"]), drug
            )


def test_drug_matching_uses_word_boundaries():
    """A substring match would let 'aspirin' match 'aspirinase'."""
    rec = make_record("1", "Aspirinase enzyme", "The aspirinase pathway.")
    assert lr.record_mentions_drug(rec, "Aspirin") is False
    rec2 = make_record("2", "Aspirin therapy", "Aspirin reduced risk.")
    assert lr.record_mentions_drug(rec2, "Aspirin") is True


def test_no_candidates_means_no_candidate_evidence():
    out = lr.retrieve_for_disease(
        "Test disease", [],
        provider=FakeProvider([make_record("111", "Some paper", "Text.")]),
        cache=lr.TTLCache(),
    )
    assert out.status == lr.LIVE_STATUS_NO_RELEVANT
    assert any("No candidate drugs" in l for l in out.limitations)


# --------------------------------------------------------------------------- #
# Failure vs genuine no-results
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("exc,kind", [
    (lr.ProviderTimeout("t"), "timeout"),
    (lr.ProviderRateLimited("r"), "rate_limited"),
    (lr.ProviderHTTPError("h"), "http_error"),
    (lr.ProviderMalformed("m"), "malformed_response"),
    (lr.ProviderUnavailable("c"), "connection_error"),
])
def test_provider_failure_is_never_reported_as_no_results(exc, kind):
    failed = lr.retrieve_for_disease("D", ["Drug"], provider=FakeProvider(exc=exc),
                                     cache=lr.TTLCache())
    empty = lr.retrieve_for_disease("D", ["Drug"], provider=FakeProvider([]),
                                    cache=lr.TTLCache())

    assert failed.status == lr.LIVE_STATUS_FAILED
    assert failed.error is not None and failed.error["kind"] == kind
    assert empty.status == lr.LIVE_STATUS_NO_RESULTS
    assert failed.status != empty.status, "an outage must not read as a negative finding"


def test_unexpected_adapter_error_is_still_a_failure():
    out = lr.retrieve_for_disease("D", ["Drug"], provider=FakeProvider(exc=KeyError("boom")),
                                  cache=lr.TTLCache())
    assert out.status == lr.LIVE_STATUS_FAILED
    assert out.error is not None and out.error["kind"] == "unexpected_error"


def test_failure_message_does_not_claim_literature_does_not_exist():
    out = lr.retrieve_for_disease("D", ["Drug"], provider=FakeProvider(exc=lr.ProviderTimeout("t")),
                                  cache=lr.TTLCache())
    joined = " ".join(out.limitations).lower()
    assert "not evidence that no literature exists" in joined


# --------------------------------------------------------------------------- #
# TTL cache
# --------------------------------------------------------------------------- #

def test_cache_hit_and_expiry_without_sleeping():
    clock = [1000.0]
    cache = lr.TTLCache(ttl_s=60, clock=lambda: clock[0])
    provider = FakeProvider([make_record("111", "Doxepin", "Doxepin text")])

    first = lr.retrieve_for_disease("D", ["Doxepin"], provider=provider, cache=cache)
    second = lr.retrieve_for_disease("D", ["Doxepin"], provider=provider, cache=cache)
    assert first.from_cache is False
    assert second.from_cache is True
    assert len(provider.calls) == 1, "a cache hit must not hit the provider"

    clock[0] += 61
    third = lr.retrieve_for_disease("D", ["Doxepin"], provider=provider, cache=cache)
    assert third.from_cache is False, "an expired entry must be re-fetched"
    assert len(provider.calls) == 2


def test_cache_serves_a_copy_not_the_stored_object():
    """Mutating a returned outcome must not corrupt the cached entry."""
    cache = lr.TTLCache(ttl_s=60)
    provider = FakeProvider([make_record("111", "Doxepin", "Doxepin text")])
    first = lr.retrieve_for_disease("D", ["Doxepin"], provider=provider, cache=cache)
    first.status = "corrupted"
    first.limitations.append("injected")
    second = lr.retrieve_for_disease("D", ["Doxepin"], provider=provider, cache=cache)
    assert second.status == lr.LIVE_STATUS_OK
    assert "injected" not in second.limitations


def test_cache_keys_are_isolated_by_query_and_provider():
    k_a = lr.TTLCache.make_key("europepmc", "disease a", 25)
    k_b = lr.TTLCache.make_key("europepmc", "disease b", 25)
    k_c = lr.TTLCache.make_key("pubmed", "disease a", 25)
    k_d = lr.TTLCache.make_key("europepmc", "disease a", 50)
    assert len({k_a, k_b, k_c, k_d}) == 4


def test_cache_key_is_not_substring_matched():
    """'asthma' must not be answered from an 'asthma and copd overlap' entry."""
    cache = lr.TTLCache(ttl_s=60)
    provider = FakeProvider([make_record("111", "Doxepin", "Doxepin text")])
    lr.retrieve_for_disease("asthma", ["Doxepin"], provider=provider, cache=cache)
    out = lr.retrieve_for_disease("asthma and copd overlap syndrome", ["Doxepin"],
                                  provider=provider, cache=cache)
    assert out.from_cache is False
    assert len(provider.calls) == 2


def test_cross_disease_isolation_end_to_end():
    cache = lr.TTLCache(ttl_s=60)
    provider = FakeProvider([make_record("111", "Doxepin", "Doxepin text")])
    a = lr.retrieve_for_disease("Disease one", ["Doxepin"], provider=provider, cache=cache)
    b = lr.retrieve_for_disease("Disease two", ["Doxepin"], provider=provider, cache=cache)
    assert a.query != b.query
    assert not (a.from_cache and b.from_cache)


def test_provider_failures_are_never_cached():
    cache = lr.TTLCache(ttl_s=60)
    provider = FakeProvider(exc=lr.ProviderTimeout("t"))
    lr.retrieve_for_disease("D", ["Drug"], provider=provider, cache=cache)
    assert len(cache) == 0, "a cached failure could be replayed as a success"

    good = FakeProvider([make_record("111", "Drug", "Drug text")])
    out = lr.retrieve_for_disease("D", ["Drug"], provider=good, cache=cache)
    assert out.status == lr.LIVE_STATUS_OK


def test_cache_is_bounded():
    cache = lr.TTLCache(ttl_s=60, max_entries=3)
    for i in range(6):
        cache.set(lr.TTLCache.make_key("p", f"q{i}", 10), i)
    assert len(cache) <= 3


def test_cache_key_includes_schema_version():
    key = lr.TTLCache.make_key("europepmc", "d", 25)
    assert key[0] == lr.LIVE_SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Bounds and configuration
# --------------------------------------------------------------------------- #

def test_results_are_bounded_by_a_hard_cap():
    provider = FakeProvider([])
    lr.retrieve_for_disease("D", ["Drug"], provider=provider, limit=100000,
                            cache=lr.TTLCache())
    assert provider.calls[0]["limit"] <= lr.HARD_MAX_RESULTS


def test_timeout_is_passed_to_the_provider():
    provider = FakeProvider([])
    lr.retrieve_for_disease("D", ["Drug"], provider=provider, timeout_s=3.5,
                            cache=lr.TTLCache())
    assert provider.calls[0]["timeout_s"] == 3.5


def test_configuration_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "0")
    assert lr.live_retrieval_enabled() is False
    monkeypatch.setenv("PHARMASURE_LIVE_RETRIEVAL", "1")
    assert lr.live_retrieval_enabled() is True
    monkeypatch.setenv("PHARMASURE_LIVE_MAX_RESULTS", "7")
    assert lr.configured_max_results() == 7
    monkeypatch.setenv("PHARMASURE_LIVE_MAX_RESULTS", "99999")
    assert lr.configured_max_results() == lr.HARD_MAX_RESULTS


def test_unknown_provider_is_rejected():
    with pytest.raises(lr.ProviderError):
        lr.get_provider("not-a-provider")


def test_query_is_bounded_and_includes_synonyms():
    q = lr.build_query("Alzheimer disease", ["AD", "Alzheimer's", "third", "fourth"])
    assert "Alzheimer disease" in q
    assert "AD" in q
    # At most two synonyms, to keep the query bounded.
    assert "third" not in q


# --------------------------------------------------------------------------- #
# Quote verification against live text
# --------------------------------------------------------------------------- #

def test_quote_present_in_live_record_verifies():
    passage = lr._record_to_passage(
        make_record("111", "Doxepin in disease X",
                    "We gave Doxepin to twelve patients and observed improvement."),
        "Disease X", "Doxepin", 0, 1,
    )
    answer = {"candidates": [{"drug_name": "Doxepin", "claims": [{
        "text": "Doxepin improved outcomes",
        "quote": "We gave Doxepin to twelve patients and observed improvement.",
        "citation_ids": ["1"],
    }]}]}
    result = verify_citations(answer, {"1": passage})
    claim = result["candidates"][0]["claims"][0]
    assert claim["verification_status"] == "verified"


def test_fabricated_quote_against_live_record_fails():
    passage = lr._record_to_passage(
        make_record("111", "Doxepin in disease X", "We gave Doxepin to twelve patients."),
        "Disease X", "Doxepin", 0, 1,
    )
    answer = {"candidates": [{"drug_name": "Doxepin", "claims": [{
        "text": "Doxepin cured everyone",
        "quote": "Doxepin cured one hundred percent of patients permanently.",
        "citation_ids": ["1"],
    }]}]}
    result = verify_citations(answer, {"1": passage})
    claim = result["candidates"][0]["claims"][0]
    assert claim["verification_status"] == "needs_review"


def test_live_passages_are_marked_as_live():
    out = lr.retrieve_for_disease(
        "Disease X", ["Doxepin"],
        provider=FakeProvider([make_record("111", "Doxepin study", "Doxepin text")]),
        cache=lr.TTLCache(),
    )
    passage = out.passages_by_drug["Doxepin"][0]
    assert passage["source_mode"] == "live_retrieval"
    assert passage["provider"] == "europepmc"
    assert passage["retrieved_at"]


def test_live_summary_omits_full_abstracts():
    out = lr.retrieve_for_disease(
        "Disease X", ["Doxepin"],
        provider=FakeProvider([make_record("111", "Doxepin", "Doxepin " + "x" * 4000)]),
        cache=lr.TTLCache(),
    )
    assert "xxxx" not in json.dumps(out.summary())
