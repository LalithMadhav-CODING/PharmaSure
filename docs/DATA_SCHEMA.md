# Data Schema Verification — PharmaSure

**Date:** 2026-10-18
**Status:** Verified against actual datasets

---

## EveryCure `matrix-scores` (PRIMARY candidate source)

- **Rows:** 39,444,648
- **Size:** Large Parquet on HuggingFace

### Schema

| Column | Type | Meaning |
|---|---|---|
| `source` | string | Drug identifier (CHEBI format, e.g. `CHEBI:45863`) |
| `target` | string | Disease identifier (MONDO format, e.g. `MONDO:0800310`) |
| `source_ec_id` | string | EveryCure drug ID (e.g. `EC:01218`) — joins to `drug-list.id` |
| `is_known_positive` | bool | **Known indication** — drug is approved/established for this disease |
| `is_known_negative` | bool | Known negative — drug does not treat this disease |
| `trial_sig_better` | bool | **Positive evidence** — trial showed significant benefit |
| `trial_non_sig_better` | bool | Non-significant trend toward benefit |
| `trial_sig_worse` | bool | **Negative evidence** — trial showed significant harm |
| `trial_non_sig_worse` | bool | Non-significant trend toward harm |
| `off_label` | bool | **Off-label use** — repurposing candidate flag |
| `ec_indications_list_off_label` | bool | On the EC indications list as off-label |
| `ec_indications_list_on_label` | bool | On the EC indications list as on-label |
| `ec_indications_list` | bool | On the EC indications list at all |
| `not_treat_score` | float | Predicted "does not treat" probability |
| `untransformed_treat_score` | float | **Predicted "treats" score** — use for ranking |

### Label distribution

| Label | Count | Use |
|---|---|---|
| `is_known_positive = true` | 25,046 | **Exclude** — known indication |
| `is_known_negative = true` | 38,408 | **Exclude** — known negative |
| Everything else (null/unknown) | 39,444,648 | **Repurposing candidates** |

### How we use it

1. **Candidate generation:** Filter `off_label = true` AND `is_known_positive = false`
2. **Known-indication labelling:** `is_known_positive = true` → label as "Known indication"
3. **Evidence direction:** `trial_sig_better` → Positive; `trial_sig_worse` → Negative; both → Mixed; neither → Uncertain
4. **Ranking:** Sort by `untransformed_treat_score` descending

---

## EveryCure `kg-edges` (NOT used for candidates)

- **Rows:** 81.1M edges, 3.56 GB
- **Problem:** General KG edges (protein interactions, pathways, etc.), NOT drug-disease specific
- **Example edge:** `PathWhiz.Reaction:107856 has_participant UMLS:C0054788`
- **Decision:** Skip `kg-edges` for candidate generation. Use `matrix-scores` instead.

---

## EveryCure `drug-list`

- **Rows:** 1,935 drugs
- **Key columns:** `id` (EC:XXXXX), `name`, `translator_id`, `drugbank_id`, `synonyms`, `drug_class`, `therapeutic_area`, `approved_usa`

## EveryCure `disease-list`

- **Rows:** 23,224 diseases
- **Key columns:** `id` (MONDO:XXXXXXX), `name`, `synonyms`, `definition`

---

## Resolves PRD §18.3 assumptions

| # | Assumption | Resolution |
|---|---|---|
| 2 | What `kg-edges` encodes | **Not used.** `matrix-scores` has explicit `is_known_positive`, `off_label`, `trial_sig_better/worse` columns |
| 8 | Whether KG has known-indication flags | **Yes.** `matrix-scores.is_known_positive` is the known-indication flag |

## Decision

**Use `matrix-scores` as the primary candidate source.** It provides:
- Repurposing candidates (`off_label = true`)
- Known indications (`is_known_positive = true`)
- Evidence direction (`trial_sig_better/worse`)
- Ranking scores (`untransformed_treat_score`)
- All in one dataset, no graph traversal needed
