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
User query → Disease Resolution → Candidate Generation → Embedding & Retrieval → Re-ranking → Generation & Verification → Scoring → Ranked Output
```

1. **Disease Resolution** — Normalize to OMIM/MONDO ID
2. **Candidate Generation** — EveryCure KG: y=2 repurposing candidates
3. **Embedding & Retrieval** — Ollama nomic-embed-text + cosine similarity
4. **Re-ranking** — Relevance + study quality + recency
5. **Generation** — Gemini/qwen3.8 grounded in passages
6. **Verification** — Citation validation (no citation = no claim)
7. **Scoring** — Per-candidate evidence score (relevance + support + study quality)

---

## Demo Queries

| Disease | Candidates | Known Indications |
|---|---|---|
| Alzheimer's disease | 10 | 13 |
| Parkinson's disease | 10 | 27 |
| Multiple myeloma | 10 | 13 |
| Type 2 diabetes | 10 | 42 |
| Asthma | 10 | 28 |

**Live Demo:** https://issues-chest-appear-circumstances.trycloudflare.com

---

## Project Structure

```
PharmaSure/
├── src/
│   ├── embeddings.py      # Ollama embedding client
│   ├── kg.py              # EveryCure knowledge graph
│   ├── retrieval.py       # NumPy cosine similarity + re-rank + scoring
│   ├── llm.py             # Gemini/qwen3.8 client
│   ├── verify.py          # Citation verification
│   ├── pipeline.py        # End-to-end RAG orchestration
│   └── app.py             # Gradio UI
├── data/
│   ├── pubmed_passages.json   # 26 real PubMed abstracts
│   ├── demo_cache.json        # Precomputed results for 5 queries
│   ├── index.npy              # Embedding index
│   └── passages.json          # Passage metadata
├── docs/
│   ├── STACK.md           # Stack design
│   ├── DECISIONS.md       # Decision log
│   ├── DATA_SCHEMA.md     # EveryCure schema
│   └── PITCH_DECK.md      # 6-slide pitch deck
├── requirements.txt
├── .env                   # API keys (gitignored)
└── README.md
```

---

## Status

- [x] Vertical slice complete
- [x] Real PubMed corpus (26 abstracts)
- [x] Per-candidate evidence scoring
- [x] Gradio UI with citation viewer
- [x] Demo cache for 5 queries
- [ ] Expand corpus to 500+ passages
- [ ] Add expert review layer
- [ ] Arena.ai deployment

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
