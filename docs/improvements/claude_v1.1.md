# 📋 Product Requirements Document

# Telemedicon — Drug Repurposing via Literature RAG

**Telemedicon 2026 · Internal Hackathon · AI + Digital Health**
**Version** 1.1 · **Date** 2026-10-18 · **Status** Skeleton complete, build in progress
**Author** Solo participant + AI agent (Hermes)

> **What changed in v1.1:** see [§20.3 Document history](#203-document-history). Items tagged **[VERIFY]** are
> claims I could not confirm from this document alone. Check them before relying on them (see [§18.3](#183-open-items-to-verify)).

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
for each candidate** and returns a ranked list where **every claim is backed by a
verified quote from a source passage**.

**The problem it solves:** finding new uses for existing drugs currently takes
weeks of manual literature review. Telemedicon compresses the first pass to
seconds by combining structured knowledge (candidate generation), hybrid
retrieval over biomedical text (evidence), and a citation-verified language model
(explanation).

**What makes it credible (not just fast):**
- **Repurposing, not rediscovery:** drugs already indicated for the disease are labelled, not presented as new ideas.
- **Verified citations:** each claim carries a verbatim quote that is programmatically checked against the cited passage.
- **Honest scoring:** the score shown is an *evidence score* computed from retrieval and study type, not an LLM's self-reported confidence.
- **Honest limits:** if the corpus lacks evidence for a disease, the system says so.

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
- **Demo-able:** a clean, presentable interface for the hackathon

### Objectives (SMART)
| Objective | Measurable target |
|---|---|
| Corpus size | 3,000–10,000 passages total (PubMed chunks + KG-edge passages) |
| Supported diseases | 5–10, listed in the UI "About" panel |
| Retrieval latency | <100 ms for the search step (query embedding timed separately) |
| End-to-end latency | <5 s p95 (uncached); <1 s for cached demo queries |
| Citation validity | 100% of *displayed* claims pass the quote-in-passage check |
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

**Acceptance criteria:** Returns 3–10 candidates, each with an evidence score,
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
│  3. Evidence retriever ── per drug+disease pair:           │
│            │               dense (nomic) + BM25 → RRF fuse  │
│            ▼                                                │
│  4. Re-ranker ── study type, recency, relevance            │
│            │      → evidence score                          │
│            ▼                                                │
│  5. Answer generator (Gemini) ── reason + claims + quotes  │
│            ▼                                                │
│  6. Citation verifier ── quote ∈ passage? else drop claim  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                              │
│                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  EveryCure KG  │  │  PubMed        │  │  Indexes     │  │
│  │  drug-list     │  │  abstracts     │  │  dense (npy) │  │
│  │  disease-list  │  │  + metadata    │  │  BM25        │  │
│  │  kg-edges      │  │  (pub type,    │  │  metadata    │  │
│  │  (structured)  │  │   year, PMID)  │  │  (json)      │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Demo cache: precomputed results for example queries │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Design rationale:** v1.0 flattened KG edges into text passages and relied on
one top-10 retrieval. That loses the structure that makes the KG useful and
caps the answer at ≤10 passages. v1.1 uses the KG for *who to consider* and the
literature for *why*, which also matches the problem statement (§2).

**Fallback:** if the KG yields fewer than 3 candidates for a disease, fall back
to dense+BM25 retrieval over disease-level queries and have the LLM extract
drug names from the retrieved passages (still subject to citation verification).

### Data flow

```
Raw sources → Acquire → Normalize → Clean → Chunk → Embed + BM25 → Index → Persist
                                                                              │
                                                                              ▼
User query → Resolve disease → KG candidates → Per-pair retrieve (hybrid) →
Re-rank + evidence score → Generate (quotes) → Verify citations → Display
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
| FR-3.3 | For each candidate, build a drug+disease query and embed it with nomic-embed-text (using the model's query/document prefixes, **[VERIFY]**) | Must |
| FR-3.4 | Run dense (cosine) and BM25 retrieval, fuse with Reciprocal Rank Fusion | Should |
| FR-3.5 | Retrieve top-30 per pair, re-rank, keep top-5 passages per candidate | Must |
| FR-3.6 | Re-rank by relevance, study type, and recency (§10.5) | Should |
| FR-3.7 | Batch all per-candidate query embeddings into one request | Should |
| FR-3.8 | Fallback path when KG candidates < 3 (see §7) | Should |

### FR-4: Answer generation
| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Return 3–10 repurposing candidates (known indications listed separately) | Must |
| FR-4.2 | Each candidate has a computed **evidence score** and tier (Strong / Moderate / Preliminary), not an LLM self-reported confidence | Must |
| FR-4.3 | Each candidate has a reason grounded in its retrieved passages | Must |
| FR-4.4 | The LLM returns, for each claim, the citation ID(s) and a **verbatim supporting quote** | Must |
| FR-4.5 | **Citation verifier:** a claim is displayed only if its citation ID exists in the retrieved set and its quote is a (whitespace/case-normalized) substring of that passage; otherwise drop the claim | Must |
| FR-4.6 | If a candidate has no verified claim, drop the candidate; if verification fails broadly, retry generation once | Must |
| FR-4.7 | Expandable "Why this drug?" reasoning | Should |

### FR-5: Citation viewer
| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Clickable citations [1], [2], [3] | Must |
| FR-5.2 | Show source passage text | Must |
| FR-5.3 | Show source metadata (PMID, year, publication type, drug, disease) | Must |
| FR-5.4 | Highlight the verified supporting quote in the passage (now cheap, since the quote is already extracted) | Should |
| FR-5.5 | Link out to the PubMed page by PMID | Should |

### FR-6: UI
| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Clean, professional interface | Must |
| FR-6.2 | Results panel with ranked candidates and a separate "Already indicated" group | Must |
| FR-6.3 | Citation viewer panel | Must |
| FR-6.4 | "Why this drug?" expandable sections | Should |
| FR-6.5 | Example query buttons | Should |
| FR-6.6 | About / data source section listing supported diseases and corpus stats | Should |
| FR-6.7 | Persistent disclaimer: "Research hypotheses only, not medical advice" | Must |

### FR-7: Robustness and demo safety
| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Abstain with a clear message when the disease is unsupported or evidence is below a minimum threshold | Must |
| FR-7.2 | Cache results for the demo/example queries; serve from cache if the LLM call fails or times out | Must |
| FR-7.3 | LLM call timeout and retry with backoff; surface a friendly error, never a stack trace | Should |
| FR-7.4 | Log per-stage timings (resolve, KG, embed, retrieve, generate, verify) | Should |

---

## 9. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Query-to-answer latency (uncached) | <5 s p95 |
| NFR-1b | Query-to-answer latency (cached demo query) | <1 s |
| NFR-2 | Search step latency (dense + BM25 + fuse, excluding query embedding) | <100 ms |
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
| Batched query embedding (all candidates) | <500 ms |
| Hybrid retrieval + rerank | <200 ms |
| Gemini generation (single call) | <3 s |
| Citation verification | <50 ms |
| UI render | <300 ms |

> The v1.0 plan used two Gemini calls (analysis + generation). v1.1 uses one in
> the normal path to protect the 5 s budget.

---

## 10. Data Requirements

### 10.1 Sources

| Source | Type | Size | License | Access |
|---|---|---|---|---|
| EveryCure `drug-list` | Structured | ~1,800 drugs | CC-BY 4.0 **[VERIFY]** | HuggingFace |
| EveryCure `disease-list` | Structured | ~22,000 diseases | CC-BY 4.0 **[VERIFY]** | HuggingFace |
| EveryCure `kg-edges` | Structured | drug-disease pairs | CC-BY 4.0 **[VERIFY]** | HuggingFace |
| PubMed abstracts | Literature | ~500–1,000 | NLM terms of use; abstracts may be publisher-copyrighted | E-utilities API |

**Licensing note:** v1.0 listed PubMed abstracts as "public domain." Treat that as
unverified: many abstracts carry publisher copyright. For a hackathon demo,
show passages with attribution and link to the PubMed page by PMID; don't
redistribute the corpus. Confirm against NLM's current terms **[VERIFY]**.

**KG caveat [VERIFY]:** before building on `kg-edges`, inspect what the edges
mean (known indications, contraindications, predicted scores, or a mix). The
candidate generator and the **Known indication** flag both depend on this.

### 10.2 Corpus scoping
Pick the supported diseases (5–10) *first*, and pick the PubMed queries to cover
them. The gold set (§14.2) decides coverage, not the other way around.
Approximate sizing: ~800 abstracts × 3–5 chunks ≈ 2.4–4k PubMed passages, plus
KG-edge passages for the supported diseases.

### 10.3 Unified schema

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

`pub_type` and `year` come from PubMed record metadata (publication type, date),
not from the LLM.

### 10.4 Chunking

| Parameter | Value |
|---|---|
| Unit | Sentence-window chunks, keeping the title with the first chunk |
| Chunk size | ~400–800 characters (v1.0 used 300–500, which splits most abstracts mid-argument) |
| Overlap | 1 sentence |
| Method | Sentence-boundary splitting; never split inside a sentence |
| Alternative | One abstract = one passage (simplest; test both on the gold set) |

### 10.5 Embedding and indexing

| Parameter | Value |
|---|---|
| Model | `nomic-embed-text` (Ollama) |
| Prefixes | `search_document: ` for passages, `search_query: ` for queries **[VERIFY against the model card]** |
| Dimensions | 768 |
| Batching | Use Ollama's batch embedding endpoint if the installed version supports it **[VERIFY]**; otherwise 10–20 per request |
| Normalization | L2-normalize once at index time; search is then a dot product |
| Dense storage | numpy `.npy` + JSON metadata |
| Sparse index | BM25 (e.g. `rank_bm25`), built over the same chunks |
| Fusion | Reciprocal Rank Fusion of dense and BM25 ranks |

### 10.6 Evidence score (initial design, to be tuned on the gold set)

For each candidate, from its top-5 retrieved passages:

```
evidence_score = 0.4 * relevance      # max fused retrieval score, min-max normalized
               + 0.3 * support        # min(#supporting passages, 5) / 5
               + 0.3 * study_weight   # best study type among passages
```

| Study type | Weight |
|---|---|
| clinical_trial | 1.0 |
| cohort / observational | 0.7 |
| preclinical (in vitro / animal) | 0.4 |
| review / other | 0.3 |

Tiers: **Strong** ≥ 0.7, **Moderate** 0.4–0.7, **Preliminary** < 0.4. The weights
and thresholds are starting guesses, not validated values. Tune them against the
gold set and report the final values in the About panel.

---

## 11. Technical Stack

| Layer | Tool | Version | Role |
|---|---|---|---|
| Language | Python | 3.12 | Core |
| Embeddings | Ollama `nomic-embed-text` | latest | Text → vectors |
| Dense search | numpy | pin from env | Cosine/dot-product search |
| Sparse search | rank_bm25 | pin from env | Keyword retrieval (drug names, rare tokens) |
| LLM | Gemini Flash | **[VERIFY]** exact model string (v1.0 listed `gemini-3.8-flash`; confirm against the API's current model list) | Generation (and optional query normalization) |
| LLM SDK | **[VERIFY]** `google-genai` vs `google-generativeai` | pin from env | Gemini client; I believe the older package is deprecated, so check |
| Data | HuggingFace datasets | pin from env | KG download |
| Data | pandas | pin from env | Data manipulation |
| HTTP | httpx | pin from env | Ollama calls |
| UI | Gradio | pin from env | Current interface |
| Config | python-dotenv | pin from env | API key management |
| VCS | git | n/a | Version control |

**Version policy:** v1.0 listed specific versions (e.g. Gradio 6.30, pandas 3.x,
datasets 5.x) that I couldn't confirm. Generate the real list with `pip freeze`
from the working environment and commit it as `requirements.txt`.

**Deliberately excluded:** torch, transformers, sentence-transformers, langchain, FAISS.

---

## 12. API Design

### 12.1 Internal pipeline API (Python functions)

```python
# embeddings.py
def embed_texts(texts: list[str], kind: str = "document") -> np.ndarray:
    """Embed texts → (N, 768), L2-normalized. kind = 'document' | 'query' (prefix)."""

# kg.py
def resolve_disease(query: str) -> dict | None:
    """Match free text to a disease-list entry (fuzzy). None if no confident match."""

def get_candidates(disease_id: str) -> list[dict]:
    """KG candidates with a 'known_indication': bool flag."""

# retrieval.py
def search_dense(query_vec: np.ndarray, index: np.ndarray, top_k: int = 30) -> list[tuple[int, float]]:
    """Return (chunk_index, score) pairs."""

def search_bm25(query: str, top_k: int = 30) -> list[tuple[int, float]]:
    """Return (chunk_index, score) pairs."""

def fuse_rrf(*ranked_lists: list[tuple[int, float]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion."""

def rerank(passages: list[dict]) -> list[dict]:
    """Re-rank by relevance, study type, recency; attach per-passage signals."""

def evidence_score(passages: list[dict]) -> dict:
    """{'score': float, 'tier': str, 'support': int, 'best_study_type': str}"""

# llm.py
def generate_answer(disease: str, candidates: list[dict]) -> dict:
    """One call. Per candidate: reason + claims[{text, citation_ids, quote}]. JSON schema enforced."""

# verify.py
def verify_claims(answer: dict, passages_by_id: dict) -> dict:
    """Drop claims whose citation ID is unknown or whose quote isn't in the cited passage."""

# pipeline.py
def run_pipeline(query: str) -> dict:
    """End-to-end: resolve → candidates → retrieve → rerank/score → generate → verify.
    Returns results, passages, and per-stage timings; serves cache for demo queries."""
```

### 12.2 Future REST API (for custom frontend)

```
POST /api/query
  Request:  {"query": "Alzheimer's disease"}
  Response: {
    "query": "Alzheimer's disease",
    "entities": {"disease": {"id": "...", "name": "Alzheimer's disease"}},
    "status": "ok | insufficient_evidence | unsupported_disease",
    "results": [
      {
        "rank": 1,
        "drug": "Metformin",
        "label": "repurposing_candidate",
        "evidence": {"score": 0.74, "tier": "Strong", "support": 4, "best_study_type": "clinical_trial"},
        "reason": "...",
        "claims": [
          {"text": "...", "citations": [1], "quote": "..."}
        ]
      }
    ],
    "known_indications": [{"drug": "...", "citations": [2]}],
    "passages": [
      {"id": 1, "text": "...", "source": "pubmed", "pmid": "...", "year": 2023, "pub_type": "clinical_trial"}
    ],
    "timings_ms": {"resolve": 0, "embed": 0, "retrieve": 0, "generate": 0, "verify": 0}
  }

GET /api/health
  Response: {"status": "ok", "corpus_size": 7500, "supported_diseases": ["..."]}
```

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
│  │  1. Metformin   Evidence: Strong ████ 0.74│  │
│  │     Reason: ... [1] [3]                   │  │
│  │     [Why this drug? ▾]  (4 papers, 1 RCT) │  │
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
│  └───────────────────────────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

Gradio note: inline clickable citations can be awkward. If they are fiddly,
render citations as buttons or links under each reason that update the viewer
panel. This is acceptable for the prototype.

### 13.2 Design principles
- **Clean:** white/light background, clear typography
- **Fast:** results appear in <5 seconds, with a visible loading state
- **Trustworthy:** citations visible by default, not hidden; the disclaimer always visible
- **Honest:** evidence tier shown with study-type context; abstention is a first-class result
- **Professional:** looks like a product, not a demo

### 13.3 Future custom frontend
- Single-page app (HTML/CSS/JS or React)
- Served by FastAPI as static files
- Same API as §12.2
- Treat as optional (P2). The demo does not depend on it. Gradio is the committed UI.

---

## 14. Evaluation & Judging Criteria

### 14.1 Judging criteria

| Criterion | Weight | How we score |
|---|---|---|
| **Technical innovation** | High | KG-first candidates + hybrid retrieval + verified-quote citations + computed evidence score |
| **Clinical relevance** | High | Known-indication separation, real drug-disease data, real literature, researcher-facing |
| **Prototype quality** | High | Clean UI, fast, working demo, no crashes, cached fallback |
| **Presentation** | Medium | 3-min demo, clear story, rehearsed |
| **Code quality** | Medium | Clean, documented, git-tracked |

### 14.2 Quality evaluation (gold set)

A small set of 5–10 disease → drug pairs where repurposing success is well known,
used to (a) choose which PubMed abstracts to fetch, (b) measure recall@10, and
(c) tune the evidence-score weights.

- Build it from sources you can cite. Illustrative well-known examples to
  consider: thalidomide (multiple myeloma), sildenafil (pulmonary arterial
  hypertension), dexamethasone (severe COVID-19). **Validate each pair yourself
  before using it**, and only include diseases that are in your supported set.
- Report: recall@10 of gold drugs, % of displayed claims passing the verifier,
  and % of results correctly labelled known vs candidate.
- Optional ablation (cheap, impressive in a demo Q&A): dense only vs dense+BM25;
  evidence score vs LLM confidence.

### 14.3 Demo script (3 minutes)
1. **Hook (30s):** "A doctor wants to repurpose a drug for Alzheimer's. Normally = weeks of review. We built a tool that does the first pass in seconds."
2. **Query (30s):** Type "Alzheimer's disease" → show the system working
3. **Results (60s):** Show ranked candidates and the "Already indicated" group → click a citation → show the highlighted quote → "every claim is verified against its source"
4. **Reasoning (30s):** Show "Why this drug?" → evidence chain and study types → "the score is computed, not the model's guess"
5. **Honesty + impact (30s):** Query an unsupported disease → "insufficient evidence." Close with "For researchers, clinicians, and students."

Rehearse with the cached path *and* the live path. Record a backup video.

---

## 15. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Query-to-answer latency (uncached) | <5 s p95 | Per-stage timers in pipeline |
| Cached demo latency | <1 s | Timer |
| Search-step latency | <100 ms | Timer in retrieval |
| Citation validity | 100% of displayed claims | Verifier pass rate |
| Verifier rejection rate | Tracked (diagnostic) | % claims dropped; high values mean prompt or retrieval problems |
| Recall@10 on gold set | ≥70% (initial target) | Gold-set script |
| Known/candidate label accuracy | ≥90% on gold set | Gold-set script |
| Demo success | 100% | Works during presentation |
| Corpus size | 3–10k | Count of passages |
| User satisfaction | Qualitative | Judge feedback |

---

## 16. Timeline & Milestones

| Time | Phase | Hours | Exit criteria | Status |
|---|---|---|---|---|
| 10–12 | Setup | 2h | venv, libs, models, docs | ✅ done |
| 12–13 | **Thin vertical slice** | 1h | ~100 passages: query → retrieve → generate → verify → Gradio stub | pending |
| 13–15 | Data pipeline | 2h | clean corpus of supported diseases; KG inspected | pending |
| 15–16:30 | Embed + index (dense + BM25) | 1.5h | searchable hybrid index | pending |
| 16:30–19 | RAG pipeline hardening | 2.5h | KG-first candidates, evidence score, verifier, abstention | pending |
| 19–21 | UI | 2h | Gradio interface live with citation viewer | pending |
| 21–00 | Integrate + test + gold-set eval | 3h | end-to-end works; recall@10 measured; demo cache built | pending |
| 00–06 | Sleep | n/a | n/a | n/a |
| 06–08 | Demo prep | 2h | scripted + rehearsed + backup video | pending |
| 08–09 | Final polish | 1h | buffer starts | pending |
| **09–12** | **Buffer** | **3h** | submit | n/a |

**Total:** 17 working + 6 sleep + 3 buffer = 26 hours

**Why the vertical slice first:** it surfaces integration problems (Ollama, Gemini
JSON output, verifier, Gradio) while there's still time to fix them, instead of
at hour 21.

**Cut order if time runs short:** (1) BM25/RRF, (2) per-candidate re-rank
signals beyond study type, (3) abstract highlighting, (4) About panel. Never cut
the verifier, the known-indication flag, or the cached demo path.

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
| Hallucination | Medium | High | Verbatim-quote requirement + programmatic verifier; drop unverifiable claims |
| LLM returns malformed JSON | Medium | Medium | Schema/JSON mode, validation, one retry |
| KG edges don't mean what we assume | Medium | High | Inspect data before building the candidate generator (§10.1); fall back to retrieval-based candidates |
| Candidates are just known drugs | High | Medium | Known-indication flag; separate group in the UI |
| Judge queries an unsupported disease | High | Medium | Abstention path + visible supported-disease list |
| Hosted-LLM use conflicts with hackathon rules | Low | High | Confirm the rule now (§18.3) |
| Time runs out | Medium | High | Vertical slice first; cut order defined (§16) |
| Corpus too small for coverage | Low | Medium | Scope diseases first; supplement with KG edges |

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
1. Does the ≤4B-parameter rule apply to hosted APIs like Gemini, or only to local models?
2. Exact Gemini model string and the correct SDK package.
3. What `kg-edges` actually encodes (indications / contraindications / predictions).
4. Dataset licenses on HuggingFace, and NLM terms for PubMed abstract display.
5. Whether `nomic-embed-text` via Ollama expects the `search_query:` / `search_document:` prefixes, and whether the installed Ollama version supports batch embedding.
6. Final supported-disease list and the gold set.

---

## 19. Future Work & Stretch Goals

| Priority | Feature | Effort |
|---|---|---|
| P1 | Export results to CSV/JSON | 1h |
| P1 | FastAPI backend (same schema as §12.2) | 1h |
| P2 | Custom HTML/JS frontend | 2–3h |
| P2 | Cross-encoder re-ranker (trained) | 3–4h |
| P2 | Full PubMed corpus (streaming) | 4–6h |
| P3 | Drug-disease knowledge graph visualization | 2–3h |
| P3 | Multi-turn conversation memory | 2h |
| P4 | Fine-tuned biomedical embeddings | 6–8h |
| P4 | Clinical trial matching | 4–6h |

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
| **BM25** | A keyword-based ranking function; strong on exact terms such as drug names |
| **RRF** | Reciprocal Rank Fusion: merges ranked lists from different retrievers |
| **Grounding** | Constraining an LLM's output to retrieved sources, not parametric knowledge |
| **Citation** | A link from a claim in the answer to the source passage it came from |
| **Citation verifier** | A programmatic check that a claim's quote actually appears in its cited passage |
| **Evidence score** | A computed score from retrieval relevance, supporting-passage count, and study type |
| **Known indication** | A drug already approved/used for the queried disease, hence not a repurposing candidate |
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
| 1.1 | 2026-10-18 | KG-first two-stage architecture; known-indication labelling; computed evidence score replaces LLM confidence; verbatim-quote citation verifier; per-candidate retrieval (30 → 5) instead of global top-10; hybrid dense+BM25 with RRF; nomic prefixes; revised chunking; single-LLM-call latency budget; abstention + cached demo path; gold set and recall@10; reconciled corpus sizing; supported-disease scoping; reordered timeline with vertical slice first; added risks; licensing, model-name, and SDK items flagged **[VERIFY]**; fixed US-1 formatting and US-4/demo-time inconsistency |

---

> [!info] How to use this document
> This PRD is the single source of truth for what we're building and why.
> Every functional requirement traces back to a user story; every design decision
> traces back to a constraint or goal. If something isn't in here, it's out of scope.
> Anything tagged **[VERIFY]** is unconfirmed; resolve those first.
