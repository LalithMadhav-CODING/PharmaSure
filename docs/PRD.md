# 📋 Product Requirements Document

# Telemedicon — Drug Repurposing via Literature RAG

**Telemedicon 2026 · Internal Hackathon · AI + Digital Health**
**Version** 1.0 · **Date** 2026-10-18 · **Status** Skeleton complete, build in progress
**Author** Solo participant + AI agent (Hermes)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Objectives](#3-goals--objectives)
4. [Non-Goals](#4-non-goals)
5. [Target Users & Personas](#5-target-users--personas)
6. [User Stories & Use Cases](#6-user-stories--use-cases)
7. [System Overview](#7-system-overview)
8. [Functional Requirements](#8-functional-requirements)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Data Requirements](#10-data-requirements)
11. [Technical Stack](#11-technical-stack)
12. [API Design](#12-api-design)
13. [UI/UX Requirements](#13-uiux-requirements)
14. [Evaluation & Judging Criteria](#14-evaluation--judging-criteria)
15. [Success Metrics](#15-success-metrics)
16. [Timeline & Milestones](#16-timeline--milestones)
17. [Risks & Mitigations](#17-risks--mitigations)
18. [Assumptions & Constraints](#18-assumptions--constraints)
19. [Future Work & Stretch Goals](#19-future-work--stretch-goals)
20. [Appendix](#20-appendix)

---

## 1. Executive Summary

**Telemedicon** is a literature-based drug repurposing assistant. A clinician or
researcher types a disease name; the system retrieves relevant biomedical
literature and generates a **ranked list of drug repurposing candidates with
citations** — grounded in real sources, not hallucinated.

**The problem it solves:** finding new uses for existing drugs currently takes
weeks of manual literature review. Telemedicon compresses this to seconds by
combining dense retrieval over a biomedical corpus with a citation-grounded
language model.

**The one-sentence pitch:** *"A doctor wants to repurpose an existing drug for
Alzheimer's. Normally this means weeks of literature review. Telemedicon does
it in seconds — with citations."*

---

## 2. Problem Statement

| | |
|---|---|
| **Current state** | Drug repurposing research is literature-bound. A researcher manually searches PubMed, reads abstracts, and cross-references drug databases. |
| **Pain point** | A single repurposing hypothesis can require reviewing 50–200 papers. At ~5 min per paper, that's 4–17 hours of reading per disease. |
| **Root cause** | No tool combines **structured drug-disease knowledge** with **retrievable literature passages** and **citation-grounded generation** in one interface. |
| **Impact** | Slower research, missed repurposing opportunities, and (without grounding) LLM-generated suggestions that can't be verified. |

---

## 3. Goals & Objectives

### Primary goal
Build a working prototype that, given a disease name, returns a **ranked list of
drug repurposing candidates with clickable citations to source passages**.

### Secondary goals
- **Grounded, not hallucinated** — every claim links to a source passage
- **Fast** — query-to-answer in <5 seconds
- **Clinically relevant** — suggestions a researcher would take seriously
- **Demo-able** — a clean, presentable interface for the hackathon

### Objectives (SMART)
| Objective | Measurable target |
|---|---|
| Corpus size | 5,000–10,000 passages |
| Retrieval latency | <100ms per query |
| End-to-end latency | <5 seconds |
| Citation coverage | 100% of claims have a citation |
| Demo uptime | 100% during the presentation |

---

## 4. Non-Goals

Explicitly **out of scope** for the hackathon prototype:

- ❌ **Not a diagnostic tool** — does not diagnose patients or recommend treatments
- ❌ **Not a substitute for clinical judgment** — output is "research hypotheses," not medical advice
- ❌ **Not a full PubMed corpus** — we use a curated subset (~500–1,000 abstracts), not all 36M+ papers
- ❌ **Not a drug interaction checker** — does not check contraindications or dosing
- ❌ **Not real-time** — the corpus is pre-indexed, not live-searching PubMed
- ❌ **Not multi-language** — English only
- ❌ **Not a published product** — no auth, no accounts, no persistence across sessions

---

## 5. Target Users & Personas

### Primary persona — Dr. Researcher
| Attribute | Value |
|---|---|
| **Role** | Pharmacology researcher / clinician-scientist |
| **Goal** | Find repurposing candidates for a disease of interest |
| **Pain** | Weeks of manual literature review |
| **Tech comfort** | High (uses PubMed, Zotero, Python) |
| **Success looks like** | A ranked list of candidates with evidence they can verify |

### Secondary persona — Hackathon Judge
| Attribute | Value |
|---|---|
| **Role** | Evaluating technical innovation, clinical relevance, prototype quality |
| **Goal** | Assess whether the tool solves a real problem, works, and is novel |
| **Success looks like** | A clean demo, a clear story, and visible technical depth |

### Tertiary persona — Student / Hobbyist
| Attribute | Value |
|---|---|
| **Role** | Learning about RAG / drug discovery |
| **Goal** | Understand how literature RAG works |
| **Success looks like** | A tool they can query and learn from |

---

## 6. User Stories & Use Cases

### US-1 — Disease query → ranked candidates
> *As a researcher, I type "Alzheimer's disease" and get a ranked list of 5
> drugs that have been studied for it, each with a reason and a citation.*

**Acceptance criteria:**
 Returns 3–10 candidates, each with a confidence score,
a reason, and at least one clickable citation.

### US-2 — Verify a claim
> *As a researcher, I click a citation [1] and see the exact source passage the
> claim came from.*

**Acceptance criteria:** Clicking a citation opens a viewer showing the source
passage text, its source (PMID or KG edge), and the drug/disease it relates to.

### US-3 — Understand the reasoning
> *As a researcher, I expand "Why this drug?" and see the mechanism or evidence
> that supports the suggestion.*

**Acceptance criteria:** Each candidate has an expandable reasoning section
grounded in the retrieved passages.

### US-4 — Judge demo
> *As a judge, I see a clean interface, a fast response, and a clear story about
> why this matters.*

**Acceptance criteria:** Demo completes in <30 seconds, shows the full pipeline
(query → retrieval → answer), and every claim is citable.

### US-5 — Explore the corpus
> *As a student, I can see what data the system is built on.*

**Acceptance criteria:** A "Data" or "About" section shows corpus size, sources,
and example passages.

---

## 7. System Overview

### High-level architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                │
│                  "Alzheimer's disease"                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      UI LAYER                               │
│              Gradio (now) → Custom HTML (later)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   PIPELINE LAYER                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Query      │→ │  Retrieval   │→ │   Answer     │      │
│  │   Analyzer   │  │  Engine      │  │  Generator   │      │
│  │  (Gemini)    │  │  (numpy)     │  │  (Gemini)    │      │
│  └──────────────┘  └──────┬───────┘  └──────────────┘      │
│                           │                                 │
│                    ┌──────┴───────┐                         │
│                    │  Re-ranker   │                         │
│                    │  (heuristic) │                         │
│                    └──────────────┘                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  EveryCure KG  │  │  PubMed        │  │  Embedding   │  │
│  │  (structured)  │  │  abstracts     │  │  index       │  │
│  │  drug-list     │  │  (literature)  │  │  (npy+json)  │  │
│  │  disease-list  │  │                │  │              │  │
│  │  kg-edges      │  │                │  │              │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data flow

```
Raw sources → Acquire → Normalize → Clean → Chunk → Embed → Index → Persist
                                                                        │
                                                                        ▼
User query → Embed query → Search index → Re-rank → Generate answer + citations
```

---

## 8. Functional Requirements

### FR-1 — Query input
| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Accept a free-text disease name or description | Must |
| FR-1.2 | Accept example queries (pre-loaded buttons) | Should |
| FR-1.3 | Validate non-empty input | Must |
| FR-1.4 | Show a loading state while processing | Should |

### FR-2 — Query analysis
| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Extract disease entity from the query | Must |
| FR-2.2 | Extract any drug mentions (for filtering) | Should |
| FR-2.3 | Return structured output (JSON) | Must |
| FR-2.4 | Handle ambiguous/vague queries gracefully | Should |

### FR-3 — Retrieval
| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Embed the query using nomic-embed-text | Must |
| FR-3.2 | Compute cosine similarity against the index | Must |
| FR-3.3 | Return top-10 passages | Must |
| FR-3.4 | Re-rank by relevance + evidence strength | Should |
| FR-3.5 | Filter by drug/disease if specified | Could |

### FR-4 — Answer generation
| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Generate a ranked list of 3–10 drug candidates | Must |
| FR-4.2 | Each candidate has a confidence score | Must |
| FR-4.3 | Each candidate has a reason grounded in passages | Must |
| FR-4.4 | Each claim has at least one citation | Must |
| FR-4.5 | "No citation, no claim" — no uncited claims | Must |
| FR-4.6 | Expandable "Why this drug?" reasoning | Should |

### FR-5 — Citation viewer
| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Clickable citations [1], [2], [3] | Must |
| FR-5.2 | Show source passage text | Must |
| FR-5.3 | Show source metadata (PMID, drug, disease) | Must |
| FR-5.4 | Highlight the relevant span in the passage | Could |

### FR-6 — UI
| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Clean, professional interface | Must |
| FR-6.2 | Results panel with ranked candidates | Must |
| FR-6.3 | Citation viewer panel | Must |
| FR-6.4 | "Why this drug?" expandable sections | Should |
| FR-6.5 | Example query buttons | Should |
| FR-6.6 | About / data source section | Could |

---

## 9. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Query-to-answer latency | <5 seconds |
| NFR-2 | Retrieval latency | <100ms |
| NFR-3 | Embedding batch time | <5 minutes (5k passages) |
| NFR-4 | Index load time | <2 seconds |
| NFR-5 | Demo uptime | 100% during presentation |
| NFR-6 | Citation coverage | 100% of claims |
| NFR-7 | Corpus size | 5,000–10,000 passages |
| NFR-8 | Python version | 3.12 |
| NFR-9 | GPU | RTX 4000 Ada 20GB (optional, not required) |
| NFR-10 | Offline capability | Embeddings + index work offline; LLM requires internet |

---

## 10. Data Requirements

### 10.1 Sources

| Source | Type | Size | License | Access |
|---|---|---|---|---|
| EveryCure `drug-list` | Structured | ~1,800 drugs | CC-BY 4.0 | HuggingFace |
| EveryCure `disease-list` | Structured | ~22,000 diseases | CC-BY 4.0 | HuggingFace |
| EveryCure `kg-edges` | Structured | drug-disease pairs | CC-BY 4.0 | HuggingFace |
| PubMed abstracts | Literature | ~500–1,000 | Public domain | E-utilities API |

### 10.2 Unified schema

```json
{
  "text": "Metformin has been studied for neuroprotective effects in Alzheimer's...",
  "source": "pubmed | kg-edge",
  "drug": "Metformin",
  "disease": "Alzheimer's disease",
  "pmid": "38912345 | null"
}
```

### 10.3 Chunking

| Parameter | Value |
|---|---|
| Chunk size | 300–500 characters |
| Overlap | 50 characters |
| Method | Character-based with sentence-boundary preference |

### 10.4 Embedding

| Parameter | Value |
|---|---|
| Model | `nomic-embed-text` (Ollama) |
| Dimensions | 768 |
| Batch size | 10–20 passages per request |
| Storage | numpy `.npy` + JSON metadata |

---

## 11. Technical Stack

| Layer | Tool | Version | Role |
|---|---|---|---|
| Language | Python | 3.12 | Core |
| Embeddings | Ollama `nomic-embed-text` | latest | Text → vectors |
| Vector store | numpy | 2.x | Cosine similarity search |
| LLM | Gemini Flash | `gemini-3.8-flash` | Query analysis + generation |
| LLM SDK | google-generativeai | 0.8.x | Gemini API client |
| Data | HuggingFace datasets | 5.x | KG download |
| Data | pandas | 3.x | Data manipulation |
| HTTP | httpx | 0.28 | Async Ollama calls |
| UI | Gradio | 6.30 | Current interface |
| Config | python-dotenv | 1.x | API key management |
| VCS | git | — | Version control |

**Deliberately excluded:** torch, transformers, sentence-transformers, langchain, FAISS.

---

## 12. API Design

### 12.1 Internal pipeline API (Python functions)

```python
# embeddings.py
def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts → (N, 768) numpy array."""

# retrieval.py
def search_index(query_vec: np.ndarray, index: np.ndarray, top_k: int = 10) -> list[int]:
    """Return indices of top-k most similar passages."""

def rerank(passages: list[dict], query: str) -> list[dict]:
    """Re-rank by relevance + evidence strength."""

# llm.py
def analyze_query(query: str) -> dict:
    """Extract disease/drug entities → structured output."""

def generate_answer(query: str, passages: list[dict]) -> dict:
    """Generate ranked candidates + reasons + citations."""

# pipeline.py
def run_pipeline(query: str) -> dict:
    """End-to-end: query → analyzed → retrieved → reranked → answered."""
```

### 12.2 Future REST API (for custom frontend)

```
POST /api/query
  Request:  {"query": "Alzheimer's disease"}
  Response: {
    "query": "Alzheimer's disease",
    "entities": {"disease": "Alzheimer's", "drugs": []},
    "results": [
      {
        "rank": 1,
        "drug": "Metformin",
        "confidence": 0.87,
        "reason": "...",
        "citations": [1, 3]
      }
    ],
    "passages": [
      {"id": 1, "text": "...", "source": "pubmed", "pmid": "..."}
    ]
  }

GET /api/health
  Response: {"status": "ok", "corpus_size": 7500}
```

---

## 13. UI/UX Requirements

### 13.1 Layout (Gradio — current)

```
┌─────────────────────────────────────────────┐
│  💊 Telemedicon — Drug Repurposing RAG       │
├─────────────────────────────────────────────┤
│                                             │
│  [ Query input box                    ]     │
│  [ Example: Alzheimer's ] [ Example: Cancer ]│
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Results                              │  │
│  │                                       │  │
│  │  1. Metformin        ████████░░ 0.87  │  │
│  │     Reason: ...                       │  │
│  │     [Why this drug? ▾]                │  │
│  │     Citations: [1] [3]                │  │
│  │                                       │  │
│  │  2. ...                               │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Citation viewer                      │  │
│  │  [1] Metformin studied for Alzheimer's│  │
│  │  PMID: 38912345                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

### 13.2 Design principles
- **Clean** — white/light background, clear typography
- **Fast** — results appear in <5 seconds
- **Trustworthy** — citations visible by default, not hidden
- **Professional** — looks like a product, not a demo

### 13.3 Future custom frontend
- Single-page app (HTML/CSS/JS or React)
- Served by FastAPI as static files
- Same API as §12.2
- User will provide the design

---

## 14. Evaluation & Judging Criteria

| Criterion | Weight | How we score |
|---|---|---|
| **Technical innovation** | High | RAG pipeline + citation grounding + structured output |
| **Clinical relevance** | High | Real drug-disease data, real literature, researcher-facing |
| **Prototype quality** | High | Clean UI, fast, working demo, no crashes |
| **Presentation** | Medium | 3-min demo, clear story, rehearsed |
| **Code quality** | Medium | Clean, documented, git-tracked |

### Demo script (3 minutes)
1. **Hook (30s):** "A doctor wants to repurpose a drug for Alzheimer's. Normally = weeks of review. We built a tool that does it in seconds."
2. **Query (30s):** Type "Alzheimer's disease" → show the system working
3. **Results (60s):** Show ranked candidates → click a citation → show source passage → "grounded, not hallucinated"
4. **Reasoning (30s):** Show "Why this drug?" → the evidence chain
5. **Impact (30s):** "For researchers, clinicians, and students."

---

## 15. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Query-to-answer latency | <5s | Timer in pipeline |
| Retrieval latency | <100ms | Timer in retrieval |
| Citation coverage | 100% | Every claim has a [n] |
| Demo success | 100% | Demo works during presentation |
| Corpus size | 5–10k | Count of passages |
| User satisfaction | Qualitative | Judge feedback |

---

## 16. Timeline & Milestones

| Time | Phase | Hours | Exit criteria | Status |
|---|---|---|---|---|
| 10–12 | Setup | 2h | venv, libs, models, docs | ✅ done |
| 12–14 | Data pipeline | 2h | clean corpus of 5–10k | pending |
| 14–15:30 | Embed + index | 1.5h | searchable index | pending |
| 15:30–18:30 | RAG pipeline | 3h | query → cited answer | pending |
| 18:30–21 | UI | 2.5h | Gradio interface live | pending |
| 21–00 | Integrate + test | 3h | end-to-end demo works | pending |
| 00–06 | Sleep | — | — | — |
| 06–08 | Demo prep | 2h | scripted + rehearsed | pending |
| 08–09 | Final polish | 1h | buffer starts | pending |
| **09–12** | **Buffer** | **3h** | submit | — |

**Total:** 17 working + 6 sleep + 3 buffer = 26 hours

---

## 17. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Package install fails | Low | High | Use `--user` + specific versions; CLI fallback |
| Ollama embedding slow | Low | Medium | Batch embed; keep model warm |
| PubMed API rate-limited | Medium | Medium | Use HuggingFace dataset fallback |
| Gemini API down | Low | High | Cache results; have screenshots backup |
| Demo breaks live | Medium | High | Record video backup; test thoroughly |
| Hallucination | Medium | High | Grounding prompt + "no citation, no claim" |
| Time runs out | Medium | High | Prioritize: pipeline > UI > extras |
| Corpus too small | Low | Medium | Use both EveryCure + PubMed; supplement with KG edges |

---

## 18. Assumptions & Constraints

### Assumptions
- Gemini API key remains valid through the hackathon
- Ollama remains running with `nomic-embed-text` pulled
- Internet access available for Gemini API + PubMed download
- User will provide custom frontend files before the demo

### Constraints
- **Time:** 26 hours total, 17 working hours
- **Solo:** one human + one AI agent
- **Compute:** RTX 4000 Ada 20GB (optional), CPU fallback works
- **Data:** public sources only, no credentialed datasets
- **Model:** ≤4B params for any local model (hackathon rule)

---

## 19. Future Work & Stretch Goals

| Priority | Feature | Effort |
|---|---|---|
| P1 | Custom HTML/JS frontend (user-provided) | 2–3h |
| P1 | FastAPI backend for custom frontend | 1h |
| P2 | Cross-encoder re-ranker (trained) | 3–4h |
| P2 | Full PubMed corpus (streaming) | 4–6h |
| P3 | Drug-disease knowledge graph visualization | 2–3h |
| P3 | Multi-turn conversation memory | 2h |
| P3 | Export results to CSV/JSON | 1h |
| P4 | Fine-tuned biomedical embeddings | 6–8h |
| P4 | Clinical trial matching | 4–6h |

---

## 20. Appendix

### 20.1 Glossary

| Term | Definition |
|---|---|
| **RAG** | Retrieval-Augmented Generation — retrieve relevant passages, then generate an answer grounded in them |
| **KG** | Knowledge Graph — structured entities (drugs, diseases) and relationships |
| **PMID** | PubMed Identifier — unique ID for a PubMed article |
| **Embedding** | A dense vector representation of text for semantic search |
| **Cosine similarity** | A measure of similarity between two vectors (1 = identical, 0 = unrelated) |
| **Grounding** | Constraining an LLM's output to retrieved sources, not parametric knowledge |
| **Citation** | A link from a claim in the answer to the source passage it came from |

### 20.2 References

| Resource | Link |
|---|---|
| EveryCure datasets | https://huggingface.co/everycure |
| PubMed E-utilities | https://www.ncbi.nlm.nih.gov/books/NBK25501/ |
| Ollama | https://ollama.com |
| Gemini API | https://ai.google.dev |
| Gradio | https://gradio.app |
| Project stack design | `docs/STACK.md` |
| Decision log | `docs/DECISIONS.md` |

### 20.3 Document history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-18 | Initial PRD |

---

> [!info] How to use this document
> This PRD is the single source of truth for what we're building and why.
> Every functional requirement traces back to a user story; every design decision
> traces back to a constraint or goal. If something isn't in here, it's out of scope.
