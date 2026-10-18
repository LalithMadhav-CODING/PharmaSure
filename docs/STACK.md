# 🏗️ Stack Design — Telemedicon (Drug Repurposing via Literature RAG)

> **Event:** Telemedicon 2026 · Internal Hackathon (AI + Digital Health)
> **Team:** Solo · **Timeline:** 26h (10am Oct 17 → 12pm Oct 18) with 3h buffer

---

## Overview

A clinician or researcher types a disease name. The system retrieves relevant
biomedical literature passages and generates a **ranked list of drug
repurposing candidates with citations** — grounded in real sources, not
hallucinated.

```
User types: "Alzheimer's disease"
         │
         ▼
┌────────────────────┐
│  Query Analyzer    │  Gemini Flash (structured output)
│  extract entities   │  → {disease: "Alzheimer's", drugs: [...]}
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Retrieval Engine  │  numpy cosine similarity over
│  (dense)           │  nomic-embed-text vectors
└────────┬───────────┘
         │ top-10 passages
         ▼
┌────────────────────┐
│  Re-rank           │  score by relevance + evidence strength
│  (heuristic)       │
└────────┬───────────┘
         │ top-5
         ▼
┌────────────────────┐
│  Answer Generator  │  Gemini Flash (grounded in passages)
│  + Citations       │  → ranked drug list + reasons + [1][2][3]
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Gradio UI         │  query box → results → clickable citations
│                    │  → source passage viewer
└────────────────────┘
```

---

## Layer-by-layer

### 1. Embeddings — Ollama `nomic-embed-text`

| | |
|---|---|
| **Model** | `nomic-embed-text:latest` (274 MB, 768-dim) |
| **Transport** | Ollama `/api/embeddings` over HTTP |
| **Why local** | 10–100x faster than API calls; zero rate limits; no key; works offline |
| **Speed** | ~ms per batch; near-instant query-time embedding |
| **Known limit** | General-purpose, not biomedical-fine-tuned. Adequate for 5–10k corpus. |

**Rejected alternative:** Gemini embeddings (slower, rate-limited, billed per request).

### 2. Vector store — numpy cosine similarity

| | |
|---|---|
| **Method** | `numpy.dot(query_vec, corpus_vec.T)` → argsort |
| **Corpus size** | 5,000–10,000 passages |
| **Latency** | <100ms per query |
| **Why not FAISS** | Corpus is small; FAISS is overkill. Can upgrade later if corpus grows. |

### 3. LLM — Gemini Flash

| | |
|---|---|
| **Model** | `gemini-3.8-flash` |
| **Transport** | `google-generativeai` Python SDK |
| **Used for** | Query analysis (structured output) + grounded answer generation |
| **Key config** | `temperature=0` for reproducible answers |

**Rejected alternative:** Ollama `qwen3:4b` — smaller, weaker tool calling. Gemini Flash is stronger for structured output + generation.

### 4. UI — Gradio

| | |
|---|---|
| **Framework** | `gradio` 6.30 |
| **Layout** | Text input → ranked results → clickable citations → source viewer |
| **Why** | Single pip install, looks professional, built in Python |

### 5. Data — HuggingFace `datasets`

| | |
|---|---|
| **EveryCure KG** | `everycure/drug-list`, `everycure/disease-list`, `everycure/kg-edges` (CC-BY 4.0) |
| **PubMed abstracts** | ~500–1,000 via E-utilities API or HuggingFace dataset |
| **Format** | Unified JSONL: `{text, source, drug, disease, pmid}` |

---

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Embeddings | Ollama nomic-embed-text | Speed priority; already running; no rate limits |
| Vector store | numpy | Small corpus; <100ms query; zero install risk |
| LLM | Gemini Flash (`gemini-3.8-flash`) | Stronger than qwen3:4b; better structured output |
| UI | Gradio | Fast to build; professional; Python-native |
| Torch/Transformers | **Excluded** | 1.5–2h install risk on Python 3.12; unnecessary |
| LangChain | **Excluded** | Abstraction overkill for a simple RAG pipeline |
| FAISS | **Excluded** | Overkill for <10k corpus |

---

## File structure

```
Telemedicon/
├── src/
│   ├── embeddings.py      # Ollama embedding client
│   ├── retrieval.py       # numpy cosine similarity + re-rank
│   ├── llm.py             # Gemini Flash client (query analysis + generation)
│   ├── pipeline.py        # end-to-end RAG orchestration
│   └── app.py             # Gradio UI
├── data/
│   └── corpus.jsonl       # unified passage corpus
├── docs/
│   ├── STACK.md           # this file
│   └── DECISIONS.md       # change log + decision history
├── requirements.txt
├── .gitignore             # ignores .env, venv/, __pycache__/
└── README.md
```

---

## Known limitations

1. **Embeddings not biomedical-fine-tuned** — nomic-embed-text is general-purpose. Acceptable for demo scale.
2. **numpy vector store** — fine for <10k, would need FAISS beyond that.
3. **PubMed coverage** — only ~500–1,000 abstracts, not the full 360GB corpus.
4. **Heuristic re-rank** — not a trained cross-encoder; uses evidence-strength heuristics.
5. **Gemini Flash may hallucinate** — mitigated by grounding prompt + citation requirement ("no citation, no claim").
