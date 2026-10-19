#!/usr/bin/env python
"""Reproducible evaluation of the citation-level counterfactual evidence audit.

Reports only measurements actually produced by this run. Sample size is stated
explicitly so results are not over-read.

Usage:
    venv/bin/python scripts/evaluate_audit.py            # uses the demo cache
    venv/bin/python scripts/evaluate_audit.py --live     # runs the full pipeline
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import audit  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEMO_QUERIES = ["Alzheimer disease", "Parkinson disease", "Multiple myeloma",
                "Type 2 diabetes", "Asthma"]


def load_cached():
    path = os.path.join(DATA, "demo_cache.json")
    if not os.path.exists(path):
        sys.exit("demo cache missing; run the pipeline first or pass --live")
    with open(path) as fh:
        return json.load(fh)


def run_live():
    from dotenv import load_dotenv
    load_dotenv()
    from src import pipeline
    out = {}
    for q in DEMO_QUERIES:
        print(f"  running live pipeline: {q} ...")
        out[q.lower()] = pipeline.run_pipeline(q)
    return out


def distribution(values):
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": round(min(values), 6),
        "p50": round(statistics.median(values), 6),
        "mean": round(statistics.fmean(values), 6),
        "max": round(max(values), 6),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="run the full pipeline instead of using the demo cache")
    args = ap.parse_args()

    corpus = run_live() if args.live else load_cached()

    t_start = time.time()

    n_queries = len(corpus)
    n_candidates = 0
    n_audited = 0
    n_multi_unit = 0
    n_one_unit = 0
    n_no_evidence = 0
    n_independence_unverified = 0
    n_with_classified_direction = 0
    n_with_conflict = 0
    n_with_null_or_contradictory = 0
    n_rank_changed = 0
    n_single_source_dominated = 0
    n_failed = 0
    n_partial = 0
    n_complete = 0

    score_deltas = []
    rank_movements = []
    units_per_candidate = []

    for key, result in corpus.items():
        for cand in result.get("results", []):
            n_candidates += 1
            a = cand.get("evidence_audit") or {}
            status = a.get("status")

            if status == "audit_failed":
                n_failed += 1
                continue
            if status == "partial":
                n_partial += 1
            if status == "complete":
                n_complete += 1

            counts = a.get("study_counts") or {}
            units = counts.get("study_units") or counts.get("eligible_independent_studies") or 0
            units_per_candidate.append(units)

            if units == 0:
                n_no_evidence += 1
                continue
            n_audited += 1
            if counts.get("study_independence_verified") is False:
                n_independence_unverified += 1
            if units >= 2:
                n_multi_unit += 1
            elif units == 1:
                n_one_unit += 1

            if (counts.get("classified") or 0) > 0:
                n_with_classified_direction += 1
            if counts.get("conflicting_evidence_present"):
                n_with_conflict += 1
            if (counts.get("contradictory") or 0) + (counts.get("null_finding") or 0) > 0:
                n_with_null_or_contradictory += 1

            stability = a.get("stability") or {}
            if stability.get("single_source_dominated"):
                n_single_source_dominated += 1

            for cf in a.get("counterfactuals", []):
                if cf.get("status") != "ok":
                    continue
                score_deltas.append(abs(float(cf["score_delta"])))
                rank_movements.append(abs(int(cf.get("rank_delta") or 0)))
                if abs(int(cf.get("rank_delta") or 0)) > 0:
                    n_rank_changed += 1

    elapsed = time.time() - t_start

    pct = lambda x, n: f"{(100.0 * x / n):.1f}%" if n else "n/a"  # noqa: E731

    print()
    print("=" * 72)
    print("CITATION-LEVEL COUNTERFACTUAL EVIDENCE AUDIT — EVALUATION")
    print("=" * 72)
    print(f"source                 : {'live pipeline' if args.live else 'demo cache'}")
    print(f"queries                : {n_queries}  ({', '.join(corpus.keys())})")
    print(f"candidates             : {n_candidates}")
    print()
    print("-- Audit coverage " + "-" * 54)
    print(f"candidates with >=1 study unit   : {n_audited} ({pct(n_audited, n_candidates)})")
    print(f"candidates with >=2 study units  : {n_multi_unit} ({pct(n_multi_unit, n_candidates)})")
    print(f"candidates with exactly 1 unit   : {n_one_unit}")
    print(f"candidates with no source records: {n_no_evidence}")
    print(f"audit status complete            : {n_complete}")
    print(f"audit status partial             : {n_partial}")
    print(f"audit status failed              : {n_failed}")
    print()
    print("-- Honesty / provenance " + "-" * 48)
    print(f"study independence reported unknown : {n_independence_unverified} ({pct(n_independence_unverified, max(n_audited,1))} of audited)")
    print(f"candidates with >=1 classified direction : {n_with_classified_direction} ({pct(n_with_classified_direction, max(n_audited,1))})")
    print(f"candidates with null/contradictory units : {n_with_null_or_contradictory}")
    print(f"candidates with conflicting directions   : {n_with_conflict}")
    print()
    print("-- Counterfactual sensitivity " + "-" * 43)
    print(f"total leave-one-out scenarios    : {len(score_deltas)}")
    print(f"candidates whose rank moved      : {n_rank_changed} ({pct(n_rank_changed, max(n_audited,1))})")
    print(f"single-source dominated (rule)   : {n_single_source_dominated} ({pct(n_single_source_dominated, max(n_audited,1))})")
    print(f"study units per candidate        : {distribution(units_per_candidate)}")
    print(f"|score delta| distribution       : {distribution(score_deltas)}")
    print(f"|rank movement| distribution     : {distribution(rank_movements)}")
    print()
    print("-- Cost " + "-" * 63)
    print(f"audit wall time for this run     : {elapsed:.3f}s")
    print(f"per candidate                    : {(1000*elapsed/max(n_candidates,1)):.2f}ms")
    print()
    print("LIMITATIONS OF THIS SAMPLE")
    print("  * Direction labels are unvalidated lexical heuristics; coverage is")
    print("    partial and no precision/recall is claimed.")
    print("  * Cross-PMID study independence is unverified (no linkage metadata).")
    print("  * Support counts passages, not distinct PMIDs (see docs/EVIDENCE_AUDIT.md).")
    print("  * Stability is a sensitivity result, NOT clinical validity.")
    print("=" * 72)


if __name__ == "__main__":
    main()
