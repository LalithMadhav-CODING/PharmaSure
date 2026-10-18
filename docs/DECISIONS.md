# 📋 Decisions & Change Log — Telemedicon

> Detailed record of every decision made, what was tried, and what changed.
> Tracked in git (not gitignored) so the project can be understood or resumed later.

---

## Session 1 — 2026-10-18

### Context
- Telemedicon 2026 hackathon (AI + Digital Health), IIIT Sri City
- 26-hour window: 10am Oct 17 → 12pm Oct 18
- Solo participant + AI agent (Hermes)
- Machine: RTX 4000 Ada 20GB, Python 3.12, Ollama running, 535GB free disk

### Decisions

| # | Decision | Reason | Rejected alternative |
|---|---|---|---|
| 1 | **Idea: Drug Repurposing via Literature RAG** | Best fit: matches user's retrieval background, high clinical relevance, clean demo, buildable in 26h | Lab/symptom interpreter, imaging triage, wearable monitoring |
| 2 | **Stack: lightweight (no torch/transformers)** | ML libraries not installed; torch install risks 1.5–2h on Python 3.12 | Full torch + transformers + FAISS + langchain |
| 3 | **Embeddings: Ollama `nomic-embed-text`** | Already have Ollama; 10–100x faster than API; no rate limits; no key | Gemini embeddings (slower, rate-limited) |
| 4 | **Vector store: numpy cosine similarity** | Corpus is small (5–10k); <100ms queries; zero install risk | FAISS (overkill for <10k) |
| 5 | **LLM: Gemini Flash** | Stronger than qwen3:4b; better structured output; cloud (no local VRAM pressure) | Ollama qwen3:4b (smaller, weaker tool calling) |
| 6 | **Model name: `gemini-3.8-flash`** | `gemini-2.0-flash` returned 404; error message recommended `gemini-3.8-flash` | gemini-2.0-flash, gemini-2.5-flash, gemini-flash-latest |
| 7 | **UI: Gradio** | Single pip install, professional look, Python-native | Streamlit, FastAPI+HTML, CLI |
| 8 | **Data: EveryCure KG + PubMed abstracts** | CC-BY 4.0, small, clean, structured; gives drug-disease pairs + literature text | Full PubMed (360GB, too large), MIMIC (requires credentialing) |
| 9 | **3-hour buffer** | 17 working hours + 6 sleep + 3 buffer = 26h | Finishing at deadline (risky) |
| 10 | **.env gitignored, docs tracked** | API key must not be committed; documentation must be in git for future reference | — |

### Changes made

| Change | Detail |
|---|---|
| Created project | `/home/additional/Projects/Telemedicon` |
| Created venv | `python3.12 -m venv venv` (Python 3.12.3) |
| Installed libraries | `numpy`, `httpx`, `gradio`, `datasets`, `pandas`, `google-generativeai` |
| Pulled Ollama models | `nomic-embed-text` (274MB), `qwen3:4b` (2.5GB) |
| Stored Gemini key | `.env` (gitignored) |
| Created docs | `docs/STACK.md`, `docs/DECISIONS.md` |
| Created requirements.txt | All pip dependencies listed |
| Created .gitignore | `.env`, `venv/`, `__pycache__/` ignored |

### Environment facts verified

| Fact | Value |
|---|---|
| Python | 3.12.3 (`/usr/bin/python3.12`) |
| GPU | RTX 4000 Ada, 20,475 MiB |
| Disk | 535GB free (`/`) |
| Ollama | running; `nomic-embed-text`, `qwen3:4b` pulled |
| Gemini | `gemini-3.8-flash` working with provided key |
| PyPI | reachable |

### Time budget

| Phase | Hours | Status |
|---|---|---|
| Setup (venv, installs, models) | 2h | ✅ done |
| Data pipeline | 2h | pending |
| Embed + index | 1.5h | pending |
| RAG pipeline | 3h | pending |
| UI | 2.5h | pending |
| Integrate + test | 3h | pending |
| Sleep | 6h | — |
| Demo prep | 2h | pending |
| Final polish | 1h | pending |
| **Buffer** | **3h** | — |
| **Total** | **26h** | — |

---

## Session 2 — 2026-10-18 (PRD Debate & Lock)

### Context
- Received PRD improvement proposals from ChatGPT and Claude (v1.1)
- Ran 4-lens debate via sub-agents (hackathon strategy, technical feasibility, clinical credibility, UX/demo)
- User locked final decisions

### Debate consensus (all 4 agents agree)
| # | Decision | Rationale |
|---|---|---|
| 1 | **Cached demo path** | #1 demo-safety feature; pre-run 3–5 queries, serve instantly |
| 2 | **Verbatim-quote citation verifier** | Highest demo ROI; "wow moment" when judge clicks citation |
| 3 | **Evidence tier labels** (Strong/Moderate/Preliminary) | Instantly readable by non-technical judges |
| 4 | **Single Gemini call** | Latency budget; fewer failure points |
| 5 | **Abstention for unsupported diseases** | "I don't know" beats hallucination |
| 6 | **Vertical slice first** | One working query > broken system with all features |
| 7 | **Known-indication labelling** | Prevents "suggesting metformin for diabetes" embarrassment |

### Tensions resolved
| Tension | Options | Final choice | Why |
|---|---|---|---|
| Verbatim check strictness | Strict substring vs. soft two-stage | **Two-stage** (source identity + claim support) | Clinical expert: strict rejects valid paraphrases; "needs review" flag instead |
| Per-candidate retrieval | Yes vs. no | **Skip for P0** | UX expert: too slow (150 ops), invisible in UI; use cached results |
| Evidence weights | 0.4/0.3/0.3 vs. 0.3/0.3/0.4 | **0.3/0.3/0.4** | Clinical: study quality should dominate over semantic relevance |

### Final locked decisions (PRD v1.2)
| # | Decision | Implementation |
|---|---|---|
| 1 | Demo reliability | Precompute and cache results for 3–5 queries |
| 2 | Citation verification | Two-stage: programmatic entity checks + LLM-assisted support check |
| 3 | Verification failures | Flag as "needs review" rather than auto-rejecting |
| 4 | Evidence tiers | Strong / Moderate / Preliminary |
| 5 | Gemini calls | One generation call in main answer path |
| 6 | Unsupported diseases | Abstain when evidence is insufficient |
| 7 | Implementation strategy | One complete vertical slice before additional features |
| 8 | Known indications | Explicitly label established indications |
| 9 | Retrieval strategy | KG-first two-stage, with dense retrieval fallback, after verifying KG schema |
| 10 | Evidence direction | Positive / Negative / Mixed; default Uncertain |
| 11 | Per-candidate retrieval | Skip for P0 |
| 12 | Evidence weights | 0.3 relevance + 0.3 support + 0.4 study quality |
| 13 | Score presentation | Label as experimental heuristic, never clinical probability |

### Changes made
| Change | Detail |
|---|---|
| PRD updated to v1.2 | All locked decisions documented; assumptions tagged **[ASSUMPTION]** |
| Improvement notes saved | `docs/improvements/chatgpt_improvements.md`, `docs/improvements/claude_v1.1.md` |
| Git committed | PRD v1.2 + improvement notes |
