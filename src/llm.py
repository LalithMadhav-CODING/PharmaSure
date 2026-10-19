"""Gemini Flash client for answer generation."""
import os
import httpx

MODEL = "qwen3.8:27b"  # 17.7GB, fits in 20GB VRAM


import json
import re


def _repair_json(t: str) -> str:
    """Best-effort repair of common LLM JSON breakage."""
    s = re.sub(r"//[^\n]*", "", t)            # strip line comments
    s = re.sub(r",\s*([}\]])", r"\1", s)      # trailing commas
    if s.count('"') % 2 == 1:                 # unterminated string
        s += '"'

    # Close any brackets still open, in correct nesting order.
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    while stack:
        s += "}" if stack.pop() == "{" else "]"
    return s


def _parse_candidates_json(raw: str):
    """Parse the model's JSON, tolerating fences, prose and truncation.

    Returns the parsed object, or None when nothing usable can be recovered.
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group())

    for chunk in candidates:
        for attempt in (chunk, _repair_json(chunk)):
            if not attempt:
                continue
            try:
                parsed = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _extract_json_block(text: str):
    """Thin wrapper kept for backwards compatibility."""
    return _parse_candidates_json(text)


def generate_answer(disease_name: str, candidates: list[dict], passages: list[dict]) -> dict:
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
    # Passage text is trimmed: the full corpus entries can run to tens of
    # thousands of characters, which crowds the context window and causes the
    # model to truncate its own JSON output mid-generation.
    MAX_PASSAGE_CHARS = 1200
    context_parts = []
    for i, p in enumerate(passages):
        drug_label = p.get('drug') or 'N/A'
        disease_label = p.get('disease') or 'N/A'
        body = (p.get('text') or '').strip()
        if len(body) > MAX_PASSAGE_CHARS:
            body = body[:MAX_PASSAGE_CHARS].rstrip() + " …"
        context_parts.append(
            f"[{i+1}] (Source: {p.get('source', 'unknown')}, PMID: {p.get('pmid', 'N/A')}, "
            f"Type: {p.get('pub_type', 'unknown')})\n"
            f"Associated Drug: {drug_label} | Associated Disease: {disease_label}\n"
            f"Text: {body}"
        )
    context = "\n\n".join(context_parts)

    # Build candidate info
    cand_info = []
    for c in candidates:
        cand_info.append(f"- {c['drug_name']} (predicted score: {c['score']:.4f})")
    cand_str = "\n".join(cand_info)

    prompt = f"""You are a drug repurposing research assistant. Given a disease and a set of candidate drugs with supporting literature passages, generate a ranked list of repurposing candidates.

DISEASE: {disease_name}

CANDIDATE DRUGS (from knowledge graph, sorted by predicted score):
{cand_str}

RETRIEVED LITERATURE PASSAGES:
{context}

For each candidate, provide:
1. drug_name: the drug name
2. reason: a 1-2 sentence explanation of WHY this drug might work for {disease_name}, grounded in the passages
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
            "options": {
                "temperature": 0.1,
                "num_ctx": 16384,
                # Room for all candidates + claims + quotes; the default cap
                # truncates the JSON mid-object.
                "num_predict": 4096,
            },
        },
        timeout=300,
    )
    payload = resp.json()
    text = (payload.get("response") or payload.get("thinking") or "").strip()

    parsed = _parse_candidates_json(text)
    if parsed is not None:
        return parsed

    # One repair attempt: hand the broken output back and ask for valid JSON.
    try:
        fix = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": MODEL,
                "prompt": (
                    "The following model output was meant to be a single valid JSON object "
                    "but is malformed. Return ONLY the corrected JSON object — no prose, no "
                    "markdown fences. Preserve all content; fix only the syntax.\n\n"
                    f"{text[:6000]}"
                ),
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0},
            },
            timeout=120,
        )
        parsed = _parse_candidates_json((fix.json().get("response") or "").strip())
        if parsed is not None:
            return parsed
    except Exception:
        pass

    # Degrade gracefully — never take the pipeline down over one bad generation.
    return {"candidates": [], "error": f"Invalid JSON response: {text[:200]}"}
