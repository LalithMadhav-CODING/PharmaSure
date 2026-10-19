"""FastAPI server and Gradio UI for PharmaSure / Telemedicon — Drug Repurposing via Literature RAG."""
import os
import sys
import json
from fastapi import FastAPI, HTTPException, Request, Response
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
    from . import pipeline, coverage
except (ImportError, ValueError):
    from src import pipeline, coverage


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
        # The Funnel hostname resolves to the Tailscale CGNAT range for any
        # tailnet member, so a browser on the tailnet treats it as a private
        # network request. Without this, Chrome's Private Network Access
        # preflight is rejected and the deployed frontend cannot reach the API.
        allow_private_network=True,
    )

    # --- Optional server-side reverse proxy for /api/* -------------------------
    # When this process serves only the UI (e.g. a small cloud container) while
    # the model runs on the local machine, forward /api/* to the real backend.
    # Keeping the browser same-origin sidesteps CORS and Chrome's Private
    # Network Access rules, which block subresource requests to a host that
    # resolves into the Tailscale CGNAT range.
    #
    # The proxy must NOT engage when this process is itself the backend. A
    # loopback/localhost request (including the test client) means we are being
    # called directly, so we answer it ourselves — otherwise a local request
    # would be forwarded out to the tunnel and back, and the test suite would
    # silently exercise the deployed server instead of the code under test.
    _LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}

    def _is_direct_local_request(request: Request) -> bool:
        host = (request.url.hostname or "").lower()
        return host in _LOCAL_HOSTNAMES or host.endswith(".local")

    def _proxy_target() -> str:
        target = os.getenv("BACKEND_API_URL", "").strip().rstrip("/")
        if target:
            return target
        cfg_path = os.path.join(repo_root, "frontend", "dist", "config.json")
        try:
            with open(cfg_path) as fh:
                return (json.load(fh).get("proxyTarget") or "").strip().rstrip("/")
        except Exception:
            return ""

    @server.middleware("http")
    async def api_proxy(request: Request, call_next):
        target = _proxy_target()
        if target and request.url.path.startswith("/api/") \
                and not _is_direct_local_request(request):
            from urllib.parse import urlparse
            target_host = urlparse(target).netloc
            # Never proxy to ourselves (the local server is reachable *as* the
            # tunnel host); only forward when we are a different host.
            if request.url.netloc != target_host:
                import httpx
                url = f"{target}{request.url.path}"
                if request.url.query:
                    url = f"{url}?{request.url.query}"
                body = await request.body()
                fwd = {
                    k: v for k, v in request.headers.items()
                    if k.lower() not in ("host", "content-length", "connection")
                }
                try:
                    async with httpx.AsyncClient(timeout=900) as client:
                        upstream = await client.request(
                            request.method, url, content=body, headers=fwd
                        )
                except Exception as exc:  # noqa: BLE001
                    return JSONResponse(
                        status_code=502,
                        content={"detail": f"Backend unreachable: {exc}"},
                    )
                skip = ("content-encoding", "content-length",
                        "transfer-encoding", "connection")
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    headers={k: v for k, v in upstream.headers.items()
                             if k.lower() not in skip},
                )
        return await call_next(request)

    @server.get("/api/health")
    def health_endpoint():
        """Health and coverage metadata.

        Distinguishes knowledge-graph vocabulary from local literature coverage.
        They are very different numbers, and conflating them overstates what the
        system can actually evidence: the graph recognises ~23k diseases, while
        the indexed corpus holds abstracts for only a small subset.
        """
        cov = coverage.coverage_metadata()
        return {
            "status": "ok",

            # --- knowledge-graph vocabulary ---
            "disease_count": cov["kg_disease_count"],
            "kg_disease_count": cov["kg_disease_count"],
            "kg_diseases_with_candidates": cov["kg_diseases_with_candidates"],
            "graph_candidates_available": True,

            # --- local literature coverage ---
            "corpus_size": cov["local_abstract_count"],
            "local_abstract_count": cov["local_abstract_count"],
            "local_literature_disease_count": cov["local_literature_disease_count"],
            "local_unique_pmid_count": cov["local_unique_pmid_count"],
            "corpus_schema_version": cov["corpus_schema_version"],

            # --- capability flags, stated explicitly rather than implied ---
            # Not every resolvable disease has local evidence, so this is False.
            "all_diseases_supported": False,
            "live_retrieval_enabled": cov["live_retrieval_enabled"],

            "demo_supported_diseases": pipeline.get_supported_diseases_list(),
            "supported_diseases": pipeline.get_supported_diseases_list(),
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

        `apiBase`   — what the BROWSER uses for API calls. Empty means
                      same-origin, which is the default and the only value that
                      avoids cross-origin/Private-Network-Access problems.
        `proxyTarget` — what THIS SERVER proxies /api/* to when it is not the
                      machine running the model.

        BACKEND_API_URL, when set, overrides proxyTarget.
        """
        payload = {}
        static_cfg = os.path.join(repo_root, "frontend", "dist", "config.json")
        if os.path.isfile(static_cfg):
            try:
                with open(static_cfg) as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    payload = loaded
            except Exception:
                payload = {}

        env_target = os.getenv("BACKEND_API_URL", "").strip().rstrip("/")
        return JSONResponse(
            content={
                "apiBase": (payload.get("apiBase") or "").rstrip("/"),
                "proxyTarget": env_target or (payload.get("proxyTarget") or "").rstrip("/"),
            },
            headers={"Cache-Control": "no-store"},
        )

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
