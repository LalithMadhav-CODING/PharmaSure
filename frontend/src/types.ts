export type EvidenceTier = 'Strong' | 'Moderate' | 'Preliminary';
export type EvidenceDirection = 'Positive' | 'Negative' | 'Mixed' | 'Uncertain';
export type VerificationStatus = 'verified' | 'needs_review';
export type ResponseStatus = 'ok' | 'insufficient_evidence' | 'unsupported_disease';

/* ------------------------------------------------------------------ *
 * Citation-Level Counterfactual Evidence Auditing (CCEA)
 * ------------------------------------------------------------------ */

export type AuditStatus =
  | 'complete'
  | 'partial'
  | 'not_auditable'
  | 'insufficient_independent_studies_for_stability_test'
  | 'audit_failed'
  | 'unavailable_for_cached_result';

/** Direction labels as produced by the backend's rule-based classifier. */
export type AuditDirectionLabel =
  | 'supportive'
  | 'contradictory'
  | 'null_finding'
  | 'uncertain'
  | 'not_classified';

export interface AuditSource {
  source_id: string;
  pmid: string | null;
  pubmed_url: string | null;
  passage_id: string | number | null;
  quote: string | null;
  citation_verified?: string;
  publication_year?: number | null;
  publication_types?: string[];
  evidence_direction: AuditDirectionLabel;
  direction_rationale?: string;
  direction_snippet?: string | null;
  safety_signal?: boolean;
  safety_snippet?: string | null;
  study_group_id?: string | null;
  metadata_warnings?: string[];
}

export interface AuditCounterfactual {
  study_group_id: string;
  pmids: string[];
  passage_ids: (string | number)[];
  removed_passage_count?: number;
  evidence_direction?: AuditDirectionLabel | null;
  publication_year?: number | null;
  publication_types?: string[];
  baseline_score: number;
  baseline_rank: number;
  counterfactual_score: number | null;
  score_delta: number | null;
  counterfactual_rank: number | null;
  rank_delta: number | null;
  status: string;
  error?: string | null;
}

export interface AuditStability {
  status: AuditStatus;
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
    study_group_id: string;
    pmids: string[];
    score_delta: number | null;
    rank_delta: number | null;
  } | null;
  source_with_max_rank_influence?: {
    study_group_id: string;
    pmids: string[];
    score_delta: number | null;
    rank_delta: number | null;
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
  caveat?: string;
}

export interface EvidenceAudit {
  version?: string;
  method?: string;
  scoring_function?: string;
  direction_method?: string;
  status: AuditStatus | string;
  reason?: string;
  note?: string;
  ranking_scope?: string;
  baseline?: {
    evidence_score: number;
    evidence_rank: number;
    displayed_kg_rank: number;
    tier?: EvidenceTier | null;
    components?: CandidateEvidence['breakdown'] | null;
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
  status?: string;
  audited?: number;
  complete?: number;
  not_auditable?: number;
  failed?: number;
  note?: string;
}

export interface Claim {
  text: string;
  citations: (string | number)[];
  quote: string;
  verification_status: VerificationStatus;
  verification_reason?: string;
}

export interface CandidateEvidence {
  score: number;
  tier: EvidenceTier;
  support: number;
  best_study_type: string;
  breakdown?: {
    relevance: number;
    relevance_weight: number;
    support: number;
    support_weight: number;
    study_quality: number;
    study_quality_weight: number;
  };
}

export interface Candidate {
  rank: number;
  drug: string;
  direction: EvidenceDirection;
  evidence: CandidateEvidence;
  reason: string;
  claims: Claim[];
  /** Citation-level counterfactual audit. Absent on legacy cached responses. */
  evidence_audit?: EvidenceAudit;
}

export interface Passage {
  id: string | number;
  text: string;
  source: string;
  pmid?: string | number | null;
  year?: number | string | null;
  pub_type?: string | null;
}

export interface KnownIndication {
  drug_name: string;
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
  id: string;
  name: string;
  synonyms?: string;
}

export interface QueryResponse {
  status: ResponseStatus;
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
  status: string;
  corpus_size: number;
  supported_diseases: string[];
  data_sources?: string[];
}
