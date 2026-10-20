export type EvidenceTier = 'Strong' | 'Moderate' | 'Preliminary';
export type VerificationStatus = 'verified' | 'needs_review';
export type ResponseStatus = 'ok' | 'insufficient_evidence' | 'unsupported_disease' | 'unknown';

/** Direction labels currently emitted by the candidate generator. */
export type CandidateDirection = 'Positive' | 'Negative' | 'Mixed' | 'Uncertain';

/** Direction labels from the audit's rule-based source classifier. */
export type AuditDirectionLabel =
  | 'supportive'
  | 'contradictory'
  | 'null_finding'
  | 'uncertain'
  | 'not_classified';

export interface EvidenceBreakdown {
  relevance?: number;
  relevance_weight?: number;
  support?: number;
  support_weight?: number;
  study_quality?: number;
  study_quality_weight?: number;
}

export interface CandidateEvidence {
  /** Heuristic evidence score on the backend's own scale; not a probability. */
  score?: number;
  tier?: EvidenceTier;
  /** In this API version this score component counts retrieved passages, not studies. */
  support?: number;
  best_study_type?: string;
  breakdown?: EvidenceBreakdown;
}

export interface Claim {
  text?: string;
  citations?: (string | number)[];
  quote?: string;
  verification_status?: VerificationStatus | string;
  verification_reason?: string;
}

export type AuditStatus =
  | 'complete'
  | 'partial'
  | 'not_auditable'
  | 'insufficient_independent_studies_for_stability_test'
  | 'audit_failed'
  | 'unavailable_for_cached_result';

export interface AuditSource {
  source_id?: string;
  pmid?: string | null;
  pubmed_url?: string | null;
  passage_id?: string | number | null;
  quote?: string | null;
  citation_verified?: string;
  source_identity_status?: string;
  quote_verification_status?: string;
  publication_year?: number | null;
  publication_types?: string[];
  evidence_direction?: AuditDirectionLabel | string;
  direction_rationale?: string;
  direction_snippet?: string | null;
  safety_signal?: boolean;
  safety_snippet?: string | null;
  study_group_id?: string | null;
  metadata_warnings?: string[];
}

export interface AuditCounterfactual {
  study_group_id?: string;
  pmids?: string[];
  passage_ids?: (string | number)[];
  removed_passage_count?: number;
  evidence_direction?: AuditDirectionLabel | string | null;
  publication_year?: number | null;
  publication_types?: string[];
  baseline_score?: number | null;
  baseline_rank?: number | null;
  counterfactual_score?: number | null;
  score_delta?: number | null;
  counterfactual_rank?: number | null;
  rank_delta?: number | null;
  status?: string;
  error?: string | null;
}

export interface AuditStability {
  status?: AuditStatus | string;
  successful_counterfactuals?: number;
  failed_counterfactuals?: number;
  max_absolute_score_change?: number | null;
  mean_absolute_score_change?: number | null;
  median_absolute_score_change?: number | null;
  max_rank_movement?: number | null;
  rank_min?: number | null;
  rank_max?: number | null;
  rank_range?: number | null;
  single_source_dominated?: boolean;
  source_with_max_score_influence?: {
    study_group_id?: string;
    pmids?: string[];
    score_delta?: number | null;
    rank_delta?: number | null;
  } | null;
  source_with_max_rank_influence?: {
    study_group_id?: string;
    pmids?: string[];
    score_delta?: number | null;
    rank_delta?: number | null;
  } | null;
}

export interface AuditStudyCounts {
  eligible_independent_studies?: number;
  study_units?: number;
  source_records?: number;
  study_independence_verified?: boolean;
  supportive?: number;
  contradictory?: number;
  null_finding?: number;
  uncertain?: number;
  not_classified?: number;
  classified?: number;
  unclassified?: number;
  classified_fraction?: number | null;
  conflicting_evidence_present?: boolean;
  duplicate_records_removed?: number;
  potentially_overlapping_studies?: number;
  caveat?: string;
}

export interface EvidenceAudit {
  version?: string;
  method?: string;
  scoring_function?: string;
  direction_method?: string;
  status?: AuditStatus | string;
  reason?: string;
  note?: string;
  ranking_scope?: string;
  baseline?: {
    evidence_score?: number | null;
    evidence_rank?: number | null;
    displayed_kg_rank?: number | null;
    tier?: EvidenceTier | null;
    components?: EvidenceBreakdown | null;
  };
  study_counts?: AuditStudyCounts;
  stability?: AuditStability;
  counterfactuals?: AuditCounterfactual[];
  sources?: AuditSource[];
  warnings?: string[];
}

export interface AuditSummary {
  version?: string;
  method?: string;
  scoring_function?: string;
  status?: string;
  audited?: number;
  complete?: number;
  not_auditable?: number;
  failed?: number;
  note?: string;
}

export interface CandidateLiteratureCoverage {
  status?: string;
  source_record_count?: number | null;
  distinct_pmid_count?: number | null;
  verification_status?: string | null;
}

export interface Candidate {
  /** `rank` is the knowledge-graph display order in the current API. */
  rank?: number;
  /** Optional numeric KG value; absent in the current pipeline response. */
  kg_score?: number | null;
  drug?: string;
  direction?: CandidateDirection | string;
  evidence?: CandidateEvidence;
  literature_coverage?: CandidateLiteratureCoverage;
  reason?: string;
  claims?: Claim[];
  evidence_audit?: EvidenceAudit;
}

export interface Passage {
  id?: string | number;
  text?: string;
  source?: string;
  pmid?: string | number | null;
  year?: number | string | null;
  pub_type?: string | null;
  title?: string | null;
  source_url?: string | null;
  provenance?: string | null;
  retrieval_score?: number;
  study_weight?: number;
}

export interface KnownIndication {
  drug_name?: string;
  drug_id?: string;
}

export interface TimingBreakdown {
  resolve?: number;
  embed?: number;
  retrieve?: number;
  generate?: number;
  verify?: number;
  total_ms?: number;
  cache_hit?: number;
  [key: string]: number | undefined;
}

export interface DiseaseMetadata {
  id?: string;
  name?: string;
  synonyms?: string;
}

export interface QueryCoverage {
  disease_resolution_status?: string;
  graph_candidate_status?: string;
  literature_status?: string;
  source_mode?: string;
  provider?: string | null;
  retrieval_status?: string;
  retrieved_record_count?: number | null;
  distinct_pmid_count?: number | null;
  retrieved_at?: string | null;
  provider_message?: string | null;
}

export interface RankingBenchmarkMethod {
  name?: string;
  product_or_model_id?: string;
  outcomes?: Record<string, number | string | null>;
  runtime_ms?: number | null;
  failures?: string[];
  limitations?: string[];
}

export interface RankingBenchmark {
  status?: string;
  protocol_id?: string;
  evaluation_date?: string;
  query_count?: number | null;
  trial_count?: number | null;
  source_access_conditions?: string;
  evaluation_rubric?: string;
  verification_mode?: string;
  methods?: RankingBenchmarkMethod[];
}

export interface QueryResponse {
  status: ResponseStatus;
  reported_status?: string;
  coverage?: QueryCoverage;
  ranking_benchmark?: RankingBenchmark;
  query?: string;
  message?: string;
  disease?: DiseaseMetadata;
  results?: Candidate[];
  known_indications?: KnownIndication[];
  passages?: Passage[];
  timings_ms?: TimingBreakdown;
  from_cache?: boolean;
  evidence_audit_summary?: AuditSummary;
}

export interface HealthResponse {
  status?: string;
  corpus_size?: number;
  disease_count?: number;
  all_diseases_supported?: boolean;
  supported_diseases?: string[];
  data_sources?: string[];
}
