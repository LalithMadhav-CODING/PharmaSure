"""Dense retrieval using numpy cosine similarity."""
import numpy as np


def search_dense(query_vec: np.ndarray, index: np.ndarray, top_k: int = 30) -> list[tuple[int, float]]:
    """Return (chunk_index, score) pairs for top-k most similar passages.

    Assumes both query_vec and index are L2-normalized, so dot product = cosine similarity.
    """
    scores = index @ query_vec  # (N,) cosine similarities
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(int(i), float(scores[i])) for i in top_indices]


def rerank(passages: list[dict], scores: list[float]) -> list[dict]:
    """Attach retrieval scores and re-rank by relevance + study type + recency.

    Study type weights: clinical_trial=1.0, cohort=0.7, preclinical=0.4, review=0.3
    """
    study_weights = {
        "clinical_trial": 1.0,
        "cohort": 0.7,
        "preclinical": 0.4,
        "review": 0.3,
        "other": 0.3,
    }

    for i, passage in enumerate(passages):
        passage["retrieval_score"] = scores[i] if i < len(scores) else 0.0
        pub_type = passage.get("pub_type", "other") or "other"
        passage["study_weight"] = study_weights.get(pub_type, 0.3)
        # Recency bonus: newer papers get a small boost
        year = passage.get("year") or 2020
        passage["recency_bonus"] = min((year - 2000) / 100.0, 0.2)

    # Combined score: retrieval + study weight + recency
    for p in passages:
        p["combined_score"] = (
            0.5 * p["retrieval_score"]
            + 0.3 * p["study_weight"]
            + 0.2 * p["recency_bonus"]
        )

    passages.sort(key=lambda x: x["combined_score"], reverse=True)
    return passages


def evidence_score(passages: list[dict], drug_name: str = "",
                   verified_claims: int = 0, total_claims: int = 0) -> dict:
    """Compute evidence score from passages relevant to a specific drug.

    Formula:  verification x (0.35*relevance + 0.35*support + 0.30*study_quality)

    Verification is a MULTIPLIER, not a term. A quotation that cannot be matched
    back to its source is not usable evidence, so a candidate whose quotations do
    not verify cannot outscore one whose quotations do — no matter how favourable
    its publication metadata is. An additive term cannot guarantee that: a
    clinical-trial publication type alone outweighed a 25% verification weight and
    let a candidate with zero verified quotations rank above fully-verified ones.

    ``verification`` is the fraction of this candidate's claims whose quotations
    passed the contiguous-excerpt check. It is 0.0 when the candidate has no
    claims, so "no verified claim" scores the same whether the model produced
    nothing or produced text that failed verification. Scoring 0 here means "no
    verified evidence", NOT "no evidence exists" and NOT "ineffective" — the
    per-candidate evidence_status distinguishes those cases.

    Labeled as an experimental heuristic, never a clinical probability.
    """
    # Verification: share of this candidate's claims whose quotes verified.
    # No claims means no verified claim, so this is 0.0 rather than excluded —
    # excluding it would reward producing nothing.
    verification = (verified_claims / total_claims) if total_claims else 0.0
    verification = max(0.0, min(1.0, verification))

    if not passages:
        return {"score": 0.0, "tier": "Preliminary", "support": 0,
                "best_study_type": "none", "verification": round(verification, 3)}

    # Filter passages for this specific drug (check drug field, not text)
    if drug_name:
        drug_passages = [p for p in passages if drug_name.lower() in (p.get("drug") or "").lower()]
    else:
        drug_passages = passages

    if not drug_passages:
        return {"score": 0.0, "tier": "Preliminary", "support": 0,
                "best_study_type": "none", "verification": round(verification, 3)}

    # Relevance: mean retrieval score for THIS drug's passages (direct, not compressed)
    retrieval_scores = [p.get("retrieval_score", 0.0) for p in drug_passages]
    relevance = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0

    # Support: passage count for this drug (more passages = stronger support)
    support_count = len(drug_passages)
    support = min(support_count, 5) / 5.0

    # Study quality: best study type among this drug's passages
    study_weights = {"clinical_trial": 1.0, "cohort": 0.7, "preclinical": 0.4, "review": 0.3, "other": 0.3}
    best_study = "other"
    best_weight = 0.3
    for p in drug_passages:
        pt = p.get("pub_type", "other") or "other"
        if study_weights.get(pt, 0.3) > best_weight:
            best_weight = study_weights[pt]
            best_study = pt

    evidence_strength = 0.35 * relevance + 0.35 * support + 0.30 * best_weight
    score = verification * evidence_strength

    if score >= 0.7:
        tier = "Strong"
    elif score >= 0.4:
        tier = "Moderate"
    else:
        tier = "Preliminary"

    return {
        "score": round(score, 3),
        "tier": tier,
        "support": support_count,
        "best_study_type": best_study,
        "verification": round(verification, 3),
        "breakdown": {
            "verification": round(verification, 3),
            "verification_role": "multiplier",
            "verified_claims": verified_claims,
            "total_claims": total_claims,
            "evidence_strength": round(evidence_strength, 3),
            "relevance": round(relevance, 3),
            "relevance_weight": 0.35,
            "support": round(support, 3),
            "support_weight": 0.35,
            "study_quality": round(best_weight, 3),
            "study_quality_weight": 0.30,
        },
    }
