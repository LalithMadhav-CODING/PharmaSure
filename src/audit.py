"""Citation-Level Counterfactual Evidence Auditing (CCEA).

Answers, for each drug-disease candidate: *which source studies influence the
candidate's evidence score, and how does that score and its evidence-rank change
when one contributing study is removed?*

Design constraints (see docs/EVIDENCE_AUDIT.md for the full methodology):

* **Additive.** Nothing here changes candidate generation, the baseline score,
  or the existing API contract. The audit is attached as an extra field.
* **Reuses the authoritative scorer.** Every baseline and counterfactual score is
  produced by ``retrieval.evidence_score`` — the same function the product
  already uses. There is deliberately no second implementation that could drift.
* **Deterministic.** No LLM calls, no re-embedding, no hash-order dependence.
  Same evidence + same config => same audit.
* **Honest about limits.** Cross-PMID study independence cannot be verified from
  this corpus, so it is reported as unverified rather than assumed. Evidence
  direction is rule-based and unvalidated; records that no rule matches are
  labelled ``not_classified`` rather than guessed.

The audit is a *sensitivity analysis of the current evidence set*. It is not a
simulation of biology, and stability is not clinical validity.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

try:
    from . import retrieval
except (ImportError, ValueError):  # pragma: no cover - direct execution
    from src import retrieval


# --------------------------------------------------------------------------- #
# Versioning / configuration (single source of truth)
# --------------------------------------------------------------------------- #

AUDIT_VERSION = "1.0"
AUDIT_METHOD = "leave_one_independent_study_out"

# Identifier for the scoring function the audit reuses. If that function's
# formula or weights change, bump this so cached audits can be invalidated.
SCORING_FUNCTION_ID = "retrieval.evidence_score:Vx(0.35R+0.35P+0.30Q)"
DIRECTION_METHOD = "lexical_rules"
DIRECTION_METHOD_VERSION = "1.0"

#: Thresholds used only for *descriptive* labels. Documented, centralised, and
#: explicitly experimental — they are not evidence of anything clinical.
STABILITY_CONFIG = {
    # Removing one study moves the score by at least this much => the ranking is
    # sensitive to that source.
    "single_source_score_delta": 0.05,
    # ...or moves the evidence-rank by at least this many places.
    "single_source_rank_delta": 2,
}

#: Tie-break for evidence-rank: higher score wins; equal scores fall back to the
#: candidate's original knowledge-graph position so ordering is always stable.
TIE_BREAK = "score_desc_then_kg_order"


# --------------------------------------------------------------------------- #
# Status / label vocabularies
# --------------------------------------------------------------------------- #

AUDIT_STATUS_COMPLETE = "complete"
AUDIT_STATUS_PARTIAL = "partial"
AUDIT_STATUS_NOT_AUDITABLE = "not_auditable"
AUDIT_STATUS_INSUFFICIENT = "insufficient_independent_studies_for_stability_test"
AUDIT_STATUS_ERROR = "audit_failed"

DIRECTION_LABELS = (
    "supportive",
    "contradictory",
    "null_finding",
    "uncertain",
    "not_classified",
)

INDEPENDENCE_LIKELY = "likely_independent"
INDEPENDENCE_SAME = "likely_same_study"
INDEPENDENCE_UNKNOWN = "unknown"

GROUPING_PMID_ONLY = "pmid_only"
GROUPING_SOURCE_ID = "source_id_fallback"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def normalize_key(value: Any) -> str:
    """Whitespace/lowercase normalisation used for matching drug and disease."""
    return " ".join(str(value or "").lower().split())


def normalize_pmid(pmid: Any) -> Optional[str]:
    """Return a digits-only PMID, or None when the value is not a valid PMID.

    Guards URL construction: we never build a PubMed link from unvalidated input.
    """
    if pmid is None:
        return None
    text = str(pmid).strip()
    if not text or not text.isdigit():
        return None
    return text


def pubmed_url(pmid: Any) -> Optional[str]:
    """Canonical PubMed URL for a validated PMID, else None."""
    clean = normalize_pmid(pmid)
    return f"https://pubmed.ncbi.nlm.nih.gov/{clean}/" if clean else None


# --------------------------------------------------------------------------- #
# Evidence-direction classification (rule-based, conservative, experimental)
# --------------------------------------------------------------------------- #
#
# These rules look for *explicit* statements only. They are deliberately narrow:
# a paper that merely mentions the drug is never labelled supportive. No rule
# match yields ``not_classified``. The matched snippet is always stored so a
# human can check the label — these labels are machine-generated and have NOT
# been validated against expert adjudication.

_NULL_RULES: list[tuple[str, str]] = [
    ("null_no_significant", r"\bno (?:statistically )?significant "
                           r"(?:difference|effect|association|benefit|improvement|reduction)\b"),
    ("null_not_associated", r"\b(?:was|were|is|are) not (?:significantly )?associated with\b"),
    ("null_not_effective", r"\b(?:was|were|is|are) not (?:more )?effective\b"),
    ("null_no_evidence", r"\bno evidence (?:of|for|that)\b"),
    ("null_failed_to", r"\bfailed to (?:show|demonstrate|improve|reduce|detect)\b"),
    ("null_ineffective", r"\bineffective\b"),
]

_CONTRADICTORY_RULES: list[tuple[str, str]] = [
    # NOTE: harm/risk statements are deliberately NOT listed here. A safety
    # concern is not evidence against efficacy, so risk language is captured
    # separately by _SAFETY_RULES and never collapsed into `contradictory`.
    ("contra_worsened", r"\b(?:worsened|exacerbated|aggravated)\b"),
    ("contra_no_benefit_arm", r"\b(?:did not|failed to) (?:provide|offer|confer) (?:any )?benefit\b"),
    ("contra_no_superiority", r"\b(?:no|not) (?:superior|better) (?:to|than)\b"),
]

#: Safety findings are recorded as their own signal, separate from direction.
_SAFETY_RULES: list[tuple[str, str]] = [
    ("safety_increased_risk", r"\b(?:was|were) associated with (?:an? )?(?:increased|higher|greater) risk\b"),
    ("safety_adverse_events", r"\b(?:adverse (?:effect|event)s?|serious adverse)\b"),
    ("safety_toxicity", r"\b(?:toxicity|hepatotoxicity|nephrotoxicity|cardiotoxicity)\b"),
    ("safety_discontinuation", r"\b(?:discontinued|withdrawn) (?:due to|because of) (?:adverse|toxicity|side effects)\b"),
]

_SUPPORTIVE_RULES: list[tuple[str, str]] = [
    ("supp_improved", r"\b(?:significantly )?(?:improved|ameliorated|attenuated)\b"),
    ("supp_reduced", r"\b(?:significantly )?(?:reduced|decreased|lowered) "
                     r"(?:the )?(?:risk|severity|frequency|duration|symptoms|levels|mortality)\b"),
    ("supp_effective", r"\b(?:was|were|is|are) (?:effective|efficacious|beneficial) "
                       r"(?:in|for|at|against)\b"),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _matching_snippet(text: str, pattern: str, *, max_len: int = 240) -> Optional[str]:
    """Return the sentence containing the first match of ``pattern``, else None."""
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        if re.search(pattern, sentence, flags=re.IGNORECASE):
            snippet = sentence.strip()
            return snippet[:max_len]
    return None


def classify_direction(passage_text: str) -> dict:
    """Classify a passage's evidence direction using explicit textual rules.

    Returns ``{"evidence_direction", "direction_rationale", "direction_snippet",
    "direction_rule", "direction_method", "direction_method_version"}``.

    Null findings take precedence over contradictions, which take precedence over
    supportive statements — an explicit "no significant difference" is a stronger
    and more specific signal than a generic efficacy verb appearing nearby.
    """
    text = passage_text or ""

    for rule_id, pattern in _NULL_RULES:
        snippet = _matching_snippet(text, pattern)
        if snippet:
            return {
                "evidence_direction": "null_finding",
                "direction_rationale": "Source text explicitly reports a null or "
                                       "non-significant result.",
                "direction_snippet": snippet,
                "direction_rule": rule_id,
                "direction_method": DIRECTION_METHOD,
                "direction_method_version": DIRECTION_METHOD_VERSION,
            }

    for rule_id, pattern in _CONTRADICTORY_RULES:
        snippet = _matching_snippet(text, pattern)
        if snippet:
            return {
                "evidence_direction": "contradictory",
                "direction_rationale": "Source text reports harm or absence of "
                                       "benefit for the hypothesis under test.",
                "direction_snippet": snippet,
                "direction_rule": rule_id,
                "direction_method": DIRECTION_METHOD,
                "direction_method_version": DIRECTION_METHOD_VERSION,
            }

    for rule_id, pattern in _SUPPORTIVE_RULES:
        snippet = _matching_snippet(text, pattern)
        if snippet:
            return {
                "evidence_direction": "supportive",
                "direction_rationale": "Source text reports a positive effect; "
                                       "not verified against the study's primary endpoint.",
                "direction_snippet": snippet,
                "direction_rule": rule_id,
                "direction_method": DIRECTION_METHOD,
                "direction_method_version": DIRECTION_METHOD_VERSION,
            }

    return {
        "evidence_direction": "not_classified",
        "direction_rationale": "No explicit directional statement matched a "
                               "defined rule.",
        "direction_snippet": None,
        "direction_rule": None,
        "direction_method": DIRECTION_METHOD,
        "direction_method_version": DIRECTION_METHOD_VERSION,
    }


# --------------------------------------------------------------------------- #
# Source-level evidence ledger (FR-02)
# --------------------------------------------------------------------------- #

def detect_safety_signal(passage_text: str) -> dict:
    """Detect explicit safety/harm language, kept separate from direction.

    A safety finding is not evidence against efficacy, so it must never be folded
    into the direction label. Returns ``{"safety_signal": bool,
    "safety_snippet": str|None, "safety_rule": str|None}``.
    """
    for rule_id, pattern in _SAFETY_RULES:
        snippet = _matching_snippet(passage_text, pattern)
        if snippet:
            return {"safety_signal": True, "safety_snippet": snippet, "safety_rule": rule_id}
    return {"safety_signal": False, "safety_snippet": None, "safety_rule": None}


def _claims_by_passage_id(claims: Iterable[dict]) -> dict[str, list[dict]]:
    """Map passage-id (as string) -> claims that cite it."""
    index: dict[str, list[dict]] = {}
    for claim in claims or []:
        for cid in claim.get("citation_ids") or claim.get("citations") or []:
            index.setdefault(str(cid), []).append(claim)
    return index


def build_evidence_ledger(
    drug_passages: list[dict],
    drug_name: str,
    disease: dict,
    claims: Optional[list[dict]] = None,
) -> list[dict]:
    """Build one structured record per retrieved passage for this candidate.

    ``drug_passages`` are the already-retrieved, already-verified passage dicts
    from the pipeline (they carry ``retrieval_score``, ``pub_type``, ``pmid`` and
    ``id``). Nothing is re-fetched or re-embedded here.
    """
    claims_index = _claims_by_passage_id(claims or [])
    records: list[dict] = []

    for position, passage in enumerate(drug_passages):
        passage_id = passage.get("id")
        pmid = normalize_pmid(passage.get("pmid"))
        warnings: list[str] = []

        if not pmid:
            warnings.append("missing_or_invalid_pmid")
        if not passage.get("year"):
            warnings.append("missing_publication_year")
        if not passage.get("pub_type"):
            warnings.append("missing_publication_type")

        related = claims_index.get(str(passage_id), [])
        quote = next((c.get("quote") for c in related if c.get("quote")), None)
        statuses = [c.get("verification_status") for c in related if c.get("verification_status")]
        # The passage is "verified" only if every claim citing it verified.
        if not statuses:
            quote_status = "not_cited"
            source_status = "not_cited"
        else:
            quote_status = "verified" if all(s == "verified" for s in statuses) else "needs_review"
            source_status = quote_status

        direction = classify_direction(passage.get("text", ""))
        safety = detect_safety_signal(passage.get("text", ""))

        record = {
            "source_id": f"{drug_name}::{pmid or 'nopmid'}::{passage_id}::{position}",
            "pmid": pmid,
            "pubmed_url": pubmed_url(pmid),
            "drug": drug_name,
            "disease_id": (disease or {}).get("id"),
            "disease": (disease or {}).get("name"),
            "passage_id": passage_id,
            "quote": quote,
            "citation_verified": quote_status,
            "source_identity_status": source_status,
            "quote_verification_status": quote_status,
            "publication_year": passage.get("year"),
            "publication_types": [passage.get("pub_type")] if passage.get("pub_type") else [],
            "included_in_score": True,
            "exclusion_reason": None,
            "metadata_warnings": warnings,
            # Study grouping is filled in by group_study_units().
            "study_group_id": None,
            "study_grouping_method": None,
            "study_independence_status": INDEPENDENCE_UNKNOWN,
            **direction,
            **safety,
        }
        records.append(record)

    return records


# --------------------------------------------------------------------------- #
# Study grouping / deduplication (FR-03, 4.2)
# --------------------------------------------------------------------------- #

def group_study_units(records: list[dict]) -> list[dict]:
    """Group ledger records into study units, deterministically.

    **Policy (chosen and applied consistently):** records sharing a PMID form one
    study unit, because they are by definition the same publication. Records
    without a usable PMID fall back to their own ``source_id`` so they are never
    silently merged with an unrelated record.

    **Known limitation:** this corpus carries no metadata linking distinct PMIDs
    to a single underlying study (no trial registration IDs, no author sets).
    Cross-PMID independence therefore CANNOT be established, so every unit is
    reported with ``study_independence_status = "unknown"`` and the audit emits a
    warning. We do not claim that different PMIDs are independent experiments.
    """
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []

    for record in records:
        if record.get("pmid"):
            key = f"pmid:{record['pmid']}"
            method = GROUPING_PMID_ONLY
        else:
            key = f"src:{record['source_id']}"
            method = GROUPING_SOURCE_ID
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        record["study_group_id"] = key
        record["study_grouping_method"] = method
        buckets[key].append(record)

    # Deterministic ordering independent of dict insertion/hash order.
    order.sort()

    groups: list[dict] = []
    for key in order:
        members = buckets[key]
        pmids = sorted({m["pmid"] for m in members if m.get("pmid")})
        types = sorted({t for m in members for t in (m.get("publication_types") or [])})
        groups.append({
            "study_group_id": key,
            "pmids": pmids,
            "passage_ids": sorted(
                [m["passage_id"] for m in members if m.get("passage_id") is not None],
                key=lambda v: (isinstance(v, str), str(v)),
            ),
            "record_count": len(members),
            "publication_year": next((m.get("publication_year") for m in members
                                      if m.get("publication_year")), None),
            "publication_types": types,
            "evidence_direction": _dominant_direction(members),
            "study_grouping_method": members[0].get("study_grouping_method"),
            "study_independence_status": INDEPENDENCE_UNKNOWN,
            "has_valid_pmid": bool(pmids),
            # A narrative review summarises other work; it is NOT an independent
            # experiment, so the audit surfaces it rather than counting it as one.
            "is_review": bool(types) and all(t == "review" for t in types),
            "safety_signal": any(m.get("safety_signal") for m in members),
        })
    return groups


def _dominant_direction(members: list[dict]) -> str:
    """Collapse a unit's records to one label; mixed labels become 'uncertain'."""
    labels = {m.get("evidence_direction") for m in members}
    labels.discard(None)
    if len(labels) == 1:
        return str(next(iter(labels)))
    if not labels:
        return "not_classified"
    # A unit reporting both a null and a positive result is genuinely mixed.
    return "uncertain"


# --------------------------------------------------------------------------- #
# Baseline scoring (FR-05) — reuses the authoritative function
# --------------------------------------------------------------------------- #

def score_passages(passages: list[dict], drug_name: str,
                   verified_claims: int = 0, total_claims: int = 0) -> dict:
    """Score a passage set with the product's own scorer, normalising output.

    ``retrieval.evidence_score`` returns a payload WITHOUT ``breakdown`` when the
    passage list is empty, so we normalise here to keep the audit's shape stable.
    The numeric result is exactly what that function returns.

    The verification counts are threaded through so the audit's baseline uses the
    same function AND the same inputs as the product. Passing different inputs here
    would make the audit describe a different score than the one displayed.
    """
    if not passages:
        return {
            "score": 0.0,
            "tier": "Preliminary",
            "support": 0,
            "best_study_type": "none",
            "verification": 0.0,
            "breakdown": {
                "verification": 0.0, "verification_role": "multiplier",
                "verified_claims": verified_claims, "total_claims": total_claims,
                "evidence_strength": 0.0,
                "relevance": 0.0, "relevance_weight": 0.35,
                "support": 0.0, "support_weight": 0.35,
                "study_quality": 0.0, "study_quality_weight": 0.30,
            },
        }
    return retrieval.evidence_score(passages, drug_name,
                                    verified_claims=verified_claims,
                                    total_claims=total_claims)


def claims_verification_counts(claims: Optional[list[dict]]) -> tuple:
    """(verified, total) for a candidate's claims."""
    claims = claims or []
    verified = sum(1 for c in claims if (c or {}).get("verification_status") == "verified")
    return verified, len(claims)


# --------------------------------------------------------------------------- #
# Evidence ranking (4.5)
# --------------------------------------------------------------------------- #

def compute_evidence_ranks(entries: list[dict]) -> dict[str, int]:
    """Rank candidates by evidence score, with a deterministic tie-break.

    ``entries`` is a list of ``{"key": <candidate key>, "score": float,
    "kg_order": int}``. Ties break on the candidate's original knowledge-graph
    position, so the ordering is reproducible.

    NOTE: this is an **evidence rank**, computed over the retrieved candidate set.
    It is NOT the EveryCure matrix rank the UI displays as ``rank``. The two are
    reported separately and must never be conflated.
    """
    ordered = sorted(entries, key=lambda e: (-float(e.get("score") or 0.0),
                                             int(e.get("kg_order") or 0)))
    return {e["key"]: i + 1 for i, e in enumerate(ordered)}


# --------------------------------------------------------------------------- #
# Leave-one-study-out (FR-06, 4.4)
# --------------------------------------------------------------------------- #

def leave_one_study_out(
    drug_passages: list[dict],
    drug_name: str,
    groups: list[dict],
    *,
    baseline_score: float,
    baseline_rank: int,
    peer_scores: dict[str, float],
    peer_kg_order: dict[str, int],
    candidate_key: str,
    verified_claims: int = 0,
    total_claims: int = 0,
    tie_break: str = TIE_BREAK,
) -> tuple[list[dict], list[str]]:
    """Remove each study unit in turn and rescore with the same function.

    Returns ``(counterfactuals, warnings)``. A failure in one scenario never
    discards the successful ones.
    """
    counterfactuals: list[dict] = []
    warnings: list[str] = []

    for group in groups:
        gid = group["study_group_id"]
        group_pmids = set(group.get("pmids") or [])
        group_passage_ids = set(str(p) for p in (group.get("passage_ids") or []))

        # Remove by PMID when we have one (removes every passage of that study);
        # otherwise fall back to the specific passage id.
        if group_pmids:
            remaining = [p for p in drug_passages
                         if normalize_pmid(p.get("pmid")) not in group_pmids]
        else:
            remaining = [p for p in drug_passages
                         if str(p.get("id")) not in group_passage_ids]

        removed_count = len(drug_passages) - len(remaining)
        entry: dict[str, Any] = {
            "study_group_id": gid,
            "pmids": group.get("pmids") or [],
            "passage_ids": group.get("passage_ids") or [],
            "removed_passage_count": removed_count,
            "evidence_direction": group.get("evidence_direction"),
            "publication_year": group.get("publication_year"),
            "publication_types": group.get("publication_types") or [],
            "baseline_score": round(float(baseline_score), 6),
            "baseline_rank": baseline_rank,
            "status": "ok",
        }

        if removed_count == 0:
            entry["status"] = "no_matching_passages_removed"
            warnings.append(f"group {gid}: no passages matched for removal")
            entry.update({
                "counterfactual_score": None, "score_delta": None,
                "counterfactual_rank": None, "rank_delta": None,
                "below_evidence_threshold": None, "score_undefined": None,
                "error": "no_matching_passages_removed",
            })
            counterfactuals.append(entry)
            continue

        try:
            cf = score_passages(remaining, drug_name,
                                verified_claims=verified_claims,
                                total_claims=total_claims)
            cf_score = float(cf["score"])

            # Re-rank over the SAME candidate set: only this candidate's score
            # changes, so peers keep their scores and the comparison stays valid.
            scores = dict(peer_scores)
            scores[candidate_key] = cf_score
            entries = [{"key": k, "score": v, "kg_order": peer_kg_order.get(k, 0)}
                       for k, v in scores.items()]
            ranks = compute_evidence_ranks(entries)
            cf_rank = ranks[candidate_key]

            entry.update({
                # Positive score_delta => removing this study LOWERED the score.
                "score_delta": round(float(baseline_score) - cf_score, 6),
                # Positive rank_delta => candidate moved DOWN the ranking.
                "rank_delta": cf_rank - baseline_rank,
                "counterfactual_score": round(cf_score, 6),
                "counterfactual_rank": cf_rank,
                "counterfactual_tier": cf.get("tier"),
                "counterfactual_support": cf.get("support"),
                "below_evidence_threshold": bool(cf_score <= 0.0),
                "score_undefined": False,
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001 - one bad scenario must not kill the audit
            entry["status"] = "error"
            entry.update({
                "counterfactual_score": None, "score_delta": None,
                "counterfactual_rank": None, "rank_delta": None,
                "below_evidence_threshold": None, "score_undefined": None,
                "error": f"{type(exc).__name__}: {exc}",
            })
            warnings.append(f"group {gid}: counterfactual failed ({type(exc).__name__})")

        counterfactuals.append(entry)

    return counterfactuals, warnings


# --------------------------------------------------------------------------- #
# Aggregation (4.6, 4.7, FR-07, FR-08)
# --------------------------------------------------------------------------- #

def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 6)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 6)


def summarize_counterfactuals(
    counterfactuals: list[dict],
    *,
    baseline_score: float,
    baseline_rank: int,
    eligible_study_count: int,
    tie_break: str = TIE_BREAK,
) -> dict:
    """Aggregate leave-one-out results into stability metrics.

    Statistics are returned as ``None`` when there are too few observations —
    never as a fabricated zero.
    """
    ok = [c for c in counterfactuals if c.get("status") == "ok"]
    failed = [c for c in counterfactuals if c.get("status") != "ok"]

    if not ok:
        return {
            "status": AUDIT_STATUS_INSUFFICIENT if eligible_study_count <= 1
            else AUDIT_STATUS_PARTIAL,
            "successful_counterfactuals": 0,
            "failed_counterfactuals": len(failed),
            "max_absolute_score_change": None,
            "mean_absolute_score_change": None,
            "median_absolute_score_change": None,
            "max_rank_movement": None,
            "rank_min": None,
            "rank_max": None,
            "rank_range": None,
            "source_with_max_score_influence": None,
            "source_with_max_rank_influence": None,
            "tie_break": tie_break,
        }

    score_deltas = [float(c["score_delta"]) for c in ok]
    abs_deltas = [abs(d) for d in score_deltas]
    rank_deltas = [int(c["rank_delta"]) for c in ok if c.get("rank_delta") is not None]
    cf_ranks = [int(c["counterfactual_rank"]) for c in ok
                if c.get("counterfactual_rank") is not None]

    max_score_idx = max(range(len(ok)), key=lambda i: abs_deltas[i])
    max_score_entry = ok[max_score_idx]

    max_rank_entry = None
    if rank_deltas:
        max_rank_entry = max(ok, key=lambda c: abs(int(c.get("rank_delta") or 0)))

    # A single source "dominates" only under the documented, experimental rule.
    dominant = [
        c for c in ok
        if abs(float(c["score_delta"])) >= STABILITY_CONFIG["single_source_score_delta"]
        or abs(int(c.get("rank_delta") or 0)) >= STABILITY_CONFIG["single_source_rank_delta"]
    ]

    if eligible_study_count <= 1:
        status = AUDIT_STATUS_INSUFFICIENT
    elif failed:
        status = AUDIT_STATUS_PARTIAL
    else:
        status = AUDIT_STATUS_COMPLETE

    return {
        "status": status,
        "successful_counterfactuals": len(ok),
        "failed_counterfactuals": len(failed),
        "max_absolute_score_change": round(max(abs_deltas), 6),
        "mean_absolute_score_change": round(sum(abs_deltas) / len(abs_deltas), 6),
        "median_absolute_score_change": _median(abs_deltas),
        "max_rank_movement": max((abs(int(c.get("rank_delta") or 0)) for c in ok), default=None),
        "rank_min": min(cf_ranks) if cf_ranks else None,
        "rank_max": max(cf_ranks) if cf_ranks else None,
        "rank_range": (max(cf_ranks) - min(cf_ranks)) if cf_ranks else None,
        "source_with_max_score_influence": {
            "study_group_id": max_score_entry["study_group_id"],
            "pmids": max_score_entry.get("pmids") or [],
            "score_delta": max_score_entry["score_delta"],
            "rank_delta": max_score_entry.get("rank_delta"),
        },
        "source_with_max_rank_influence": ({
            "study_group_id": max_rank_entry["study_group_id"],
            "pmids": max_rank_entry.get("pmids") or [],
            "score_delta": max_rank_entry["score_delta"],
            "rank_delta": max_rank_entry.get("rank_delta"),
        } if max_rank_entry else None),
        "single_source_dominated": bool(dominant),
        "single_source_dominated_count": len(dominant),
        "tie_break": tie_break,
    }


def summarize_directions(groups: list[dict]) -> dict:
    """Count study units per direction label (FR-08).

    Each study unit counts at most once per category, so repeated passages from
    one PMID never inflate the tally.
    """
    counts = {label: 0 for label in DIRECTION_LABELS}
    for group in groups:
        label = group.get("evidence_direction") or "not_classified"
        counts[label if label in counts else "not_classified"] += 1

    classified = sum(counts[l] for l in ("supportive", "contradictory", "null_finding"))
    total = len(groups)
    return {
        **counts,
        "eligible_study_units": total,
        "classified": classified,
        "unclassified": counts["not_classified"] + counts["uncertain"],
        "classified_fraction": round(classified / total, 4) if total else None,
        # "No contradiction retrieved" is NOT the same as "evidence is consistent".
        "conflicting_evidence_present": bool(
            (counts["supportive"] and counts["contradictory"])
            or (counts["supportive"] and counts["null_finding"])
            or (counts["contradictory"] and counts["null_finding"])
        ),
        "caveat": ("Direction labels are machine-generated by unvalidated lexical "
                   "rules; unclassified sources are not evidence of consistency."),
    }


# --------------------------------------------------------------------------- #
# Per-candidate audit
# --------------------------------------------------------------------------- #

def audit_candidate(
    *,
    drug_name: str,
    disease: dict,
    drug_passages: list[dict],
    claims: Optional[list[dict]],
    baseline_evidence: dict,
    candidate_key: str,
    baseline_rank: int,
    peer_scores: dict[str, float],
    peer_kg_order: dict[str, int],
) -> dict:
    """Produce the full audit payload for one candidate.

    Never raises: any internal failure is returned as an explicit ``audit_failed``
    status so a broken audit cannot take down the candidate result.
    """
    warnings: list[str] = []
    # The candidate's knowledge-graph origin, reported separately from the evidence
    # rank. Computed once so every exit path from this function reports the same
    # value instead of falling back to the evidence rank.
    candidate_graph_rank = (peer_kg_order.get(candidate_key) or 0) + 1
    try:
        ledger = build_evidence_ledger(drug_passages, drug_name, disease, claims)
        groups = group_study_units(ledger)

        # Same verification inputs the product used, so the audit's baseline is the
        # displayed score rather than a differently-computed one.
        _verified, _total = claims_verification_counts(claims)
        baseline = score_passages(drug_passages, drug_name,
                                  verified_claims=_verified, total_claims=_total)
        baseline_score = float(baseline["score"])

        if not groups:
            return _empty_audit(
                status=AUDIT_STATUS_NOT_AUDITABLE,
                reason="no_source_records_retrieved",
                warnings=["No retrieved passages are associated with this candidate."],
                baseline=baseline,
                baseline_rank=baseline_rank,
                ledger=ledger,
                groups=groups,
                input_record_count=len(drug_passages),
                graph_rank=candidate_graph_rank,
            )

        missing_pmid_groups = [g["study_group_id"] for g in groups if not g["has_valid_pmid"]]
        if missing_pmid_groups:
            warnings.append(
                f"{len(missing_pmid_groups)} study unit(s) have no valid PMID and "
                f"cannot be treated as independent studies."
            )
        review_units = [g["study_group_id"] for g in groups if g.get("is_review")]
        if review_units:
            warnings.append(
                f"{len(review_units)} study unit(s) are narrative reviews; a review "
                f"summarises other work and is not an independent experiment."
            )
        warnings.append(
            "Cross-PMID study independence cannot be verified from this corpus "
            "(no trial-registration or author metadata); distinct PMIDs are "
            "treated as separate units for sensitivity testing only."
        )

        if len(groups) == 1:
            return _empty_audit(
                status=AUDIT_STATUS_INSUFFICIENT,
                reason="only_one_study_unit",
                warnings=warnings + [
                    "Only one study unit contributes; stability cannot be assessed "
                    "and no robustness claim is made."
                ],
                baseline=baseline,
                baseline_rank=baseline_rank,
                ledger=ledger,
                groups=groups,
                input_record_count=len(drug_passages),
                graph_rank=candidate_graph_rank,
            )

        counterfactuals, cf_warnings = leave_one_study_out(
            drug_passages, drug_name, groups,
            baseline_score=baseline_score,
            verified_claims=_verified, total_claims=_total,
            baseline_rank=baseline_rank,
            peer_scores=peer_scores,
            peer_kg_order=peer_kg_order,
            candidate_key=candidate_key,
        )
        warnings.extend(cf_warnings)

        stability = summarize_counterfactuals(
            counterfactuals,
            baseline_score=baseline_score,
            baseline_rank=baseline_rank,
            eligible_study_count=len(groups),
        )

        return {
            "version": AUDIT_VERSION,
            "method": AUDIT_METHOD,
            "scoring_function": SCORING_FUNCTION_ID,
            "direction_method": f"{DIRECTION_METHOD}@{DIRECTION_METHOD_VERSION}",
            "status": stability["status"],
            "ranking_scope": "evidence_rank_over_retrieved_candidates",
            "note": ("Evidence rank is computed over the retrieved candidate set and "
                     "is distinct from the displayed knowledge-graph candidate rank."),
            "baseline": {
                "evidence_score": round(baseline_score, 6),
                "evidence_rank": baseline_rank,
                # peer_kg_order is 0-based for stable sorting; the UI's rank is 1-based.
                "displayed_kg_rank": (peer_kg_order.get(candidate_key) or 0) + 1,
                "tier": baseline.get("tier"),
                "components": baseline.get("breakdown"),
            },
            "study_counts": {
                "eligible_independent_studies": len(groups),
                "study_units": len(groups),
                "source_records": len(ledger),
                # Retrieved passage records that collapsed onto a source already in
                # the ledger. Reported so the count of records is not mistaken for a
                # count of independent studies.
                "duplicate_records_removed": max(0, len(drug_passages) - len(ledger)),
                "study_independence_verified": False,
                # NOTE: `potentially_overlapping_studies` is deliberately NOT
                # reported. Cross-publication overlap cannot be established from the
                # metadata this corpus carries, and a number here would be a claim we
                # cannot support. Consumers should render it as not established, not
                # as zero.
                **summarize_directions(groups),
            },
            "stability": stability,
            "counterfactuals": counterfactuals,
            "sources": ledger,
            "warnings": warnings,
        }
    except Exception as exc:  # noqa: BLE001 - audit must never break the response
        return _empty_audit(
            status=AUDIT_STATUS_ERROR,
            reason=f"{type(exc).__name__}: {exc}",
            warnings=[f"Audit failed: {type(exc).__name__}"],
            baseline={"score": 0.0, "tier": "Preliminary", "breakdown": None},
            baseline_rank=baseline_rank,
            ledger=[],
            groups=[],
            input_record_count=len(drug_passages),
            graph_rank=candidate_graph_rank,
        )


def _empty_audit(*, status, reason, warnings, baseline, baseline_rank, ledger, groups,
                 input_record_count: Optional[int] = None,
                 graph_rank: Optional[int] = None) -> dict:
    """Shared shape for audits that could not be completed.

    ``baseline_rank`` is the EVIDENCE rank. ``displayed_kg_rank`` is the
    knowledge-graph origin and is a different quantity — it must be passed in
    explicitly. Deriving it from ``baseline_rank`` conflated the two, so an
    incomplete audit reported the evidence rank as if it were the graph rank.
    """
    records_in = len(ledger) if input_record_count is None else input_record_count
    return {
        "version": AUDIT_VERSION,
        "method": AUDIT_METHOD,
        "scoring_function": SCORING_FUNCTION_ID,
        "direction_method": f"{DIRECTION_METHOD}@{DIRECTION_METHOD_VERSION}",
        "status": status,
        "reason": reason,
        "ranking_scope": "evidence_rank_over_retrieved_candidates",
        "baseline": {
            "evidence_score": round(float(baseline.get("score") or 0.0), 6),
            "evidence_rank": baseline_rank,
            "displayed_kg_rank": graph_rank,
            "tier": baseline.get("tier"),
            "components": baseline.get("breakdown"),
        },
        "study_counts": {
            "eligible_independent_studies": len(groups),
            "study_units": len(groups),
            "source_records": len(ledger),
            "duplicate_records_removed": max(0, records_in - len(ledger)),
            "study_independence_verified": False,
            **summarize_directions(groups),
        },
        "stability": summarize_counterfactuals(
            [], baseline_score=float(baseline.get("score") or 0.0),
            baseline_rank=baseline_rank, eligible_study_count=len(groups),
        ),
        "counterfactuals": [],
        "sources": ledger,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- #
# Query-level entry point (pipeline integration)
# --------------------------------------------------------------------------- #

def attach_audits(
    results: list[dict],
    top_passages: list[dict],
    disease: dict,
    *,
    enabled: bool = True,
) -> dict:
    """Attach ``evidence_audit`` to every candidate in a pipeline result list.

    Mutates ``results`` in place and returns a small summary. Designed to be
    additive: the existing keys (``rank``, ``evidence``, ``claims``) are untouched,
    and a per-candidate audit failure cannot remove that candidate.
    """
    summary = {"audited": 0, "complete": 0, "not_auditable": 0, "failed": 0}
    if not enabled or not results:
        for result in results or []:
            result["evidence_audit"] = {
                "version": AUDIT_VERSION,
                "method": AUDIT_METHOD,
                "status": AUDIT_STATUS_NOT_AUDITABLE,
                "reason": "audit_disabled_or_no_candidates",
                "warnings": ["Audit not computed for this response."],
            }
        return summary

    # --- baseline evidence scores for the whole candidate set -----------------
    per_candidate: dict[str, dict] = {}
    for fallback_order, result in enumerate(results):
        drug_name = result.get("drug") or ""
        drug_passages = [
            p for p in top_passages
            if normalize_key(drug_name) and normalize_key(drug_name) in normalize_key(p.get("drug"))
        ]
        # The pipeline now sorts `results` by evidence score, so the list index is
        # the EVIDENCE position, not the knowledge-graph position. The graph origin
        # must come from evidence_summary.graph_rank, or the tie-break and the
        # reported displayed_kg_rank would both silently describe the wrong order.
        graph_rank = (result.get("evidence_summary") or {}).get("graph_rank")
        kg_order = (int(graph_rank) - 1) if isinstance(graph_rank, int) else fallback_order
        per_candidate[drug_name] = {
            "drug_name": drug_name,
            "passages": drug_passages,
            "claims": result.get("claims") or [],
            "score": float((result.get("evidence") or {}).get("score") or 0.0),
            "kg_order": kg_order,
            "key": drug_name,
        }

    peer_scores = {k: v["score"] for k, v in per_candidate.items()}
    peer_kg_order = {k: v["kg_order"] for k, v in per_candidate.items()}
    baseline_ranks = compute_evidence_ranks(
        [{"key": k, "score": v["score"], "kg_order": v["kg_order"]}
         for k, v in per_candidate.items()]
    )

    for result in results:
        drug_name = result.get("drug") or ""
        info = per_candidate.get(drug_name)
        if not info:
            result["evidence_audit"] = {
                "version": AUDIT_VERSION, "method": AUDIT_METHOD,
                "status": AUDIT_STATUS_NOT_AUDITABLE,
                "reason": "candidate_not_indexed",
                "warnings": ["Candidate could not be indexed for auditing."],
            }
            continue

        audit = audit_candidate(
            drug_name=drug_name,
            disease=disease,
            drug_passages=info["passages"],
            claims=info["claims"],
            baseline_evidence=result.get("evidence") or {},
            candidate_key=drug_name,
            baseline_rank=baseline_ranks.get(drug_name) or (info["kg_order"] + 1),
            peer_scores=peer_scores,
            peer_kg_order=peer_kg_order,
        )
        result["evidence_audit"] = audit

        summary["audited"] += 1
        if audit.get("status") == AUDIT_STATUS_COMPLETE:
            summary["complete"] += 1
        elif audit.get("status") == AUDIT_STATUS_ERROR:
            summary["failed"] += 1
        else:
            summary["not_auditable"] += 1

    return summary
