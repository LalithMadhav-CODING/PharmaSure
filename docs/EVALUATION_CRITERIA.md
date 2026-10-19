# PharmaSure — Mapping to Evaluation Criteria

**Project:** PharmaSure — Drug Repurposing & Evidence Verification Assistant
**Team:** _[team name — add members]_
**Repo:** github.com/LalithMadhav-CODING/PharmaSure
**Live:** https://pharmasure-y64x.onrender.com (UI) · https://adminit.tailb9365a.ts.net (direct)

> **How to read this.** Every number below was measured on the running system, not
> estimated. Where something is not yet true, it is labelled **Planned** and
> listed again under *Known Limitations* so nothing here overstates the build.

---

## 1. Problem Identification and Clarity — 15%

**The problem.** Bringing a new drug to market takes 10–15 years and costs over
US$1B, and most candidates fail. **Drug repurposing** — finding a new indication
for an already-approved drug — compresses that to roughly 3–5 years at a fraction
of the cost, because the safety profile is already established. The bottleneck is
no longer the molecule; it is **finding and defending the evidence**.

**Who has this problem.**
- Translational and clinical researchers screening repurposing hypotheses
- Rare-disease clinicians and patient-advocacy groups, where no approved therapy
  exists and repurposing is often the only realistic route
- Pharmacoepidemiology / drug-safety teams assessing off-label signals

**Why it is hard today.** The evidence is fragmented across tens of millions of
PubMed abstracts *and* structured knowledge graphs, in incompatible formats.
A researcher must (a) generate candidate drugs, (b) find the supporting
literature, and (c) **prove each claim traces to a real paper**. Step (c) is where
most tooling fails.

**Limitations of current solutions.**

| Approach | Limitation |
|---|---|
| Manual literature review | Days per hypothesis; not exhaustive; not reproducible |
| Commercial KG / repurposing platforms | Expensive, closed, licensed per seat |
| General-purpose LLM chatbots | Produce **confident citations that do not exist** — unusable in a clinical evidence chain |

**Our framing.** The hard part is not generating hypotheses — it is generating
hypotheses **whose every claim is traceable to a verbatim sentence in a real,
identifiable paper**. PharmaSure is built around that constraint, and abstains
when the evidence is not there.

---

## 2. Technical Innovation — 20%

**Architecture (input → processing → output):**

```
user query ("Common cold")
   │
   ├─ 1. Disease resolution        EveryCure KG → MONDO ontology ID
   ├─ 2. Candidate generation      EveryCure matrix-scores → top 10 drugs
   ├─ 3. Retrieval                 disease-scoped dense search over 842 passages
   │                               (nomic-embed-text, 768-d, local)
   ├─ 4. Synthesis                 qwen3.8:27b (local, 20GB GPU) → claims + citations
   ├─ 5. Two-stage verification    source identity + verbatim substring check
   └─ 6. Evidence scoring          relevance + support + study quality
   │
   └─ output: ranked candidates, each with quotes + PubMed links, or an abstention
```

**What is genuinely novel here:**

1. **Verifiable-by-construction citations.** Two independent stages: (1) *source
   identity* — does the cited passage actually mention this drug for this
   disease? (2) *claim support* — is the quoted sentence a **contiguous verbatim
   substring** of that passage? A quote spliced with `"..."` is rejected, not
   quietly accepted. This is the difference between a plausible answer and a
   defensible one.

2. **Retrieval scoped by evidence provenance, not just similarity.** Naive
   semantic search over a biomedical corpus returns abstracts that are *about*
   the disease while naming unrelated drugs — we measured this: querying
   "Common cold" surfaced Aspirin / Dexamethasone / Ketamine abstracts, so **no
   candidate matched any passage and every score collapsed to 0**. PharmaSure
   scopes retrieval to passages tagged with the resolved disease, then ranks by
   similarity within that set. This turned a silently-broken scorer into a
   working one.

3. **Fully local inference.** Embeddings and a 27B-parameter LLM run on one
   workstation GPU. No per-query API cost, and **no patient or query data leaves
   the host** — a prerequisite for anything clinical.

4. **Knowledge-graph candidate list is authoritative.** A short or malformed LLM
   generation cannot shrink the result set; every KG candidate is always
   reported, with model-generated rationale attached where it exists and an
   explicit "no literature evidence found" where it does not.

5. **Explainable scoring.** Each candidate's score decomposes into *semantic
   relevance*, *number of supporting studies*, and *best study type* — with
   clinical trials weighted above reviews above case reports. Shown in the UI as
   a formula breakdown, not a black-box number.

**Engineering robustness.** LLM JSON output is repaired and retried rather than
crashing the request; the model's reasoning mode is disabled so it stops emitting
answers into the wrong field; over-long passages are truncated before embedding.
These were found by measurement, not assumption.

---

## 3. Clinical Relevance and Validation — 20%

**Real data only.** No synthetic records anywhere in the pipeline.

| Source | Content | Scale |
|---|---|---|
| EveryCure knowledge graph | disease → drug candidate scores, true indication labels | 23,224 diseases · 24,174 candidate sets · 5,748 drugs |
| PubMed (E-utilities) | real abstracts, with PMID, year, publication type | 842 passages · 840 unique PMIDs · 113 diseases · 187 drugs |

Publication types retrieved: 385 reviews, 216 journal articles, **106 clinical
trials**, 91 conference abstracts, 30 case reports, 5 cohort studies,
5 meta-analyses, 4 preclinical. Years span **1962–2026**.

**Validation performed (all reproducible):**

| Check | Method | Result |
|---|---|---|
| Citations resolve to a real paper | HTTP fetch of every cited PMID | ✅ `pubmed.ncbi.nlm.nih.gov/<pmid>/` → HTTP 203 |
| Quotes are verbatim | contiguous-substring test against the cited passage | ✅ **24/24 quotes** across 3 diseases |
| Citation IDs are valid | every `citation_id` maps to a returned passage | ✅ 0 invalid |
| Abstains rather than fabricates | queries with no supporting literature | ✅ returns `insufficient_evidence` |
| Scores vary and are explainable | per-candidate relevance / support / study-quality | ✅ 4–5 of 10 candidates carry real evidence |

**Clinically important design decisions.**

- **Established indications are shown separately** from repurposing candidates
  (e.g. 27 on-label drugs for Common cold). This prevents the system from
  "discovering" what clinicians already prescribe.
- **Evidence tiering** — Strong / Moderate / Preliminary — derived from study
  type, so a Phase III trial is not presented as equivalent to a case report.
- **Every output carries a research-hypothesis disclaimer**; the tool proposes
  candidates for investigation, it does not recommend treatment.
- **Traceability is the deliverable.** The UI's citation drawer shows the exact
  source sentence highlighted against the passage text, with the PubMed link.

---

## 4. Social Impact and Sustainability — 15%

**Impact.**

- **Rare disease is the sharpest case:** the large majority of rare diseases have
  no approved therapy, and repurposing is frequently the only viable path.
  Lowering the cost of *finding and defending* a repurposing hypothesis
  disproportionately benefits exactly these patients, who have the least
  commercial incentive working for them.
- **Neglected and low-prevalence conditions** that industry will not fund are
  reachable by the same workflow.
- **Low-resource settings:** because inference is local, the system runs without
  cloud spend, recurring API fees, or reliable high-bandwidth connectivity.

**Cost position.** Runs on a single workstation with a 20 GB GPU. Marginal cost
per query is electricity — no per-token or per-seat licensing.

**Sustainability.**

- **Open data:** EveryCure (open knowledge graph) + PubMed (public literature).
- **Open stack:** Python / FastAPI, React + TypeScript, Ollama, numpy. No
  proprietary model licence, no vendor lock-in.
- **Runs offline** after the corpus is built, so the system does not stop working
  if a third-party API changes terms or pricing.
- **Incremental corpus growth:** adding a disease is one script run
  (`scripts/build_corpus.py`) — coverage can be expanded by collaborators without
  architectural change.

**Potential adopters.** Academic medical centres and translational research cores;
rare-disease foundations and patient-advocacy groups; hospital pharmacy &
therapeutics committees; public-health and national research bodies; CROs
triaging repurposing portfolios.

---

## 5. Quality of the Prototype / Proof of Concept — 20%

**It is a working system, not a mock-up.**

- **Frontend:** React 18 + TypeScript + Vite + Tailwind — search, ranked candidate
  cards, evidence-tier badges, claim lists, and a citation drawer with exact-quote
  highlighting and PubMed links.
- **Backend:** FastAPI with `POST /api/query`, `GET /api/health`, a runtime
  `/config.json`, and the original Gradio console preserved at `/gradio`.
- **Deployment:** UI served from Render; model backend runs on the local GPU and
  is published over a Tailscale Funnel, with the deployed UI proxying `/api/*`
  same-origin. The heavy components (27B model, vector index) stay on the machine
  that can actually run them.

**Measured behaviour (5 demonstration diseases + live queries):**

| Metric | Result |
|---|---|
| Candidates returned | **10 per query** (knowledge-graph top-10) |
| Claims with citations | 8–9 per query |
| Candidates with scored evidence | 4–5 of 10 |
| Cached demo query | instant |
| Live (uncached) query | **~18–27 s** end-to-end |
| Diseases resolvable | 23,224 |
| Diseases with literature in corpus | 113 |

**Performance work.** Query latency was cut from **~56 s to ~22 s** by measurement
rather than guesswork: disabling the model's reasoning mode (it was emitting
answers into the wrong field), forcing all layers onto the GPU (Ollama's default
left ~1.9 GB on the CPU), bounding prompt size, and capping output verbosity.
Retrieval was simultaneously corrected to scope by disease provenance — which is
what made evidence scores meaningful instead of uniformly zero.

**Engineering hygiene.** Reproducible corpus builder (`scripts/build_corpus.py`)
and index rebuilder (`scripts/rebuild_index.py`); integration tests; docs
(PRD, STACK, DECISIONS, PITCH_DECK); a tagged known-good release
(`v1.2-working`) for safe rollback.

**Known Limitations — stated deliberately.**

| Limitation | Detail |
|---|---|
| Corpus coverage | 113 of 23,224 diseases have literature. Every disease *resolves* and returns candidates, but uncovered ones score 0.000 and abstain on evidence. |
| Live query latency | ~22 s for a non-cached disease (27B model generating 10 candidates with citations). Demo diseases are precomputed and instant. |
| Demo topology | The model backend runs on a local workstation; the public UI depends on that host being awake. |
| Corpus attribution | A minority of retrieved abstracts match a disease but discuss a different drug; these rank low and are correctly reported as "no evidence" for a candidate rather than mis-cited. |
| Not clinically validated | No clinician adjudication of outputs yet. Every result is a research hypothesis requiring clinical validation. |

---

## 6. Presentation and Communication — 10%

- **Live, clickable demo** rather than slides alone: a judge can type a disease,
  open a citation, and land on the actual PubMed paper.
- **The verification is visible.** The citation drawer shows the quoted sentence
  against its source passage, with the PubMed link — the core claim is
  inspectable in one click.
- **Honest abstention is demonstrated, not hidden.** "Insufficient evidence" is a
  first-class outcome, which is the correct behaviour for a clinical tool and
  distinguishes it from a chatbot that always answers.
- **Provenance is surfaced in the UI:** resolved ontology ID (MONDO), candidate
  counts, established-indication separation, and a data-sources panel.
- **Persistent disclaimer** that outputs are research hypotheses, not medical
  advice.
- Supporting materials: `docs/PITCH_DECK.md` (6-slide narrative), README, and
  architecture/stack documentation in-repo.

---

## Appendix — Reproducing these numbers

```bash
# rebuild the literature corpus from PubMed (real abstracts, ~20 min)
venv/bin/python scripts/build_corpus.py

# re-embed and rebuild the vector index
venv/bin/python scripts/rebuild_index.py

# run the API
venv/bin/python src/app.py        # → http://127.0.0.1:7860

# verify a query end-to-end
curl -X POST http://127.0.0.1:7860/api/query \
     -H 'Content-Type: application/json' -d '{"query":"Common cold"}'
```

**Stack:** Python 3.12 · FastAPI · Ollama (qwen3.8:27b, nomic-embed-text) ·
numpy vector search · React 18 + TypeScript + Vite + Tailwind · Tailscale Funnel ·
Render.
