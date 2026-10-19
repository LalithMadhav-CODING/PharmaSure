"""Gemini Flash client for answer generation."""
import os
import httpx

MODEL = "qwen3.8:27b"  # 17.7GB, fits in 20GB VRAM


def generate_answer(disease: str, candidates: list[dict], passages: list[dict]) -> dict:
    """Generate ranked candidates + reasons + citations + direction in one Gemini call.

    Returns:
        {
            "candidates": [
                {
                    "drug_name": ...,
                    "reason": ...,
                    "direction": "Positive|Negative|Mixed|Uncertain",
                    "claims": [{"text": ..., "citation_ids": [...], "quote": ...}],
                }
            ]
        }
    """

    # Build context passages
    context_parts = []
    for i, p in enumerate(passages):
        drug_label = p.get('drug') or 'N/A'
        disease_label = p.get('disease') or 'N/A'
        context_parts.append(
            f"[{i+1}] (Source: {p.get('source', 'unknown')}, PMID: {p.get('pmid', 'N/A')}, "
            f"Type: {p.get('pub_type', 'unknown')})\n"
            f"Associated Drug: {drug_label} | Associated Disease: {disease_label}\n"
            f"Text: {p['text']}"
        )
    context = "\n\n".join(context_parts)

    # Build candidate info
    cand_info = []
    for c in candidates:
        cand_info.append(f"- {c['drug_name']} (predicted score: {c['score']:.4f})")
    cand_str = "\n".join(cand_info)

    prompt = f"""You are a drug repurposing research assistant. Given a disease and a set of candidate drugs with supporting literature passages, generate a ranked list of repurposing candidates.

DISEASE: {disease}

CANDIDATE DRUGS (from knowledge graph, sorted by predicted score):
{cand_str}

RETRIEVED LITERATURE PASSAGES:
{context}

For each candidate, provide:
1. drug_name: the drug name
2. reason: a 1-2 sentence explanation of WHY this drug might work for {disease}, grounded in the passages
3. direction: one of "Positive" (evidence supports), "Negative" (evidence refutes), "Mixed" (both), or "Uncertain" (cannot determine). Default to "Uncertain" if unclear.
4. claims: a list of specific factual claims, each with:
   - text: the claim
   - citation_ids: list of passage numbers [1], [2], etc. that support this claim
   - quote: a VERBATIM quote from the cited passage that supports the claim (exact substring, do not paraphrase)

IMPORTANT RULES:
- Only use the retrieved passages as evidence. Do not use your training data.
- Every claim MUST have at least one citation and a verbatim quote from that passage.
- If no passage supports a claim, do not make that claim.
- If a drug has no supporting passages, say "No literature evidence found" for that drug.
- Label your confidence: if evidence is weak or ambiguous, say so.
- This is for research hypothesis generation, NOT medical advice.

Respond in JSON format:
{{
  "candidates": [
    {{
      "drug_name": "...",
      "reason": "...",
      "direction": "Positive|Negative|Mixed|Uncertain",
      "claims": [
        {{"text": "...", "citation_ids": [1], "quote": "verbatim excerpt"}}
      ]
    }}
  ]
}}"""

    import httpx
    resp = httpx.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        },
        timeout=120,
    )
    text = resp.json().get("response", "").strip() or resp.json().get("thinking", "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

    import json
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from text
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
        return {"candidates": [], "error": f"Invalid JSON response: {text[:200]}"}
