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


def evidence_score(passages: list[dict], drug_name: str = "") -> dict:
    """Compute evidence score from passages relevant to a specific drug.

    Formula: 0.3 * relevance + 0.3 * support + 0.4 * study_quality
    Labeled as experimental heuristic, never clinical probability.
    """
    if not passages:
        return {"score": 0.0, "tier": "Preliminary", "support": 0, "best_study_type": "none"}

    # Filter passages for this specific drug (check drug field, not text)
    if drug_name:
        drug_passages = [p for p in passages if drug_name.lower() in (p.get("drug") or "").lower()]
    else:
        drug_passages = passages

    # Relevance: mean of top-3 retrieval scores for THIS drug's passages
    top_scores = sorted([p.get("retrieval_score", 0.0) for p in drug_passages], reverse=True)[:3]
    raw_relevance = sum(top_scores) / len(top_scores) if top_scores else 0.0
    relevance = max(0.0, min(1.0, (raw_relevance - 0.2) / 0.4))

    # Support: fraction of this drug's passages that have disease info
    support_count = sum(1 for p in drug_passages if p.get("disease"))
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

    score = 0.3 * relevance + 0.3 * support + 0.4 * best_weight

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
    }
