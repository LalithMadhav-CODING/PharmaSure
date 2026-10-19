"""FastAPI server and Gradio UI for PharmaSure / Telemedicon — Drug Repurposing via Literature RAG."""
import os
import sys
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import gradio as gr
import uvicorn

# Ensure repository root is on sys.path for direct python execution
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from . import pipeline
except (ImportError, ValueError):
    from src import pipeline


def format_result(result: dict) -> str:
    """Format pipeline result as Markdown for display (preserved for Gradio UI)."""
    if result.get("status") == "unsupported_disease":
        return f"## ⚠️ Unsupported Disease\n\n{result.get('message', 'Unsupported disease.')}"

    if result.get("status") == "insufficient_evidence":
        return f"## ⚠️ Insufficient Evidence\n\n{result.get('message', 'Insufficient evidence.')}"

    disease_name = result.get("disease", {}).get("name", result.get("query", "Unknown"))
    md = f"## 🔬 Results for: {disease_name}\n\n"

    # Timings
    t = result.get("timings_ms", {})
    md += f"*Latency: {t.get('total_ms', 0)}ms"
    if result.get("from_cache"):
        md += " (cached)"
    md += "*\n\n"

    # Known indications
    known = result.get("known_indications", [])
    if known:
        md += "### Already Indicated\n"
        for k in known:
            md += f"- {k['drug_name']}\n"
        md += "\n"

    # Repurposing candidates
    results = result.get("results", [])
    if results:
        md += "### Repurposing Candidates\n\n"
        for r in results:
            tier = r.get("evidence", {}).get("tier", "Preliminary")
            direction = r.get("direction", "Uncertain")
            score = r.get("evidence", {}).get("score", 0.0)

            # Tier emoji
            tier_icon = {"Strong": "🟢", "Moderate": "🟡", "Preliminary": "🔴"}.get(tier, "⚪")
            # Direction emoji
            dir_icon = {"Positive": "✅", "Negative": "❌", "Mixed": "⚠️", "Uncertain": "❓"}.get(direction, "❓")

            md += f"**{r.get('rank', 1)}. {r.get('drug', 'Unknown')}** — {tier_icon} {tier} (score: {score:.3f}) {dir_icon} {direction}\n\n"
            md += f"> {r.get('reason', '')}\n\n"

            # Claims with citations
            for claim in r.get("claims", []):
                status_icon = {"verified": "✅", "needs_review": "⚠️"}.get(claim.get("verification_status", ""), "❓")
                cids = claim.get("citations") or claim.get("citation_ids", [])
                citations = " ".join(f"[{cid}]" for cid in cids)
                md += f"- {status_icon} {claim.get('text', '')} {citations}\n"
                if claim.get("verification_reason") and claim.get("verification_status") != "verified":
                    md += f"  - *{claim.get('verification_reason')}*\n"

            md += "\n"

    # Citation passages
    passages = result.get("passages", [])
    if passages:
        md += "<details><summary>📄 Source Passages</summary>\n\n"
        for p in passages:
            pid = p.get("id", "N/A")
            pmid = p.get("pmid", "N/A")
            source = p.get("source", "unknown")
            year = p.get("year", "N/A")
            pub_type = p.get("pub_type", "unknown")
            md += f"**[{pid}]** ({source}, {year}, {pub_type}, PMID: {pmid})\n\n"
            md += f"> {p.get('text', '')[:300]}...\n\n"
        md += "</details>\n"

    return md


def query_fn(query: str) -> str:
    """Run the pipeline and format results for Gradio."""
    if not query.strip():
        return "Please enter a disease name."
    result = pipeline.run_pipeline(query)
    return format_result(result)


def create_gradio_app() -> gr.Blocks:
    """Create the Gradio app (kept functional for backward compatibility)."""
    with gr.Blocks(title="PharmaSure — Drug Repurposing RAG") as app:
        gr.Markdown("# 💊 PharmaSure — Drug Repurposing via Literature RAG\n")
        gr.Markdown("⚠️ *Research hypotheses only, not medical advice.*\n")

        with gr.Row():
            query_input = gr.Textbox(
                label="Disease",
                placeholder="e.g. Alzheimer's disease",
                scale=4,
            )
            submit_btn = gr.Button("Search", variant="primary", scale=1)

        # Example queries
        gr.Markdown("### Examples")
        with gr.Row():
            for example in ["Alzheimer's disease", "Parkinson's disease", "Multiple myeloma"]:
                gr.Button(example).click(
                    fn=lambda e=example: e,
                    outputs=query_input,
                )

        # Results
        result_md = gr.Markdown(label="Results")

        # Event handlers
        submit_btn.click(fn=query_fn, inputs=query_input, outputs=result_md)
        query_input.submit(fn=query_fn, inputs=query_input, outputs=result_md)

    return app


def create_app() -> FastAPI:
    """Create the full-stack FastAPI application serving APIs, static UI, and Gradio testbed."""
    server = FastAPI(
        title="Telemedicon — Drug Repurposing via Literature RAG",
        description="Biomedical Literature-Based Drug Repurposing Research Platform",
        version="1.2.0"
    )

    # Allow all origins for preview proxy support
    server.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @server.get("/api/health")
    def health_endpoint():
        """Health and metadata endpoint returning corpus size and supported diseases."""
        return {
            "status": "ok",
            "corpus_size": 7500,
            "disease_count": 23224,
            "all_diseases_supported": True,
            "data_sources": [
                "EveryCure Knowledge Graph (matrix-scores)",
                "PubMed Literature Abstracts"
            ]
        }

    @server.post("/api/query")
    async def query_endpoint(request: Request):
        """Main RAG query endpoint accepting {'query': '...'}."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        query_text = body.get("query", "")
        if not isinstance(query_text, str) or not query_text.strip():
            raise HTTPException(status_code=400, detail="The 'query' field is required")

        result = pipeline.run_pipeline(query_text.strip())
        return JSONResponse(content=result)

    @server.get("/config.json")
    def runtime_config():
        """Runtime frontend config.

        Lets the deployed UI talk to a backend running elsewhere (e.g. a local
        machine exposed through a tunnel) without rebuilding the bundle: the
        frontend fetches this at startup and uses `apiBase` for all API calls.

        Resolution order:
          1. BACKEND_API_URL env var (set on the host running this service)
          2. the checked-in static frontend/public/config.json
          3. "" => same-origin
        """
        env_url = os.getenv("BACKEND_API_URL", "").strip().rstrip("/")
        if env_url:
            return JSONResponse(content={"apiBase": env_url},
                                headers={"Cache-Control": "no-store"})

        static_cfg = os.path.join(repo_root, "frontend", "dist", "config.json")
        if os.path.isfile(static_cfg):
            try:
                with open(static_cfg) as fh:
                    return JSONResponse(content=json.load(fh),
                                        headers={"Cache-Control": "no-store"})
            except Exception:
                pass

        return JSONResponse(content={"apiBase": ""},
                            headers={"Cache-Control": "no-store"})

    # Mount legacy Gradio UI at /gradio
    gradio_blocks = create_gradio_app()
    server = gr.mount_gradio_app(server, gradio_blocks, path="/gradio")

    # Static files for production React frontend
    dist_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
    assets_dir = os.path.join(dist_dir, "assets")

    if os.path.exists(assets_dir):
        server.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if os.path.exists(dist_dir):
        # Confine static serving to the build output. The raw request path can
        # contain traversal sequences (e.g. "..%2f..%2f.env") which os.path.join
        # would follow straight out of dist_dir and serve arbitrary files.
        dist_root = os.path.realpath(dist_dir)

        @server.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            candidate = os.path.realpath(
                os.path.join(dist_root, full_path.lstrip("/"))
            )
            if (candidate == dist_root or candidate.startswith(dist_root + os.sep)) \
                    and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(dist_root, "index.html"))

    return server


# Default app instance
app = create_app()


if __name__ == "__main__":
    uvicorn.run("src.app:app", host="0.0.0.0", port=7860, reload=False)
