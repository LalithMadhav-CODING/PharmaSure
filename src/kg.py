"""Disease resolution and candidate generation from EveryCure matrix-scores."""
import json
import os
import re


# Module-level cache for loaded datasets
_diseases_lookup = None
_drugs_lookup = None
_candidates_lookup = None


def _load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_data():
    """Load and cache compact lookups (memory-efficient for 512MB RAM)."""
    global _diseases_lookup, _drugs_lookup, _candidates_lookup
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    if _diseases_lookup is None:
        _diseases_lookup = _load_json(os.path.join(base, "disease_lookup.json"))
    if _drugs_lookup is None:
        _drugs_lookup = _load_json(os.path.join(base, "drug_lookup.json"))
    if _candidates_lookup is None:
        _candidates_lookup = _load_json(os.path.join(base, "candidates.json"))
    return _diseases_lookup, _drugs_lookup, _candidates_lookup


def _normalize(text: str) -> str:
    """Normalize disease name for matching: lowercase, remove possessive 's, remove punctuation, collapse spaces."""
    import re
    text = text.lower()
    text = re.sub(r"'s\b", "", text)  # remove possessive 's
    text = re.sub(r"[^a-z0-9\s]", "", text)  # remove remaining punctuation
    return text.strip()


def resolve_disease(query: str) -> dict | None:
    """Match free text to a disease by name (case-insensitive, punctuation-insensitive, exact then fuzzy)."""
    diseases_lookup, _, _ = load_data()
    q = _normalize(query)

    # Build normalized name → id mapping for exact match
    norm_to_id = {}
    for did, info in diseases_lookup.items():
        name = info.get("n", "")
        norm = _normalize(name)
        if norm and norm not in norm_to_id:
            norm_to_id[norm] = (did, name, info.get("s", []))

    # Exact match
    if q in norm_to_id:
        did, name, synonyms = norm_to_id[q]
        return {"id": did, "name": name, "synonyms": list(synonyms) if synonyms else []}

    # Fuzzy match — prefer shortest name (most common/generic disease)
    matches = []
    for norm, (did, name, synonyms) in norm_to_id.items():
        if q in norm:
            matches.append((len(norm), did, name, synonyms))
    if matches:
        matches.sort()
        _, did, name, synonyms = matches[0]
        return {"id": did, "name": name, "synonyms": list(synonyms) if synonyms else []}

    return None


def get_candidates(disease_id: str, top_n: int = 10) -> dict:
    """Get candidate drugs and known indications for a disease from pre-computed lookup.

    Returns:
        {
            "candidates": [{"drug_id": ..., "drug_name": ..., "score": ...}, ...],
            "known_indications": [{"drug_name": ...}, ...],
        }
    """
    _, drugs_lookup, lookup = load_data()

    entry = lookup.get(disease_id, {"c": [], "k": []})

    # Build candidate list from pre-computed top-10
    candidates = []
    for item in entry.get("c", [])[:top_n]:
        ec_id, score = item[0], item[1]
        drug_name = _get_drug_name(drugs_lookup, ec_id)
        candidates.append({
            "drug_id": ec_id,
            "drug_name": drug_name,
            "score": score,
        })

    # Build known indications list
    known_indications = []
    for drug_id in entry.get("k", []):
        drug_name = _get_drug_name(drugs_lookup, drug_id)
        known_indications.append({"drug_name": drug_name or drug_id, "drug_id": drug_id})
    # Keep only entries with human-readable names (not identifier fallbacks)
    known_indications = [
        k for k in known_indications
        if isinstance(k["drug_name"], str)
        and not k["drug_name"].startswith(("CHEBI:", "UMLS:", "UNII:", "RXCUI:", "PUBCHEM"))
    ]

    return {"candidates": candidates, "known_indications": known_indications}


def _get_drug_name(drugs_lookup: dict, drug_id: str) -> str | None:
    """Look up drug name from compact drug lookup."""
    if not drug_id:
        return None
    # Direct lookup
    name = drugs_lookup.get(drug_id)
    if name:
        return name
    # Try CHEBI prefix variations
    for key in [drug_id, drug_id.replace("CHEBI:", ""), f"CHEBI:{drug_id}"]:
        if key in drugs_lookup:
            return drugs_lookup[key]
    return None
