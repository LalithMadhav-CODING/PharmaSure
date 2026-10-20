#!/usr/bin/env python
"""Rebuild data/candidates.json from EveryCure matrix-scores.

The previous build hardcoded `rn <= 10`, which capped every disease at ten
candidates. The cap is now an explicit parameter so it is a documented choice
rather than a hidden constant.

Usage:
    venv/bin/python scripts/build_candidates.py [--top-n 25]

Notes:
- `is_known_positive = false AND is_known_negative = false` keeps only genuine
  repurposing candidates; known indications are stored separately under 'k'.
- Output is compact JSON (no spaces) because the whole file is loaded into memory.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

DEFAULT_TOP_N = 25
OUT = os.path.join("data", "candidates.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="candidates kept per disease (ranked by treat score)")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args()

    import duckdb
    from huggingface_hub import hf_hub_download

    files = []
    for i in range(11):
        fname = f"data/scores/train-{i:05d}-of-00011.parquet"
        files.append(hf_hub_download("everycure/matrix-scores", fname, repo_type="dataset"))
    print(f"parquet files: {len(files)}", flush=True)

    con = duckdb.connect()
    # The full matrix is large; the window function over every parquet file will not
    # fit in RAM. Spill to disk rather than failing, and drop insertion-order
    # preservation which is the biggest single consumer.
    con.execute("SET memory_limit='2GB'")
    con.execute("SET temp_directory='/tmp/duckdb_spill'")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET threads=2")
    file_list = ",".join(f"'{f}'" for f in files)

    ranked = con.execute(f"""
        WITH ranked AS (
            SELECT target as disease_id,
                   source_ec_id as ec_id,
                   ROUND(untransformed_treat_score, 4) as score,
                   ROW_NUMBER() OVER (PARTITION BY target
                                      ORDER BY untransformed_treat_score DESC) as rn
            FROM read_parquet([{file_list}])
            WHERE is_known_positive = false
              AND is_known_negative = false
              AND source_ec_id IS NOT NULL
              AND source_ec_id != ''
        )
        SELECT disease_id, ec_id, score FROM ranked WHERE rn <= {args.top_n}
        ORDER BY disease_id, rn
    """).fetchall()
    print(f"candidate rows: {len(ranked)}", flush=True)

    lookup: dict = {}
    for disease_id, ec_id, score in ranked:
        lookup.setdefault(disease_id, {"c": [], "k": []})["c"].append([ec_id, score])

    known = con.execute(f"""
        SELECT target as disease_id, source as drug_id
        FROM read_parquet([{file_list}])
        WHERE is_known_positive = true AND source IS NOT NULL AND source != ''
    """).fetchall()
    for disease_id, drug_id in known:
        lookup.setdefault(disease_id, {"c": [], "k": []})["k"].append(drug_id)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(lookup, fh, separators=(",", ":"))

    size = os.path.getsize(args.out)
    counts = [len(v["c"]) for v in lookup.values()]
    print(f"diseases: {len(lookup)}")
    print(f"candidates/disease: min={min(counts)} max={max(counts)}")
    print(f"{args.out}: {size / 1024 / 1024:.1f} MB (top_n={args.top_n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
