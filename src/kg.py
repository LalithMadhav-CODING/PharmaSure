"""Disease resolution and candidate generation from EveryCure matrix-scores."""
import json
import os
import pandas as pd
from datasets import load_dataset


# Module-level cache for loaded datasets
_drugs_df = None
_diseases_df = None
_candidates_lookup = None


def load_data():
    """Load and cache EveryCure datasets."""
    global _drugs_df, _diseases_df, _candidates_lookup
    if _drugs_df is None:
        drugs = load_dataset("everycure/drug-list", split="train")
        _drugs_df = drugs.to_pandas()
    if _diseases_df is None:
        diseases = load_dataset("everycure/disease-list", split="train")
        _diseases_df = diseases.to_pandas()
    if _candidates_lookup is None:
        candidates_path = os.path.join(os.path.dirname(__file__), "..", "data", "candidates.json")
        if os.path.exists(candidates_path):
            with open(candidates_path) as f:
                _candidates_lookup = json.load(f)
        else:
            _candidates_lookup = {}
    return _drugs_df, _diseases_df, _candidates_lookup


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

    # Fuzzy match (substring, normalized) — prefer shortest name (most common/generic disease)
    fuzzy = diseases_df[diseases_df["name"].apply(lambda x: q in _normalize(str(x)))].copy()
    if len(fuzzy) > 0:
        fuzzy["_norm_len"] = fuzzy["name"].apply(lambda x: len(_normalize(str(x))))
        fuzzy = fuzzy.sort_values("_norm_len")
        row = fuzzy.iloc[0]
        return {"id": row["id"], "name": row["name"], "synonyms": row.get("synonyms", "")}

    return None


def get_candidates(disease_id: str, top_n: int = 10) -> dict:
    """Get candidate drugs and known indications for a disease from pre-computed lookup.

    Returns:
        {
            "candidates": [{"drug_id": ..., "drug_name": ..., "score": ...}, ...],
            "known_indications": [{"drug_name": ...}, ...],
        }
    """
    drugs_df, _, lookup = load_data()

    entry = lookup.get(disease_id, {"c": [], "k": []})

    # Build candidate list from pre-computed top-10
    candidates = []
    for item in entry.get("c", [])[:top_n]:
        ec_id, score = item[0], item[1]
        drug_name = _get_drug_name(drugs_df, ec_id)
        candidates.append({
            "drug_id": ec_id,
            "drug_name": drug_name,
            "score": score,
        })

    # Build known indications list
    known_indications = []
    for drug_id in entry.get("k", []):
        drug_name = _get_drug_name(drugs_df, drug_id)
        known_indications.append({"drug_name": drug_name or drug_id, "drug_id": drug_id})
    # Keep only entries with human-readable names (not identifier fallbacks)
    known_indications = [
        k for k in known_indications
        if isinstance(k["drug_name"], str)
        and not k["drug_name"].startswith(("CHEBI:", "UMLS:", "UNII:", "RXCUI:", "PUBCHEM"))
    ]

    return {"candidates": candidates, "known_indications": known_indications}


def _get_drug_name(drugs_df, drug_id: str) -> str | None:
    """Look up drug name from drug-list by EC ID or CHEBI ID."""
    import math
    # Try EC ID first
    match = drugs_df[drugs_df["id"] == drug_id]
    if len(match) > 0:
        name = match.iloc[0]["name"]
        if isinstance(name, str):
            return name
        if isinstance(name, float) and not math.isnan(name):
            return str(name)
    # Try CHEBI ID via translator_id
    match = drugs_df[drugs_df["translator_id"].str.contains(drug_id, na=False)]
    if len(match) > 0:
        name = match.iloc[0]["name"]
        if isinstance(name, str):
            return name
        if isinstance(name, float) and not math.isnan(name):
            return str(name)
    return None
