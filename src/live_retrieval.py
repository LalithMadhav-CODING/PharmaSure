"""Phase 5: bounded live literature retrieval from official biomedical APIs.

Purpose
-------
When a disease resolves in the knowledge graph but the local corpus holds no
literature for it, the system previously had nothing to say and returned
``no_local_evidence``. This module expands coverage at query time by querying an
official provider (Europe PMC), under strict bounds.

Hard rules enforced here
------------------------
1.  Only official APIs. No scraping.
2.  Bounded results and an explicit timeout on every request.
3.  A provider failure is NEVER reported as a successful search with zero
    results. ``provider_failed`` and ``no_results`` are distinct statuses.
4.  A disease-only paper is NOT evidence for every graph candidate. Each record
    is matched against a specific candidate drug before it can become evidence.
5.  Records are deduplicated by stable identifier. Multiple records for the same
    source are one study unit, not independent corroboration.
6.  Nothing is fabricated: a record with no PMID keeps ``source_id=None`` and is
    flagged, rather than being given an invented identifier.
7.  Live records are marked as live-retrieved and never presented as local
    corpus evidence.

Provider
--------
Europe PMC REST search API (single request, JSON, abstracts included):
    https://www.ebi.ac.uk/europepmc/webservices/rest/search

Europe PMC is operated by EMBL-EBI. It is an official biomedical literature API
and requires no API key for this endpoint. NCBI E-utilities would need two
requests (esearch + efetch) for the same result, which is why Europe PMC is the
default here. The ``LiteratureProvider`` protocol keeps the choice swappable.

Configuration (environment variables)
-------------------------------------
    PHARMASURE_LIVE_RETRIEVAL   "1" (default) enables live retrieval, "0" disables
    PHARMASURE_LIVE_PROVIDER    provider name, default "europepmc"
    PHARMASURE_LIVE_TIMEOUT_S   per-request timeout seconds, default 10
    PHARMASURE_LIVE_MAX_RESULTS bounded result count, default 25 (hard cap 100)
    PHARMASURE_LIVE_CACHE_TTL_S successful-response TTL seconds, default 3600
    PHARMASURE_LIVE_USER_AGENT  contact string sent to the provider
"""
from __future__ import annotations

import copy
import html
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is an existing dependency
    httpx = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

PROVIDER_EUROPEPMC = "europepmc"

#: Bump when the record shape, query construction or cache key changes, so stale
#: cached payloads are never served as current.
LIVE_SCHEMA_VERSION = "2026-10-live-v1"

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_RESULTS = 25
HARD_MAX_RESULTS = 100
DEFAULT_CACHE_TTL_S = 3600.0

#: Retrieval outcome statuses. These are deliberately distinct: a provider that
#: failed must never be indistinguishable from a provider that succeeded and
#: genuinely found nothing.
LIVE_STATUS_OK = "ok"
LIVE_STATUS_NO_RESULTS = "no_results"
LIVE_STATUS_NO_RELEVANT = "no_relevant_records"
LIVE_STATUS_FAILED = "provider_failed"
LIVE_STATUS_DISABLED = "disabled"


# --------------------------------------------------------------------------- #
# Provider errors — one class per distinguishable failure mode
# --------------------------------------------------------------------------- #

class ProviderError(Exception):
    """Base class for provider failures. Never swallowed into a success."""

    kind = "provider_error"

    def __init__(self, message: str, *, kind: Optional[str] = None):
        super().__init__(message)
        if kind:
            self.kind = kind

    def as_dict(self) -> dict:
        return {"kind": self.kind, "message": str(self)}


class ProviderTimeout(ProviderError):
    kind = "timeout"


class ProviderRateLimited(ProviderError):
    kind = "rate_limited"


class ProviderHTTPError(ProviderError):
    kind = "http_error"


class ProviderMalformed(ProviderError):
    kind = "malformed_response"


class ProviderUnavailable(ProviderError):
    kind = "connection_error"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


def live_retrieval_enabled() -> bool:
    """Whether live retrieval may be attempted. Read per call so tests can toggle."""
    raw = os.environ.get("PHARMASURE_LIVE_RETRIEVAL", "1")
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def configured_provider_name() -> str:
    return (os.environ.get("PHARMASURE_LIVE_PROVIDER") or PROVIDER_EUROPEPMC).strip().lower()


def configured_timeout_s() -> float:
    return _env_float("PHARMASURE_LIVE_TIMEOUT_S", DEFAULT_TIMEOUT_S)


def configured_max_results() -> int:
    return max(1, min(_env_int("PHARMASURE_LIVE_MAX_RESULTS", DEFAULT_MAX_RESULTS), HARD_MAX_RESULTS))


def configured_cache_ttl_s() -> float:
    return _env_float("PHARMASURE_LIVE_CACHE_TTL_S", DEFAULT_CACHE_TTL_S)


def configured_user_agent() -> str:
    return os.environ.get(
        "PHARMASURE_LIVE_USER_AGENT",
        "PharmaSure/1.0 (drug-repurposing research; contact via repository)",
    )


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LiveRecord:
    """One retrieved literature record, with provenance preserved."""

    source_id: Optional[str]      # PMID where available, else None (never invented)
    provider: str
    title: str
    abstract: str
    year: Optional[int]
    url: Optional[str]
    journal: Optional[str]
    pub_types: tuple = ()
    doi: Optional[str] = None
    retrieved_at: str = ""
    provider_rank: int = 0

    @property
    def study_type(self) -> str:
        """Map provider publication types onto the corpus's vocabulary.

        Only applied when the provider actually supplied type metadata; otherwise
        this is 'other' rather than a guess.
        """
        joined = " ".join(self.pub_types).lower()
        if not joined:
            return "other"
        if "clinical trial" in joined or "randomized controlled trial" in joined:
            return "clinical_trial"
        if "review" in joined or "meta-analysis" in joined or "systematic review" in joined:
            return "review"
        if "cohort" in joined or "observational" in joined or "case-control" in joined:
            return "cohort"
        if "animal" in joined or "mice" in joined or "in vitro" in joined or "preclinical" in joined:
            return "preclinical"
        return "other"

    def text(self) -> str:
        """Title + abstract, the text quotations are verified against."""
        return f"{self.title} {self.abstract}".strip()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["pub_types"] = list(self.pub_types)
        d["study_type"] = self.study_type
        return d


@dataclass
class RetrievalOutcome:
    """Result of one live retrieval attempt, success or failure."""

    status: str
    provider: str
    query: str
    records: list = field(default_factory=list)
    records_retrieved: int = 0
    records_after_dedup: int = 0
    records_without_identifier: int = 0
    relevant_records: int = 0
    passages_by_drug: dict = field(default_factory=dict)
    error: Optional[dict] = None
    from_cache: bool = False
    cache_ttl_s: float = DEFAULT_CACHE_TTL_S
    retrieved_at: str = ""
    limitations: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "provider": self.provider,
            "query": self.query,
            "records_retrieved": self.records_retrieved,
            "records_after_dedup": self.records_after_dedup,
            "records_without_identifier": self.records_without_identifier,
            "relevant_records": self.relevant_records,
            "records": [r.as_dict() for r in self.records],
            "passages_by_drug": {
                drug: [_passage_public(p) for p in ps]
                for drug, ps in self.passages_by_drug.items()
            },
            "error": self.error,
            "from_cache": self.from_cache,
            "cache_ttl_s": self.cache_ttl_s,
            "retrieved_at": self.retrieved_at,
            "limitations": list(self.limitations),
            "schema_version": LIVE_SCHEMA_VERSION,
        }

    def summary(self) -> dict:
        """Compact, API-safe view: counts and provenance, no abstracts.

        Full record text is deliberately excluded so a response cannot balloon to
        hundreds of kilobytes of provider prose.
        """
        return {
            "status": self.status,
            "provider": self.provider,
            "query": self.query,
            "records_retrieved": self.records_retrieved,
            "records_after_dedup": self.records_after_dedup,
            "records_without_identifier": self.records_without_identifier,
            "relevant_records": self.relevant_records,
            "candidates_with_live_evidence": len(self.passages_by_drug),
            "from_cache": self.from_cache,
            "cache_ttl_s": self.cache_ttl_s,
            "retrieved_at": self.retrieved_at,
            "error": self.error,
            "limitations": list(self.limitations),
            "schema_version": LIVE_SCHEMA_VERSION,
        }


def _passage_public(p: dict) -> dict:
    return {
        "pmid": p.get("pmid"),
        "title": p.get("title"),
        "year": p.get("year"),
        "url": p.get("url"),
        "journal": p.get("journal"),
        "pub_type": p.get("pub_type"),
        "source_mode": p.get("source_mode"),
        "retrieved_at": p.get("retrieved_at"),
    }


# --------------------------------------------------------------------------- #
# Text normalisation and matching
# --------------------------------------------------------------------------- #

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: Optional[str]) -> str:
    """Strip provider markup and collapse whitespace.

    Europe PMC abstracts embed structural tags (``<h4>Background</h4>``); leaving
    them in would corrupt quotation verification and display.
    """
    if not value:
        return ""
    text = _TAG_RE.sub(" ", str(value))
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def normalize_for_match(value: Optional[str]) -> str:
    """Normalisation used for drug-mention matching (documented, reversible)."""
    text = clean_text(value).lower()
    text = text.replace("\u2019", "'")
    return _WS_RE.sub(" ", text).strip()


def drug_pattern(drug_name: str) -> Optional[re.Pattern]:
    """Word-boundary pattern for a drug name.

    Word boundaries matter: a substring match would let 'aspirin' match
    'aspirinase' and, worse, let short drug names match inside unrelated words.
    """
    name = (drug_name or "").strip().lower()
    if not name:
        return None
    escaped = re.escape(name)
    escaped = escaped.replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")


def record_mentions_drug(record: LiveRecord, drug_name: str) -> bool:
    """Whether this record's own text names the candidate drug.

    This is the candidate-specific relevance check. Co-occurrence in a paper is
    NOT proof of a therapeutic relationship — it only establishes that the record
    is about this drug at all, which is the minimum bar for it to be considered
    evidence for the candidate. Downstream scoring and the audit still apply.
    """
    pattern = drug_pattern(drug_name)
    if pattern is None:
        return False
    return pattern.search(normalize_for_match(record.text())) is not None


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #

def build_query(disease_name: str, synonyms: Optional[list] = None) -> str:
    """Build a bounded provider query for a disease.

    Phrase-matched on the canonical name plus at most two synonyms, restricted to
    title/abstract. The result count is bounded separately; this only shapes
    relevance.
    """
    names = []
    for candidate in [disease_name] + list(synonyms or [])[:2]:
        cleaned = clean_text(candidate)
        if cleaned and cleaned.lower() not in {n.lower() for n in names}:
            names.append(cleaned)
    if not names:
        return ""
    disease_clause = " OR ".join(f'"{n}"' for n in names)
    return f"({disease_clause}) AND (TITLE_ABS:drug OR TITLE_ABS:treatment OR TITLE_ABS:therapy)"


# --------------------------------------------------------------------------- #
# Provider protocol and Europe PMC implementation
# --------------------------------------------------------------------------- #

class LiteratureProvider(Protocol):
    name: str

    def search(self, query: str, limit: int, timeout_s: float) -> list:  # pragma: no cover
        ...


class EuropePMCProvider:
    """Europe PMC REST search. Official API, no key required."""

    name = PROVIDER_EUROPEPMC
    ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, client=None, user_agent: Optional[str] = None):
        self._client = client
        self._user_agent = user_agent or configured_user_agent()

    def _get(self, params: dict, timeout_s: float):
        if self._client is not None:
            return self._client.get(self.ENDPOINT, params=params, timeout=timeout_s)
        if httpx is None:  # pragma: no cover
            raise ProviderUnavailable("httpx is not installed; live retrieval unavailable")
        return httpx.get(
            self.ENDPOINT, params=params, timeout=timeout_s,
            headers={"User-Agent": self._user_agent},
        )

    def search(self, query: str, limit: int, timeout_s: float) -> list:
        if not query:
            return []
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(max(1, min(int(limit), HARD_MAX_RESULTS))),
            "resultType": "core",
        }

        try:
            response = self._get(params, timeout_s)
        except Exception as exc:  # httpx raises a family of transport errors
            name = type(exc).__name__.lower()
            if "timeout" in name:
                raise ProviderTimeout(f"Europe PMC request timed out after {timeout_s}s") from exc
            raise ProviderUnavailable(f"Could not reach Europe PMC: {name}") from exc

        status = getattr(response, "status_code", None)
        if status == 429:
            raise ProviderRateLimited("Europe PMC rate limit reached (HTTP 429)")
        if status is not None and status >= 500:
            raise ProviderHTTPError(f"Europe PMC server error (HTTP {status})")
        if status is not None and status >= 400:
            raise ProviderHTTPError(f"Europe PMC request rejected (HTTP {status})")

        try:
            payload = response.json()
        except Exception as exc:
            raise ProviderMalformed("Europe PMC returned a non-JSON response") from exc

        if not isinstance(payload, dict):
            raise ProviderMalformed("Europe PMC response was not a JSON object")
        results = payload.get("resultList", {})
        if not isinstance(results, dict):
            raise ProviderMalformed("Europe PMC resultList had an unexpected shape")
        entries = results.get("result", [])
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            raise ProviderMalformed("Europe PMC result list was not an array")

        retrieved_at = _utc_now()
        records = []
        for rank, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            record = self._to_record(entry, retrieved_at, rank)
            if record is not None:
                records.append(record)
        return records

    @staticmethod
    def _to_record(entry: dict, retrieved_at: str, rank: int) -> Optional[LiveRecord]:
        title = clean_text(entry.get("title"))
        abstract = clean_text(entry.get("abstractText"))
        if not title and not abstract:
            # A record with no usable text cannot support any quotation.
            return None

        raw_pmid = entry.get("pmid")
        pmid = str(raw_pmid).strip() if raw_pmid not in (None, "") else None
        if pmid and not pmid.isdigit():
            pmid = None  # never present a malformed identifier as a real one

        year = None
        raw_year = entry.get("pubYear")
        try:
            year = int(str(raw_year)[:4]) if raw_year not in (None, "") else None
        except (TypeError, ValueError):
            year = None

        pub_types = ()
        type_list = entry.get("pubTypeList")
        if isinstance(type_list, dict):
            values = type_list.get("pubType")
            if isinstance(values, list):
                pub_types = tuple(str(v) for v in values if v)
            elif isinstance(values, str) and values:
                pub_types = (values,)

        url = None
        if pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        elif entry.get("doi"):
            url = f"https://doi.org/{entry['doi']}"

        return LiveRecord(
            source_id=pmid,
            provider=PROVIDER_EUROPEPMC,
            title=title,
            abstract=abstract,
            year=year,
            url=url,
            journal=clean_text(entry.get("journalTitle")) or None,
            pub_types=pub_types,
            doi=(str(entry.get("doi")).strip() or None) if entry.get("doi") else None,
            retrieved_at=retrieved_at,
            provider_rank=rank,
        )


PROVIDERS: dict = {PROVIDER_EUROPEPMC: EuropePMCProvider}


def get_provider(name: Optional[str] = None):
    key = (name or configured_provider_name()).lower()
    factory = PROVIDERS.get(key)
    if factory is None:
        raise ProviderError(f"Unknown provider '{key}'", kind="unknown_provider")
    return factory()


# --------------------------------------------------------------------------- #
# TTL cache
# --------------------------------------------------------------------------- #

class TTLCache:
    """Bounded TTL cache with injectable clock, so expiry is testable without sleeps.

    Only successful retrievals are stored. A provider failure is never cached, so
    a transient outage cannot be replayed as a successful empty result.
    """

    def __init__(self, ttl_s: float = DEFAULT_CACHE_TTL_S, max_entries: int = 128,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl_s = float(ttl_s)
        self.max_entries = max(1, int(max_entries))
        self._clock = clock
        self._store: dict = {}

    @staticmethod
    def make_key(provider: str, query: str, limit: int) -> tuple:
        """Exact, normalised key. No substring or prefix matching is ever used."""
        return (
            LIVE_SCHEMA_VERSION,
            (provider or "").lower(),
            _WS_RE.sub(" ", (query or "").strip().lower()),
            int(limit),
        )

    def get(self, key: tuple):
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: tuple, value) -> None:
        if len(self._store) >= self.max_entries:
            oldest = min(self._store.items(), key=lambda kv: kv[1][0])
            del self._store[oldest[0]]
        self._store[key] = (self._clock() + self.ttl_s, value)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


_CACHE = TTLCache()


def reset_cache() -> None:
    """Test/ops hook: drop all cached live responses."""
    _CACHE.clear()


# --------------------------------------------------------------------------- #
# Deduplication
# --------------------------------------------------------------------------- #

def deduplicate(records: list) -> tuple:
    """Collapse records that describe the same source.

    Keyed on the stable identifier when present. Two records sharing a PMID are
    one study unit: counting them twice would overstate independent evidence.

    Records with no identifier cannot be safely deduplicated; they are kept but
    counted separately so callers can report the uncertainty instead of hiding it.
    """
    by_id: dict = {}
    unidentified: list = []
    for record in records:
        if record.source_id:
            if record.source_id not in by_id:
                by_id[record.source_id] = record
        else:
            unidentified.append(record)
    deduped = list(by_id.values()) + unidentified
    return deduped, len(unidentified)


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def retrieve_for_disease(
    disease_name: str,
    candidate_drugs: Optional[list] = None,
    *,
    synonyms: Optional[list] = None,
    provider=None,
    provider_name: Optional[str] = None,
    limit: Optional[int] = None,
    timeout_s: Optional[float] = None,
    cache: Optional[TTLCache] = None,
    use_cache: bool = True,
    retrieved_at: Optional[str] = None,
) -> RetrievalOutcome:
    """Retrieve live literature for a disease and bind it to specific candidates.

    Returns a :class:`RetrievalOutcome` whose ``status`` distinguishes success
    with results, success with nothing relevant, and provider failure. The caller
    must not collapse these into one outcome.
    """
    name = clean_text(disease_name)
    limit = configured_max_results() if limit is None else max(1, min(int(limit), HARD_MAX_RESULTS))
    timeout_s = configured_timeout_s() if timeout_s is None else float(timeout_s)
    cache = cache if cache is not None else _CACHE
    timestamp = retrieved_at or _utc_now()
    drugs = [d for d in (candidate_drugs or []) if d and str(d).strip()]

    outcome = RetrievalOutcome(
        status=LIVE_STATUS_DISABLED,
        provider=(provider_name or configured_provider_name()),
        query="",
        cache_ttl_s=cache.ttl_s,
        retrieved_at=timestamp,
    )

    if not name:
        outcome.status = LIVE_STATUS_NO_RESULTS
        outcome.limitations.append("No disease name was supplied, so no live search was performed.")
        return outcome

    query = build_query(name, synonyms)
    outcome.query = query
    if not query:
        outcome.status = LIVE_STATUS_NO_RESULTS
        outcome.limitations.append("The disease name normalised to an empty query.")
        return outcome

    key = TTLCache.make_key(outcome.provider, query, limit)

    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            # Deep-copy before returning. Handing back the stored object by
            # reference would let a caller's mutation (including the
            # from_cache flag itself) corrupt the cached entry and any other
            # caller still holding it.
            served = copy.deepcopy(cached)
            served.from_cache = True
            return served

    try:
        if provider is None:
            provider = get_provider(outcome.provider)
        records = provider.search(query, limit, timeout_s)
    except ProviderError as exc:
        # Failure is surfaced, never cached, and never reported as "no results".
        outcome.status = LIVE_STATUS_FAILED
        outcome.error = exc.as_dict()
        outcome.limitations.append(
            "The literature provider could not be reached. This is a retrieval "
            "failure, not evidence that no literature exists."
        )
        return outcome
    except Exception as exc:  # defensive: an unexpected adapter bug is still a failure
        outcome.status = LIVE_STATUS_FAILED
        outcome.error = {"kind": "unexpected_error", "message": type(exc).__name__}
        outcome.limitations.append(
            "The literature provider raised an unexpected error. This is a "
            "retrieval failure, not evidence that no literature exists."
        )
        return outcome

    outcome.records_retrieved = len(records)
    if not records:
        outcome.status = LIVE_STATUS_NO_RESULTS
        outcome.limitations.append(
            f"The provider responded successfully and returned no records for "
            f"this disease. Absence of indexed literature is not evidence of "
            f"ineffectiveness."
        )
        if use_cache:
            cache.set(key, copy.deepcopy(outcome))
        return outcome

    deduped, unidentified = deduplicate(records)
    outcome.records = deduped
    outcome.records_after_dedup = len(deduped)
    outcome.records_without_identifier = unidentified
    if unidentified:
        outcome.limitations.append(
            f"{unidentified} retrieved record(s) carried no stable identifier and "
            f"could not be deduplicated or cited by identifier."
        )

    # Candidate-specific binding. A disease-only paper is not evidence for a drug.
    passages_by_drug: dict = {}
    relevant_total = 0
    for drug in drugs:
        matched = [r for r in deduped if record_mentions_drug(r, drug)]
        if not matched:
            continue
        relevant_total += len(matched)
        passages = []
        for i, record in enumerate(matched):
            passages.append(_record_to_passage(record, name, drug, i, len(matched)))
        passages_by_drug[drug] = passages

    outcome.relevant_records = relevant_total
    outcome.passages_by_drug = passages_by_drug

    if not passages_by_drug:
        outcome.status = LIVE_STATUS_NO_RELEVANT
        if not drugs:
            outcome.limitations.append(
                "No candidate drugs were supplied, so retrieved records could not "
                "be bound to a specific candidate."
            )
        else:
            outcome.limitations.append(
                f"{len(deduped)} record(s) were retrieved for this disease, but none "
                f"name any of the {len(drugs)} graph candidates. They are not "
                f"presented as candidate evidence."
            )
    else:
        outcome.status = LIVE_STATUS_OK

    if use_cache:
        # Store a snapshot, not the object being returned. Otherwise the caller
        # holds a reference to the cached entry and any later mutation of it
        # corrupts the cache for every subsequent request.
        cache.set(key, copy.deepcopy(outcome))
    return outcome


def _record_to_passage(record: LiveRecord, disease_name: str, drug: str,
                       position: int, total: int) -> dict:
    """Convert a live record into a passage-shaped dict the pipeline can score.

    Marked ``source_mode='live_retrieval'`` so live evidence is never confused
    with the indexed local corpus.
    """
    # Deterministic relevance signal from provider ordering, bounded to (0, 1].
    relevance = 1.0 - (position / (total + 1)) if total else 0.5
    return {
        "pmid": record.source_id,
        "title": record.title,
        "text": record.text(),
        "disease": disease_name,
        "drug": drug,
        "year": record.year,
        "url": record.url,
        "journal": record.journal,
        "pub_type": record.study_type,
        "source_mode": "live_retrieval",
        "provider": record.provider,
        "retrieved_at": record.retrieved_at,
        "retrieval_score": round(relevance, 6),
        "study_weight": 0.3,
        "recency_bonus": 0.0,
        "combined_score": round(relevance, 6),
    }
