import {
  AuditCounterfactual,
  AuditSource,
  AuditStudyCounts,
  AuditStability,
  Candidate,
  CandidateEvidence,
  CandidateLiteratureCoverage,
  Claim,
  DiseaseMetadata,
  EvidenceAudit,
  EvidenceBreakdown,
  HealthResponse,
  KnownIndication,
  Passage,
  QueryCoverage,
  QueryResponse,
  RankingBenchmark,
  RankingBenchmarkMethod,
  ResponseStatus,
  TimingBreakdown,
} from '../types';

const API_BASE_FALLBACK = '';
const QUERY_TIMEOUT_MS = 120_000;
const HEALTH_TIMEOUT_MS = 10_000;

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function asStringOrNumber(value: unknown): string | number | undefined {
  return typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value))
    ? value
    : undefined;
}

function asStringArray(value: unknown): string[] | undefined {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : undefined;
}

function asCitationIds(value: unknown): (string | number)[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.filter(
    (item): item is string | number =>
      typeof item === 'string' || (typeof item === 'number' && Number.isFinite(item)),
  );
}

function mapBreakdown(value: unknown): EvidenceBreakdown | undefined {
  if (!isRecord(value)) return undefined;
  const breakdown: EvidenceBreakdown = {
    relevance: asFiniteNumber(value.relevance),
    relevance_weight: asFiniteNumber(value.relevance_weight),
    support: asFiniteNumber(value.support),
    support_weight: asFiniteNumber(value.support_weight),
    study_quality: asFiniteNumber(value.study_quality),
    study_quality_weight: asFiniteNumber(value.study_quality_weight),
  };
  return Object.values(breakdown).some((item) => item !== undefined) ? breakdown : undefined;
}

function mapCandidateEvidence(value: unknown): CandidateEvidence | undefined {
  if (!isRecord(value)) return undefined;
  const score = asFiniteNumber(value.score);
  const support = asFiniteNumber(value.support);
  const tierValue = asString(value.tier);
  const evidence: CandidateEvidence = {
    score,
    tier: tierValue === 'Strong' || tierValue === 'Moderate' || tierValue === 'Preliminary'
      ? tierValue
      : undefined,
    support,
    best_study_type: asString(value.best_study_type),
    breakdown: mapBreakdown(value.breakdown),
  };
  return Object.values(evidence).some((item) => item !== undefined) ? evidence : undefined;
}

function mapClaim(value: unknown): Claim | undefined {
  if (!isRecord(value)) return undefined;
  const claim: Claim = {
    text: asString(value.text),
    citations: asCitationIds(value.citations) ?? asCitationIds(value.citation_ids),
    quote: asString(value.quote),
    verification_status: asString(value.verification_status),
    verification_reason: asString(value.verification_reason),
  };
  return Object.values(claim).some((item) => item !== undefined) ? claim : undefined;
}

function mapAuditSource(value: unknown): AuditSource | undefined {
  if (!isRecord(value)) return undefined;
  const source: AuditSource = {
    source_id: asString(value.source_id),
    pmid: typeof value.pmid === 'string' ? value.pmid : null,
    pubmed_url: typeof value.pubmed_url === 'string' ? value.pubmed_url : null,
    passage_id: asStringOrNumber(value.passage_id) ?? null,
    quote: typeof value.quote === 'string' ? value.quote : null,
    citation_verified: asString(value.citation_verified),
    source_identity_status: asString(value.source_identity_status),
    quote_verification_status: asString(value.quote_verification_status),
    publication_year: asFiniteNumber(value.publication_year) ?? null,
    publication_types: asStringArray(value.publication_types),
    evidence_direction: asString(value.evidence_direction),
    direction_rationale: asString(value.direction_rationale),
    direction_snippet: typeof value.direction_snippet === 'string' ? value.direction_snippet : null,
    safety_signal: typeof value.safety_signal === 'boolean' ? value.safety_signal : undefined,
    safety_snippet: typeof value.safety_snippet === 'string' ? value.safety_snippet : null,
    study_group_id: typeof value.study_group_id === 'string' ? value.study_group_id : null,
    metadata_warnings: asStringArray(value.metadata_warnings),
  };
  return Object.values(source).some((item) => item !== undefined) ? source : undefined;
}

function mapCounterfactual(value: unknown): AuditCounterfactual | undefined {
  if (!isRecord(value)) return undefined;
  const passageIds = Array.isArray(value.passage_ids)
    ? value.passage_ids.filter(
        (id): id is string | number =>
          typeof id === 'string' || (typeof id === 'number' && Number.isFinite(id)),
      )
    : undefined;
  const counterfactual: AuditCounterfactual = {
    study_group_id: asString(value.study_group_id),
    pmids: asStringArray(value.pmids),
    passage_ids: passageIds,
    removed_passage_count: asFiniteNumber(value.removed_passage_count),
    evidence_direction: asString(value.evidence_direction),
    publication_year: asFiniteNumber(value.publication_year) ?? null,
    publication_types: asStringArray(value.publication_types),
    baseline_score: asFiniteNumber(value.baseline_score) ?? null,
    baseline_rank: asFiniteNumber(value.baseline_rank) ?? null,
    counterfactual_score: asFiniteNumber(value.counterfactual_score) ?? null,
    score_delta: asFiniteNumber(value.score_delta) ?? null,
    counterfactual_rank: asFiniteNumber(value.counterfactual_rank) ?? null,
    rank_delta: asFiniteNumber(value.rank_delta) ?? null,
    status: asString(value.status),
    error: typeof value.error === 'string' ? value.error : null,
  };
  return Object.values(counterfactual).some((item) => item !== undefined) ? counterfactual : undefined;
}

function mapStudyCounts(value: unknown): AuditStudyCounts | undefined {
  if (!isRecord(value)) return undefined;
  const counts: AuditStudyCounts = {
    eligible_independent_studies: asFiniteNumber(value.eligible_independent_studies),
    study_units: asFiniteNumber(value.study_units),
    source_records: asFiniteNumber(value.source_records),
    study_independence_verified: typeof value.study_independence_verified === 'boolean'
      ? value.study_independence_verified
      : undefined,
    supportive: asFiniteNumber(value.supportive),
    contradictory: asFiniteNumber(value.contradictory),
    null_finding: asFiniteNumber(value.null_finding),
    uncertain: asFiniteNumber(value.uncertain),
    not_classified: asFiniteNumber(value.not_classified),
    classified: asFiniteNumber(value.classified),
    unclassified: asFiniteNumber(value.unclassified),
    classified_fraction: asFiniteNumber(value.classified_fraction) ?? null,
    conflicting_evidence_present: typeof value.conflicting_evidence_present === 'boolean'
      ? value.conflicting_evidence_present
      : undefined,
    duplicate_records_removed: asFiniteNumber(value.duplicate_records_removed),
    potentially_overlapping_studies: asFiniteNumber(value.potentially_overlapping_studies),
    caveat: asString(value.caveat),
  };
  return Object.values(counts).some((item) => item !== undefined) ? counts : undefined;
}

function mapStability(value: unknown): AuditStability | undefined {
  if (!isRecord(value)) return undefined;
  const mapInfluence = (input: unknown) => {
    if (!isRecord(input)) return input === null ? null : undefined;
    return {
      study_group_id: asString(input.study_group_id),
      pmids: asStringArray(input.pmids),
      score_delta: asFiniteNumber(input.score_delta) ?? null,
      rank_delta: asFiniteNumber(input.rank_delta) ?? null,
    };
  };
  const stability: AuditStability = {
    status: asString(value.status),
    successful_counterfactuals: asFiniteNumber(value.successful_counterfactuals),
    failed_counterfactuals: asFiniteNumber(value.failed_counterfactuals),
    max_absolute_score_change: asFiniteNumber(value.max_absolute_score_change) ?? null,
    mean_absolute_score_change: asFiniteNumber(value.mean_absolute_score_change) ?? null,
    median_absolute_score_change: asFiniteNumber(value.median_absolute_score_change) ?? null,
    max_rank_movement: asFiniteNumber(value.max_rank_movement) ?? null,
    rank_min: asFiniteNumber(value.rank_min) ?? null,
    rank_max: asFiniteNumber(value.rank_max) ?? null,
    rank_range: asFiniteNumber(value.rank_range) ?? null,
    single_source_dominated: typeof value.single_source_dominated === 'boolean'
      ? value.single_source_dominated
      : undefined,
    source_with_max_score_influence: mapInfluence(value.source_with_max_score_influence),
    source_with_max_rank_influence: mapInfluence(value.source_with_max_rank_influence),
  };
  return Object.values(stability).some((item) => item !== undefined) ? stability : undefined;
}

function mapEvidenceAudit(value: unknown): EvidenceAudit | undefined {
  if (!isRecord(value)) return undefined;

  let baseline: EvidenceAudit['baseline'];
  if (isRecord(value.baseline)) {
    baseline = {
      evidence_score: asFiniteNumber(value.baseline.evidence_score) ?? null,
      evidence_rank: asFiniteNumber(value.baseline.evidence_rank) ?? null,
      displayed_kg_rank: asFiniteNumber(value.baseline.displayed_kg_rank) ?? null,
      tier: value.baseline.tier === 'Strong' || value.baseline.tier === 'Moderate' || value.baseline.tier === 'Preliminary'
        ? value.baseline.tier
        : undefined,
      components: mapBreakdown(value.baseline.components) ?? null,
    };
  }

  const counterfactuals = Array.isArray(value.counterfactuals)
    ? value.counterfactuals.map(mapCounterfactual).filter((item): item is AuditCounterfactual => Boolean(item))
    : undefined;
  const sources = Array.isArray(value.sources)
    ? value.sources.map(mapAuditSource).filter((item): item is AuditSource => Boolean(item))
    : undefined;

  const audit: EvidenceAudit = {
    version: asString(value.version),
    method: asString(value.method),
    scoring_function: asString(value.scoring_function),
    direction_method: asString(value.direction_method),
    status: asString(value.status),
    reason: asString(value.reason),
    note: asString(value.note),
    ranking_scope: asString(value.ranking_scope),
    baseline,
    study_counts: mapStudyCounts(value.study_counts),
    stability: mapStability(value.stability),
    counterfactuals,
    sources,
    warnings: asStringArray(value.warnings),
  };
  return Object.values(audit).some((item) => item !== undefined) ? audit : undefined;
}

function mapCandidateCoverage(value: unknown): CandidateLiteratureCoverage | undefined {
  if (!isRecord(value)) return undefined;
  const coverage: CandidateLiteratureCoverage = {
    status: asString(value.status),
    source_record_count: asFiniteNumber(value.source_record_count) ?? (value.source_record_count === null ? null : undefined),
    distinct_pmid_count: asFiniteNumber(value.distinct_pmid_count) ?? (value.distinct_pmid_count === null ? null : undefined),
    verification_status: typeof value.verification_status === 'string' || value.verification_status === null
      ? value.verification_status
      : undefined,
  };
  return Object.values(coverage).some((item) => item !== undefined) ? coverage : undefined;
}

function mapCandidate(value: unknown): Candidate | undefined {
  if (!isRecord(value)) return undefined;
  const claims = Array.isArray(value.claims)
    ? value.claims.map(mapClaim).filter((claim): claim is Claim => Boolean(claim))
    : undefined;
  const candidate: Candidate = {
    rank: asFiniteNumber(value.rank),
    kg_score: asFiniteNumber(value.kg_score) ?? (value.kg_score === null ? null : undefined),
    drug: asString(value.drug),
    direction: asString(value.direction),
    evidence: mapCandidateEvidence(value.evidence),
    literature_coverage: mapCandidateCoverage(value.literature_coverage),
    reason: asString(value.reason),
    claims,
    evidence_audit: mapEvidenceAudit(value.evidence_audit),
  };
  return Object.values(candidate).some((item) => item !== undefined) ? candidate : undefined;
}

function mapPassage(value: unknown): Passage | undefined {
  if (!isRecord(value)) return undefined;
  const passage: Passage = {
    id: asStringOrNumber(value.id),
    text: asString(value.text),
    source: asString(value.source),
    pmid: typeof value.pmid === 'string' || typeof value.pmid === 'number' ? value.pmid : null,
    year: typeof value.year === 'string' || typeof value.year === 'number' ? value.year : null,
    pub_type: typeof value.pub_type === 'string' ? value.pub_type : null,
    title: typeof value.title === 'string' ? value.title : null,
    source_url: typeof value.source_url === 'string' ? value.source_url : null,
    provenance: typeof value.provenance === 'string' ? value.provenance : null,
    retrieval_score: asFiniteNumber(value.retrieval_score),
    study_weight: asFiniteNumber(value.study_weight),
  };
  return Object.values(passage).some((item) => item !== undefined) ? passage : undefined;
}

function mapKnownIndication(value: unknown): KnownIndication | undefined {
  if (!isRecord(value)) return undefined;
  const indication: KnownIndication = {
    drug_name: asString(value.drug_name),
    drug_id: asString(value.drug_id),
  };
  return Object.values(indication).some((item) => item !== undefined) ? indication : undefined;
}

function mapTimings(value: unknown): TimingBreakdown | undefined {
  if (!isRecord(value)) return undefined;
  const timings: TimingBreakdown = {};
  for (const [key, item] of Object.entries(value)) {
    const numericValue = asFiniteNumber(item);
    if (numericValue !== undefined) timings[key] = numericValue;
  }
  return Object.keys(timings).length > 0 ? timings : undefined;
}

function mapDisease(value: unknown): DiseaseMetadata | undefined {
  if (!isRecord(value)) return undefined;
  const disease: DiseaseMetadata = {
    id: asString(value.id),
    name: asString(value.name),
    synonyms: asString(value.synonyms),
  };
  return Object.values(disease).some((item) => item !== undefined) ? disease : undefined;
}

function mapQueryCoverage(value: unknown): QueryCoverage | undefined {
  if (!isRecord(value)) return undefined;
  const coverage: QueryCoverage = {
    disease_resolution_status: asString(value.disease_resolution_status),
    graph_candidate_status: asString(value.graph_candidate_status),
    literature_status: asString(value.literature_status),
    source_mode: asString(value.source_mode),
    provider: typeof value.provider === 'string' || value.provider === null ? value.provider : undefined,
    retrieval_status: asString(value.retrieval_status),
    retrieved_record_count: asFiniteNumber(value.retrieved_record_count) ?? (value.retrieved_record_count === null ? null : undefined),
    distinct_pmid_count: asFiniteNumber(value.distinct_pmid_count) ?? (value.distinct_pmid_count === null ? null : undefined),
    retrieved_at: typeof value.retrieved_at === 'string' || value.retrieved_at === null ? value.retrieved_at : undefined,
    provider_message: typeof value.provider_message === 'string' || value.provider_message === null ? value.provider_message : undefined,
  };
  return Object.values(coverage).some((item) => item !== undefined) ? coverage : undefined;
}

function mapBenchmarkMethod(value: unknown): RankingBenchmarkMethod | undefined {
  if (!isRecord(value)) return undefined;
  let outcomes: RankingBenchmarkMethod['outcomes'];
  if (isRecord(value.outcomes)) {
    outcomes = {};
    for (const [metric, result] of Object.entries(value.outcomes)) {
      if (typeof result === 'string' || result === null) outcomes[metric] = result;
      else if (asFiniteNumber(result) !== undefined) outcomes[metric] = asFiniteNumber(result)!;
    }
  }
  const method: RankingBenchmarkMethod = {
    name: asString(value.name),
    product_or_model_id: asString(value.product_or_model_id),
    outcomes,
    runtime_ms: asFiniteNumber(value.runtime_ms) ?? (value.runtime_ms === null ? null : undefined),
    failures: asStringArray(value.failures),
    limitations: asStringArray(value.limitations),
  };
  return Object.values(method).some((item) => item !== undefined) ? method : undefined;
}

function mapRankingBenchmark(value: unknown): RankingBenchmark | undefined {
  if (!isRecord(value)) return undefined;
  const methods = Array.isArray(value.methods)
    ? value.methods.map(mapBenchmarkMethod).filter((method): method is RankingBenchmarkMethod => Boolean(method))
    : undefined;
  const benchmark: RankingBenchmark = {
    status: asString(value.status),
    protocol_id: asString(value.protocol_id),
    evaluation_date: asString(value.evaluation_date),
    query_count: asFiniteNumber(value.query_count) ?? (value.query_count === null ? null : undefined),
    trial_count: asFiniteNumber(value.trial_count) ?? (value.trial_count === null ? null : undefined),
    source_access_conditions: asString(value.source_access_conditions),
    evaluation_rubric: asString(value.evaluation_rubric),
    verification_mode: asString(value.verification_mode),
    methods,
  };
  return Object.values(benchmark).some((item) => item !== undefined) ? benchmark : undefined;
}

function mapQueryResponse(value: unknown, originalQuery: string): QueryResponse {
  if (!isRecord(value)) {
    throw new Error('The backend returned a malformed response (expected a JSON object).');
  }
  const reportedStatus = asString(value.status);
  const status: ResponseStatus = reportedStatus === 'ok'
    || reportedStatus === 'unsupported_disease'
    || reportedStatus === 'insufficient_evidence'
    ? reportedStatus
    : 'unknown';

  const results = Array.isArray(value.results)
    ? value.results.map(mapCandidate).filter((candidate): candidate is Candidate => Boolean(candidate))
    : undefined;
  const knownIndications = Array.isArray(value.known_indications)
    ? value.known_indications
        .map(mapKnownIndication)
        .filter((item): item is KnownIndication => Boolean(item))
    : undefined;
  const passages = Array.isArray(value.passages)
    ? value.passages.map(mapPassage).filter((passage): passage is Passage => Boolean(passage))
    : undefined;

  let auditSummary: QueryResponse['evidence_audit_summary'];
  if (isRecord(value.evidence_audit_summary)) {
    auditSummary = {
      version: asString(value.evidence_audit_summary.version),
      method: asString(value.evidence_audit_summary.method),
      scoring_function: asString(value.evidence_audit_summary.scoring_function),
      status: asString(value.evidence_audit_summary.status),
      audited: asFiniteNumber(value.evidence_audit_summary.audited),
      complete: asFiniteNumber(value.evidence_audit_summary.complete),
      not_auditable: asFiniteNumber(value.evidence_audit_summary.not_auditable),
      failed: asFiniteNumber(value.evidence_audit_summary.failed),
      note: asString(value.evidence_audit_summary.note),
    };
  }

  return {
    status,
    reported_status: reportedStatus,
    coverage: mapQueryCoverage(value.coverage),
    ranking_benchmark: mapRankingBenchmark(value.ranking_benchmark),
    query: asString(value.query) ?? originalQuery,
    message: asString(value.message),
    disease: mapDisease(value.disease),
    results,
    known_indications: knownIndications,
    passages,
    timings_ms: mapTimings(value.timings_ms),
    from_cache: typeof value.from_cache === 'boolean' ? value.from_cache : undefined,
    evidence_audit_summary: auditSummary,
  };
}

// Runtime /config.json supports deployments where UI and API have separate hosts.
// VITE_API_BASE_URL is a build-time override; same-origin relative URLs are the default.
let apiBasePromise: Promise<string> | null = null;

function getApiBase(): Promise<string> {
  if (!apiBasePromise) {
    const buildTime = (import.meta.env.VITE_API_BASE_URL || '').trim();
    apiBasePromise = fetch('/config.json', {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(2_500),
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((config: unknown) => {
        const runtime = isRecord(config) && typeof config.apiBase === 'string'
          ? config.apiBase.trim()
          : '';
        return (runtime || buildTime || API_BASE_FALLBACK).replace(/\/+$/, '');
      })
      .catch(() => (buildTime || API_BASE_FALLBACK).replace(/\/+$/, ''));
  }
  return apiBasePromise;
}

let activeQueryController: AbortController | null = null;
let latestRequestId = 0;

async function fetchJson(url: string, options: RequestInit, timeoutMs: number): Promise<unknown> {
  // Callers supply an AbortController for queries (so a newer query can cancel an old one).
  const suppliedSignal = options.signal;
  const timeoutController = new AbortController();
  let didTimeOut = false;
  const timeoutId = window.setTimeout(() => {
    didTimeOut = true;
    timeoutController.abort();
  }, timeoutMs);

  let signal: AbortSignal;
  if (suppliedSignal) {
    signal = AbortSignal.any([suppliedSignal, timeoutController.signal]);
  } else {
    signal = timeoutController.signal;
  }

  try {
    const response = await fetch(url, { ...options, signal });
    if (!response.ok) {
      let detail = `Request failed (${response.status}).`;
      try {
        const payload: unknown = await response.json();
        if (isRecord(payload) && typeof payload.detail === 'string' && payload.detail.trim()) {
          detail = payload.detail;
        } else if (isRecord(payload) && typeof payload.message === 'string' && payload.message.trim()) {
          detail = payload.message;
        }
      } catch {
        // Keep the useful status-based message when the server body is not JSON.
      }
      throw new Error(detail);
    }

    try {
      return await response.json();
    } catch {
      throw new Error('The backend returned malformed JSON. Please retry the query.');
    }
  } catch (error) {
    if (didTimeOut) {
      throw new Error(`The backend request timed out after ${Math.round(timeoutMs / 1000)} seconds. Please retry.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  const base = await getApiBase();
  const data = await fetchJson(
    `${base}/api/health`,
    { headers: { Accept: 'application/json' } },
    HEALTH_TIMEOUT_MS,
  );
  if (!isRecord(data)) {
    throw new Error('The health endpoint returned a malformed response.');
  }

  return {
    status: asString(data.status),
    corpus_size: asFiniteNumber(data.corpus_size),
    disease_count: asFiniteNumber(data.disease_count),
    all_diseases_supported: typeof data.all_diseases_supported === 'boolean'
      ? data.all_diseases_supported
      : undefined,
    supported_diseases: asStringArray(data.supported_diseases),
    data_sources: asStringArray(data.data_sources),
  };
}

export async function queryDisease(
  query: string,
): Promise<{ data: QueryResponse; isLatest: boolean }> {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) throw new Error('Please enter a disease or condition name.');

  activeQueryController?.abort();
  const controller = new AbortController();
  activeQueryController = controller;
  const requestId = ++latestRequestId;

  try {
    const base = await getApiBase();
    const raw = await fetchJson(
      `${base}/api/query`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ query: normalizedQuery }),
        signal: controller.signal,
      },
      QUERY_TIMEOUT_MS,
    );
    return {
      data: mapQueryResponse(raw, normalizedQuery),
      isLatest: requestId === latestRequestId,
    };
  } finally {
    if (activeQueryController === controller) {
      activeQueryController = null;
    }
  }
}
