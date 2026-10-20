"""Phase 6 acceptance tests: RRF ranking and evaluation metrics.

Metric expectations are hand-computed from small known examples, so a bug in the
formulas cannot pass by agreeing with itself.

Run:  venv/bin/python -m pytest tests/test_ranking.py -v
"""
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import ranking


# --------------------------------------------------------------------------- #
# RRF: correctness on known examples
# --------------------------------------------------------------------------- #

def test_rrf_hand_computed_single_list():
    out = ranking.reciprocal_rank_fusion({"a": ["X", "Y"]}, k=60)
    assert out["order"] == ["X", "Y"]
    assert out["candidates"][0]["score"] == pytest.approx(1 / 61)
    assert out["candidates"][1]["score"] == pytest.approx(1 / 62)


def test_rrf_hand_computed_two_lists():
    out = ranking.reciprocal_rank_fusion({"a": ["X", "Y"], "b": ["Y", "X"]}, k=60)
    expected = 1 / 61 + 1 / 62
    for candidate in out["candidates"]:
        assert candidate["score"] == pytest.approx(expected)
    # Perfect tie: broken on identifier ascending, deterministically.
    assert out["order"] == ["X", "Y"]


def test_rrf_rewards_agreement_across_lists():
    agree = ranking.reciprocal_rank_fusion({"a": ["X", "Y"], "b": ["X", "Y"]}, k=60)
    assert agree["order"][0] == "X"
    assert agree["candidates"][0]["score"] == pytest.approx(2 / 61)


def test_rrf_k_parameter_changes_scores_but_not_necessarily_order():
    small = ranking.reciprocal_rank_fusion({"a": ["X", "Y"]}, k=1)
    large = ranking.reciprocal_rank_fusion({"a": ["X", "Y"]}, k=1000)
    assert small["candidates"][0]["score"] == pytest.approx(1 / 2)
    assert large["candidates"][0]["score"] == pytest.approx(1 / 1001)
    assert small["order"] == large["order"] == ["X", "Y"]


def test_rrf_negative_k_is_rejected():
    with pytest.raises(ValueError):
        ranking.reciprocal_rank_fusion({"a": ["X"]}, k=-1)


# --------------------------------------------------------------------------- #
# RRF: edge cases
# --------------------------------------------------------------------------- #

def test_rrf_handles_empty_input():
    out = ranking.reciprocal_rank_fusion({}, k=60)
    assert out["order"] == []
    assert out["candidates"] == []


def test_rrf_handles_empty_lists():
    out = ranking.reciprocal_rank_fusion({"a": [], "b": ["X"]}, k=60)
    assert out["order"] == ["X"]
    assert out["inputs"]["a"]["size"] == 0


def test_rrf_missing_candidate_gets_no_imputed_rank():
    out = ranking.reciprocal_rank_fusion({"a": ["X", "Y"], "b": ["Y"]}, k=60)
    detail = {c["candidate"]: c for c in out["candidates"]}
    assert "b" not in detail["X"]["ranks"], "a missing candidate must not receive a rank"
    assert "b" not in detail["X"]["contributions"]
    assert out["candidates_missing_from_some_list"] == 1


def test_rrf_duplicates_keep_the_best_rank_and_are_reported():
    out = ranking.reciprocal_rank_fusion({"a": ["X", "X", "Y"]}, k=60)
    detail = {c["candidate"]: c for c in out["candidates"]}
    assert detail["X"]["ranks"]["a"] == 1, "the duplicate must not overwrite the best rank"
    assert out["inputs"]["a"]["duplicates_removed"] == 1
    assert out["inputs"]["a"]["size"] == 2


def test_rrf_ignores_none_entries():
    out = ranking.reciprocal_rank_fusion({"a": [None, "X"]}, k=60)
    assert out["order"] == ["X"]


def test_rrf_weights_are_applied():
    out = ranking.reciprocal_rank_fusion(
        {"a": ["X"], "b": ["Y"]}, k=60, weights={"a": 2.0, "b": 1.0}
    )
    assert out["order"][0] == "X"
    assert out["candidates"][0]["score"] == pytest.approx(2 / 61)


def test_rrf_is_deterministic_across_runs():
    inputs = {"a": ["X", "Y", "Z"], "b": ["Z", "Y", "X"]}
    first = ranking.reciprocal_rank_fusion(inputs, k=60)
    second = ranking.reciprocal_rank_fusion(inputs, k=60)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_rrf_output_preserves_reproducible_provenance():
    out = ranking.reciprocal_rank_fusion({"a": ["X", "Y"], "b": ["Y"]}, k=60)
    assert out["k"] == 60
    assert out["method"] == ranking.RANKING_METHOD_RRF
    assert out["schema_version"] == ranking.RANKING_SCHEMA_VERSION
    detail = {c["candidate"]: c for c in out["candidates"]}
    # Every contribution must be re-derivable from the recorded rank.
    for candidate, info in detail.items():
        for name, position in info["ranks"].items():
            expected = out["weights"][name] / (out["k"] + position)
            assert info["contributions"][name] == pytest.approx(expected)


# --------------------------------------------------------------------------- #
# Metrics: hand-computed
# --------------------------------------------------------------------------- #

def test_precision_at_k():
    ranked = ["A", "B", "C", "D"]
    relevant = {"A", "C"}
    assert ranking.precision_at_k(ranked, relevant, 1) == pytest.approx(1.0)
    assert ranking.precision_at_k(ranked, relevant, 2) == pytest.approx(0.5)
    assert ranking.precision_at_k(ranked, relevant, 4) == pytest.approx(0.5)


def test_recall_at_k():
    ranked = ["A", "B", "C", "D"]
    relevant = {"A", "C"}
    assert ranking.recall_at_k(ranked, relevant, 1) == pytest.approx(0.5)
    assert ranking.recall_at_k(ranked, relevant, 3) == pytest.approx(1.0)


def test_precision_and_recall_are_zero_without_labels():
    ranked = ["A", "B"]
    assert ranking.precision_at_k(ranked, set(), 2) == 0.0
    assert ranking.recall_at_k(ranked, set(), 2) == 0.0


def test_reciprocal_rank():
    assert ranking.reciprocal_rank(["A", "B", "C"], {"A"}) == pytest.approx(1.0)
    assert ranking.reciprocal_rank(["A", "B", "C"], {"B"}) == pytest.approx(0.5)
    assert ranking.reciprocal_rank(["A", "B", "C"], {"C"}) == pytest.approx(1 / 3)
    assert ranking.reciprocal_rank(["A", "B"], {"Z"}) == 0.0


def test_ndcg_hand_computed():
    relevance = {"A": 1.0, "B": 0.0}
    # Perfect order: DCG = 1/log2(2) = 1.0, IDCG = 1.0
    assert ranking.ndcg_at_k(["A", "B"], relevance, 2) == pytest.approx(1.0)
    # Reversed: DCG = 1/log2(3) = 0.6309...
    expected = (1 / math.log2(3)) / 1.0
    assert ranking.ndcg_at_k(["B", "A"], relevance, 2) == pytest.approx(expected)


def test_ndcg_graded_relevance():
    relevance = {"A": 2.0, "B": 1.0}
    perfect = ranking.ndcg_at_k(["A", "B"], relevance, 2)
    assert perfect == pytest.approx(1.0)
    worse = ranking.ndcg_at_k(["B", "A"], relevance, 2)
    assert 0.0 < worse < 1.0


def test_ndcg_is_zero_when_nothing_is_relevant():
    """Dividing by an ideal DCG of zero must not fabricate a perfect score."""
    assert ranking.ndcg_at_k(["A", "B"], {}, 2) == 0.0
    assert ranking.ndcg_at_k(["A", "B"], {"Z": 0.0}, 2) == 0.0


def test_average_precision():
    # relevant at positions 1 and 3: (1/1 + 2/3) / 2
    assert ranking.average_precision(["A", "B", "C"], {"A", "C"}) == pytest.approx(
        (1.0 + 2 / 3) / 2
    )
    assert ranking.average_precision(["A", "B"], set()) == 0.0


def test_evaluate_ranking_reports_all_cutoffs():
    out = ranking.evaluate_ranking(["A", "B", "C"], {"A"}, ks=(1, 2))
    assert out["n_relevant"] == 1
    assert out["precision@1"] == pytest.approx(1.0)
    assert out["recall@2"] == pytest.approx(1.0)
    assert out["mrr"] == pytest.approx(1.0)
    assert "ndcg@1" not in out, "NDCG needs graded relevance and must not be invented"


def test_k_zero_and_empty_rankings_do_not_crash():
    assert ranking.precision_at_k([], {"A"}, 0) == 0.0
    assert ranking.recall_at_k([], {"A"}, 0) == 0.0
    assert ranking.ndcg_at_k([], {"A": 1}, 0) == 0.0


# --------------------------------------------------------------------------- #
# Diagnostics: never accuracy
# --------------------------------------------------------------------------- #

def test_rank_agreement_reports_identity_and_shift():
    out = ranking.rank_agreement(["A", "B", "C"], ["A", "B", "C"])
    assert out["same_top_1"] is True
    assert out["max_rank_shift"] == 0
    assert out["kendall_tau_common"] == pytest.approx(1.0)

    out2 = ranking.rank_agreement(["A", "B", "C"], ["C", "B", "A"])
    assert out2["same_top_1"] is False
    assert out2["kendall_tau_common"] == pytest.approx(-1.0)
    assert out2["max_rank_shift"] == 2


def test_rank_agreement_handles_disjoint_and_empty():
    out = ranking.rank_agreement(["A"], ["B"])
    assert out["n_common"] == 0
    assert out["jaccard"] == 0.0
    assert out["kendall_tau_common"] == 0.0
    assert out["only_in_a"] == ["A"] and out["only_in_b"] == ["B"]

    empty = ranking.rank_agreement([], [])
    assert empty["n_common"] == 0 and empty["jaccard"] == 0.0


def test_diagnostics_are_not_accuracy_metrics():
    """The diagnostics payload must not carry any metric that implies correctness."""
    result = {
        "status": "ok",
        "evidence_scope": "local_corpus",
        "results": [
            {"drug": "A", "evidence": {"score": 0.5},
             "evidence_summary": {"distinct_pmid_count": 2}},
            {"drug": "B", "evidence": {"score": 0.0},
             "evidence_summary": {"distinct_pmid_count": 0}},
        ],
    }
    diag = ranking.literature_diagnostics(result)
    assert diag["n_candidates"] == 2
    assert diag["n_candidates_with_evidence"] == 1
    assert diag["evidence_coverage"] == pytest.approx(0.5)
    assert diag["total_distinct_pmids"] == 2
    for forbidden in ("precision", "recall", "ndcg", "mrr", "accuracy"):
        assert forbidden not in json.dumps(diag).lower()


# --------------------------------------------------------------------------- #
# Building rankings from a real-shaped result
# --------------------------------------------------------------------------- #

def _sample_result():
    return {
        "status": "ok",
        "results": [
            {"rank": 1, "drug": "Alpha", "evidence": {"score": 0.10},
             "evidence_summary": {"graph_rank": 1}},
            {"rank": 2, "drug": "Beta", "evidence": {"score": 0.90},
             "evidence_summary": {"graph_rank": 2}},
            {"rank": 3, "drug": "Gamma", "evidence": {"score": 0.0},
             "evidence_summary": {"graph_rank": 3}},
        ],
    }


def test_graph_ranking_follows_graph_rank():
    assert ranking.graph_ranking(_sample_result()) == ["Alpha", "Beta", "Gamma"]


def test_literature_ranking_follows_evidence_score():
    assert ranking.literature_ranking(_sample_result()) == ["Beta", "Alpha", "Gamma"]


def test_literature_ranking_is_deterministic_under_ties():
    """Zero-evidence candidates must not appear in arbitrary arrival order."""
    result = {"results": [
        {"drug": "Zeta", "evidence": {"score": 0.0}, "evidence_summary": {}},
        {"drug": "Alpha", "evidence": {"score": 0.0}, "evidence_summary": {}},
    ]}
    assert ranking.literature_ranking(result) == ["Alpha", "Zeta"]


def test_both_rankings_cover_the_same_candidate_universe():
    """RRF must fuse comparable inputs, not one list that silently drops items."""
    result = _sample_result()
    inputs = ranking.build_rankings(result)
    graph = inputs[ranking.RANKING_METHOD_GRAPH]
    literature = inputs[ranking.RANKING_METHOD_LITERATURE]
    assert set(graph) == set(literature)
    assert len(graph) == 3


def test_rrf_fuses_graph_and_literature_on_identical_inputs():
    result = _sample_result()
    inputs = ranking.build_rankings(result)
    out = ranking.reciprocal_rank_fusion(inputs, k=60)

    # Alpha (graph 1, literature 2) and Beta (graph 2, literature 1) are an exact
    # tie under RRF: 1/(k+1) + 1/(k+2) either way. The tie breaks on the
    # identifier, so the ordering is still deterministic.
    assert out["candidates"][0]["score"] == pytest.approx(out["candidates"][1]["score"])
    assert out["order"][0] == "Alpha"
    assert set(out["order"]) == {"Alpha", "Beta", "Gamma"}
    detail = {c["candidate"]: c for c in out["candidates"]}
    assert detail["Beta"]["ranks"] == {
        ranking.RANKING_METHOD_GRAPH: 2,
        ranking.RANKING_METHOD_LITERATURE: 1,
    }


def test_rrf_reorders_when_the_evidence_signal_is_much_stronger():
    """A rank gap wide enough to overcome the graph order must change the top."""
    result = {"results": [
        {"drug": "Alpha", "evidence": {"score": 0.0}, "evidence_summary": {"graph_rank": 1}},
        {"drug": "Beta", "evidence": {"score": 0.9}, "evidence_summary": {"graph_rank": 2}},
        {"drug": "Gamma", "evidence": {"score": 0.5}, "evidence_summary": {"graph_rank": 3}},
    ]}
    inputs = ranking.build_rankings(result)
    # graph: Alpha, Beta, Gamma   literature: Beta, Gamma, Alpha
    assert inputs[ranking.RANKING_METHOD_GRAPH] == ["Alpha", "Beta", "Gamma"]
    assert inputs[ranking.RANKING_METHOD_LITERATURE] == ["Beta", "Gamma", "Alpha"]

    out = ranking.reciprocal_rank_fusion(inputs, k=60)
    # Beta   1/62 + 1/61 = 0.032522
    # Alpha  1/61 + 1/63 = 0.032266
    # Gamma  1/63 + 1/62 = 0.032002
    assert out["order"] == ["Beta", "Alpha", "Gamma"]
    assert out["order"] != inputs[ranking.RANKING_METHOD_GRAPH], (
        "this is the case RRF exists to handle: it must differ from the baseline"
    )


def test_rrf_does_not_replace_the_baseline():
    """The baseline order must remain available and unmodified."""
    result = _sample_result()
    inputs = ranking.build_rankings(result)
    baseline = list(inputs[ranking.RANKING_METHOD_GRAPH])
    ranking.reciprocal_rank_fusion(inputs, k=60)
    assert inputs[ranking.RANKING_METHOD_GRAPH] == baseline
    assert ranking.graph_ranking(result) == ["Alpha", "Beta", "Gamma"]
