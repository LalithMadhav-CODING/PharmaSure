# Ranking Alternatives and the Reproducible Benchmark

Phase 6 deliverable. Covers Reciprocal Rank Fusion (RRF), the benchmark harness,
metric definitions, and the protocol for comparing PharmaSure against external
systems.

## 1. What is being compared

| Method | Definition | Status |
|---|---|---|
| `graph_rank` | The EveryCure knowledge-graph candidate order. | **Existing baseline. Still the default.** |
| `literature_evidence_rank` | Candidates ordered by PharmaSure's literature evidence score. | Existing signal, exposed as a ranking. |
| `reciprocal_rank_fusion` | RRF over the two rankings above. | **Alternative. Not the default.** |

RRF is *not* a replacement for the existing ranking. It is implemented as a
separate, pure, deterministic function so it can be compared against the baseline
on identical inputs. Switching the product's default would require measured
evidence that it is better, which this repository does not currently have.

## 2. RRF definition

```
RRF(c) = Σ_lists  weight[list] / (k + rank_in_list(c))
```

- `k` defaults to **60** (Cormack, Clarke & Buettcher, 2009), configurable via
  `--rrf-k`.
- `rank_in_list` is 1-based.
- Graph rank and literature rank are fused **by position only**. Graph scores and
  evidence scores are never added to one another, because they have different
  semantics and scales — adding them would be meaningless.

### Handling of edge cases (all tested)

| Case | Behaviour |
|---|---|
| Candidate missing from a list | Receives no contribution from it. No imputed rank, no penalty. Counted in `candidates_missing_from_some_list`. |
| Candidate duplicated within a list | Keeps its **best** (lowest) rank; the duplicate is counted in `inputs[name].duplicates_removed`. |
| Empty list | Contributes nothing; still reported with `size: 0`. |
| `None` entries | Skipped. |
| Score ties in the fused output | Broken on candidate identifier ascending, so ordering is stable across runs. |
| `k < 0` | Raises `ValueError`. |

### Explainability

`reciprocal_rank_fusion()` returns, for every candidate, the per-list rank and
the per-list contribution, plus the `k` and weights used. Every contribution is
re-derivable from the recorded rank — asserted by test.

## 3. Metrics — and when they are refused

Implemented in `src/ranking.py`, each hand-verified against small known examples
in `tests/test_ranking.py`:

- `precision@k` — fraction of the top-k that are relevant.
- `recall@k` — fraction of relevant items found in the top-k.
- `reciprocal_rank` / MRR — 1 / position of the first relevant item.
- `ndcg@k` — DCG with the standard `log2(i+1)` discount, normalised by ideal DCG.
- `average_precision` — mean of precision@i at the positions of relevant items.

**Guards against fabricated scores.** These are not stylistic; each prevents a
zero denominator from becoming a perfect score:

- No relevant items → `recall` returns `0.0`, not `1.0`.
- Ideal DCG of zero → `ndcg` returns `0.0`, not `1.0`.
- No labels supplied → **no metrics are reported at all** and the run is marked
  `unlabelled_diagnostics_only: true`.

### Unlabelled diagnostics (never accuracy)

`rank_agreement()` reports Kendall tau-b, Jaccard overlap, rank shifts and
top-1 agreement. `literature_diagnostics()` reports evidence coverage and
distinct-PMID counts.

These describe **agreement and coverage, not correctness**. A high tau means two
methods agree; it does not mean either is more accurate. Rank stability is not
evidence of clinical efficacy. A test asserts the diagnostics payload contains no
metric name implying accuracy.

## 4. Running the benchmark

```bash
# Offline, reproducible, no network
venv/bin/python scripts/benchmark.py --no-live

# With live retrieval enabled (network)
venv/bin/python scripts/benchmark.py

# With a labelled relevance set
venv/bin/python scripts/benchmark.py --labels benchmark/labels.json

# Single query
venv/bin/python scripts/benchmark.py --only q03
```

Options: `--queries`, `--labels`, `--out`, `--rrf-k`, `--ks`, `--no-live`, `--only`.

Query set: `benchmark/queries_v1.json` (versioned — bump the version rather than
editing a file whose results were already recorded). It covers local-evidence
diseases, a live-retrieval case, a rare disease with no literature, a
no-candidates case, an unresolved disease and a typographic variant.

Output: JSON under `benchmark/results/`, recording the query-set version, corpus
schema version, ranking schema version, `rrf_k`, cutoffs, live-retrieval state and
provider, Python/platform, and every query's status, rankings, agreement,
diagnostics, metrics and errors. **Failed queries are recorded, not omitted.**

## 5. Actual results

### Offline run (`--no-live`)

```
Benchmark: 2026-10-benchmark-queries-v1 (10 queries, rrf_k=60)
Corpus: 2026-10-corpus-v2 | live_retrieval=False (europepmc)
  q01  ok  n=10  tau(graph,rrf)=+0.78 top1_same=True
  q02  ok  n=10  tau(graph,rrf)=+0.87 top1_same=True
  q03  ok  n=10  tau(graph,rrf)=+0.82 top1_same=False
  q04  ok  n=10  tau(graph,rrf)=+0.73 top1_same=True
  q05  ok  n=10  tau(graph,rrf)=+0.82 top1_same=True
  q06  no_local_evidence    (abstained)
  q07  no_local_evidence    (abstained)
  q08  no_candidates        (abstained)
  q09  unsupported_disease  (abstained)
  q10  ok  n=10  tau(graph,rrf)=+0.78 top1_same=True
ok=6 abstained=4 errors=0 labelled=0
mean tau(graph, rrf) = +0.800 over 6 ranked queries
metrics available: False
```

### Live run

```
n_queries=10 n_ok=7 n_abstained=3 n_errors=0
status_counts: ok=7, no_relevant_evidence=1, no_candidates=1, unsupported_disease=1
mean_kendall_tau_graph_vs_rrf = +0.790
queries_where_rrf_changes_top_candidate = 2
metrics available: False
```

With live retrieval on, q06 (Fibrodysplasia ossificans progressiva) is answered
from live evidence instead of abstaining; q07 (Zygodactyly type 4) becomes
`no_relevant_evidence` — the provider responded successfully and nothing relevant
was found.

### What these numbers do and do not say

They say RRF agrees substantially with the graph baseline (mean tau ≈ +0.79) and
changes the top candidate on 2 of 7 ranked queries.

They do **not** say RRF is better. **No labelled relevance set was available**, so
no accuracy metric is reported and no superiority claim is made — in either
direction.

## 6. Worked example (real output)

Alzheimer disease, `rrf_k=60`:

```
baseline graph : Galantamine, Norepinephrine, Insulin human, Memantine, Interferon alfa
literature     : Galantamine, Insulin human, Norepinephrine, Memantine, Acetylcysteine
RRF            : Galantamine, Insulin human, Norepinephrine, Memantine, Acetylcysteine
tau(graph,rrf) : 0.778   top-1 identical: True
```

Galantamine (graph rank 1, literature rank 1) wins the fusion. Norepinephrine and
Insulin human swap, because the literature signal puts Insulin human ahead while
the graph puts Norepinephrine ahead; RRF resolves the disagreement on combined
rank position.

Note that Galantamine's evidence is **fragile**: the Phase 3 audit shows removing
PMID 42851720 drops its score from 0.779 to 0.424 and its rank from 1 to 3. A
ranking is not a conclusion.

## 7. External-system comparison protocol

Not yet run. No claim of superiority over Gemini, Claude, TxGNN, Open Targets or
any other system is made, and none should be inferred from the numbers above.

To run a fair comparison, record all of the following per trial:

1. **Fixed query set** — reuse `benchmark/queries_v1.json` so both systems see
   identical queries.
2. **Source conditions** — for a source-grounded comparison, supply the *same*
   documents to PharmaSure and to the comparator where it supports that workflow.
   Note explicitly whether web search or tools were enabled.
3. **Exact system identity** — product and model name, version, date, and settings.
4. **Prompt** — verbatim.
5. **Repeated trials** where output variability matters; report variance.
6. **Rubric** — source correctness, candidate traceability, coverage of
   contradictory findings, evidence completeness, unsupported claims,
   reproducibility, latency. Blinded human review where feasible.
7. **Specialist tools** — TxGNN and Open Targets are separate comparators for
   tasks they actually support (e.g. prediction benchmarks), not general chat
   baselines. Do not compare them on tasks they were not built for.
8. **Failures recorded** — empty or errored trials are included, never dropped.

Do not scrape private services, bypass access controls, or claim an API
integration that does not exist. If Gemini API access is unavailable, run the
protocol manually and label the results **not yet run**.

## 8. Limitations

- No labelled relevance set exists in this repository, so **no accuracy metric is
  reported**. Known indications in the graph are already-approved uses, not
  ground truth for *repurposing* candidates, so they are not used as labels.
- Scores are ordering signals, not probabilities of efficacy or clinical success.
- Rank agreement and rank stability are not evidence of clinical validity.
- RRF is compared against the baseline, not assumed to be better.
- The literature ranking's evidence score is passage-counted, not
  PMID-deduplicated, so a single study with several passages can carry more
  support than a single-passage study.
