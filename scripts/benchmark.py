#!/usr/bin/env python
"""Phase 6: reproducible ranking benchmark.

Compares the existing graph-rank baseline with Reciprocal Rank Fusion on
identical candidate/evidence inputs, and records enough configuration to
reproduce the run.

What this does NOT do
---------------------
It does not invent ground truth. If no labelled relevance set is supplied, it
reports unlabelled diagnostics only and marks the run as such. Rank agreement
between two methods is not accuracy, and a stable ranking is not evidence of
clinical efficacy.

Usage
-----
    # Diagnostics only (no labels needed)
    venv/bin/python scripts/benchmark.py

    # With a labelled relevance set
    venv/bin/python scripts/benchmark.py --labels benchmark/labels_example.json

    # Skip network-dependent live retrieval for a fully offline run
    venv/bin/python scripts/benchmark.py --no-live

Outputs JSON to benchmark/results/ and prints a summary. Every query is recorded,
including failures: failed trials are not silently dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src import coverage, pipeline, ranking  # noqa: E402


DEFAULT_QUERIES = os.path.join("benchmark", "queries_v1.json")
RESULTS_DIR = os.path.join("benchmark", "results")


def load_queries(path: str) -> dict:
    with open(path) as fh:
        payload = json.load(fh)
    if "queries" not in payload or not isinstance(payload["queries"], list):
        raise ValueError(f"{path} does not contain a 'queries' list")
    return payload


def load_labels(path: str | None) -> dict:
    """Load a labelled relevance set.

    Expected shape::

        {
          "version": "...",
          "labels": {
            "<query id or disease name>": {
              "relevant": ["Drug A", "Drug B"],
              "graded": {"Drug A": 2, "Drug B": 1}     # optional
            }
          }
        }

    Returns {} when no path is given, which makes the run unlabelled.
    """
    if not path:
        return {}
    with open(path) as fh:
        payload = json.load(fh)
    labels = payload.get("labels")
    if not isinstance(labels, dict):
        raise ValueError(f"{path} does not contain a 'labels' object")
    return labels


def labels_for(labels: dict, entry: dict) -> dict | None:
    """Look a query up by id first, then by its literal text."""
    for key in (entry.get("id"), entry.get("query")):
        if key and key in labels:
            value = labels[key]
            if isinstance(value, dict):
                return value
            if isinstance(value, list):
                return {"relevant": value}
    return None


def run_query(entry: dict, rrf_k: int, no_live: bool) -> dict:
    """Run one benchmark query and capture its rankings, or its failure."""
    record = {
        "id": entry.get("id"),
        "query": entry.get("query"),
        "category": entry.get("category"),
        "status": None,
        "error": None,
        "elapsed_ms": None,
        "rankings": {},
        "agreement": {},
        "diagnostics": {},
        "metrics": None,
        "labels_available": False,
    }

    started = time.time()
    try:
        result = pipeline.run_pipeline(entry["query"])
    except Exception as exc:
        # A failed trial is recorded, never omitted.
        record["status"] = "exception"
        record["error"] = {"kind": type(exc).__name__, "message": str(exc)[:300]}
        record["elapsed_ms"] = int((time.time() - started) * 1000)
        return record

    record["elapsed_ms"] = int((time.time() - started) * 1000)
    record["status"] = result.get("status")
    record["evidence_scope"] = result.get("evidence_scope")

    if result.get("status") != "ok":
        # Abstentions carry no ranking to evaluate. Recorded, not scored.
        record["diagnostics"] = {
            "abstained": True,
            "candidate_pool_size": len(result.get("candidate_pool") or []),
            "message": (result.get("message") or "")[:300],
        }
        return record

    inputs = ranking.build_rankings(result)
    graph_order = inputs[ranking.RANKING_METHOD_GRAPH]
    literature_order = inputs[ranking.RANKING_METHOD_LITERATURE]

    fusion = ranking.reciprocal_rank_fusion(inputs, k=rrf_k)

    record["rankings"] = {
        "graph_rank": graph_order,
        "literature_evidence_rank": literature_order,
        "reciprocal_rank_fusion": fusion["order"],
    }
    record["rrf_provenance"] = {
        "k": fusion["k"],
        "weights": fusion["weights"],
        "inputs": fusion["inputs"],
        "candidates_missing_from_some_list": fusion["candidates_missing_from_some_list"],
        "top_candidate_detail": fusion["candidates"][0] if fusion["candidates"] else None,
    }
    record["agreement"] = {
        "graph_vs_rrf": ranking.rank_agreement(graph_order, fusion["order"]),
        "literature_vs_rrf": ranking.rank_agreement(literature_order, fusion["order"]),
        "graph_vs_literature": ranking.rank_agreement(graph_order, literature_order),
    }
    record["diagnostics"] = ranking.literature_diagnostics(result)
    record["n_candidates"] = len(result.get("results") or [])
    return record


def apply_labels(record: dict, label: dict, ks) -> None:
    """Compute metrics for one query. Only called when real labels exist."""
    relevant = label.get("relevant") or []
    graded = label.get("graded") or None
    if not relevant and not graded:
        return

    rankings = record.get("rankings") or {}
    if not rankings:
        return

    metrics = {}
    for method, order in rankings.items():
        metrics[method] = ranking.evaluate_ranking(
            order, relevant, ks=ks, relevance=graded
        )
    record["metrics"] = metrics
    record["labels_available"] = True


def summarise(records: list, ks) -> dict:
    ok = [r for r in records if r["status"] == "ok"]
    errors = [r for r in records if r["error"]]
    abstained = [r for r in records if r["status"] and r["status"] != "ok"]

    agreement_graph_rrf = [
        r["agreement"]["graph_vs_rrf"]["kendall_tau_common"]
        for r in ok if r.get("agreement")
    ]
    same_top1 = sum(
        1 for r in ok
        if r.get("agreement") and r["agreement"]["graph_vs_rrf"]["same_top_1"]
    )

    labelled = [r for r in records if r.get("labels_available")]
    summary = {
        "n_queries": len(records),
        "n_ok": len(ok),
        "n_abstained": len(abstained),
        "n_errors": len(errors),
        "status_counts": _counts(r["status"] for r in records),
        "labelled_queries": len(labelled),
        "metrics_available": bool(labelled),
        "unlabelled_diagnostics_only": not labelled,
        "mean_kendall_tau_graph_vs_rrf": (
            sum(agreement_graph_rrf) / len(agreement_graph_rrf)
            if agreement_graph_rrf else None
        ),
        "queries_where_rrf_changes_top_candidate": len(ok) - same_top1 if ok else 0,
    }

    if labelled:
        for method in ("graph_rank", "literature_evidence_rank", "reciprocal_rank_fusion"):
            values = {}
            for k in list(ks) + ["mrr"]:
                key = f"mrr" if k == "mrr" else (
                    f"precision@{k}" if f"precision@{k}" in (labelled[0]["metrics"][method]) else None
                )
                if key is None:
                    continue
                vals = [r["metrics"][method][key] for r in labelled
                        if key in (r["metrics"][method] or {})]
                if vals:
                    values[key] = sum(vals) / len(vals)
            summary.setdefault("mean_metrics_by_method", {})[method] = values

    return summary


def _counts(values) -> dict:
    out: dict = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="PharmaSure ranking benchmark")
    parser.add_argument("--queries", default=DEFAULT_QUERIES,
                        help="versioned query set JSON")
    parser.add_argument("--labels", default=None,
                        help="labelled relevance set JSON (optional)")
    parser.add_argument("--out", default=None, help="output JSON path")
    parser.add_argument("--rrf-k", type=int, default=ranking.DEFAULT_RRF_K,
                        help="RRF smoothing constant")
    parser.add_argument("--ks", default="1,3,5,10", help="cutoffs for @k metrics")
    parser.add_argument("--no-live", action="store_true",
                        help="disable live retrieval for a fully offline run")
    parser.add_argument("--only", default=None, help="run a single query id")
    args = parser.parse_args()

    ks = tuple(int(x) for x in args.ks.split(",") if x.strip())
    query_set = load_queries(args.queries)
    labels = load_labels(args.labels)

    if args.no_live:
        os.environ["PHARMASURE_LIVE_RETRIEVAL"] = "0"

    entries = query_set["queries"]
    if args.only:
        entries = [e for e in entries if e.get("id") == args.only]

    cov = coverage.coverage_metadata()
    run_meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query_set_version": query_set.get("version"),
        "query_set_path": args.queries,
        "ranking_schema_version": ranking.RANKING_SCHEMA_VERSION,
        "rrf_k": args.rrf_k,
        "cutoffs": list(ks),
        "corpus_schema_version": cov.get("corpus_schema_version"),
        "local_abstract_count": cov.get("local_abstract_count"),
        "local_literature_disease_count": cov.get("local_literature_disease_count"),
        "kg_disease_count": cov.get("kg_disease_count"),
        "live_retrieval_enabled": cov.get("live_retrieval_enabled"),
        "live_retrieval_provider": cov.get("live_retrieval_provider"),
        "labels_supplied": bool(labels),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }

    print(f"Benchmark: {run_meta['query_set_version']} "
          f"({len(entries)} queries, rrf_k={args.rrf_k})")
    print(f"Corpus: {run_meta['corpus_schema_version']} | "
          f"live_retrieval={run_meta['live_retrieval_enabled']} "
          f"({run_meta['live_retrieval_provider']})")
    print("-" * 78)

    records = []
    for entry in entries:
        record = run_query(entry, args.rrf_k, args.no_live)
        label = labels_for(labels, entry)
        if label and record["status"] == "ok":
            apply_labels(record, label, ks)
        records.append(record)

        if record["error"]:
            print(f"  {record['id']:<4} ERROR {record['error']['kind']}")
        elif record["status"] != "ok":
            print(f"  {record['id']:<4} {record['status']:<24} (abstained, no ranking)")
        else:
            agr = record["agreement"]["graph_vs_rrf"]
            print(f"  {record['id']:<4} {record['status']:<8} "
                  f"n={record['n_candidates']:<3} "
                  f"tau(graph,rrf)={agr['kendall_tau_common']:+.2f} "
                  f"top1_same={agr['same_top_1']}")

    summary = summarise(records, ks)

    limitations = [
        "Scores are ordering signals, not probabilities of efficacy or clinical success.",
        "Rank stability and rank agreement are NOT evidence of clinical validity.",
        "RRF is compared against the existing baseline, not assumed to be better.",
    ]
    if not summary["metrics_available"]:
        limitations.append(
            "NO LABELLED RELEVANCE SET WAS SUPPLIED, so no accuracy metrics "
            "(precision/recall/NDCG/MRR) are reported. Only unlabelled "
            "diagnostics are shown. This run cannot establish that either "
            "method ranks better."
        )
    if summary["n_errors"]:
        limitations.append(
            f"{summary['n_errors']} query/queries raised an exception and are "
            f"recorded as errors rather than omitted."
        )

    payload = {
        "run": run_meta,
        "summary": summary,
        "queries": records,
        "limitations": limitations,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = args.out or os.path.join(
        RESULTS_DIR,
        f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
    )
    with open(out_path, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)

    print("-" * 78)
    print(f"ok={summary['n_ok']} abstained={summary['n_abstained']} "
          f"errors={summary['n_errors']} labelled={summary['labelled_queries']}")
    if summary["mean_kendall_tau_graph_vs_rrf"] is not None:
        print(f"mean tau(graph, rrf) = {summary['mean_kendall_tau_graph_vs_rrf']:+.3f} "
              f"over {summary['n_ok']} ranked queries")
    print(f"metrics available: {summary['metrics_available']}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
