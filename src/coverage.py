"""Disease coverage: what the knowledge graph knows vs what the local corpus holds.

The distinction matters and is easy to conflate:

* The **knowledge graph** (EveryCure) resolves a very large disease vocabulary and
  can propose candidate drugs for most of it.
* The **local literature corpus** covers only a small subset of those diseases.

A disease can therefore be *resolvable with candidates* and still have **no
disease-specific literature at all**. Presenting passages from unrelated diseases
as evidence for it would be fabrication, so coverage is modelled explicitly here
and enforced in the pipeline.

Nothing in this module invents data: every count is computed from the files that
are actually loaded.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")

#: Bumped whenever the corpus or the scoring inputs change, so cached results
#: can be recognised as belonging to an older evidence set.
CORPUS_SCHEMA_VERSION = "2026-10-corpus-v2"

#: Where a response's evidence came from.
EVIDENCE_SCOPE_LOCAL = "local_corpus"
EVIDENCE_SCOPE_LIVE = "live_retrieval"
EVIDENCE_SCOPE_NONE = "none"
EVIDENCE_SCOPE_EXPLORATORY = "exploratory_global"


def _read_json(name: str):
    path = os.path.join(_DATA, name)
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


#: Possessive "'s" is removed BEFORE punctuation stripping, otherwise
#: "Alzheimer's disease" would normalise to "alzheimer s disease" and fail to
#: match the canonical "alzheimer disease".
_POSSESSIVE = re.compile(r"['\u2019]s\b")


def normalize_disease_key(value: Optional[str]) -> str:
    """Canonical comparison key for a disease name.

    Lowercases, drops possessives and punctuation, and collapses whitespace so
    that "Alzheimer's disease", "Alzheimer disease" and "alzheimer  disease" all
    compare equal. Used for coverage checks and cache identity — never for
    substring matching.
    """
    text = (value or "").lower()
    text = _POSSESSIVE.sub("", text)
    for ch in "'\u2019`,-–—()[]{}:;./":
        text = text.replace(ch, " ")
    return " ".join(text.split())


@lru_cache(maxsize=1)
def _corpus_index() -> dict:
    """Index the local corpus once: diseases, abstracts, and per-disease counts."""
    passages = _read_json("passages.json") or []
    by_disease: dict[str, int] = {}
    pmids: set[str] = set()
    for p in passages:
        key = normalize_disease_key(p.get("disease"))
        if not key:
            continue
        by_disease[key] = by_disease.get(key, 0) + 1
        pmid = p.get("pmid")
        if pmid:
            pmids.add(str(pmid))
    return {
        "passage_count": len(passages),
        "unique_pmids": len(pmids),
        "by_disease": by_disease,
        "disease_count": len(by_disease),
    }


@lru_cache(maxsize=1)
def _kg_index() -> dict:
    """Index the knowledge graph lookup once."""
    diseases = _read_json("disease_lookup.json") or {}
    candidates = _read_json("candidates.json") or {}
    with_candidates = sum(1 for v in candidates.values() if v.get("c"))
    return {
        "disease_count": len(diseases),
        "diseases_with_candidates": with_candidates,
    }


def local_passage_count(disease_name: Optional[str]) -> int:
    """How many local passages are tagged with this disease (0 if none)."""
    return _corpus_index()["by_disease"].get(normalize_disease_key(disease_name), 0)


def has_local_literature(disease_name: Optional[str]) -> bool:
    """True only when the local corpus actually holds passages for this disease."""
    return local_passage_count(disease_name) > 0


def coverage_metadata() -> dict:
    """Coverage facts for the health endpoint.

    Reports graph vocabulary and local literature coverage as **separate**
    numbers, because they are separate things.
    """
    corpus = _corpus_index()
    kg = _kg_index()
    return {
        "kg_disease_count": kg["disease_count"],
        "kg_diseases_with_candidates": kg["diseases_with_candidates"],
        "local_literature_disease_count": corpus["disease_count"],
        "local_abstract_count": corpus["passage_count"],
        "local_unique_pmid_count": corpus["unique_pmids"],
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        # Phase 5: live retrieval now exists and is reported honestly from its own
        # configuration, so the frontend can enable or hide the affordance.
        "live_retrieval_enabled": _live_retrieval_enabled(),
        "live_retrieval_provider": _live_provider_name(),
    }


def _live_retrieval_enabled() -> bool:
    """Read the live-retrieval switch without importing at module scope.

    Imported lazily so coverage stays usable even if the live module or its HTTP
    dependency is unavailable.
    """
    try:
        try:
            from . import live_retrieval
        except (ImportError, ValueError):
            from src import live_retrieval
        return bool(live_retrieval.live_retrieval_enabled())
    except Exception:
        return False


def _live_provider_name() -> Optional[str]:
    try:
        try:
            from . import live_retrieval
        except (ImportError, ValueError):
            from src import live_retrieval
        return live_retrieval.configured_provider_name()
    except Exception:
        return None
