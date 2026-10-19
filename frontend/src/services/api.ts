import { QueryResponse, HealthResponse } from '../types';

const API_BASE_FALLBACK = ''; // relative path for same-origin proxy

// API base resolution order:
//   1. runtime /config.json  -> lets the deployed bundle target a tunneled backend
//   2. build-time VITE_API_BASE_URL
//   3. same-origin (local dev / single-service deploy)
let apiBasePromise: Promise<string> | null = null;

function getApiBase(): Promise<string> {
  if (!apiBasePromise) {
    const buildTime = (import.meta as any)?.env?.VITE_API_BASE_URL;
    apiBasePromise = fetch('/config.json', { headers: { Accept: 'application/json' } })
      .then((res) => (res.ok ? res.json() : null))
      .then((cfg) => {
        const runtime = cfg && typeof cfg.apiBase === 'string' ? cfg.apiBase.trim() : '';
        return (runtime || buildTime || API_BASE_FALLBACK).replace(/\/+$/, '');
      })
      .catch(() => (buildTime || API_BASE_FALLBACK).replace(/\/+$/, ''));
  }
  return apiBasePromise;
}

let activeAbortController: AbortController | null = null;
let latestRequestId = 0;

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${await getApiBase()}/api/health`, {
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  const data = await response.json();
  return {
    status: data.status || 'unknown',
    corpus_size: typeof data.corpus_size === 'number' ? data.corpus_size : 7500,
    supported_diseases: Array.isArray(data.supported_diseases) ? data.supported_diseases : [],
    data_sources: Array.isArray(data.data_sources) ? data.data_sources : [
      'EveryCure Knowledge Graph (matrix-scores)',
      'PubMed Literature Abstracts'
    ],
  };
}

export async function queryDisease(query: string): Promise<{ data: QueryResponse; isLatest: boolean }> {
  // Cancel any prior in-flight request to prevent race conditions & stale state
  if (activeAbortController) {
    activeAbortController.abort();
  }

  const controller = new AbortController();
  activeAbortController = controller;
  const requestId = ++latestRequestId;

  try {
    const response = await fetch(`${await getApiBase()}/api/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ query: query.trim() }),
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorDetail = `Server error (${response.status})`;
      try {
        const errJson = await response.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // use default errorDetail
      }
      throw new Error(errorDetail);
    }

    const json = await response.json();

    // Normalize response fields defensively
    const normalized: QueryResponse = {
      status: json.status || 'ok',
      query: json.query || query,
      message: json.message || '',
      disease: json.disease ? {
        id: json.disease.id || 'N/A',
        name: json.disease.name || query,
        synonyms: json.disease.synonyms || '',
      } : undefined,
      results: Array.isArray(json.results) ? json.results.map((c: any, idx: number) => ({
        rank: typeof c.rank === 'number' ? c.rank : idx + 1,
        drug: c.drug || 'Unknown Candidate',
        direction: (['Positive', 'Negative', 'Mixed', 'Uncertain'].includes(c.direction) ? c.direction : 'Uncertain'),
        evidence: {
          score: typeof c.evidence?.score === 'number' ? Math.max(0, Math.min(1, c.evidence.score)) : 0,
          tier: (['Strong', 'Moderate', 'Preliminary'].includes(c.evidence?.tier) ? c.evidence.tier : 'Preliminary'),
          support: typeof c.evidence?.support === 'number' ? c.evidence.support : 0,
          best_study_type: c.evidence?.best_study_type || 'unspecified',
        },
        reason: c.reason || 'No clinical rationale provided.',
        claims: Array.isArray(c.claims) ? c.claims.map((cl: any) => ({
          text: cl.text || '',
          citations: Array.isArray(cl.citations) ? cl.citations : (Array.isArray(cl.citation_ids) ? cl.citation_ids : []),
          quote: cl.quote || '',
          verification_status: cl.verification_status === 'verified' ? 'verified' : 'needs_review',
          verification_reason: cl.verification_reason || undefined,
        })) : [],
        // Counterfactual audit: passed through when present. Legacy cached
        // responses legitimately omit it, and the UI renders an explicit
        // "unavailable" state rather than inventing one.
        evidence_audit: (c.evidence_audit && typeof c.evidence_audit === 'object')
          ? {
              ...c.evidence_audit,
              counterfactuals: Array.isArray(c.evidence_audit.counterfactuals)
                ? c.evidence_audit.counterfactuals
                : [],
              sources: Array.isArray(c.evidence_audit.sources) ? c.evidence_audit.sources : [],
              warnings: Array.isArray(c.evidence_audit.warnings) ? c.evidence_audit.warnings : [],
            }
          : undefined,
      })) : [],
      known_indications: Array.isArray(json.known_indications) ? json.known_indications.map((k: any) => ({
        drug_name: k.drug_name || 'Unknown',
        drug_id: k.drug_id || undefined,
      })) : [],
      passages: Array.isArray(json.passages) ? json.passages.map((p: any, pIdx: number) => ({
        id: p.id !== undefined ? p.id : (pIdx + 1),
        text: p.text || '',
        source: p.source || 'PubMed',
        pmid: p.pmid || null,
        year: p.year || null,
        pub_type: p.pub_type || null,
      })) : [],
      timings_ms: json.timings_ms || { total_ms: 0 },
      from_cache: Boolean(json.from_cache),
      evidence_audit_summary: (json.evidence_audit_summary && typeof json.evidence_audit_summary === 'object')
        ? json.evidence_audit_summary
        : undefined,
    };

    return {
      data: normalized,
      isLatest: requestId === latestRequestId,
    };
  } finally {
    if (activeAbortController === controller) {
      activeAbortController = null;
    }
  }
}
