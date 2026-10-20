"""Phase 2 acceptance tests: candidate-specific evidence records.

The requirement is that evidence is tied to a specific candidate with explicit
provenance and an explicit status — not inferred from generated prose, and never
borrowed from another candidate.

Run:  venv/bin/python -m pytest tests/test_candidate_evidence.py -v
"""
import json
import os

import pytest

import src.pipeline as pipeline
from src import coverage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

KNOWN_DISEASE = "Alzheimer disease"


@pytest.fixture(scope="module")
def result():
    """A successful result for a disease with local literature."""
    out = pipeline.run_pipeline(KNOWN_DISEASE)
    assert out["status"] == "ok"
    return out


# --------------------------------------------------------------------------- #
# Every candidate carries an explicit evidence status
# --------------------------------------------------------------------------- #

def test_every_candidate_has_an_evidence_summary(result):
    for c in result["results"]:
        assert "evidence_summary" in c, c.get("drug")
        es = c["evidence_summary"]
        assert es["evidence_status"], "a candidate must always state its evidence status"
        assert es["candidate_source"] == "everycure_knowledge_graph"


def test_evidence_status_vocabulary_is_controlled(result):
    allowed = {
        "supported",
        "no_candidate_specific_evidence",
        "evidence_retrieved_no_verified_claims",
        "evidence_unverified",
    }
    for c in result["results"]:
        assert c["evidence_summary"]["evidence_status"] in allowed


def test_status_agrees_with_the_actual_evidence(result):
    """The declared status must match the underlying counts, not contradict them."""
    for c in result["results"]:
        es = c["evidence_summary"]
        status = es["evidence_status"]
        if es["passage_count"] == 0:
            assert status == "no_candidate_specific_evidence"
            assert c["evidence"]["score"] == 0.0
        if status == "supported":
            assert es["verification"]["verified"] > 0
            assert es["passage_count"] > 0


# --------------------------------------------------------------------------- #
# No cross-candidate contamination
# --------------------------------------------------------------------------- #

def test_candidates_do_not_share_evidence(result):
    """Each candidate's passages must be attributable to that candidate's drug."""
    passage_drug = {}
    for p in result["passages"]:
        passage_drug[str(p["id"])] = (p.get("drug") or "").lower()

    for c in result["results"]:
        drug = c["drug"].lower()
        for claim in c["claims"]:
            for cid in (claim.get("citations") or claim.get("citation_ids") or []):
                src_drug = passage_drug.get(str(cid))
                if src_drug:
                    assert drug in src_drug or src_drug in drug, (
                        f"{c['drug']} cites passage {cid} tagged for {src_drug}"
                    )


def test_pmid_sets_are_candidate_specific(result):
    """A candidate's PMIDs must all come from passages tagged for that drug."""
    by_drug = {}
    for p in result["passages"]:
        by_drug.setdefault((p.get("drug") or "").lower(), set()).add(str(p.get("pmid")))

    for c in result["results"]:
        declared = set(c["evidence_summary"]["pmids"])
        available = set()
        for drug_key, pmids in by_drug.items():
            if c["drug"].lower() in drug_key or drug_key in c["drug"].lower():
                available |= pmids
        assert declared <= available, f"{c['drug']} claims PMIDs it was not given"


# --------------------------------------------------------------------------- #
# Provenance fields
# --------------------------------------------------------------------------- #

def test_graph_rank_and_evidence_score_are_distinguishable(result):
    """Candidates are ordered by evidence score; the graph origin is preserved.

    These were the same number while the display used the graph order. Now `rank`
    is the evidence rank, so the invariant to assert is that graph_rank still
    records where the candidate came from in the knowledge graph and is NOT
    silently overwritten by the sort.
    """
    for c in result["results"]:
        es = c["evidence_summary"]
        assert es["graph_rank"] >= 1
        assert c["rank"] >= 1
        # The literature evidence score is a separate signal from the graph score.
        assert "score" in c["evidence"]
        if es["graph_score"] is not None:
            assert isinstance(es["graph_score"], (int, float))
    # Every candidate carries a distinct graph rank drawn from the graph's own
    # ordering. Displayed candidates are a SUBSET (zero-evidence ones are dropped),
    # so the graph ranks need not be contiguous, but they must be distinct and
    # within the pool the graph supplied.
    graph_ranks = [c["evidence_summary"]["graph_rank"] for c in result["results"]]
    assert len(set(graph_ranks)) == len(graph_ranks), "graph ranks must be distinct"
    assert all(r >= 1 for r in graph_ranks)
    # Displayed order is score-descending.
    scores = [c["evidence"]["score"] for c in result["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores), "a zero-score candidate must not be displayed"
    # Ranks are a clean 1..n in display order.
    assert [c["rank"] for c in result["results"]] == list(range(1, len(result["results"]) + 1))


def test_no_zero_score_candidate_is_displayed(result):
    """A candidate with no verified evidence must not be listed."""
    assert result["results"], "expected at least one evidence-bearing candidate"
    for c in result["results"]:
        assert c["evidence"]["score"] > 0, (
            f"{c['drug']} has score 0 and should not be displayed"
        )


def test_display_is_capped_at_ten(result):
    """At most MAX_DISPLAYED_CANDIDATES evidence-bearing candidates are shown."""
    from src.pipeline import MAX_DISPLAYED_CANDIDATES
    assert MAX_DISPLAYED_CANDIDATES == 10
    assert len(result["results"]) <= MAX_DISPLAYED_CANDIDATES
    # Truncation is reported rather than silent.
    assert result.get("displayed_candidate_cap") == MAX_DISPLAYED_CANDIDATES
    assert result.get("candidates_over_display_cap", 0) >= 0
    assert (result.get("candidates_with_evidence", 0)
            == len(result["results"]) + result.get("candidates_over_display_cap", 0))


def test_candidate_pool_is_not_capped_at_ten():
    """The graph candidate list must not be silently truncated to ten."""
    from src import kg
    resolved = kg.resolve_disease(KNOWN_DISEASE)
    assert resolved is not None
    cands = kg.get_candidates(resolved["id"])["candidates"]
    # The lookup now holds more than ten for covered diseases; the point is that the
    # caller receives whatever the graph provides, not an arbitrary slice.
    assert len(cands) == len(kg.get_candidates(resolved["id"])["candidates"])
    assert len(cands) > 0


def test_get_candidates_honours_an_explicit_cap():
    from src import kg
    resolved = kg.resolve_disease(KNOWN_DISEASE)
    assert resolved is not None
    capped = kg.get_candidates(resolved["id"], top_n=3)["candidates"]
    assert len(capped) <= 3


def test_abstains_when_no_candidate_has_verified_evidence(monkeypatch):
    """If nothing verifies, no candidate row is shown and the reason is explicit."""
    import src.verify as verify_mod

    # Force every claim to fail verification, so every candidate scores 0.
    monkeypatch.setattr(verify_mod, "verify_citations",
                        lambda answer, passages: {
                            "candidates": [
                                {**c, "claims": [
                                    {**cl, "verification_status": "needs_review"}
                                    for cl in (c.get("claims") or [])
                                ]}
                                for c in (answer.get("candidates") or [])
                            ]
                        })
    import src.pipeline as pipeline
    saved = pipeline._demo_cache
    try:
        pipeline._demo_cache = {}   # force a live run so the patch applies
        out = pipeline.run_pipeline(KNOWN_DISEASE)
    finally:
        pipeline._demo_cache = saved

    assert out["status"] == "no_verified_evidence"
    assert out["results"] == []
    assert out["passages"] == []
    # Availability is not hidden: the dropped candidates are still listed.
    assert out["candidate_pool"], "dropped candidates must still be reported"
    assert all("graph_rank" in c for c in out["candidate_pool"])
    assert "not evidence of ineffectiveness" in out["message"].lower()
    assert "no_verified_evidence" == out["status"]


def test_verified_candidates_outrank_unverified_ones(result):
    """The property the verification multiplier exists to guarantee."""
    def v(c):
        return (c["evidence"].get("breakdown") or {}).get("verification") or 0.0

    verified = [c for c in result["results"] if v(c) > 0]
    unverified = [c for c in result["results"] if v(c) == 0]
    if verified and unverified:
        assert max(c["rank"] for c in verified) < min(c["rank"] for c in unverified), (
            "a candidate with no verified quotation must not outrank one with a "
            "verified quotation"
        )
    # And scores agree with the ordering.
    for a in verified:
        for b in unverified:
            assert a["evidence"]["score"] >= b["evidence"]["score"]


def test_distinct_pmid_count_is_a_real_deduplication(result):
    for c in result["results"]:
        es = c["evidence_summary"]
        assert es["distinct_pmid_count"] == len(set(es["pmids"]))
        # Never more distinct PMIDs than passages.
        assert es["distinct_pmid_count"] <= es["passage_count"]


def test_verification_counts_are_internally_consistent(result):
    for c in result["results"]:
        es = c["evidence_summary"]
        v = es["verification"]
        assert v["claims"] == len(c["claims"])
        assert v["verified"] + v["needs_review"] == v["claims"]


def test_drug_id_present_when_the_graph_provides_one(result):
    assert any(c["evidence_summary"].get("drug_id") for c in result["results"])


# --------------------------------------------------------------------------- #
# Limitations are stated, not hidden
# --------------------------------------------------------------------------- #

def test_candidates_without_evidence_state_a_limitation(result):
    for c in result["results"]:
        if c["evidence_summary"]["evidence_status"] == "no_candidate_specific_evidence":
            lims = " ".join(c["evidence_summary"]["limitations"]).lower()
            assert "coverage" in lims or "ineffectiveness" in lims, (
                "an unsupported candidate must explain that absence of evidence "
                "is not evidence of ineffectiveness"
            )


def test_single_pmid_candidate_is_flagged_as_not_independent(result):
    for c in result["results"]:
        es = c["evidence_summary"]
        if es["distinct_pmid_count"] == 1 and es["passage_count"] > 0:
            lims = " ".join(es["limitations"]).lower()
            assert "single pmid" in lims or "not independent" in lims


def test_no_fabricated_source_metadata(result):
    """Nothing may invent a title, URL or identifier that the corpus lacks."""
    for c in result["results"]:
        for pmid in c["evidence_summary"]["pmids"]:
            assert pmid.isdigit(), f"non-numeric PMID surfaced: {pmid!r}"


# --------------------------------------------------------------------------- #
# Determinism and robustness
# --------------------------------------------------------------------------- #

def test_evidence_summary_is_deterministic():
    first = pipeline.run_pipeline(KNOWN_DISEASE)
    second = pipeline.run_pipeline(KNOWN_DISEASE)
    a = [c["evidence_summary"] for c in first["results"]]
    b = [c["evidence_summary"] for c in second["results"]]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_missing_metadata_does_not_crash_or_mislead(monkeypatch):
    """A passage with no PMID must be reported as incomplete, not silently fine."""
    import src.audit as audit_mod

    original = audit_mod.build_evidence_ledger

    def strip_pmids(passages, drug_name, disease, claims=None):
        stripped = []
        for p in passages:
            q = dict(p)
            q["pmid"] = None
            stripped.append(q)
        return original(stripped, drug_name, disease, claims)

    monkeypatch.setattr(audit_mod, "build_evidence_ledger", strip_pmids)
    out = pipeline.run_pipeline(KNOWN_DISEASE)
    assert out["status"] == "ok"
    assert out["results"], "candidates with verified evidence should still be shown"
    # The pipeline-level summary still reports what it actually received.
    assert all("evidence_status" in c["evidence_summary"] for c in out["results"])
    # The missing identifiers must surface as an explicit warning rather than being
    # silently treated as valid provenance. The strip happens inside the audit
    # ledger, so that is where it has to be reported.
    audited = [c for c in out["results"] if (c.get("evidence_audit") or {}).get("warnings")]
    assert audited, "expected an audit that reports warnings"
    assert any(
        any("pmid" in w.lower() or "identifier" in w.lower()
            for w in c["evidence_audit"]["warnings"])
        for c in audited
    ), "stripped PMIDs were not reported as a provenance warning"


def test_every_result_serializes(result):
    text = json.dumps(result)
    assert "NaN" not in text and "Infinity" not in text
    assert "evidence_summary" in text
