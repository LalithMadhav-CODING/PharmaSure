"""Gradio UI for Telemedicon — Drug Repurposing via Literature RAG."""
import json
import gradio as gr
from . import pipeline


def format_result(result: dict) -> str:
    """Format pipeline result as Markdown for display."""
    if result["status"] == "unsupported_disease":
        return f"## ⚠️ Unsupported Disease\n\n{result['message']}"

    if result["status"] == "insufficient_evidence":
        return f"## ⚠️ Insufficient Evidence\n\n{result['message']}"

    md = f"## 🔬 Results for: {result['disease']['name']}\n\n"

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
            tier = r["evidence"]["tier"]
            direction = r["direction"]
            score = r["evidence"]["score"]

            # Tier emoji
            tier_icon = {"Strong": "🟢", "Moderate": "🟡", "Preliminary": "🔴"}.get(tier, "⚪")
            # Direction emoji
            dir_icon = {"Positive": "✅", "Negative": "❌", "Mixed": "⚠️", "Uncertain": "❓"}.get(direction, "❓")

            md += f"**{r['rank']}. {r['drug']}** — {tier_icon} {tier} (score: {score:.3f}) {dir_icon} {direction}\n\n"
            md += f"> {r['reason']}\n\n"

            # Claims with citations
            for claim in r.get("claims", []):
                status_icon = {"verified": "✅", "needs_review": "⚠️"}.get(claim.get("verification_status", ""), "❓")
                citations = " ".join(f"[{cid}]" for cid in claim.get("citation_ids", []))
                md += f"- {status_icon} {claim['text']} {citations}\n"
                if claim.get("verification_reason") and claim["verification_status"] != "verified":
                    md += f"  - *{claim['verification_reason']}*\n"

            md += "\n"

    # Citation passages
    passages = result.get("passages", [])
    if passages:
        md += "<details><summary>📄 Source Passages</summary>\n\n"
        for i, p in enumerate(passages):
            pmid = p.get("pmid", "N/A")
            source = p.get("source", "unknown")
            year = p.get("year", "N/A")
            pub_type = p.get("pub_type", "unknown")
            md += f"**[{i+1}]** ({source}, {year}, {pub_type}, PMID: {pmid})\n\n"
            md += f"> {p['text'][:300]}...\n\n"
        md += "</details>\n"

    return md


def query_fn(query: str) -> str:
    """Run the pipeline and format results."""
    if not query.strip():
        return "Please enter a disease name."
    result = pipeline.run_pipeline(query)
    return format_result(result)


def create_app() -> gr.Blocks:
    """Create the Gradio app."""
    with gr.Blocks(title="Telemedicon — Drug Repurposing RAG") as app:
        gr.Markdown("# 💊 Telemedicon — Drug Repurposing via Literature RAG\n")
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


if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
