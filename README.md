# PharmaSure — Drug Repurposing via Literature RAG

**Telemedicon 2026 · Internal Hackathon · AI + Digital Health**

A clinician or researcher types a disease name. The system retrieves relevant biomedical literature and generates a **ranked list of drug repurposing candidates with citations** — grounded in real sources, not hallucinated.

---

## Quick Start

```bash
# Setup
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your Gemini key
echo 'GEMINI_API_KEY=your-key-here' > .env

# Run
python src/app.py
```

---

## Stack

| Layer | Tool |
|---|---|
| Embeddings | Ollama `nomic-embed-text` (local, 768-dim) |
| Vector store | NumPy cosine similarity |
| LLM | Gemini Flash / qwen3.8:27b fallback |
| UI | Gradio |
| Data | EveryCure `matrix-scores` (39.4M drug-disease pairs) + PubMed abstracts |

See [`docs/STACK.md`](docs/STACK.md) for the full design and [`docs/DECISIONS.md`](docs/DECISIONS.md) for the complete decision log.

---

## Pipeline

```
User query → Disease Resolution → Candidate Generation → Embedding & Retrieval
→ Re-ranking → Generation → Citation Verification → Evidence Scoring
→ Counterfactual Evidence Audit → Ranked Output
```

1. **Disease Resolution** — free text → canonical EveryCure/MONDO identity
2. **Candidate Generation** — EveryCure knowledge graph, top-10 repurposing candidates
3. **Embedding & Retrieval** — Ollama `nomic-embed-text` + NumPy cosine similarity,
   scoped to passages tagged with the resolved disease
4. **Re-ranking** — relevance + study type + recency
5. **Generation** — local `qwen3.8:27b` (Ollama), grounded strictly in retrieved passages
6. **Citation Verification** — two stages: source identity (does the passage mention this
   drug for this disease?) and claim support (is the quote a *contiguous verbatim*
   substring?). No citation → no claim.
7. **Evidence Scoring** — `S = 0.25·R + 0.35·P + 0.40·Q` (relevance, support, study quality)
8. **Counterfactual Evidence Audit** — leave-one-study-out sensitivity: how the score and
   evidence rank change when a contributing study is removed. See
   [docs/EVIDENCE_AUDIT.md](docs/EVIDENCE_AUDIT.md).

---

## Evidence Stability Audit

Each candidate card carries an expandable **Evidence stability audit**. For every
candidate it shows the contributing study units, per-source influence, and what happens
to the evidence score and evidence rank when one study is removed.

Example (Alzheimer's disease → Galantamine): 3 study units, baseline score 0.779, and
removing PMID 42851720 drops the score to 0.424 — a 0.355 change that moves it two places
down the evidence ranking. That is a single-source dependence the summary score alone
would hide.

**Honest by construction.** The audit reports:
- **Evidence rank is not the displayed rank.** The `#N` on a card is the knowledge-graph
  order; the audit computes a separate *evidence* rank and labels both.
- **Study independence is unverified.** The corpus has no trial-registration or author
  metadata linking distinct PMIDs, so independence is reported as `unknown`, never assumed.
- **Direction labels are unvalidated heuristics**, with the exact triggering sentence
  stored. Unclassified sources are not evidence of consistency.
- **Safety ≠ efficacy.** Harm/risk language is recorded as a separate safety signal and is
  never folded into a "contradictory" direction.
- **Stability is not clinical validity.** Stated in the UI, not just the docs.

---

## Demo Queries

| Disease | Candidates | Known Indications |
|---|---|---|
| Alzheimer's disease | 10 | 13 |
| Parkinson's disease | 10 | 27 |
| Multiple myeloma | 10 | 13 |
| Type 2 diabetes | 10 | 40 |
| Asthma | 10 | 27 |

**Live demo:** https://pharmasure-y64x.onrender.com (UI) ·
https://adminit.tailb9365a.ts.net (direct, same-origin)

The model backend runs on a local GPU host and is published over a Tailscale Funnel; the
Render-hosted UI proxies `/api/*` to it same-origin.

---

## Tests

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python -m pytest tests/ -q                      # full suite
venv/bin/python -m pytest tests/test_audit.py -v         # audit algorithm
venv/bin/python scripts/evaluate_audit.py                # reproducible evaluation
```

Current: **87 passed**.

## Project Structure

```
PharmaSure/
├── src/
│   ├── embeddings.py      # Ollama embedding client (truncation + retry)
│   ├── kg.py              # EveryCure knowledge graph
│   ├── retrieval.py       # NumPy cosine similarity + re-rank + scoring
│   ├── llm.py             # Local qwen3.8 client (robust JSON handling)
│   ├── verify.py          # Two-stage citation verification
│   ├── audit.py           # Counterfactual evidence auditing (CCEA)
│   ├── pipeline.py        # End-to-end RAG orchestration
│   └── app.py             # FastAPI + React frontend + Gradio at /gradio
├── frontend/              # React 18 + TypeScript + Vite + Tailwind
│   └── src/components/
│       ├── CandidateCard.tsx
│       ├── CitationDrawer.tsx
│       └── EvidenceAudit.tsx      # Evidence stability audit UI
├── data/
│   ├── pubmed_passages.json   # 842 real PubMed abstracts, 113 diseases
│   ├── demo_cache.json        # Precomputed results for 5 demo queries
│   ├── index.npy              # Embedding index (840 × 768)
│   └── passages.json          # Indexed passage metadata
├── scripts/
│   ├── build_corpus.py        # Fetch real abstracts from PubMed
│   ├── rebuild_index.py       # Re-embed and rebuild the index
│   └── evaluate_audit.py      # Reproducible audit evaluation
├── tests/
│   ├── test_audit.py          # Audit algorithm unit tests
│   └── test_api_integration.py
├── docs/
│   ├── EVIDENCE_AUDIT.md  # Audit methodology + limitations
│   ├── STACK.md           # Stack design
│   ├── DECISIONS.md       # Decision log
│   ├── DATA_SCHEMA.md     # EveryCure schema
│   ├── EVALUATION_CRITERIA.md
│   └── PITCH_DECK.md      # 6-slide pitch deck
├── requirements.txt
└── README.md
```

---

## Status

- [x] Vertical slice complete
- [x] Real PubMed corpus — 842 abstracts across 113 diseases
- [x] Per-candidate evidence scoring with published formula breakdown
- [x] Two-stage citation verification (contiguous verbatim quotes only)
- [x] Citation-level counterfactual evidence auditing (CCEA)
- [x] React research UI + citation drawer + legacy Gradio console
- [x] Demo cache for 5 queries, rebuilt with audits
- [x] 87 automated tests passing
- [ ] Expand corpus beyond 113 diseases
- [ ] Cross-PMID study-independence linkage
- [ ] Expert adjudication of evidence-direction labels

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Embeddings | Ollama nomic-embed-text | Local, fast, no rate limits |
| Vector store | NumPy | Small corpus, <100ms query |
| LLM | Gemini Flash / qwen3.8:27b | Strong JSON output, fits in 20GB VRAM |
| Data | EveryCure matrix-scores | 39.4M pairs, true indication labels |
| Scoring | 0.25*relevance + 0.35*support + 0.40*study_quality | Per-candidate, transparent |

---

## License

MIT
