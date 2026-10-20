# PharmaSure frontend / API integration

This document describes the API contract inspected in `src/app.py`, `src/pipeline.py`, `src/audit.py`, and `docs/EVIDENCE_AUDIT.md`, plus optional fields needed for the evidence-coverage and benchmark states. The frontend does not alter or infer backend results when these fields are absent.

## Current endpoints

### `GET /api/health`

Currently returns `status`, `corpus_size`, `disease_count`, `all_diseases_supported`, `supported_diseases`, and `data_sources`. The frontend displays returned health metadata and uses only `supported_diseases` as examples. Health success is not treated as proof of literature coverage for a submitted disease.

### `POST /api/query`

Request body: `{ "query": "<disease name>" }`.

Current response fields consumed by the frontend:

- Query: `status`, `query`, `message`, `disease.{id,name,synonyms}`, `results`, `known_indications`, `passages`, `timings_ms`, `from_cache`, and `evidence_audit_summary`.
- Candidate: `rank` (knowledge-graph display order), `drug`, `direction`, `reason`, `claims[]`, `evidence.{score,tier,support,best_study_type,breakdown}`, and `evidence_audit`. Optional additive fields `kg_score` (number or `null`) and `literature_coverage.{status,source_record_count,distinct_pmid_count,verification_status}` are mapped/displayed if returned; they are not present in the current API response.
- Claim: `text`, `citations` or `citation_ids`, `quote`, `verification_status`, and `verification_reason`.
- Passage: `id`, `text`, `source`, `pmid`, `year`, `pub_type`, `retrieval_score`, and `study_weight`. The cached/live pipeline may include numeric retrieval and study-type weights; the UI displays these only when they are finite numbers returned by the API. `retrieval_score` is the backend retrieval relevance value, not clinical evidence strength.
- Audit: `status`, `reason`, `method`, `scoring_function`, `ranking_scope`, `baseline`, `study_counts`, `stability`, `counterfactuals`, `sources`, and `warnings`. Counterfactual values are rendered only when returned. The frontend keeps the KG display rank separate from the audit's evidence rank.
- Audit source: `source_id`, `pmid`, `pubmed_url`, `passage_id`, `quote`, `source_identity_status`, `quote_verification_status`, publication metadata, `evidence_direction`, `safety_signal`, and warnings.

The current scorer reports `evidence.support` as a passage count. The normalized support component is separately returned under `evidence.breakdown.support`. Neither represents a distinct-study count. The current query response does not include a numeric knowledge-graph score, a per-query source mode, live-provider status, disease-specific corpus-coverage status, or benchmark results.

## Current frontend behavior

- Queries call the real `/api/query` endpoint using `{ query }`; a newer query cancels a stale request. Query timeout is 120 seconds.
- The disease example chips and initial cached-demo query come only from names returned by `/api/health`.
- Candidate source records are assembled only from the candidate's audit ledger and/or its own cited passage IDs. The complete disease-level passage array is not treated as candidate evidence.
- Cached results are labeled when `from_cache` is `true`. The UI does not describe a cache hit as live retrieval.
- When a field is absent, the UI reports it as not returned/unavailable; it does not substitute scores, titles, evidence directions, counts, or benchmark metrics.

## Optional backend contract needed for complete coverage reporting

The current response does not distinguish disease resolution, graph candidate availability, local literature coverage, and external retrieval status. Add the following **optional additive** `coverage` object to `/api/query` when those values are known. Omit unknown values or set them to `null`; do not convert unknown into `false`, `0`, or a successful state.

```json
{
  "coverage": {
    "disease_resolution_status": "resolved | unresolved | unknown",
    "graph_candidate_status": "available | none | unavailable | unknown",
    "literature_status": "available | none | insufficient | unavailable | unknown",
    "source_mode": "local | live | mixed | unknown",
    "provider": "PubMed | Europe PMC | null",
    "retrieval_status": "not_attempted | in_progress | succeeded | empty | rate_limited | timeout | unavailable | failed | unknown",
    "retrieved_record_count": 12,
    "distinct_pmid_count": 8,
    "retrieved_at": "2026-10-20T12:30:00Z",
    "provider_message": null
  },
  "results": [
    {
      "drug": "returned candidate name",
      "literature_coverage": {
        "status": "available | none | insufficient | unknown",
        "source_record_count": 3,
        "distinct_pmid_count": 2,
        "verification_status": "verified | needs_review | unknown"
      }
    }
  ]
}
```

`retrieved_record_count` and `distinct_pmid_count` describe the query's retrieved set. `results[].literature_coverage` describes only that candidate and must count records actually linked to it—not disease-level search hits. A live source mode/status must only be returned when a provider request actually occurred.

Recommended optional passage metadata: `title`, `source_url`, and `provenance` (`local`, `live`, `mixed`, or `unknown`). The frontend already tolerates these fields when present, but the current backend passage schema does not include them. The audit currently provides validated PubMed URLs in `sources[].pubmed_url`.

Recommended optional candidate field: `kg_score` (number or `null`) if the graph score is to be displayed. `rank` remains the graph's displayed candidate order. If a combined score is added, include its named/versioned method and component definition; do not infer a score from rank.

## Optional evidence redundancy fields

The audit currently reports `study_counts.study_independence_verified` and evidence-direction summaries. Duplicate-removal and overlap counts are not in the current audit response. If computed, add:

```json
{
  "study_counts": {
    "duplicate_records_removed": 2,
    "potentially_overlapping_studies": null
  }
}
```

`null`/omission means unknown, not zero. Do not infer independent experiments from distinct PMIDs.

## Ranking benchmark contract

No ranking or general-AI benchmark field is returned by the current API, so no comparison is displayed. To enable one, add a versioned `ranking_benchmark` object with at least:

```json
{
  "ranking_benchmark": {
    "status": "complete | partial | planned | not_run | failed",
    "protocol_id": "string",
    "evaluation_date": "YYYY-MM-DD",
    "query_count": 0,
    "trial_count": 0,
    "source_access_conditions": "string",
    "evaluation_rubric": "string",
    "verification_mode": "automatic | human | mixed | none",
    "methods": [
      {
        "name": "PharmaSure",
        "product_or_model_id": "exact version/model identifier",
        "outcomes": { "metric_name": 0.0 },
        "runtime_ms": null,
        "failures": [],
        "limitations": []
      }
    ]
  }
}
```

All displayed outcomes must be computed results for the declared protocol. Do not return example metrics in production responses or expose a winner claim unsupported by those results.

## Configuration and running locally

- Frontend dev server: `cd frontend && npm ci && npm run dev`.
- Vite proxies browser-relative `/api/*` and `/gradio/*` routes to `http://127.0.0.1:7860` by default. Set `VITE_DEV_PROXY_TARGET` (or `BACKEND_API_URL` for the local Vite process) to change that dev-server target.
- The browser API base can be configured by runtime `frontend/public/config.json` (`apiBase`) or the build-time `VITE_API_BASE_URL`; empty means same-origin. Do not put backend keys in either frontend setting.
- Backend: start the existing FastAPI application using its documented environment and data; no backend code was changed for this UI work.
