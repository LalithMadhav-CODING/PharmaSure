# Live Literature Retrieval (Phase 5)

When a disease resolves in the knowledge graph but the indexed corpus holds no
literature for it, PharmaSure attempts **bounded live retrieval** from an official
biomedical API instead of abstaining outright.

## Provider

**Europe PMC REST search** — `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
(EMBL-EBI). Official API, JSON, no API key required for this endpoint.

Chosen over NCBI E-utilities because it returns abstracts in a **single** request;
E-utilities needs `esearch` then `efetch`. The provider sits behind a
`LiteratureProvider` protocol with a registry, so it is swappable. No scraping is
performed anywhere.

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `PHARMASURE_LIVE_RETRIEVAL` | `1` (on) | `0`/`false`/`no`/`off` disables live retrieval entirely. |
| `PHARMASURE_LIVE_PROVIDER` | `europepmc` | Provider name. |
| `PHARMASURE_LIVE_TIMEOUT_S` | `10` | Per-request timeout. |
| `PHARMASURE_LIVE_MAX_RESULTS` | `25` | Bounded result count. Hard cap 100. |
| `PHARMASURE_LIVE_CACHE_TTL_S` | `3600` | TTL for **successful** responses. |
| `PHARMASURE_LIVE_USER_AGENT` | PharmaSure contact string | Sent to the provider. |

Readiness and the active provider are reported by `/api/health` as
`live_retrieval_enabled` and `live_retrieval_provider`. No secrets are exposed.

## Statuses

Each is distinct, and the API never collapses them:

| Status | Meaning |
|---|---|
| `ok` + `evidence_scope="local_corpus"` | Answered from the indexed corpus. Takes precedence; live retrieval is not attempted. |
| `ok` + `evidence_scope="live_retrieval"` | Answered from live records bound to specific candidates. |
| `no_relevant_evidence` | The provider **responded successfully** and nothing relevant was found. |
| `provider_unavailable` | The provider **failed** (timeout, HTTP error, rate limit, malformed response, connection failure). |
| `no_local_evidence` | No local literature **and** live retrieval is disabled. |
| `no_candidates` | Resolved, but the graph proposes no candidates. |
| `unsupported_disease` | Could not be resolved to a canonical identity. |

A provider failure is never reported as a successful search that found nothing,
and provider failure messages state explicitly that they are *not* evidence that
no literature exists.

## Evidence boundary

**A disease-only paper is not evidence for a drug.** Every retrieved record is
matched against a specific candidate drug with a word-boundary pattern before it
can become evidence. Word boundaries matter: a substring match would let
`aspirin` match `aspirinase`.

Observed in practice: a search for *Zygodactyly type 4* returned a coronary artery
dissection paper, which the relevance check correctly dropped.

Records sharing a PMID collapse to one study unit, so duplicate records are never
counted as independent evidence. Records with no identifier are kept but counted
and reported as a limitation — never given an invented identifier.

## Query construction

Phrase-quoted on the canonical disease name plus at most two synonyms, restricted
to title/abstract:

```
("Zygodactyly type 4" OR "syndactyly type 1d" OR "syndactyly type 1, Castilla type")
  AND (TITLE_ABS:drug OR TITLE_ABS:treatment OR TITLE_ABS:therapy)
```

**Precision was chosen deliberately.** Europe PMC has **zero** hits for the exact
phrase `"Zygodactyly type 4"`; the loose unquoted query returns 26 mostly
irrelevant papers (an OCT paper, focal dermal hypoplasia). Using the loose form
would risk presenting an unrelated paper as evidence if it happened to name a
candidate drug. For a rare disease the honest outcome is `no_relevant_evidence`,
not a plausible-looking wrong answer.

## Caching

TTL cache with an injectable clock (expiry is tested without sleeps). Keys include
the schema version, provider, normalised query and limit — **exact matching only**,
so one disease can never be served another disease's cached result.

- Only **successful** retrievals are cached. A transient outage cannot be replayed
  as a successful empty result.
- The cache is bounded; the oldest entry is evicted when full.
- Cached payloads are deep-copied on write and read, so a caller mutating a result
  cannot corrupt the cached entry.

## Provenance

Each live record preserves provider, PMID, title, abstract, year, URL, journal,
publication types and retrieval timestamp. Live passages carry
`source_mode="live_retrieval"` and are never presented as local corpus evidence.
Quotations are verified against the exact retrieved text by the existing
contiguous-excerpt verifier.

`/api/query` gains optional fields (existing fields unchanged):

```json
{
  "evidence_scope": "live_retrieval",
  "live_retrieval": {
    "status": "ok", "provider": "europepmc", "query": "...",
    "records_retrieved": 25, "records_after_dedup": 25,
    "records_without_identifier": 4, "relevant_records": 1,
    "candidates_with_live_evidence": 1,
    "from_cache": false, "cache_ttl_s": 3600.0,
    "retrieved_at": "2026-10-19T20:33:03+00:00",
    "error": null, "limitations": [], "schema_version": "2026-10-live-v1"
  }
}
```

The summary deliberately excludes full abstracts so a response cannot balloon.

## Limitations

- No full-text retrieval; abstracts only.
- Phrase matching means an obscure disease name that is discussed only under
  different terminology will return no results rather than guessing.
- Records without a PMID cannot be deduplicated or cited by identifier; they are
  counted and disclosed, not silently merged.
- `study_type` is derived from provider publication types only when supplied;
  otherwise it is `other` rather than a guess.
- Live evidence is marked as live and is not part of the indexed corpus, so its
  coverage is not reflected in the corpus counts.

## Tests

`tests/test_live_retrieval.py` (39) and `tests/test_live_pipeline.py` (14). All use
fake providers or fake HTTP clients — **no test requires network access**.

Manual smoke test against the real API:

```bash
venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from src import live_retrieval as lr
out = lr.retrieve_for_disease('Fibrodysplasia ossificans progressiva',
                              ['Doxycycline'], cache=lr.TTLCache())
print(out.status, out.records_retrieved, list(out.passages_by_drug))"
# -> ok 25 ['Doxycycline']
```
