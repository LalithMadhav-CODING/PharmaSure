"""Disease resolution and candidate generation from EveryCure matrix-scores."""
import pandas as pd
import numpy as np
from datasets import load_dataset


# Module-level cache for loaded datasets
_drugs_df = None
_diseases_df = None
_matrix_df = None


def load_data():
    """Load and cache EveryCure datasets."""
    global _drugs_df, _diseases_df, _matrix_df
    if _drugs_df is None:
        drugs = load_dataset("everycure/drug-list", split="train")
        _drugs_df = drugs.to_pandas()
    if _diseases_df is None:
        diseases = load_dataset("everycure/disease-list", split="train")
        _diseases_df = diseases.to_pandas()
    if _matrix_df is None:
        matrix = load_dataset("everycure/matrix-scores", split="train")
        _matrix_df = matrix.to_pandas()
    return _drugs_df, _diseases_df, _matrix_df


def _normalize(text: str) -> str:
    """Normalize disease name for matching: lowercase, remove possessive 's, remove punctuation, collapse spaces."""
    import re
    text = text.lower()
    text = re.sub(r"'s\b", "", text)  # remove possessive 's
    text = re.sub(r"[^a-z0-9\s]", "", text)  # remove remaining punctuation
    return text.strip()


def resolve_disease(query: str) -> dict | None:
    """Match free text to a disease by name (case-insensitive, punctuation-insensitive, exact then fuzzy)."""
    _, diseases_df, _ = load_data()
    q = _normalize(query)

    # Exact match (normalized)
    exact = diseases_df[diseases_df["name"].apply(lambda x: _normalize(str(x))) == q]
    if len(exact) > 0:
        row = exact.iloc[0]
        return {"id": row["id"], "name": row["name"], "synonyms": row.get("synonyms", "")}

    # Fuzzy match (substring, normalized)
    fuzzy = diseases_df[diseases_df["name"].apply(lambda x: q in _normalize(str(x)))]
    if len(fuzzy) > 0:
        row = fuzzy.iloc[0]
        return {"id": row["id"], "name": row["name"], "synonyms": row.get("synonyms", "")}

    return None


def get_candidates(disease_id: str, top_n: int = 10) -> dict:
    """Get candidate drugs and known indications for a disease from matrix-scores.

    Returns:
        {
            "candidates": [{"drug_id": ..., "drug_name": ..., "score": ...}, ...],
            "known_indications": [{"drug_name": ...}, ...],
        }
    """
    drugs_df, _, matrix_df = load_data()

    # Filter matrix-scores for this disease
    disease_edges = matrix_df[matrix_df["target"] == disease_id]

    # Known indications (is_known_positive = true)
    known = disease_edges[disease_edges["is_known_positive"] == True]
    known_ids = set(known["source_ec_id"].tolist())

    # Repurposing candidates: NOT known positive, NOT known negative (the "unknown" ones)
    # These are drugs that may treat the disease but aren't established indications
    candidates_df = disease_edges[
        (disease_edges["is_known_positive"] == False) &
        (disease_edges["is_known_negative"] == False)
    ].copy()

    # Sort by predicted treat score (descending)
    candidates_df = candidates_df.sort_values(
        "untransformed_treat_score", ascending=False
    ).head(top_n)

    # Build candidate list
    candidates = []
    for _, row in candidates_df.iterrows():
        drug_id = row["source_ec_id"]
        drug_name = _get_drug_name(drugs_df, drug_id)
        candidates.append({
            "drug_id": drug_id,
            "drug_name": drug_name,
            "score": float(row["untransformed_treat_score"]),
            "trial_sig_better": bool(row["trial_sig_better"]),
            "trial_sig_worse": bool(row["trial_sig_worse"]),
        })

    # Build known indications list
    known_indications = []
    for drug_id in known_ids:
        drug_name = _get_drug_name(drugs_df, drug_id)
        # Always include, even if name lookup fails (use ID as fallback)
        known_indications.append({"drug_name": drug_name or drug_id, "drug_id": drug_id})

    return {"candidates": candidates, "known_indications": known_indications}


def _get_drug_name(drugs_df, drug_id: str) -> str | None:
    """Look up drug name from drug-list by EC ID."""
    match = drugs_df[drugs_df["id"] == drug_id]
    if len(match) > 0:
        name = match.iloc[0]["name"]
        if name is None or (isinstance(name, float) and name != name):  # NaN check
            return None
        return name
    return None
