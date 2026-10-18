# 💊 Telemedicon — Drug Repurposing via Literature RAG

**Telemedicon 2026 · Internal Hackathon · AI + Digital Health**

A clinician or researcher types a disease name. The system retrieves relevant
biomedical literature and generates a **ranked list of drug repurposing
candidates with citations** — grounded in real sources, not hallucinated.

## Quick start

```bash
# Setup
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your Gemini key
echo 'GEMINI_API_KEY=your-key-here' > .env

# Run (once the pipeline is built)
python src/app.py
```

## Stack

| Layer | Tool |
|---|---|
| Embeddings | Ollama `nomic-embed-text` (local) |
| Vector store | numpy cosine similarity |
| LLM | Gemini Flash (`gemini-3.8-flash`) |
| UI | Gradio |
| Data | HuggingFace (EveryCure KG + PubMed abstracts) |

See [`docs/STACK.md`](docs/STACK.md) for the full design and
[`docs/DECISIONS.md`](docs/DECISIONS.md) for the complete decision log.

## Status

🚧 **Skeleton complete** — venv, libraries, docs, and git initialized.
Next: data pipeline + RAG implementation.
