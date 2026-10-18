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
