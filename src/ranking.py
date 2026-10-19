"""Phase 6: ranking alternatives (Reciprocal Rank Fusion) and evaluation metrics.

Design rules enforced here
--------------------------
1.  The existing ranking is preserved as the baseline. RRF is an *alternative*
    that must be compared against it, never a silent replacement.
2.  Every function is pure and deterministic: identical inputs produce identical
    orderings, including under ties (ties break on the candidate identifier).
3.  Graph rank and literature evidence score are separate signals with different
    semantics. They are fused only by rank position, never by adding a score to a
    probability.
4.  Nothing here is a probability of efficacy. These are ordering signals.
5.  Metrics are computed only from supplied labels. When no labels exist, the
    caller gets diagnostics, not accuracy numbers.

RRF reference: Cormack, Clarke & Buettcher (2009), "Reciprocal Rank Fusion
outperforms Condorcet and individual rank learning methods". The standard
smoothing constant k=60 is used as the default.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

#: Default RRF smoothing constant. The paper's value; larger k flattens the
#: contribution of top ranks, smaller k sharpens it.
DEFAULT_RRF_K = 60

RANKING_METHOD_GRAPH = "graph_rank"
RANKING_METHOD_LITERATURE = "literature_evidence_rank"
RANKING_METHOD_RRF = "reciprocal_rank_fusion"

#: Bumped when ranking semantics change, so a benchmark run can be tied to the
#: exact method that produced it.
RANKING_SCHEMA_VERSION = "2026-10-ranking-v1"


# --------------------------------------------------------------------------- #
# Reciprocal Rank Fusion
# --------------------------------------------------------------------------- #

def reciprocal_rank_fusion(
    rankings: dict,
    k: int = DEFAULT_RRF_K,
    weights: Optional[dict] = None,
) -> dict:
    """Fuse several ranked lists by Reciprocal Rank Fusion.

    ``rankings`` maps a name to a list of candidate identifiers ordered best
    first. Each candidate's score is::

        RRF(c) = sum_over_lists ( weight[list] / (k + rank_in_list(c)) )

    with rank counted from 1.

    Handled deterministically and explicitly:

    * a candidate missing from a list simply receives no contribution from it
      (no imputed rank, no penalty);
    * a candidate appearing more than once in one list keeps its best (lowest)
      rank, and the duplicate is reported in ``inputs``;
    * an empty list contributes nothing;
    * ties in the fused score break on the candidate identifier, so the output
      ordering is stable across runs.

    Returns a dict carrying the fused order plus enough provenance to reproduce
    it: the parameter, the weights, each candidate's per-list rank and per-list
    contribution, and per-input diagnostics.
    """
    if k < 0:
        raise ValueError("RRF k must be non-negative")

    weights = dict(weights or {})
    for name in rankings:
        weights.setdefault(name, 1.0)

    scores: dict = {}
    ranks: dict = {}
    contributions: dict = {}
    inputs: dict = {}

    for name, ranked in rankings.items():
        seen: dict = {}
        duplicates = 0
        for position, candidate in enumerate(ranked or [], start=1):
            if candidate is None:
                continue
            key = str(candidate)
            if key in seen:
                duplicates += 1
                continue
            seen[key] = position

        weight = float(weights.get(name, 1.0))
        inputs[name] = {
            "size": len(seen),
            "duplicates_removed": duplicates,
            "weight": weight,
        }

        for key, position in seen.items():
            contribution = weight / (k + position)
            scores[key] = scores.get(key, 0.0) + contribution
            ranks.setdefault(key, {})[name] = position
            contributions.setdefault(key, {})[name] = contribution

    # Deterministic ordering: score descending, then identifier ascending.
    ordered = sorted(scores.keys(), key=lambda c: (-scores[c], c))

    missing_ranks = sum(
        1 for c in ordered if len(ranks.get(c, {})) < len(inputs)
    )

    return {
        "method": RANKING_METHOD_RRF,
        "schema_version": RANKING_SCHEMA_VERSION,
        "k": k,
        "weights": weights,
        "candidates": [
            {
                "candidate": c,
                "score": scores[c],
                "ranks": dict(ranks.get(c, {})),
                "contributions": dict(contributions.get(c, {})),
            }
            for c in ordered
        ],
        "order": ordered,
        "inputs": inputs,
        "candidates_missing_from_some_list": missing_ranks,
    }


def rrf_order(rankings: dict, k: int = DEFAULT_RRF_K,
              weights: Optional[dict] = None) -> list:
    """Convenience: just the fused identifier order."""
    return reciprocal_rank_fusion(rankings, k=k, weights=weights)["order"]


# --------------------------------------------------------------------------- #
# Building the input rankings from a pipeline result
# --------------------------------------------------------------------------- #

def graph_ranking(result: dict) -> list:
    """The knowledge-graph candidate order — the existing default baseline.

    Taken from the graph's own rank, which is what the product already returns.
    """
    entries = []
    for i, candidate in enumerate(result.get("results") or []):
        summary = candidate.get("evidence_summary") or {}
        rank = summary.get("graph_rank") or candidate.get("rank") or (i + 1)
        drug = candidate.get("drug") or summary.get("drug_name")
        if drug:
            entries.append((int(rank), str(drug)))
    entries.sort(key=lambda t: (t[0], t[1]))
    return [drug for _, drug in entries]


def literature_ranking(result: dict) -> list:
    """Candidates ordered by literature evidence score, best first.

    Tie-breaks on the drug name so the ordering is deterministic. Candidates with
    no evidence all share score 0.0 and are therefore ordered alphabetically
    rather than in arbitrary arrival order.
    """
    entries = []
    for candidate in result.get("results") or []:
        drug = candidate.get("drug")
        if not drug:
            continue
        score = float((candidate.get("evidence") or {}).get("score") or 0.0)
        entries.append((-score, str(drug)))
    entries.sort()
    return [drug for _, drug in entries]


def build_rankings(result: dict) -> dict:
    """The two input rankings RRF fuses, with their provenance named."""
    return {
        RANKING_METHOD_GRAPH: graph_ranking(result),
        RANKING_METHOD_LITERATURE: literature_ranking(result),
    }


def rank_positions(order: Iterable) -> dict:
    """Map identifier -> 1-based position."""
    return {str(c): i + 1 for i, c in enumerate(order)}


# --------------------------------------------------------------------------- #
# Metrics — only meaningful when labels are supplied
# --------------------------------------------------------------------------- #

def precision_at_k(ranked: list, relevant: set, k: int) -> float:
    """Fraction of the top-k that are relevant. 0.0 if k <= 0."""
    if k <= 0:
        return 0.0
    top = [str(c) for c in ranked[:k]]
    if not top:
        return 0.0
    return sum(1 for c in top if c in relevant) / len(top)


def recall_at_k(ranked: list, relevant: set, k: int) -> float:
    """Fraction of all relevant items found in the top-k.

    Returns 0.0 when there are no relevant items: recall is undefined without a
    denominator, and reporting 1.0 would be a fabricated perfect score.
    """
    if not relevant or k <= 0:
        return 0.0
    top = {str(c) for c in ranked[:k]}
    return len(top & relevant) / len(relevant)


def reciprocal_rank(ranked: list, relevant: set) -> float:
    """1 / position of the first relevant item. 0.0 if none is found."""
    for i, candidate in enumerate(ranked, start=1):
        if str(candidate) in relevant:
            return 1.0 / i
    return 0.0


def dcg_at_k(gains: list, k: int) -> float:
    """Discounted cumulative gain with the standard log2(i+1) discount."""
    total = 0.0
    for i, gain in enumerate(gains[:k], start=1):
        total += float(gain) / math.log2(i + 1)
    return total


def ndcg_at_k(ranked: list, relevance: dict, k: int) -> float:
    """Normalised DCG. ``relevance`` maps identifier -> gain (e.g. 0/1 or graded).

    Returns 0.0 when the ideal DCG is 0 (no relevant items), rather than
    fabricating a perfect score by dividing zero by zero.
    """
    if k <= 0:
        return 0.0
    gains = [float(relevance.get(str(c), 0.0)) for c in ranked[:k]]
    ideal = sorted((float(g) for g in relevance.values()), reverse=True)[:k]
    idcg = dcg_at_k(ideal, k)
    if idcg <= 0:
        return 0.0
    return dcg_at_k(gains, k) / idcg


def average_precision(ranked: list, relevant: set) -> float:
    """Mean of precision@i over the positions of relevant items."""
    if not relevant:
        return 0.0
    hits = 0
    total = 0.0
    for i, candidate in enumerate(ranked, start=1):
        if str(candidate) in relevant:
            hits += 1
            total += hits / i
    return total / len(relevant)


def evaluate_ranking(ranked: list, relevant: Iterable, ks=(1, 3, 5, 10),
                     relevance: Optional[dict] = None) -> dict:
    """Compute metrics for one ranking against one labelled query.

    ``relevant`` must be a real labelled set. Passing an empty set yields zeros,
    which the caller must present as "no labels", not as "no accuracy".
    """
    rel = {str(c) for c in relevant}
    out = {
        "n_ranked": len(ranked),
        "n_relevant": len(rel),
        "mrr": reciprocal_rank(ranked, rel),
        "average_precision": average_precision(ranked, rel),
    }
    for k in ks:
        out[f"precision@{k}"] = precision_at_k(ranked, rel, k)
        out[f"recall@{k}"] = recall_at_k(ranked, rel, k)
    if relevance:
        graded = {str(c): float(g) for c, g in relevance.items()}
        for k in ks:
            out[f"ndcg@{k}"] = ndcg_at_k(ranked, graded, k)
    return out


# --------------------------------------------------------------------------- #
# Unlabelled diagnostics — never presented as accuracy
# --------------------------------------------------------------------------- #

def rank_agreement(order_a: list, order_b: list) -> dict:
    """How two orderings relate, without any notion of correctness.

    These are diagnostics only. A high overlap does NOT mean either ranking is
    more accurate; it means they agree. Rank stability is not evidence of
    efficacy.
    """
    a, b = [str(c) for c in order_a], [str(c) for c in order_b]
    set_a, set_b = set(a), set(b)
    common = set_a & set_b
    union = set_a | set_b

    pos_a, pos_b = rank_positions(a), rank_positions(b)
    shifted = {c: pos_b[c] - pos_a[c] for c in common}

    return {
        "n_a": len(a),
        "n_b": len(b),
        "n_common": len(common),
        "jaccard": (len(common) / len(union)) if union else 0.0,
        "same_top_1": bool(a and b and a[0] == b[0]),
        "kendall_tau_common": _kendall_tau(a, b, common),
        "max_rank_shift": max(shifted.values()) if shifted else 0,
        "mean_abs_rank_shift": (
            sum(abs(v) for v in shifted.values()) / len(shifted) if shifted else 0.0
        ),
        "only_in_a": sorted(set_a - set_b),
        "only_in_b": sorted(set_b - set_a),
    }


def _kendall_tau(order_a: list, order_b: list, common: set) -> float:
    """Kendall tau-b over the items common to both orderings."""
    items = sorted(common)
    if len(items) < 2:
        return 0.0
    pos_a, pos_b = rank_positions(order_a), rank_positions(order_b)
    concordant = discordant = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            x, y = items[i], items[j]
            da = pos_a[x] - pos_a[y]
            db = pos_b[x] - pos_b[y]
            if da * db > 0:
                concordant += 1
            elif da * db < 0:
                discordant += 1
    pairs = concordant + discordant
    return (concordant - discordant) / pairs if pairs else 0.0


def literature_diagnostics(result: dict) -> dict:
    """Evidence-coverage diagnostics for a single query result.

    These describe the evidence, not the ranking's correctness.
    """
    results = result.get("results") or []
    with_evidence = [c for c in results if ((c.get("evidence") or {}).get("score") or 0) > 0]
    distinct = [int((c.get("evidence_summary") or {}).get("distinct_pmid_count") or 0)
                for c in results]
    return {
        "n_candidates": len(results),
        "n_candidates_with_evidence": len(with_evidence),
        "evidence_coverage": (len(with_evidence) / len(results)) if results else 0.0,
        "total_distinct_pmids": sum(distinct),
        "max_distinct_pmids_for_one_candidate": max(distinct) if distinct else 0,
        "evidence_scope": result.get("evidence_scope"),
        "audit_status": (result.get("evidence_audit_summary") or {}).get("status"),
    }
