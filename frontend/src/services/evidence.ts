import { AuditDirectionLabel, AuditSource, Candidate, Claim, Passage } from '../types';

export interface CandidateEvidenceRecord {
  key: string;
  passageId?: string | number;
  pmid?: string;
  title?: string;
  year?: number | string;
  sourceName?: string;
  sourceId?: string;
  publicationTypes: string[];
  relevanceScore?: number;
  studyWeight?: number;
  text?: string;
  quote?: string;
  sourceUrl?: string;
  provenance?: string;
  sourceIdentityStatus?: string;
  quoteVerificationStatus?: string;
  direction?: AuditDirectionLabel | string;
  directionRationale?: string;
  directionSnippet?: string;
  safetySignal?: boolean;
  safetySnippet?: string;
  metadataWarnings: string[];
  studyGroupId?: string;
  includedInAudit?: boolean;
  claims: Claim[];
}

export interface CandidateEvidenceGroup {
  key: string;
  pmid?: string;
  records: CandidateEvidenceRecord[];
}

function normalizePmid(value: string | number | null | undefined): string | undefined {
  if (value === null || value === undefined) return undefined;
  const valueAsString = String(value).trim();
  return /^\d+$/.test(valueAsString) ? valueAsString : undefined;
}

function safeHttpUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? value : undefined;
  } catch {
    return undefined;
  }
}

function pubmedUrl(pmid: string | undefined): string | undefined {
  return pmid ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/` : undefined;
}

function idKey(value: string | number | null | undefined): string | undefined {
  return value === null || value === undefined ? undefined : String(value);
}

function statusForClaims(claims: Claim[], field: 'verification_status'): string | undefined {
  const statuses = [...new Set(claims
    .map((claim) => claim[field])
    .filter((status): status is string => typeof status === 'string' && status.length > 0))];
  if (statuses.length === 1) return statuses[0];
  if (statuses.length > 1) return 'mixed';
  return undefined;
}

function relatedClaims(claims: Claim[], passageId: string | number | null | undefined): Claim[] {
  const expected = idKey(passageId);
  if (expected === undefined) return [];
  return claims.filter((claim) => claim.citations?.some((id) => String(id) === expected));
}

function passageFor(source: AuditSource, passageById: Map<string, Passage>): Passage | undefined {
  const key = idKey(source.passage_id);
  return key === undefined ? undefined : passageById.get(key);
}

function makeRecord(
  source: AuditSource | undefined,
  passage: Passage | undefined,
  claims: Claim[],
  index: number,
): CandidateEvidenceRecord {
  const passageId = source?.passage_id ?? passage?.id;
  const pmid = normalizePmid(source?.pmid ?? passage?.pmid);
  const claimsForPassage = relatedClaims(claims, passageId);
  const quote = source?.quote || claimsForPassage.find((claim) => claim.quote)?.quote;
  const safeSourceUrl = safeHttpUrl(source?.pubmed_url)
    || safeHttpUrl(passage?.source_url)
    || pubmedUrl(pmid);
  const publicationTypes = source?.publication_types?.length
    ? source.publication_types
    : passage?.pub_type
      ? [passage.pub_type]
      : [];

  return {
    key: source?.source_id || (passageId !== undefined ? `passage:${passageId}` : `record:${index}`),
    passageId,
    pmid,
    title: passage?.title || undefined,
    year: source?.publication_year ?? passage?.year ?? undefined,
    sourceName: passage?.source || undefined,
    sourceId: source?.source_id || undefined,
    publicationTypes,
    relevanceScore: passage?.retrieval_score,
    studyWeight: passage?.study_weight,
    text: passage?.text || undefined,
    quote,
    sourceUrl: safeSourceUrl,
    provenance: passage?.provenance || undefined,
    sourceIdentityStatus: source?.source_identity_status || undefined,
    quoteVerificationStatus: source?.quote_verification_status
      || (source?.citation_verified === 'verified' ? 'verified' : source?.citation_verified)
      || statusForClaims(claimsForPassage, 'verification_status'),
    direction: source?.evidence_direction || undefined,
    directionRationale: source?.direction_rationale || undefined,
    directionSnippet: source?.direction_snippet || undefined,
    safetySignal: source?.safety_signal,
    safetySnippet: source?.safety_snippet || undefined,
    metadataWarnings: source?.metadata_warnings || [],
    studyGroupId: source?.study_group_id || undefined,
    includedInAudit: source ? true : undefined,
    claims: claimsForPassage,
  };
}

/**
 * Build a candidate-specific view only from the audit source ledger and claims
 * that cite returned passages. The disease-wide passage array is never treated
 * as candidate evidence on its own.
 */
export function getCandidateEvidenceRecords(
  candidate: Candidate,
  passages: Passage[],
): CandidateEvidenceRecord[] {
  const claims = candidate.claims || [];
  const passageById = new Map<string, Passage>();
  for (const passage of passages) {
    const key = idKey(passage.id);
    if (key !== undefined) passageById.set(key, passage);
  }

  const auditSources = candidate.evidence_audit?.sources || [];
  const records: CandidateEvidenceRecord[] = [];
  const seenPassages = new Set<string>();

  auditSources.forEach((source, index) => {
    const passage = passageFor(source, passageById);
    const key = idKey(source.passage_id ?? passage?.id);
    if (key !== undefined && seenPassages.has(key)) return;
    if (key !== undefined) seenPassages.add(key);
    records.push(makeRecord(source, passage, claims, index));
  });

  // Legacy responses may not contain an audit ledger. Show only passages that
  // are explicitly cited by this candidate's returned claims in that case.
  for (const claim of claims) {
    for (const citationId of claim.citations || []) {
      const key = String(citationId);
      if (seenPassages.has(key)) continue;
      const passage = passageById.get(key);
      if (!passage) continue;
      seenPassages.add(key);
      records.push(makeRecord(undefined, passage, claims, records.length));
    }
  }

  return records;
}

export function groupEvidenceByPublication(records: CandidateEvidenceRecord[]): CandidateEvidenceGroup[] {
  const groups = new Map<string, CandidateEvidenceGroup>();
  records.forEach((record) => {
    const pmid = record.pmid;
    const key = pmid ? `pmid:${pmid}` : `source:${record.key}`;
    const existing = groups.get(key);
    if (existing) {
      existing.records.push(record);
    } else {
      groups.set(key, { key, pmid, records: [record] });
    }
  });
  return [...groups.values()];
}

export function distinctPmidCount(records: CandidateEvidenceRecord[]): number {
  return new Set(records.map((record) => record.pmid).filter(Boolean)).size;
}

export function safeSourceUrl(value: string | null | undefined): string | undefined {
  return safeHttpUrl(value);
}

export function pubmedUrlFor(value: string | number | null | undefined): string | undefined {
  return pubmedUrl(normalizePmid(value));
}
