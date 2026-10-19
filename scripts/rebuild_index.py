#!/usr/bin/env python
"""Re-embed the corpus and rebuild the retrieval index.

Reads data/pubmed_passages.json, embeds every passage with the Ollama
nomic-embed-text model, and writes data/index.npy + data/passages.json.

Run:  venv/bin/python scripts/rebuild_index.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import embeddings, pipeline  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SRC = os.path.join(DATA, "pubmed_passages.json")


def main():
    with open(SRC) as f:
        passages = json.load(f)
    print(f"corpus: {len(passages)} passages from {SRC}")

    # Deduplicate by pmid so the same abstract cannot outrank itself.
    seen, unique = set(), []
    for p in passages:
        key = p.get("pmid") or p.get("text", "")[:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    if len(unique) != len(passages):
        print(f"deduped: {len(passages)} -> {len(unique)}")

    texts = [p["text"] for p in unique]

    t0 = time.time()
    index = embeddings.embed_texts(texts, kind="document")
    dt = time.time() - t0
    print(f"embedded {index.shape[0]} x {index.shape[1]} in {dt:.1f}s "
          f"({dt / max(1, len(texts)):.2f}s/passage)")

    pipeline.save_index(index, unique)
    print("wrote data/index.npy + data/passages.json")

    # Sanity: a self-query should retrieve its own passage at rank 1.
    probe = unique[0]
    qv = embeddings.embed_query(probe["text"][:200])
    hits = pipeline.retrieval.search_dense(qv, index, top_k=3)
    print(f"probe self-retrieval: {[(i, round(s, 4)) for i, s in hits]}")


if __name__ == "__main__":
    main()
