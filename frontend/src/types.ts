export type EvidenceTier = 'Strong' | 'Moderate' | 'Preliminary';
export type EvidenceDirection = 'Positive' | 'Negative' | 'Mixed' | 'Uncertain';
export type VerificationStatus = 'verified' | 'needs_review';
export type ResponseStatus = 'ok' | 'insufficient_evidence' | 'unsupported_disease';

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
}

export interface Candidate {
  rank: number;
  drug: string;
  direction: EvidenceDirection;
  evidence: CandidateEvidence;
  reason: string;
  claims: Claim[];
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
}

export interface HealthResponse {
  status: string;
  corpus_size: number;
  supported_diseases: string[];
  data_sources?: string[];
}
