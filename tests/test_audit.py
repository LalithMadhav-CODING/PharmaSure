"""Unit tests for Citation-Level Counterfactual Evidence Auditing (src/audit.py).

Fixtures are synthetic and deterministic so the expected values are derived from
the authoritative scorer rather than hard-coded, which keeps these tests valid if
the corpus changes.

Run:  venv/bin/python -m pytest tests/test_audit.py -v
"""
import copy
import json

import pytest

from src import audit, retrieval


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def passage(pmid, drug: str = "DrugA", text: str = "",
            pub_type: "str | None" = "clinical_trial",
            year: "int | None" = 2020, rid: float = 0.8, pid: int = 1, **extra):
    p = {
        "id": pid,
        "pmid": pmid,
        "drug": drug,
        "text": text,
        "pub_type": pub_type,
        "year": year,
        "retrieval_score": rid,
        "source": "pubmed",
        "disease": "Test disease",
    }
    p.update(extra)
    return p


DISEASE = {"id": "MONDO:0000001", "name": "Test disease"}


def three_study_set(drug="DrugA"):
    """Three passages, three distinct PMIDs, decreasing relevance."""
    return [
        passage("11111111", drug=drug, rid=0.9, pid=1, text="Treatment improved outcomes."),
        passage("22222222", drug=drug, rid=0.7, pid=2, text="No significant difference was observed."),
        passage("33333333", drug=drug, rid=0.5, pid=3, text="The drug was well tolerated.",
                pub_type="review"),
    ]


def peer_ctx(scores, kg_orders=None):
    kg_orders = kg_orders or {k: i for i, k in enumerate(scores)}
    ranks = audit.compute_evidence_ranks(
        [{"key": k, "score": v, "kg_order": kg_orders[k]} for k, v in scores.items()]
    )
    return scores, kg_orders, ranks


def run_audit(drug_passages, claims=None, scores=None, drug="DrugA"):
    scores = scores or {drug: 0.5, "Other": 0.4}
    scores = {**scores, drug: audit.score_passages(drug_passages, drug)["score"]}
    ps, ko, ranks = peer_ctx(scores)
    return audit.audit_candidate(
        drug_name=drug,
        disease=DISEASE,
        drug_passages=drug_passages,
        claims=claims,
        baseline_evidence={},
        candidate_key=drug,
        baseline_rank=ranks[drug],
        peer_scores=ps,
        peer_kg_order=ko,
    )


# =========================================================================== #
# 6.1 Study grouping
# =========================================================================== #

def test_same_pmid_passages_become_one_study_unit():
    passages = [
        passage("11111111", pid=1, rid=0.9),
        passage("11111111", pid=2, rid=0.8),
        passage("22222222", pid=3, rid=0.5),
    ]
    ledger = audit.build_evidence_ledger(passages, "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    assert len(groups) == 2, "two passages sharing a PMID must form one unit"
    big = next(g for g in groups if g["pmids"] == ["11111111"])
    assert big["record_count"] == 2
    assert sorted(big["passage_ids"]) == [1, 2]


def test_distinct_pmids_remain_separate_units():
    ledger = audit.build_evidence_ledger(three_study_set(), "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    assert len(groups) == 3


def test_cross_pmid_independence_is_reported_unknown_not_assumed():
    ledger = audit.build_evidence_ledger(three_study_set(), "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    # The corpus cannot establish that distinct PMIDs are independent studies.
    assert all(g["study_independence_status"] == audit.INDEPENDENCE_UNKNOWN for g in groups)
    assert all(g["study_grouping_method"] == audit.GROUPING_PMID_ONLY for g in groups)


def test_missing_pmid_is_not_treated_as_independent_study():
    passages = [
        passage(None, pid=1, rid=0.9),
        passage("", pid=2, rid=0.8),
        passage("22222222", pid=3, rid=0.5),
    ]
    ledger = audit.build_evidence_ledger(passages, "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    no_pmid = [g for g in groups if not g["has_valid_pmid"]]
    assert len(no_pmid) == 2, "each PMID-less record is its own fallback unit"
    assert all(g["study_grouping_method"] == audit.GROUPING_SOURCE_ID for g in no_pmid)

    result = run_audit(passages)
    assert any("no valid PMID" in w for w in result["warnings"])


def test_grouping_is_deterministic_regardless_of_input_order():
    passages = three_study_set()
    forward = audit.group_study_units(audit.build_evidence_ledger(passages, "DrugA", DISEASE))
    backward = audit.group_study_units(
        audit.build_evidence_ledger(list(reversed(passages)), "DrugA", DISEASE)
    )
    assert [g["study_group_id"] for g in forward] == [g["study_group_id"] for g in backward]


def test_duplicate_records_do_not_inflate_study_counts():
    dup = passage("11111111", pid=1, rid=0.9)
    ledger = audit.build_evidence_ledger([dup, copy.deepcopy(dup)], "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    assert len(groups) == 1
    assert groups[0]["record_count"] == 2


def test_review_unit_is_flagged_and_warned_about():
    passages = [
        passage("11111111", pid=1, pub_type="clinical_trial"),
        passage("22222222", pid=2, pub_type="review"),
    ]
    result = run_audit(passages)
    assert any("narrative review" in w for w in result["warnings"])


def test_every_record_is_reachable_through_a_group():
    ledger = audit.build_evidence_ledger(three_study_set(), "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    grouped = {r["source_id"] for g in groups for r in ledger if r["study_group_id"] == g["study_group_id"]}
    assert grouped == {r["source_id"] for r in ledger}
    assert all(r["study_group_id"] for r in ledger)


# =========================================================================== #
# 6.2 Evidence direction
# =========================================================================== #

@pytest.mark.parametrize("text,expected", [
    ("Treatment improved symptoms significantly.", "supportive"),
    ("No significant difference was found between groups.", "null_finding"),
    ("The drug was ineffective in this population.", "null_finding"),
    ("Symptoms were exacerbated by treatment.", "contradictory"),
    ("This sentence says nothing directional about outcomes.", "not_classified"),
    ("", "not_classified"),
])
def test_classify_direction_labels(text, expected):
    assert audit.classify_direction(text)["evidence_direction"] == expected


def test_classifier_only_returns_declared_labels():
    samples = [
        "improved", "no significant difference", "ineffective", "worsened",
        "adverse events were common", "random text", "",
    ]
    for s in samples:
        label = audit.classify_direction(s)["evidence_direction"]
        assert label in audit.DIRECTION_LABELS


def test_mentioning_the_drug_is_not_supportive():
    # The drug name alone, with no directional statement, must stay unclassified.
    result = audit.classify_direction("DrugA is a medication used in this setting.")
    assert result["evidence_direction"] == "not_classified"


def test_null_finding_is_distinct_from_contradictory():
    null = audit.classify_direction("There was no significant difference in mortality.")
    contra = audit.classify_direction("Outcomes were worsened by the intervention.")
    assert null["evidence_direction"] == "null_finding"
    assert contra["evidence_direction"] == "contradictory"
    assert null["evidence_direction"] != contra["evidence_direction"]


def test_safety_language_is_not_labelled_contradictory():
    text = "Therapy was associated with an increased risk of adverse events."
    direction = audit.classify_direction(text)["evidence_direction"]
    safety = audit.detect_safety_signal(text)
    assert direction != "contradictory", "a safety concern is not evidence against efficacy"
    assert safety["safety_signal"] is True
    assert safety["safety_snippet"]


def test_safety_signal_is_recorded_on_the_ledger_record():
    passages = [passage("11111111", text="Treatment caused hepatotoxicity in two patients.")]
    ledger = audit.build_evidence_ledger(passages, "DrugA", DISEASE)
    assert ledger[0]["safety_signal"] is True
    assert ledger[0]["safety_rule"] == "safety_toxicity"


def test_mixed_labels_within_one_unit_collapse_to_uncertain():
    members = [
        {"evidence_direction": "supportive"},
        {"evidence_direction": "null_finding"},
    ]
    assert audit._dominant_direction(members) == "uncertain"


def test_direction_counts_deduplicate_repeated_passages():
    # Two passages from ONE pmid: the unit counts once, not twice.
    passages = [
        passage("11111111", pid=1, text="Treatment improved outcomes."),
        passage("11111111", pid=2, text="Treatment improved outcomes."),
    ]
    ledger = audit.build_evidence_ledger(passages, "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    counts = audit.summarize_directions(groups)
    assert counts["eligible_study_units"] == 1
    assert counts["supportive"] == 1


def test_unclassified_records_are_counted_as_coverage_not_omitted():
    ledger = audit.build_evidence_ledger(three_study_set(), "DrugA", DISEASE)
    groups = audit.group_study_units(ledger)
    counts = audit.summarize_directions(groups)
    assert counts["eligible_study_units"] == 3
    assert counts["classified"] + counts["unclassified"] == 3


def test_direction_provenance_is_retained():
    ledger = audit.build_evidence_ledger(
        [passage("11111111", text="The drug was ineffective.")], "DrugA", DISEASE
    )
    rec = ledger[0]
    assert rec["direction_rule"] == "null_ineffective"
    assert rec["direction_snippet"]
    assert rec["direction_method"] == audit.DIRECTION_METHOD
    assert rec["direction_method_version"]


def test_no_conflict_is_not_claimed_when_most_sources_are_unclassified():
    # All three units are directionally unclassified, so there is nothing to
    # conflict — and the summary must say so rather than implying consistency.
    passages = [
        passage("11111111", pid=1, text="The drug is used in this setting."),
        passage("22222222", pid=2, text="A narrative overview of management."),
        passage("33333333", pid=3, text="Pharmacokinetic properties are described."),
    ]
    ledger = audit.build_evidence_ledger(passages, "DrugA", DISEASE)
    counts = audit.summarize_directions(audit.group_study_units(ledger))
    assert counts["conflicting_evidence_present"] is False
    assert counts["classified"] == 0
    assert counts["unclassified"] == 3
    assert "not evidence of consistency" in counts["caveat"]


# =========================================================================== #
# 6.3 Baseline scoring
# =========================================================================== #

def test_audit_score_uses_the_authoritative_scoring_function():
    passages = three_study_set()
    expected = retrieval.evidence_score(passages, "DrugA")
    got = audit.score_passages(passages, "DrugA")
    assert got["score"] == expected["score"]
    assert got["tier"] == expected["tier"]
    assert got["support"] == expected["support"]


def test_baseline_components_are_preserved():
    passages = three_study_set()
    got = audit.score_passages(passages, "DrugA")
    assert set(got["breakdown"]) >= {
        "relevance", "relevance_weight", "support", "support_weight",
        "study_quality", "study_quality_weight",
        "verification", "verification_role",
    }
    assert got["breakdown"]["relevance_weight"] == 0.35
    assert got["breakdown"]["support_weight"] == 0.35
    assert got["breakdown"]["study_quality_weight"] == 0.30
    # Verification multiplies the strength terms rather than adding to them.
    assert got["breakdown"]["verification_role"] == "multiplier"


def test_verification_gates_the_score():
    """A candidate whose quotations do not verify cannot outscore one that does.

    This is the property the multiplier exists to guarantee: no amount of
    favourable publication metadata can lift a candidate with zero verified
    quotations above a fully-verified one.
    """
    passages = three_study_set()

    unverified = audit.score_passages(passages, "DrugA", verified_claims=0, total_claims=2)
    verified = audit.score_passages(passages, "DrugA", verified_claims=2, total_claims=2)
    half = audit.score_passages(passages, "DrugA", verified_claims=1, total_claims=2)

    assert unverified["score"] == 0.0
    assert 0.0 < half["score"] < verified["score"]
    # Identical passages, so the only difference is verification.
    assert (unverified["breakdown"]["evidence_strength"]
            == verified["breakdown"]["evidence_strength"])


def test_empty_evidence_scores_zero_with_a_stable_shape():
    got = audit.score_passages([], "DrugA")
    assert got["score"] == 0.0
    assert got["tier"] == "Preliminary"
    # retrieval.evidence_score omits `breakdown` for empty input; the audit
    # normalises it so downstream consumers always see the same keys.
    assert got["breakdown"]["relevance"] == 0.0


def test_evidence_score_is_not_the_everycure_matrix_score():
    passages = three_study_set()
    result = run_audit(passages)
    assert result["baseline"]["evidence_score"] == audit.score_passages(passages, "DrugA")["score"]
    assert result["ranking_scope"] == "evidence_rank_over_retrieved_candidates"
    assert "distinct from the displayed knowledge-graph candidate rank" in result["note"]


def test_score_stays_within_unit_interval():
    for pub_type in ("clinical_trial", "cohort", "review", "case_report", "unknown"):
        got = audit.score_passages([passage("11111111", pub_type=pub_type)], "DrugA")
        assert 0.0 <= got["score"] <= 1.0


def test_study_type_mapping_is_unchanged():
    weights = {"clinical_trial": 1.0, "cohort": 0.7, "preclinical": 0.4, "review": 0.3}
    for pub_type, expected in weights.items():
        got = audit.score_passages([passage("11111111", pub_type=pub_type)], "DrugA")
        assert got["breakdown"]["study_quality"] == expected


def test_support_counts_passages_not_distinct_pmids():
    """DOCUMENTS A DIVERGENCE FROM THE BUILD SPEC.

    The spec states the support component `P` is PMID-deduplicated. The live
    implementation in retrieval.evidence_score counts PASSAGES:

        support = min(len(drug_passages), 5) / 5.0

    The audit reuses that function rather than silently changing the baseline, so
    two passages from one PMID yield support 0.4, not 0.2. This test pins the real
    behaviour; see docs/EVIDENCE_AUDIT.md ("Divergence from the specification").
    """
    two_same_pmid = [
        passage("11111111", pid=1, rid=0.9),
        passage("11111111", pid=2, rid=0.9),
    ]
    got = audit.score_passages(two_same_pmid, "DrugA")
    assert got["support"] == 2
    assert got["breakdown"]["support"] == pytest.approx(0.4)


# =========================================================================== #
# 6.4 Leave-one-study-out
# =========================================================================== #

def test_single_study_unit_yields_insufficient_status():
    result = run_audit([passage("11111111")])
    assert result["status"] == audit.AUDIT_STATUS_INSUFFICIENT
    assert result["reason"] == "only_one_study_unit"
    assert result["counterfactuals"] == []
    assert any("cannot be assessed" in w for w in result["warnings"])


def test_zero_eligible_studies_yields_not_auditable():
    result = run_audit([])
    assert result["status"] == audit.AUDIT_STATUS_NOT_AUDITABLE
    assert result["reason"] == "no_source_records_retrieved"


def test_two_or_more_units_produce_one_scenario_each():
    passages = three_study_set()
    result = run_audit(passages)
    assert result["status"] == audit.AUDIT_STATUS_COMPLETE
    assert len(result["counterfactuals"]) == 3
    assert result["stability"]["successful_counterfactuals"] == 3


def test_removing_a_unit_removes_all_of_its_passages():
    passages = [
        passage("11111111", pid=1, rid=0.9),
        passage("11111111", pid=2, rid=0.9),
        passage("22222222", pid=3, rid=0.5),
    ]
    result = run_audit(passages)
    cf = next(c for c in result["counterfactuals"] if c["pmids"] == ["11111111"])
    assert cf["removed_passage_count"] == 2

    remaining = [p for p in passages if p["pmid"] != "11111111"]
    assert cf["counterfactual_score"] == audit.score_passages(remaining, "DrugA")["score"]


def test_score_delta_sign_convention():
    passages = three_study_set()
    result = run_audit(passages)
    baseline = result["baseline"]["evidence_score"]
    for cf in result["counterfactuals"]:
        # Positive delta => removing the study LOWERED the score.
        assert cf["score_delta"] == pytest.approx(baseline - cf["counterfactual_score"])


def test_rank_delta_sign_convention():
    passages = three_study_set()
    result = run_audit(passages)
    baseline_rank = result["baseline"]["evidence_rank"]
    for cf in result["counterfactuals"]:
        # Positive delta => the candidate moved DOWN the ranking.
        assert cf["rank_delta"] == cf["counterfactual_rank"] - baseline_rank


def test_most_influential_study_is_identified():
    passages = [
        passage("11111111", pid=1, rid=0.99, pub_type="clinical_trial"),
        passage("22222222", pid=2, rid=0.10, pub_type="review"),
        passage("33333333", pid=3, rid=0.10, pub_type="review"),
    ]
    result = run_audit(passages)
    top = result["stability"]["source_with_max_score_influence"]
    assert top["pmids"] == ["11111111"]


def test_removing_a_zero_effect_study_yields_zero_delta_not_an_error():
    """A removal with genuinely no effect must give exactly 0, not an error.

    Support saturates at ``min(count, 5) / 5``, so with six identical passages
    removing one still leaves five and the support component is unchanged; the
    mean relevance and best study type are also unchanged. The delta must be 0.
    """
    passages = [
        passage(f"{i:08d}", pid=i, rid=0.8, pub_type="clinical_trial")
        for i in range(1, 7)
    ]
    result = run_audit(passages)
    assert len(result["counterfactuals"]) == 6
    for cf in result["counterfactuals"]:
        assert cf["status"] == "ok"
        assert cf["score_delta"] == pytest.approx(0.0, abs=1e-9)


def test_support_component_saturates_so_large_sets_are_less_removal_sensitive():
    """Documents the count-based support behaviour of the live scorer."""
    six = [passage(f"{i:08d}", pid=i, rid=0.8) for i in range(1, 7)]
    three = [passage(f"{i:08d}", pid=i, rid=0.8) for i in range(1, 4)]
    assert audit.score_passages(six, "DrugA")["breakdown"]["support"] == 1.0
    assert audit.score_passages(three, "DrugA")["breakdown"]["support"] == pytest.approx(0.6)


def test_counterfactuals_do_not_mutate_the_baseline_or_input():
    passages = three_study_set()
    snapshot = copy.deepcopy(passages)
    result = run_audit(passages)
    assert passages == snapshot, "input evidence must not be mutated"
    assert result["baseline"]["evidence_score"] == audit.score_passages(snapshot, "DrugA")["score"]


def test_input_order_does_not_change_results():
    passages = three_study_set()
    a = run_audit(passages)
    b = run_audit(list(reversed(passages)))
    assert a["baseline"]["evidence_score"] == b["baseline"]["evidence_score"]
    assert ([c["score_delta"] for c in a["counterfactuals"]]
            == [c["score_delta"] for c in b["counterfactuals"]])


def test_repeated_calculation_is_identical():
    passages = three_study_set()
    first = run_audit(passages)
    second = run_audit(passages)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_rank_recalculation_uses_the_same_candidate_set():
    passages = three_study_set()
    scores = {"DrugA": audit.score_passages(passages, "DrugA")["score"],
              "Other": 0.4, "Third": 0.6}
    ps, ko, ranks = peer_ctx(scores)
    result = audit.audit_candidate(
        drug_name="DrugA", disease=DISEASE, drug_passages=passages, claims=None,
        baseline_evidence={}, candidate_key="DrugA",
        baseline_rank=ranks["DrugA"], peer_scores=ps, peer_kg_order=ko,
    )
    for cf in result["counterfactuals"]:
        expected = audit.compute_evidence_ranks([
            {"key": k, "score": (cf["counterfactual_score"] if k == "DrugA" else v),
             "kg_order": ko[k]} for k, v in ps.items()
        ])["DrugA"]
        assert cf["counterfactual_rank"] == expected


def test_ties_are_broken_deterministically():
    entries = [
        {"key": "b", "score": 0.5, "kg_order": 1},
        {"key": "a", "score": 0.5, "kg_order": 0},
        {"key": "c", "score": 0.5, "kg_order": 2},
    ]
    ranks = audit.compute_evidence_ranks(entries)
    assert ranks == {"a": 1, "b": 2, "c": 3}
    assert audit.compute_evidence_ranks(list(reversed(entries))) == ranks


def test_a_failed_scenario_does_not_erase_successful_ones(monkeypatch):
    passages = three_study_set()
    real = audit.score_passages

    def flaky(p, drug, **kwargs):
        # Fail only the scenario that removes pmid 22222222 (leaving pids 1 and 3).
        if sorted(x["id"] for x in p) == [1, 3]:
            raise RuntimeError("boom")
        return real(p, drug, **kwargs)

    monkeypatch.setattr(audit, "score_passages", flaky)
    result = run_audit(passages)
    ok = [c for c in result["counterfactuals"] if c["status"] == "ok"]
    failed = [c for c in result["counterfactuals"] if c["status"] == "error"]
    assert len(ok) == 2 and len(failed) == 1
    assert result["status"] == audit.AUDIT_STATUS_PARTIAL
    assert any("counterfactual failed" in w for w in result["warnings"])
    # The successful scenarios keep their numbers.
    assert all(c["score_delta"] is not None for c in ok)


def test_audit_never_calls_the_llm_or_embeddings(monkeypatch):
    import src.llm as llm_mod
    import src.embeddings as emb_mod

    def explode(*a, **k):
        raise AssertionError("the audit must not call the model or embedder")

    monkeypatch.setattr(llm_mod, "generate_answer", explode)
    monkeypatch.setattr(emb_mod, "embed_texts", explode)
    monkeypatch.setattr(emb_mod, "embed_query", explode)

    result = run_audit(three_study_set())
    assert result["status"] == audit.AUDIT_STATUS_COMPLETE


def test_displayed_kg_rank_is_one_based_and_separate_from_evidence_rank():
    passages = three_study_set()
    scores = {"DrugA": audit.score_passages(passages, "DrugA")["score"], "Other": 0.99}
    ps, ko, ranks = peer_ctx(scores)
    result = audit.audit_candidate(
        drug_name="DrugA", disease=DISEASE, drug_passages=passages, claims=None,
        baseline_evidence={}, candidate_key="DrugA",
        baseline_rank=ranks["DrugA"], peer_scores=ps, peer_kg_order=ko,
    )
    assert result["baseline"]["displayed_kg_rank"] == ko["DrugA"] + 1
    # DrugA scores lower than Other, so its evidence rank is 2 while the
    # knowledge-graph rank is 1 — the two must not be conflated.
    assert result["baseline"]["evidence_rank"] == 2
    assert result["baseline"]["displayed_kg_rank"] == 1


# =========================================================================== #
# 6.5 Aggregate metrics
# =========================================================================== #

def test_aggregate_metrics_are_mathematically_correct():
    passages = [
        passage("11111111", pid=1, rid=0.9, pub_type="clinical_trial"),
        passage("22222222", pid=2, rid=0.6, pub_type="review"),
        passage("33333333", pid=3, rid=0.3, pub_type="review"),
    ]
    result = run_audit(passages)
    deltas = [abs(c["score_delta"]) for c in result["counterfactuals"]]
    st = result["stability"]
    # Reported metrics are rounded to 6dp, so compare within that tolerance.
    assert st["max_absolute_score_change"] == pytest.approx(max(deltas), abs=1e-6)
    assert st["mean_absolute_score_change"] == pytest.approx(sum(deltas) / len(deltas), abs=1e-6)
    assert st["median_absolute_score_change"] == pytest.approx(sorted(deltas)[1], abs=1e-6)


def test_rank_range_reflects_observed_counterfactual_ranks():
    passages = three_study_set()
    result = run_audit(passages)
    ranks = [c["counterfactual_rank"] for c in result["counterfactuals"]]
    st = result["stability"]
    assert st["rank_min"] == min(ranks)
    assert st["rank_max"] == max(ranks)
    assert st["rank_range"] == max(ranks) - min(ranks)


def test_metrics_are_null_rather_than_zero_when_insufficient():
    st = audit.summarize_counterfactuals(
        [], baseline_score=0.0, baseline_rank=1, eligible_study_count=1
    )
    assert st["max_absolute_score_change"] is None
    assert st["mean_absolute_score_change"] is None
    assert st["median_absolute_score_change"] is None
    assert st["status"] == audit.AUDIT_STATUS_INSUFFICIENT


def test_success_and_failure_counts_are_reported():
    st = audit.summarize_counterfactuals(
        [{"status": "ok", "score_delta": 0.1, "rank_delta": 1, "counterfactual_rank": 2,
          "study_group_id": "g1", "pmids": ["1"]},
         {"status": "error", "score_delta": None, "rank_delta": None,
          "counterfactual_rank": None, "study_group_id": "g2", "pmids": ["2"]}],
        baseline_score=0.5, baseline_rank=1, eligible_study_count=2,
    )
    assert st["successful_counterfactuals"] == 1
    assert st["failed_counterfactuals"] == 1
    assert st["status"] == audit.AUDIT_STATUS_PARTIAL


def test_absolute_metrics_are_never_negative():
    result = run_audit(three_study_set())
    st = result["stability"]
    assert st["max_absolute_score_change"] >= 0
    assert st["mean_absolute_score_change"] >= 0
    assert st["median_absolute_score_change"] >= 0
    assert st["max_rank_movement"] >= 0


def test_serialization_is_stable():
    result = run_audit(three_study_set())
    a = json.dumps(result, sort_keys=True)
    b = json.dumps(run_audit(three_study_set()), sort_keys=True)
    assert a == b


# =========================================================================== #
# attach_audits — pipeline integration
# =========================================================================== #

def _results_and_passages():
    passages = [
        passage("11111111", drug="DrugA", pid=1, rid=0.9),
        passage("22222222", drug="DrugA", pid=2, rid=0.7),
        passage("33333333", drug="DrugB", pid=3, rid=0.6),
    ]
    results = [
        {"rank": 1, "drug": "DrugA", "evidence": audit.score_passages(passages[:2], "DrugA"),
         "claims": [], "reason": "", "direction": "Uncertain"},
        {"rank": 2, "drug": "DrugB", "evidence": audit.score_passages(passages[2:], "DrugB"),
         "claims": [], "reason": "", "direction": "Uncertain"},
    ]
    return results, passages


def test_attach_audits_adds_audit_without_removing_existing_keys():
    results, passages = _results_and_passages()
    summary = audit.attach_audits(results, passages, DISEASE)
    assert summary["audited"] == 2
    for r in results:
        assert "evidence_audit" in r
        # Existing contract preserved.
        assert {"rank", "drug", "evidence", "claims", "reason", "direction"} <= set(r)


def test_attach_audits_does_not_alter_baseline_scores():
    results, passages = _results_and_passages()
    before = [r["evidence"]["score"] for r in results]
    audit.attach_audits(results, passages, DISEASE)
    assert [r["evidence"]["score"] for r in results] == before


def test_attach_audits_marks_disabled_state_explicitly():
    results, passages = _results_and_passages()
    summary = audit.attach_audits(results, passages, DISEASE, enabled=False)
    assert summary["audited"] == 0
    assert all(r["evidence_audit"]["status"] == audit.AUDIT_STATUS_NOT_AUDITABLE
               for r in results)


def test_a_candidate_without_passages_still_appears_and_is_not_auditable():
    results, passages = _results_and_passages()
    results.append({"rank": 3, "drug": "DrugZ", "evidence": {"score": 0.0, "tier": "Preliminary"},
                    "claims": [], "reason": "", "direction": "Uncertain"})
    audit.attach_audits(results, passages, DISEASE)
    assert results[-1]["drug"] == "DrugZ"
    assert results[-1]["evidence_audit"]["status"] == audit.AUDIT_STATUS_NOT_AUDITABLE


def test_audit_candidate_returns_error_status_instead_of_raising(monkeypatch):
    def explode(*a, **k):
        raise ValueError("induced failure")

    monkeypatch.setattr(audit, "build_evidence_ledger", explode)
    result = run_audit(three_study_set())
    assert result["status"] == audit.AUDIT_STATUS_ERROR
    assert any("Audit failed" in w for w in result["warnings"])


# =========================================================================== #
# Helpers
# =========================================================================== #

def test_pmid_validation_guards_url_construction():
    assert audit.normalize_pmid("12345678") == "12345678"
    assert audit.normalize_pmid(12345678) == "12345678"
    assert audit.normalize_pmid("abc") is None
    assert audit.normalize_pmid("") is None
    assert audit.normalize_pmid(None) is None
    assert audit.normalize_pmid("12; DROP") is None

    assert audit.pubmed_url("12345678") == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert audit.pubmed_url("nope") is None


def test_ledger_records_carry_provenance_and_verification():
    claims = [{"text": "t", "citation_ids": [1], "quote": "Treatment improved outcomes.",
               "verification_status": "verified"}]
    ledger = audit.build_evidence_ledger(three_study_set(), "DrugA", DISEASE, claims)
    rec = ledger[0]
    assert rec["quote"] == "Treatment improved outcomes."
    assert rec["citation_verified"] == "verified"
    assert rec["pubmed_url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")
    assert rec["included_in_score"] is True
    assert rec["source_id"]


def test_missing_metadata_produces_warnings_not_fabrication():
    ledger = audit.build_evidence_ledger(
        [passage("11111111", year=None, pub_type=None)], "DrugA", DISEASE
    )
    warnings = ledger[0]["metadata_warnings"]
    assert "missing_publication_year" in warnings
    assert "missing_publication_type" in warnings
    assert ledger[0]["publication_year"] is None
