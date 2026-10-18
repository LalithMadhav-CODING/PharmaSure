# Telemedicon — Recommended PRD Improvements

**Project:** Telemedicon — Drug Repurposing via Literature RAG  
**Based on:** `PRD.md`, Version 1.0, dated 2026-10-18  
**Purpose:** A focused improvement plan for making Telemedicon more scientifically reliable, explainable, measurable, and demo-ready without expanding the hackathon scope unnecessarily.

---

## 1. Executive Recommendation

Evolve Telemedicon from a standard literature RAG demo into an **evidence-first drug-repurposing research assistant**.

Keep the core product flow simple:

1. A researcher enters a disease name or description.
2. Telemedicon retrieves relevant literature passages and structured drug–disease associations.
3. It normalizes entities, deduplicates evidence, and ranks candidate hypotheses.
4. It generates concise explanations grounded in source passages.
5. It validates citations before displaying results.
6. The researcher can inspect supporting and conflicting evidence.

The highest-value improvements are scientific reliability and traceability—not adding more AI agents or a more complicated technology stack.

## 2. Critical Improvements

### 2.1 Validate whether citations support claims

Attaching a citation does not prove that the cited passage supports the associated claim.

**Recommended changes**
- Store the exact source passage and stable source identifier for each citation.
- Link each factual claim to one or more specific passages.
- Check that each cited source exists in the indexed corpus.
- Add a claim-support validation step before displaying the answer.
- Suppress or qualify claims that cannot be supported by retrieved evidence.
- If evidence is insufficient, say so rather than inventing an explanation.

**Suggested acceptance criteria**
- Every displayed factual claim has at least one resolvable source citation.
- Citations open the exact passage used by the system.
- Unsupported claims are removed or explicitly marked as unverified.
- Citation coverage and claim-support rate are measured separately.

### 2.2 Distinguish structured associations from literature evidence

An EveryCure knowledge-graph edge and a PubMed passage represent different evidence types. A structured association must not be presented as if it were a clinical study.

**Recommended changes**
- Label evidence by source type: `pubmed`, `kg-edge`, or another explicitly supported type.
- Preserve source identifiers and provenance.
- Record study type and evidence level only when the source or a validated extraction step supports them.
- Distinguish direct evidence from an inference made by the system.
- Do not imply that an association establishes clinical efficacy.

### 2.3 Define what scores mean

The PRD's example score (`0.87`) is ambiguous. Users could interpret it as an 87% probability that a drug will work.

**Recommended changes**
- Use a clearly named `evidence_score` only after defining its calculation.
- Keep retrieval relevance separate from evidence strength.
- Do not use an LLM's self-reported confidence as a clinical probability.
- Explain the score's inputs and limitations in the UI.
- If no defensible scoring method has been implemented, omit the score or label it as an experimental, uncalibrated ranking score.

A retrieval score, a composite evidence score, and a probability of clinical success are not interchangeable.

### 2.4 Rank evidence, not just semantic similarity

Vector similarity can retrieve passages that mention a drug without supporting its use for the target disease. Negative findings may also be overlooked.

**Recommended ranking signals**
- Relevance to the requested disease.
- Correct drug–disease entity match.
- Evidence direction: positive, negative, mixed, or unclear.
- Source and study characteristics, when available.
- Independent corroboration from distinct sources.
- Duplicate or near-duplicate evidence penalties.

Do not reward repeated copies of the same study as independent confirmation. Keep the first implementation heuristic and explainable rather than introducing a trained reranker before the core system works.

### 2.5 Make performance targets measurable

The PRD targets less than five seconds end to end, including remote model calls. Treat this as a target to test, not a guarantee.

**Recommended changes**
- Measure embedding, retrieval, reranking, generation, and total latency separately.
- Report median and p95 latency on a fixed test set.
- Add timeouts and graceful error handling for remote services.
- Cache stable query results where appropriate.
- Prepare a prevalidated demo query and corpus snapshot for network or API failures.

## 3. Resolve PRD Ambiguities

| Current ambiguity | Recommended clarification |
|---|---|
| Corpus target is 5,000–10,000 passages, while the planned PubMed subset is 500–1,000 abstracts. | Track abstract count, knowledge-graph edge count, and final passage count separately. |
| The unified schema includes a PMID, but knowledge-graph edges may not have one. | Make PMID nullable and preserve a source type and source-specific identifier. |
| Confidence score is required but undefined. | Define an interpretable scoring method or omit the score until one exists. |
| Citation coverage is required but validation is unspecified. | Add citation resolution and claim-support checks. |
| Candidate definition is unclear. | Distinguish known indications from potential repurposing hypotheses when reliable indication data is available. |
| Latency is specified only end to end. | Set stage-level budgets, timeouts, and fallback behavior. |
| Demo depends on live services. | Preload a validated corpus and prepare a tested fallback path. |

**Terminology clarification:** A corpus of 5,000–10,000 passages does not necessarily contain 5,000–10,000 independent scientific sources. Report passage count and unique source count separately.

## 4. Recommended Architecture

Keep the existing Python, NumPy, Ollama, Gemini, and Gradio stack. Add lightweight pipeline stages rather than separate services.

```text
User query
   |
   v
1. Query normalization
   - Resolve disease aliases where possible
   - Extract disease and optional drug entities
   - Detect ambiguous queries
   |
   v
2. Hybrid evidence retrieval
   - NumPy vector similarity
   - Keyword search
   - Structured drug–disease lookup
   |
   v
3. Evidence processing
   - Normalize drug and disease names
   - Deduplicate passages and sources
   - Preserve provenance
   - Classify evidence direction when supported
   |
   v
4. Evidence-aware ranking
   - Relevance
   - Entity match
   - Evidence direction
   - Source characteristics
   - Independent corroboration
   |
   v
5. Structured answer generation
   - Candidate hypothesis
   - Evidence summary
   - Limitations
   - Source passage IDs
   |
   v
6. Citation validation
   - Confirm source and passage IDs
   - Check claim-to-source mapping
   - Remove or qualify unsupported claims
   |
   v
7. Results UI
   - Ranked candidates
   - Evidence labels
   - Clickable citations
   - Supporting and conflicting evidence
```

These stages can be Python modules inside the existing application. Do not introduce a graph database, autonomous multi-agent framework, or a new frontend solely to support this flow.

## 5. Data Schema Improvements

The current unified schema is too small to represent provenance and different source types reliably.

A recommended conceptual schema is:

```json
{
  "passage_id": "passage-001",
  "text": "Exact source passage text",
  "source_type": "pubmed",
  "source_id": "source-specific-id",
  "pmid": null,
  "drug_name": "Normalized drug name, if available",
  "drug_id": null,
  "disease_name": "Normalized disease name, if available",
  "disease_id": null,
  "study_type": "unknown",
  "evidence_direction": "unclear",
  "provenance": {
    "dataset": "source dataset name",
    "dataset_version": null
  }
}
```

This is a schema proposal, not actual research data. Populate fields only when supported; use `null` or `unknown` rather than guessing.

Recommended data rules:
- Keep raw source records separately from normalized records.
- Preserve the original source identifiers.
- Normalize drug and disease names without discarding original text.
- Deduplicate repeated passages while retaining source provenance.
- Keep structured knowledge-graph relationships distinct from literature passages.
- Track corpus build date and index version so results can be reproduced.

## 6. Retrieval and Ranking

### 6.1 Hybrid retrieval

Combine the existing embedding search with keyword search and structured knowledge-graph lookup. This can help with exact biomedical terms, abbreviations, synonyms, and named drug–disease relationships.

Keep the initial implementation lightweight. A simple keyword scorer and the existing NumPy index are sufficient for a baseline.

### 6.2 Evidence direction

Where supported by the source or a validated extraction step, classify findings as `positive`, `negative`, `mixed`, or `unclear`.

Do not infer a positive effect merely because a drug and disease appear in the same passage. Preserve uncertainty when direction cannot be established.

### 6.3 Candidate aggregation

Group evidence by normalized drug and target disease before generating the final list. This reduces duplicate candidates and prevents multiple passages from the same study from being counted as independent corroboration.

### 6.4 Ranking transparency

Record the ranking signals for each candidate. Show a concise explanation of why it was ranked, without presenting heuristic weights as validated clinical science.

## 7. UI/UX Improvements

Each candidate card should show:

1. Normalized drug name and synonyms.
2. Proposed research hypothesis.
3. Clearly named ranking or evidence score, if implemented.
4. Evidence direction and study type, when known.
5. Short evidence summary with citations visible by default.
6. Supporting and conflicting findings.
7. Limitations and unresolved questions.
8. Exact source passages available in the citation viewer.

Suggested labels:
- **Research hypothesis**
- **Evidence direction**
- **Source type**
- **Unique sources**
- **Known indication status** (only when verifiable)
- **Limitations**

Avoid labels such as “87% confidence” unless the number has a defensible, calibrated meaning. Make it explicit that the tool supports research hypothesis generation and does not provide treatment recommendations.

## 8. API Contract Improvements

The API should make provenance and uncertainty explicit. A conceptual candidate object could be:

```json
{
  "rank": 1,
  "drug": {
    "name": "Example drug",
    "normalized_id": null
  },
  "hypothesis": "Research hypothesis description",
  "evidence_score": null,
  "evidence_score_method": "not_calibrated",
  "evidence_direction": "mixed",
  "citations": [
    {
      "source_type": "pubmed",
      "source_id": "example-source-id",
      "passage_id": "passage-001",
      "supports_claim": null
    }
  ],
  "limitations": [
    "Evidence requires manual scientific review"
  ]
}
```

The values above are placeholders for schema design, not actual scientific findings.

Also consider:
- A request ID for debugging.
- Corpus and index version fields.
- Explicit error responses for ambiguous input, empty retrieval, timeout, and upstream API failure.
- A distinction between “no relevant evidence found” and “evidence of no benefit.”
- Stable citation IDs rather than relying only on UI-generated citation numbers.

## 9. Evaluation Improvements

Engineering speed and citation coverage are necessary but insufficient. Add a small manually reviewed test set.

| Metric | Purpose |
|---|---|
| Recall@10 | Measures whether relevant evidence appears in the retrieved top ten. |
| Ranking quality | Checks whether stronger, more relevant evidence is ranked higher. |
| Citation validity | Checks whether each citation resolves to the correct source. |
| Claim-support rate | Measures whether cited passages support the associated claims. |
| Entity accuracy | Checks disease and drug identification. |
| Evidence-polarity accuracy | Checks positive, negative, mixed, and unclear classification. |
| Unsupported candidate rate | Measures how often candidates lack adequate supporting evidence. |
| Median and p95 latency | Measures typical and tail response times. |

For a hackathon prototype, start with 20–50 carefully reviewed queries if time permits. Document the size and limitations of the evaluation set. Do not present a small prototype evaluation as proof of clinical validity.

Keep these metrics separate:
- **Citation coverage:** What fraction of claims have citations.
- **Citation validity:** What fraction of citations resolve correctly.
- **Claim support:** What fraction of claims are actually supported by their cited evidence.

## 10. Hackathon Priorities

Given the PRD's solo-participant setup and time constraints, prioritize in this order.

### P0 — Required for a credible demo
- Build a reproducible corpus and index.
- Complete the end-to-end query-to-candidate pipeline.
- Show real source passages in the citation viewer.
- Validate citations and suppress unsupported claims.
- Handle empty results and ambiguous queries.
- Test the primary demo query and several failure cases.
- Prepare a fallback for network or API failure.

### P1 — High value after P0 works
- Hybrid retrieval.
- Drug and disease normalization.
- Evidence direction and duplicate-source handling.
- Candidate cards with limitations and provenance.
- A small evaluation report with measured latency and claim-support results.

### P2 — Defer until after the demo
- Trained cross-encoder reranking.
- Full PubMed-scale indexing.
- Knowledge-graph visualization.
- Multi-turn memory.
- CSV/JSON export.
- Fine-tuned biomedical embeddings.
- A separate custom frontend if Gradio meets the demo needs.

Do not add autonomous multi-agent orchestration, model fine-tuning, or a complex graph database before the core evidence pipeline works.

## 11. Suggested PRD Sections to Update

Update these existing sections rather than rewriting the entire document:
- **§3 Goals & Objectives:** Define scientific reliability and evidence-quality goals.
- **§8 Functional Requirements:** Add citation validation, evidence polarity, deduplication, and insufficient-evidence behavior.
- **§9 Non-Functional Requirements:** Add stage-level latency measurement and graceful degradation.
- **§10 Data Requirements:** Add provenance, source identifiers, corpus versioning, and separate source/passages counts.
- **§12 API Design:** Define stable citation IDs, explicit uncertainty, and error responses.
- **§13 UI/UX Requirements:** Add evidence type, evidence direction, limitations, and counterevidence.
- **§14 Evaluation & Judging Criteria:** Include retrieval and claim-support evaluation.
- **§15 Success Metrics:** Separate citation coverage, validity, and support.
- **§17 Risks & Mitigations:** Add misleading scores, duplicate evidence, negative findings, and unsupported claims.

## 12. Final Recommendation

The strongest differentiator for Telemedicon is not simply that it can generate a ranked list. It is that it can explain, for every candidate:

1. **Why was this drug retrieved?** — query relevance.
2. **What evidence supports or contradicts the hypothesis?** — traceable scientific evidence.
3. **What can legitimately be concluded?** — uncertainty and limitations.

Keep the current stack and interface until the improved evidence pipeline works end to end. Build the smallest reliable system that can produce a reproducible, source-verifiable research hypothesis, and make its limitations visible.

---

*This document is a set of proposed improvements to the existing PRD. It does not replace the original PRD or claim that the proposed features have already been implemented.*
