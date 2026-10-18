# 📋 Product Requirements Document

# Telemedicon — Drug Repurposing via Literature RAG

**Telemedicon 2026 · Internal Hackathon · AI + Digital Health**
**Version** 1.2 · **Date** 2026-10-18 · **Status** PRD locked, vertical slice next
**Author** Solo participant + AI agent (Hermes)

> **What changed in v1.2:** see [§20.3 Document history](#203-document-history). Decisions were debated across 4 lenses (strategy, feasibility, clinical credibility, UX/demo) and locked. Unresolved assumptions are tagged **[ASSUMPTION]** and listed in [§18.3](#183-open-items-to-verify).

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
18. [Assumptions, Constraints & Open Items](#18-assumptions-constraints--open-items)
19. [Future Work & Stretch Goals](#19-future-work--stretch-goals)
20. [Appendix](#20-appendix)

---

## 1. Executive Summary

**Telemedicon** is a literature-based drug repurposing assistant. A clinician or
researcher types a disease name; the system proposes **repurposing candidates**
from a structured drug–disease knowledge graph, then gathers **literature evidence
for each candidate** and returns a ranked list where **every claim is backed by
a verified quote from a source passage**.

**The problem it solves:** finding new uses for existing drugs currently takes
weeks of manual literature review. Telemedicon compresses the first pass to
seconds by combining structured knowledge (candidate generation), dense
retrieval over biomedical text (evidence), and a citation-verified language
model (explanation).

**What makes it credible (not just fast):**
- **Repurposing, not rediscovery:** drugs already indicated for the disease are labelled, not presented as new ideas.
- **Verified citations:** each claim carries a verbatim quote that is programmatically checked against the cited passage.
- **Honest scoring:** the score shown is an *evidence score* computed from retrieval and study type, not an LLM's self-reported confidence.
- **Honest limits:** if the corpus lacks evidence for a disease, the system says so.
- **Evidence direction:** each candidate is tagged Positive / Negative / Mixed / Uncertain — a drug that failed trials is not presented as a success.

**The one-sentence pitch:** *"A doctor wants to repurpose an existing drug for
Alzheimer's. Normally this means weeks of literature review. Telemedicon does
the first pass in seconds, and every claim is checkable."*

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
Build a working prototype that, given a disease name from the supported set,
returns a **ranked list of drug repurposing candidates with verified, clickable
citations to source passages**, with already-indicated drugs clearly labelled.

### Secondary goals
- **Grounded, not hallucinated:** every claim links to a source passage *and* a verified supporting quote
- **Fast:** query-to-answer in <5 seconds
- **Clinically relevant:** suggestions a researcher would take seriously
- **Honest:** abstains when evidence is insufficient
- **Transparent:** evidence direction (positive/negative/mixed) and study quality are visible
- **Demo-able:** a clean, presentable interface for the hackathon

### Objectives (SMART)
| Objective | Measurable target |
|---|---|
| Corpus size | 3,000–10,000 passages total (PubMed chunks + KG-edge passages) |
| Supported diseases | 5–10, listed in the UI "About" panel |
| Retrieval latency | <100 ms for the search step (query embedding timed separately) |
| End-to-end latency | <5 s p95 (uncached); <1 s for cached demo queries |
| Citation validity | 100% of *displayed* claims pass the two-stage verifier |
| Retrieval quality | Recall@10 ≥ 70% of gold-set drugs surfaced (initial target; tune after first run) |
| Demo uptime | 100% during the presentation (cached fallback available) |

---

## 4. Non-Goals

Explicitly **out of scope** for the hackathon prototype:

- ❌ **Not a diagnostic tool:** does not diagnose patients or recommend treatments
- ❌ **Not a substitute for clinical judgment:** output is "research hypotheses," not medical advice
- ❌ **Not a claim of efficacy:** a high evidence score means *more supporting literature in our corpus*, not that the drug works
- ❌ **Not a full PubMed corpus:** we use a curated subset (~500–1,000 abstracts), not all 36M+ papers
- ❌ **Not a drug interaction checker:** does not check contraindications or dosing
- ❌ **Not real-time:** the corpus is pre-indexed, not live-searching PubMed
- ❌ **Not multi-language:** English only
- ❌ **Not a published product:** no auth, no accounts, no persistence across sessions
- ❌ **Not per-candidate retrieval loops:** skipped for P0 (see §7)
- ❌ **Not a REST API or custom frontend:** deferred (see §12.2, §13.3)

---

## 5. Target Users & Personas

### Primary persona: Dr. Researcher
| Attribute | Value |
|---|---|
| **Role** | Pharmacology researcher / clinician-scientist |
| **Goal** | Find repurposing candidates for a disease of interest |
| **Pain** | Weeks of manual literature review |
| **Tech comfort** | High (uses PubMed, Zotero, Python) |
| **Success looks like** | A ranked list of *new* candidates with evidence they can verify |

### Secondary persona: Hackathon Judge
| Attribute | Value |
|---|---|
| **Role** | Evaluating technical innovation, clinical relevance, prototype quality |
| **Goal** | Assess whether the tool solves a real problem, works, and is novel |
| **Success looks like** | A clean demo, a clear story, and visible technical depth (including how it avoids hallucination) |

### Tertiary persona: Student / Hobbyist
| Attribute | Value |
|---|---|
| **Role** | Learning about RAG / drug discovery |
| **Goal** | Understand how literature RAG works |
| **Success looks like** | A tool they can query and learn from |

---

## 6. User Stories & Use Cases

### US-1: Disease query → ranked candidates
> *As a researcher, I type "Alzheimer's disease" and get a ranked list of drugs
> that have been studied for it, each with a reason, an evidence score, and a citation.*

**Acceptance criteria:** Returns 3–10 candidates, each with an evidence tier,
a reason, and at least one clickable citation. Drugs already indicated for the
disease are shown in a separate, clearly labelled group.

### US-2: Verify a claim
> *As a researcher, I click a citation [1] and see the exact source passage the
> claim came from.*

**Acceptance criteria:** Clicking a citation opens a viewer showing the source
passage text with the supporting quote highlighted, its source (PMID or KG edge),
and the drug/disease it relates to.

### US-3: Understand the reasoning
> *As a researcher, I expand "Why this drug?" and see the mechanism or evidence
> that supports the suggestion.*

**Acceptance criteria:** Each candidate has an expandable reasoning section
grounded in the retrieved passages, plus the study types behind the evidence score.

### US-4: Judge demo
> *As a judge, I see a clean interface, a fast response, and a clear story about
> why this matters.*

**Acceptance criteria:** The 3-minute scripted demo (§14) runs end to end; each
query returns in <5 s (or instantly from cache); every displayed claim is citable.

### US-5: Explore the corpus
> *As a student, I can see what data the system is built on.*

**Acceptance criteria:** A "Data" or "About" section shows corpus size, sources,
the supported diseases, and example passages.

### US-6: Trust the novelty
> *As a researcher, I can tell which suggestions are already approved for this
> disease and which are genuinely new.*

**Acceptance criteria:** Each result is tagged **Known indication** or
**Repurposing candidate**; known indications are not ranked among the candidates.

### US-7: Know when the system doesn't know
> *As a researcher, if I query a disease the corpus doesn't cover, I get a clear
> "insufficient evidence" message, not a guess.*

**Acceptance criteria:** Out-of-corpus or low-evidence queries return an
abstention message plus the list of supported diseases.

### US-8: See the evidence direction
> *As a researcher, I can see whether the evidence for a candidate is positive,
> negative, or mixed.*

**Acceptance criteria:** Each candidate has a direction tag (Positive / Negative /
Mixed / Uncertain); Uncertain is shown when classification confidence is low.

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
│  1. Disease resolver ── match query to disease-list        │
│            │            (fuzzy match; LLM only as fallback) │
│            ▼                                                │
│  2. Candidate generator ── KG edges → candidate drugs      │
│            │               + known-indication flag          │
│            ▼                                                │
│  3. Evidence retriever ── dense retrieval (numpy)          │
│            │               over corpus passages             │
│            ▼                                                │
│  4. Re-ranker ── study type, recency, relevance            │
│            │      → evidence score                          │
│            ▼                                                │
│  5. Answer generator (Gemini) ── reason + claims + quotes  │
│            ▼                                                │
│  6. Citation verifier (two-stage)                          │
│            │  Stage 1: source identity — does the citation  │
│            │  exist and match the drug+disease?             │
│            │  Stage 2: claim support — does the passage    │
│            │  actually support the claim?                  │
│            │  Flag failures as "needs review"               │
│            ▼                                                │
│  7. Display ── candidates + citations + tiers + direction  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  EveryCure KG  │  │  PubMed        │  │  Indexes     │  │
│  │  drug-list     │  │  abstracts     │  │  dense (npy) │  │
│  │  disease-list  │  │  + metadata    │  │  metadata    │  │
│  │  kg-edges      │  │  (pub type,    │  │  (json)      │  │
│  │  (structured)  │  │   year, PMID)  │  │              │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Demo cache: precomputed results for example queries │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Design rationale:** KG-first gives structured candidates with zero retrieval
latency; literature provides the evidence. Dense retrieval is the fallback if the
KG yields <3 candidates. Per-candidate retrieval loops are skipped for P0.

**Fallback:** if the KG yields fewer than 3 candidates for a disease, fall back
to dense retrieval over disease-level queries and have the LLM extract
drug names from the retrieved passages (still subject to citation verification).

### Data flow

```
Raw sources → Acquire → Normalize → Clean → Chunk → Embed → Index → Persist
                                                                        │
                                                                        ▼
User query → Resolve disease → KG candidates → Dense retrieve →
Re-rank + evidence score → Generate (quotes) → Verify citations (two-stage) → Display
```

---

## 8. Functional Requirements

### FR-1: Query input
| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Accept a free-text disease name or description | Must |
| FR-1.2 | Accept example queries (pre-loaded buttons) | Should |
| FR-1.3 | Validate non-empty input | Must |
| FR-1.4 | Show a loading state while processing | Should |

### FR-2: Query analysis and disease resolution
| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Resolve the query to a disease entity in `disease-list` (string/fuzzy match first) | Must |
| FR-2.2 | If no confident match, optionally call the LLM to normalize the query, then retry the match | Should |
| FR-2.3 | Return structured output (JSON); use the SDK's JSON/schema mode and validate the result | Must |
| FR-2.4 | Handle ambiguous/vague queries gracefully (show top matches, ask the user to pick) | Should |
| FR-2.5 | If the resolved disease is not in the supported set, abstain (see FR-7) | Must |

### FR-3: Candidate generation and retrieval
| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Generate candidate drugs from `kg-edges` for the resolved disease | Must |
| FR-3.2 | Flag candidates that are already indicated for the disease as **Known indication** | Must |
| FR-3.3 | Embed the disease query with nomic-embed-text | Must |
| FR-3.4 | Run dense (cosine) retrieval over the corpus | Must |
| FR-3.5 | Retrieve top-30 passages, re-rank, keep top-10 | Must |
| FR-3.6 | Re-rank by relevance, study type, and recency (§10.5) | Should |
| FR-3.7 | Fallback path when KG candidates < 3 (see §7) | Should |

### FR-4: Answer generation
| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Return 3–10 repurposing candidates (known indications listed separately) | Must |
| FR-4.2 | Each candidate has a computed **evidence score** and tier (Strong / Moderate / Preliminary), not an LLM self-reported confidence | Must |
| FR-4.3 | Each candidate has a reason grounded in its retrieved passages | Must |
| FR-4.4 | The LLM returns, for each claim, the citation ID(s) and a **verbatim supporting quote** | Must |
| FR-4.5 | **Citation verifier (two-stage):** | Must |
| FR-4.5a | Stage 1 — source identity: does the citation ID exist and match the drug+disease? | Must |
| FR-4.5b | Stage 2 — claim support: does the passage actually support the claim? | Must |
| FR-4.5c | Flag failures as **"needs review"** — do not auto-reject paraphrases | Must |
| FR-4.6 | If a candidate has no verified claim, drop the candidate; if verification fails broadly, retry generation once | Must |
| FR-4.7 | Each candidate has an evidence **direction** tag: Positive / Negative / Mixed / Uncertain | Must |
| FR-4.8 | Default direction to **Uncertain** when classification confidence is low | Must |
| FR-4.9 | Expandable "Why this drug?" reasoning | Should |

### FR-5: Citation viewer
| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Clickable citations [1], [2], [3] | Must |
| FR-5.2 | Show source passage text | Must |
| FR-5.3 | Show source metadata (PMID, year, publication type, drug, disease) | Must |
| FR-5.4 | Highlight the verified supporting quote in the passage | Should |
| FR-5.5 | Show "needs review" flag when the verifier is uncertain | Must |
| FR-5.6 | Link out to the PubMed page by PMID | Should |

### FR-6: UI
| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Clean, professional interface | Must |
| FR-6.2 | Results panel with ranked candidates and a separate "Already indicated" group | Must |
| FR-6.3 | Citation viewer panel | Must |
| FR-6.4 | Evidence tier badges (Strong / Moderate / Preliminary) | Must |
| FR-6.5 | Evidence direction tags (Positive / Negative / Mixed / Uncertain) | Must |
| FR-6.6 | "Why this drug?" expandable sections | Should |
| FR-6.7 | Example query buttons | Should |
| FR-6.8 | About / data source section listing supported diseases and corpus stats | Should |
| FR-6.9 | Persistent disclaimer: "Research hypotheses only, not medical advice" | Must |

### FR-7: Robustness and demo safety
| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Abstain with a clear message when the disease is unsupported or evidence is below a minimum threshold | Must |
| FR-7.2 | Cache results for the demo/example queries; serve from cache if the LLM call fails or times out | Must |
| FR-7.3 | LLM call timeout and retry with backoff; surface a friendly error, never a stack trace | Should |
| FR-7.4 | Log per-stage timings (resolve, KG, embed, retrieve, generate, verify) | Should |
| FR-7.5 | Cached demo path works offline (embeddings + index local; no LLM call needed) | Must |

---

## 9. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Query-to-answer latency (uncached) | <5 s p95 |
| NFR-1b | Query-to-answer latency (cached demo query) | <1 s |
| NFR-2 | Search step latency (dense, excluding query embedding) | <100 ms |
| NFR-2b | Query embedding latency, timed and reported separately | Report only |
| NFR-3 | Embedding batch time | <5 minutes (5k passages) |
| NFR-4 | Index load time | <2 seconds |
| NFR-5 | Demo uptime | 100% during presentation |
| NFR-6 | Citation validity (displayed claims passing the verifier) | 100% |
| NFR-7 | Corpus size | 3,000–10,000 passages |
| NFR-8 | Python version | 3.12 |
| NFR-9 | GPU | RTX 4000 Ada 20GB (optional, not required) |
| NFR-10 | Offline capability | Embeddings + index work offline; LLM requires internet; cached demo works offline |

### Latency budget (targets, to be measured)
| Stage | Budget |
|---|---|
| Disease resolve + KG lookup | <100 ms |
| Query embedding | <500 ms |
| Dense retrieval + rerank | <200 ms |
| Gemini generation (single call) | <3 s |
| Citation verification (two-stage) | <50 ms |
| UI render | <300 ms |

---

## 10. Data Requirements

### 10.1 Sources

| Source | Type | Size | License | Access |
|---|---|---|---|---|
| EveryCure `drug-list` | Structured | ~1,800 drugs | CC-BY 4.0 **[ASSUMPTION]** | HuggingFace |
| EveryCure `disease-list` | Structured | ~22,000 diseases | CC-BY 4.0 **[ASSUMPTION]** | HuggingFace |
| EveryCure `kg-edges` | Structured | drug-disease pairs | CC-BY 4.0 **[ASSUMPTION]** | HuggingFace |
| PubMed abstracts | Literature | ~500–1,000 | NLM terms of use **[ASSUMPTION]** | E-utilities API |

### 10.2 Unified schema

```json
{
  "chunk_id": "pm-38912345-2",
  "text": "Metformin has been studied for neuroprotective effects in Alzheimer's...",
  "source": "pubmed | kg-edge",
  "drug": "Metformin",
  "disease": "Alzheimer's disease",
  "pmid": "38912345 | null",
  "year": 2023,
  "pub_type": "clinical_trial | cohort | preclinical | review | other | null"
}
```

### 10.3 Chunking

| Parameter | Value |
|---|---|
| Chunk size | ~400–800 characters |
| Overlap | 1 sentence |
| Method | Sentence-boundary splitting; never split inside a sentence |

### 10.4 Embedding and indexing

| Parameter | Value |
|---|---|
| Model | `nomic-embed-text` (Ollama) |
| Dimensions | 768 |
| Normalization | L2-normalize once at index time; search is then a dot product |
| Dense storage | numpy `.npy` + JSON metadata |
| Sparse index | Not in P0 (dense only; BM25 deferred) |

### 10.5 Evidence score (initial design, to be tuned)

For each candidate, from its top-10 retrieved passages:

```
evidence_score = 0.3 * relevance      # max cosine similarity, min-max normalized
               + 0.3 * support        # min(#supporting passages, 5) / 5
               + 0.4 * study_weight   # best study type among passages
```

| Study type | Weight |
|---|---|
| clinical_trial | 1.0 |
| cohort / observational | 0.7 |
| preclinical (in vitro / animal) | 0.4 |
| review / other | 0.3 |

Tiers: **Strong** ≥ 0.7, **Moderate** 0.4–0.7, **Preliminary** < 0.4.

**Important:** This is an *experimental heuristic*, not a clinical probability.
The weights are starting guesses, not validated values. Label as such in the UI.

### 10.6 Evidence direction

Each candidate is tagged with an evidence direction:

| Direction | Meaning |
|---|---|
| **Positive** | Literature supports the repurposing hypothesis |
| **Negative** | Literature refutes or shows no benefit |
| **Mixed** | Both supporting and refuting evidence found |
| **Uncertain** | Direction cannot be reliably determined (default) |

Direction is classified by the LLM during generation, with Uncertain as the
default when confidence is low.

---

## 11. Technical Stack

| Layer | Tool | Version | Role |
|---|---|---|---|
| Language | Python | 3.12 | Core |
| Embeddings | Ollama `nomic-embed-text` | latest | Text → vectors |
| Dense search | numpy | 2.x | Dot-product search |
| LLM | Gemini Flash | `gemini-3.8-flash` | Generation (single call) |
| LLM SDK | google-generativeai | 0.8.x | Gemini client |
| Data | HuggingFace datasets | 5.x | KG download |
| Data | pandas | 3.x | Data manipulation |
| HTTP | httpx | 0.28 | Ollama calls |
| UI | Gradio | 6.30 | Current interface |
| Config | python-dotenv | 1.x | API key management |

**Deliberately excluded:** torch, transformers, sentence-transformers, langchain, FAISS, BM25 (P0), REST API (P0).

---

## 12. API Design

### 12.1 Internal pipeline API (Python functions)

```python
# embeddings.py
def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts → (N, 768), L2-normalized."""

# kg.py
def resolve_disease(query: str) -> dict | None:
    """Match free text to a disease-list entry (fuzzy)."""

def get_candidates(disease_id: str) -> list[dict]:
    """KG candidates with a 'known_indication': bool flag."""

# retrieval.py
def search_dense(query_vec: np.ndarray, index: np.ndarray, top_k: int = 30) -> list[tuple[int, float]]:
    """Return (chunk_index, score) pairs."""

def rerank(passages: list[dict]) -> list[dict]:
    """Re-rank by relevance, study type, recency; attach per-passage signals."""

def evidence_score(passages: list[dict]) -> dict:
    """{'score': float, 'tier': str, 'support': int, 'best_study_type': str}"""

# llm.py
def generate_answer(disease: str, candidates: list[dict], passages: list[dict]) -> dict:
    """One Gemini call. Per candidate: reason + claims[{text, citation_ids, quote}] + direction."""

# verify.py
def verify_citations(answer: dict, passages_by_id: dict) -> dict:
    """Two-stage: (1) source identity, (2) claim support.
    Flag failures as 'needs review', do not auto-reject."""

# pipeline.py
def run_pipeline(query: str) -> dict:
    """End-to-end: resolve → candidates → retrieve → rerank/score → generate → verify.
    Returns results, passages, and per-stage timings; serves cache for demo queries."""
```

### 12.2 Future REST API (for custom frontend — deferred)

```
POST /api/query
  Request:  {"query": "Alzheimer's disease"}
  Response: {
    "query": "Alzheimer's disease",
    "status": "ok | insufficient_evidence | unsupported_disease",
    "results": [...],
    "known_indications": [...],
    "passages": [...],
    "timings_ms": {"resolve": 0, "embed": 0, "retrieve": 0, "generate": 0, "verify": 0}
  }
```

**Status:** Deferred to P2. Not needed for the Gradio demo.

---

## 13. UI/UX Requirements

### 13.1 Layout (Gradio, current)

```
┌─────────────────────────────────────────────────┐
│  💊 Telemedicon — Drug Repurposing RAG           │
│  ⚠ Research hypotheses only, not medical advice │
├─────────────────────────────────────────────────┤
│                                                 │
│  [ Query input box                        ]     │
│  [ Alzheimer's ] [ Parkinson's ] [ ... ]        │
│  Supported diseases: ...  (About ▸)             │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │  Repurposing candidates                   │  │
│  │                                           │  │
│  │  1. Metformin   Strong ████████ 0.74      │  │
│  │     Direction: Positive                   │  │
│  │     Reason: ... [1] [3]                   │  │
│  │     [Why this drug? ▾]                    │  │
│  │                                           │  │
│  │  2. ...                                   │  │
│  │                                           │  │
│  │  ▸ Already indicated for this disease (2) │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │  Citation viewer                          │  │
│  │  [1] ...highlighted supporting quote...   │  │
│  │  PMID 38912345 · 2023 · clinical trial    │  │
│  │  ✓ Verified | Needs review                │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 13.2 Design principles
- **Clean:** white/light background, clear typography
- **Fast:** results appear in <5 seconds, with a visible loading state
- **Trustworthy:** citations visible by default; the disclaimer always visible
- **Honest:** evidence tier + direction shown; abstention is a first-class result
- **Professional:** looks like a product, not a demo

### 13.3 Future custom frontend
- Single-page app (HTML/CSS/JS)
- Served by FastAPI as static files
- **Status:** Deferred to P2. The demo does not depend on it.

---

## 14. Evaluation & Judging Criteria

### 14.1 Judging criteria

| Criterion | Weight | How we score |
|---|---|---|
| **Technical innovation** | High | KG-first candidates + dense retrieval + two-stage verified-quote citations + computed evidence score |
| **Clinical relevance** | High | Known-indication separation, evidence direction, real drug-disease data, researcher-facing |
| **Prototype quality** | High | Clean UI, fast, working demo, no crashes, cached fallback |
| **Presentation** | Medium | 3-min demo, clear story, rehearsed |
| **Code quality** | Medium | Clean, documented, git-tracked |

### 14.2 Demo script (3 minutes)
1. **Hook (30s):** "A doctor wants to repurpose a drug for Alzheimer's. Normally = weeks of review. We built a tool that does the first pass in seconds."
2. **Query (30s):** Type "Alzheimer's disease" → cached results appear instantly → show ranked candidates with tier badges and direction tags
3. **Results (60s):** Click a citation → show the highlighted quote → "every claim is verified against its source"
4. **Honesty (30s):** Show a "Preliminary" or "Mixed" candidate → "the system reports weak and mixed evidence, not just strong"
5. **Impact (30s):** Query an unsupported disease → "insufficient evidence." Close with "For researchers, clinicians, and students."

---

## 15. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Query-to-answer latency (uncached) | <5 s p95 | Per-stage timers in pipeline |
| Cached demo latency | <1 s | Timer |
| Search-step latency | <100 ms | Timer in retrieval |
| Citation validity | 100% of displayed claims | Verifier pass rate |
| Verifier "needs review" rate | Tracked (diagnostic) | % claims flagged |
| Recall@10 on gold set | ≥70% (initial target) | Gold-set script |
| Known/candidate label accuracy | ≥90% on gold set | Gold-set script |
| Demo success | 100% | Works during presentation |
| Corpus size | 3–10k | Count of passages |

---

## 16. Timeline & Milestones

| Time | Phase | Hours | Exit criteria | Status |
|---|---|---|---|---|
| 10–12 | Setup | 2h | venv, libs, models, docs | ✅ done |
| 12–13 | **Thin vertical slice** | 1h | ~100 passages: query → retrieve → generate → verify → Gradio stub | pending |
| 13–15 | Data pipeline | 2h | clean corpus of supported diseases; KG inspected | pending |
| 15–16:30 | Embed + index | 1.5h | searchable dense index | pending |
| 16:30–19 | RAG pipeline hardening | 2.5h | KG-first candidates, evidence score, verifier, abstention | pending |
| 19–21 | UI | 2h | Gradio interface live with citation viewer | pending |
| 21–00 | Integrate + test + demo cache | 3h | end-to-end works; demo cache built; backup video | pending |
| 00–06 | Sleep | n/a | n/a | n/a |
| 06–08 | Demo prep | 2h | scripted + rehearsed + backup video | pending |
| 08–09 | Final polish | 1h | buffer starts | pending |
| **09–12** | **Buffer** | **3h** | submit | n/a |

**Total:** 17 working + 6 sleep + 3 buffer = 26 hours

**Why the vertical slice first:** it surfaces integration problems (Ollama, Gemini
JSON output, verifier, Gradio) while there's still time to fix them.

**Cut order if time runs short:** (1) evidence direction labels, (2) About panel,
(3) abstract highlighting. Never cut the verifier, the known-indication flag, or
the cached demo path.

---

## 17. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Package install fails | Low | High | Pin from working `pip freeze`; CLI fallback |
| Ollama embedding slow | Low | Medium | Batch embed; keep model warm; embed once and persist |
| PubMed API rate-limited | Medium | Medium | Fetch early; cache raw responses; HuggingFace dataset fallback |
| Gemini API down / rate-limited / quota | Medium | High | Timeout + retry; cached results for demo queries; screenshots/video backup |
| Venue network unreliable | Medium | High | Cached demo path works offline; phone hotspot as backup |
| Demo breaks live | Medium | High | Record video backup; test both cached and live paths |
| Hallucination | Medium | High | Verbatim-quote requirement + two-stage verifier; flag unverifiable claims |
| LLM returns malformed JSON | Medium | Medium | Schema/JSON mode, validation, one retry |
| KG edges don't mean what we assume | Medium | High | Inspect data before building the candidate generator (§10.1); fall back to retrieval-based candidates |
| Candidates are just known drugs | High | Medium | Known-indication flag; separate group in the UI |
| Judge queries an unsupported disease | High | Medium | Abstention path + visible supported-disease list |
| Verbatim-quote verifier false positives | Medium | Medium | Normalize aggressively; verifier only flags, never blocks |
| Evidence direction misclassification | Medium | Medium | Default to Uncertain; show direction as "Uncertain" when confidence is low |
| Time runs out | Medium | High | Vertical slice first; cut order defined (§16) |

---

## 18. Assumptions, Constraints & Open Items

### 18.1 Assumptions
- Gemini API key remains valid and within quota through the hackathon
- Ollama remains running with `nomic-embed-text` pulled
- Internet access available for Gemini API + PubMed download (the cached demo path does not need it)

### 18.2 Constraints
- **Time:** 26 hours total, 17 working hours
- **Solo:** one human + one AI agent
- **Compute:** RTX 4000 Ada 20GB (optional), CPU fallback works
- **Data:** public sources only, no credentialed datasets
- **Model:** ≤4B params for any local model (hackathon rule)

### 18.3 Open items to verify

| # | Item | Why it matters | Status |
|---|---|---|---|
| 1 | Does the ≤4B-parameter rule applies to hosted APIs like Gemini? | Compliance | **[ASSUMPTION]** |
| 2 | What `kg-edges` actually encodes (indications / contraindications / predictions) | Known-indication labelling depends on this | **[ASSUMPTION]** |
| 3 | Exact Gemini model string (`gemini-3.8-flash` verified working) | API calls | ✅ verified |
| 4 | Dataset licenses on HuggingFace (CC-BY 4.0 claimed) | Legal | **[ASSUMPTION]** |
| 5 | NLM terms for PubMed abstract display | Legal | **[ASSUMPTION]** |
| 6 | Whether `nomic-embed-text` expects query/document prefixes | Embedding quality | **[ASSUMPTION]** |
| 7 | Final supported-disease list and the gold set | Demo coverage | pending |
| 8 | Whether EveryCure KG has known-indication flags | Known-indication labelling | **[ASSUMPTION]** |

---

## 19. Future Work & Stretch Goals

| Priority | Feature | Effort |
|---|---|---|
| P1 | Export results to CSV/JSON | 1h |
| P1 | FastAPI backend (same schema as §12.2) | 1h |
| P2 | Custom HTML/JS frontend | 2–3h |
| P2 | Hybrid dense+BM25+RRF retrieval | 1.5h |
| P2 | Cross-encoder re-ranker (trained) | 3–4h |
| P3 | Drug-disease knowledge graph visualization | 2–3h |
| P3 | Multi-turn conversation memory | 2h |
| P4 | Full PubMed corpus (streaming) | 4–6h |
| P4 | Fine-tuned biomedical embeddings | 6–8h |

---

## 20. Appendix

### 20.1 Glossary

| Term | Definition |
|---|---|
| **RAG** | Retrieval-Augmented Generation: retrieve relevant passages, then generate an answer grounded in them |
| **KG** | Knowledge Graph: structured entities (drugs, diseases) and relationships |
| **PMID** | PubMed Identifier: unique ID for a PubMed article |
| **Embedding** | A dense vector representation of text for semantic search |
| **Cosine similarity** | A measure of similarity between two vectors (1 = identical, 0 = unrelated) |
| **Grounding** | Constraining an LLM's output to retrieved sources, not parametric knowledge |
| **Citation** | A link from a claim in the answer to the source passage it came from |
| **Two-stage verifier** | Stage 1: source identity (does the citation exist and match drug+disease?). Stage 2: claim support (does the passage support the claim?). Failures flagged as "needs review." |
| **Evidence score** | A computed score from retrieval relevance, supporting-passage count, and study type. Experimental heuristic, not clinical probability. |
| **Known indication** | A drug already approved/used for the queried disease, hence not a repurposing candidate |
| **Evidence direction** | Whether the literature supports (Positive), refutes (Negative), both (Mixed), or cannot determine (Uncertain) a repurposing hypothesis |
| **Recall@k** | Fraction of gold-set drugs that appear in the top k results |

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
| 1.1 | 2026-10-18 | KG-first architecture, known-indication labelling, computed evidence score, per-candidate retrieval, hybrid retrieval |
| 1.2 | 2026-10-18 | **Debated across 4 lenses (strategy, feasibility, clinical, UX). Locked decisions:** two-stage citation verifier (source identity + claim support, "needs review" flag); evidence direction labels (Pos/Neg/Mixed/Uncertain); evidence weights 0.3/0.3/0.4 (study quality dominates); skip per-candidate retrieval for P0; vertical slice first; cached demo path; single Gemini call. Unresolved assumptions tagged **[ASSUMPTION]**. |

---

> [!info] How to use this document
> This PRD is the single source of truth for what we're building and why.
> Every functional requirement traces back to a user story; every design decision
> traces back to a constraint or goal. If something isn't in here, it's out of scope.
> Anything tagged **[ASSUMPTION]** is unconfirmed; resolve those during the build.
