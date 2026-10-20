import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  ExternalLink,
  FileText,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { Candidate } from '../types';
import {
  CandidateEvidenceRecord,
  distinctPmidCount,
  groupEvidenceByPublication,
  safeSourceUrl,
} from '../services/evidence';

interface EvidenceExplorerProps {
  candidate: Candidate;
  records: CandidateEvidenceRecord[];
  onOpenCitation: (citationId: string | number, relatedQuote?: string, sourceUrl?: string) => void;
}

const DIRECTION_LABELS: Record<string, string> = {
  supportive: 'Supportive',
  contradictory: 'Contradictory',
  null_finding: 'Null finding',
  uncertain: 'Uncertain / mixed',
  not_classified: 'Not classified',
};

const DIRECTION_TONES: Record<string, string> = {
  supportive: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  contradictory: 'border-rose-200 bg-rose-50 text-rose-800',
  null_finding: 'border-sky-200 bg-sky-50 text-sky-800',
  uncertain: 'border-amber-200 bg-amber-50 text-amber-900',
  not_classified: 'border-slate-200 bg-slate-100 text-slate-700',
};

function verificationLabel(value: string | undefined): { label: string; tone: string } {
  if (value === 'verified') return { label: 'Verified', tone: 'border-emerald-200 bg-emerald-50 text-emerald-800' };
  if (value === 'needs_review') return { label: 'Needs review', tone: 'border-amber-200 bg-amber-50 text-amber-900' };
  if (value === 'not_cited') return { label: 'Not cited', tone: 'border-slate-200 bg-slate-50 text-slate-600' };
  if (value === 'mixed') return { label: 'Mixed claim statuses', tone: 'border-amber-200 bg-amber-50 text-amber-900' };
  return { label: 'Not reported separately', tone: 'border-slate-200 bg-slate-50 text-slate-600' };
}

function EvidenceRecord({
  record,
  onOpenCitation,
}: {
  record: CandidateEvidenceRecord;
  onOpenCitation: EvidenceExplorerProps['onOpenCitation'];
}) {
  const sourceIdentity = verificationLabel(record.sourceIdentityStatus);
  const quoteVerification = verificationLabel(record.quoteVerificationStatus);
  const externalUrl = safeSourceUrl(record.sourceUrl);
  const title = record.title || (record.pmid ? `PMID ${record.pmid}` : 'Publication title not returned');
  const direction = record.direction ? DIRECTION_LABELS[record.direction] : undefined;
  const directionTone = record.direction ? DIRECTION_TONES[record.direction] : undefined;

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h4 className="break-words text-sm font-semibold leading-5 text-slate-900">{title}</h4>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-slate-500">
            {record.pmid && <span className="font-mono">PMID {record.pmid}</span>}
            {record.year !== undefined && record.year !== null && <span>{record.year}</span>}
            {record.sourceName && <span>{record.sourceName}</span>}
            {record.publicationTypes.length > 0 && <span>{record.publicationTypes.join(', ').replace(/_/g, ' ')}</span>}
            {record.relevanceScore !== undefined && <span>Retrieval relevance: <span className="font-mono">{record.relevanceScore.toFixed(3)}</span></span>}
            {record.studyWeight !== undefined && <span>Study-type weight: <span className="font-mono">{record.studyWeight.toFixed(3)}</span></span>}
            {record.sourceId && <span className="font-mono">Source ID: {record.sourceId}</span>}
            {record.provenance && <span>Provenance: {record.provenance}</span>}
          </div>
        </div>
        {externalUrl && (
          <a
            href={externalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-teal-800 hover:border-teal-700 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
          >
            <span>Open source</span>
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        )}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Source identity</p>
          <span className={`mt-1 inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${sourceIdentity.tone}`}>
            {sourceIdentity.label}
          </span>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Quotation matching</p>
          <span className={`mt-1 inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${quoteVerification.tone}`}>
            {quoteVerification.label}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-700">
          {record.includedInAudit ? <ShieldCheck className="h-3.5 w-3.5 text-teal-700" aria-hidden="true" /> : <FileText className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />}
          {record.includedInAudit ? 'Candidate-specific audit record' : 'Passage linked by candidate claim'}
        </span>
        {direction && (
          <span className={`rounded-full border px-2.5 py-1 font-medium ${directionTone || DIRECTION_TONES.not_classified}`}>
            Rule-based direction: {direction}
          </span>
        )}
        {record.safetySignal && (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 font-medium text-amber-900">
            <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
            Safety signal (separate from efficacy direction)
          </span>
        )}
      </div>

      {record.claims.length > 0 && (
        <div className="mt-4 space-y-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Candidate claim(s) linked to this passage</p>
          {record.claims.map((claim, index) => {
            const claimStatus = verificationLabel(typeof claim.verification_status === 'string' ? claim.verification_status : undefined);
            return (
              <div key={`${record.key}-claim-${index}`} className="rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                {claim.text && <p className="text-xs leading-5 text-slate-800">{claim.text}</p>}
                <span className={`mt-2 inline-flex rounded border px-2 py-0.5 text-[10px] font-medium ${claimStatus.tone}`}>
                  Claim verification: {claimStatus.label}
                </span>
                {claim.verification_reason && <p className="mt-1 text-[11px] text-slate-600">{claim.verification_reason}</p>}
              </div>
            );
          })}
        </div>
      )}

      {record.quote ? (
        <div className="mt-4 rounded-lg border-l-2 border-teal-700 bg-teal-50/50 px-3.5 py-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-teal-900">Exact returned quotation</p>
          <blockquote className="text-xs leading-5 text-slate-800">“{record.quote}”</blockquote>
        </div>
      ) : record.text ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Returned source passage (no separate quotation supplied)</p>
          <p className="whitespace-pre-wrap text-xs leading-5 text-slate-700">{record.text}</p>
        </div>
      ) : (
        <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          The response links this source record to the candidate but does not include passage text or a quotation.
        </p>
      )}

      {record.directionSnippet && (
        <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-700">
          <span className="font-semibold">Classifier snippet:</span> {record.directionSnippet}
        </p>
      )}
      {record.safetySnippet && (
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
          <span className="font-semibold">Safety snippet:</span> {record.safetySnippet}
        </p>
      )}
      {record.metadataWarnings.length > 0 && (
        <p className="mt-2 text-[11px] text-amber-800">Metadata notes: {record.metadataWarnings.join(', ').replace(/_/g, ' ')}</p>
      )}

      {record.passageId !== undefined && (
        <button
          type="button"
          onClick={() => onOpenCitation(record.passageId!, record.quote, record.sourceUrl)}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-teal-800 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
          Inspect full returned passage [{record.passageId}]
        </button>
      )}
    </article>
  );
}

export const EvidenceExplorer: React.FC<EvidenceExplorerProps> = ({
  candidate,
  records,
  onOpenCitation,
}) => {
  const [filter, setFilter] = useState('all');
  const groups = useMemo(() => groupEvidenceByPublication(records), [records]);
  const distinctPmids = distinctPmidCount(records);
  const availableDirections = useMemo(
    () => [...new Set(records.map((record) => record.direction).filter((direction): direction is string => Boolean(direction && DIRECTION_LABELS[direction])))],
    [records],
  );

  useEffect(() => setFilter('all'), [candidate]);

  const filteredGroups = groups
    .map((group) => ({
      ...group,
      records: filter === 'all' ? group.records : group.records.filter((record) => record.direction === filter),
    }))
    .filter((group) => group.records.length > 0);

  const score = candidate.evidence?.score;
  const rank = candidate.rank;
  const candidateName = candidate.drug?.trim() || 'Candidate name unavailable';
  const studyCounts = candidate.evidence_audit?.study_counts;
  const independenceStatus = studyCounts?.study_independence_verified === false
    ? 'Not established'
    : studyCounts?.study_independence_verified === true
      ? 'Reported as verified'
      : 'Not reported';

  return (
    <section id="evidence-explorer" aria-labelledby="evidence-explorer-heading" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-teal-800">Candidate-specific source review</p>
            <h2 id="evidence-explorer-heading" className="mt-1 text-lg font-semibold text-slate-950">Evidence Explorer</h2>
            <p className="mt-1 text-xs text-slate-600">Inspect only records linked to the selected candidate by the audit ledger or its returned citations.</p>
          </div>
          <span className="w-fit rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-600">
            KG rank {rank === undefined ? 'not returned' : `#${rank}`}{typeof candidate.kg_score === 'number' ? ` · score ${candidate.kg_score.toFixed(3)}` : ''}
          </span>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Selected hypothesis</p>
            <p className="mt-1 truncate text-sm font-semibold text-slate-900" title={candidateName}>{candidateName}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Literature evidence score</p>
            <p className="mt-1 font-mono text-sm font-semibold text-slate-900">{score === undefined ? 'Not returned' : score.toFixed(3)}</p>
            <p className="text-[10px] text-slate-500">Backend heuristic; not probability of efficacy</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Candidate-linked sources</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{records.length} record{records.length === 1 ? '' : 's'} · {distinctPmids} distinct PMID{distinctPmids === 1 ? '' : 's'}</p>
            <p className="text-[10px] text-slate-500">PMID groups are publications, not confirmed independent experiments</p>
          </div>
        </div>

        <p className="mt-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-[10px] leading-4 text-slate-600">
          Duplicate records removed: {studyCounts?.duplicate_records_removed ?? 'Not reported'} · Potentially overlapping studies: {studyCounts?.potentially_overlapping_studies ?? 'Not reported'} · Study independence: {independenceStatus}
        </p>

        {candidate.reason && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Backend-returned rationale</p>
            <p className="mt-1 text-xs leading-5 text-slate-700">{candidate.reason}</p>
          </div>
        )}
        {candidate.evidence?.breakdown && (
          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-600">
              {candidate.evidence.breakdown.relevance !== undefined && <span>Relevance component: <strong className="font-mono text-slate-900">{candidate.evidence.breakdown.relevance.toFixed(3)}</strong></span>}
              {candidate.evidence.breakdown.support !== undefined && <span>Passage-support component: <strong className="font-mono text-slate-900">{candidate.evidence.breakdown.support.toFixed(3)}</strong></span>}
              {candidate.evidence.breakdown.study_quality !== undefined && <span>Study-type component: <strong className="font-mono text-slate-900">{candidate.evidence.breakdown.study_quality.toFixed(3)}</strong></span>}
              {candidate.evidence.best_study_type && <span>Highest-weighted study type: <strong className="text-slate-900">{candidate.evidence.best_study_type.replace(/_/g, ' ')}</strong></span>}
            </div>
            <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
              {candidate.evidence.breakdown.relevance_weight !== undefined && candidate.evidence.breakdown.support_weight !== undefined && candidate.evidence.breakdown.study_quality_weight !== undefined
                ? `Returned weighting: relevance × ${candidate.evidence.breakdown.relevance_weight} + support × ${candidate.evidence.breakdown.support_weight} + study type × ${candidate.evidence.breakdown.study_quality_weight}. `
                : ''}
              The support component is based on passages in the current scorer, not distinct PMIDs; the score is not an efficacy probability.
            </p>
          </div>
        )}
      </div>

      <div className="px-4 py-4 sm:px-5">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Sources grouped by publication</h3>
            <p className="mt-0.5 text-[11px] text-slate-500">Repeated passages with the same PMID are kept together. Cross-PMID independence is not established.</p>
          </div>
          {availableDirections.length > 0 && (
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <span className="font-medium">Filter findings</span>
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                className="min-h-9 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
              >
                <option value="all">All returned classifications</option>
                {availableDirections.map((direction) => (
                  <option key={direction} value={direction}>{DIRECTION_LABELS[direction]}</option>
                ))}
              </select>
            </label>
          )}
        </div>

        {records.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
            <FileText className="mx-auto h-7 w-7 text-slate-400" aria-hidden="true" />
            <h3 className="mt-2 text-sm font-semibold text-slate-800">No candidate-linked evidence records returned</h3>
            <p className="mx-auto mt-1 max-w-xl text-xs leading-5 text-slate-600">
              The response may contain disease-level passages, but none are linked to this candidate by the returned audit ledger or citation IDs. The API does not report disease-level corpus coverage, so this is not proof that no relevant literature exists.
            </p>
          </div>
        ) : filteredGroups.length === 0 ? (
          <p className="rounded-lg bg-slate-50 p-4 text-xs text-slate-600">No source records match this backend-provided finding classification.</p>
        ) : (
          <div className="space-y-4">
            {filteredGroups.map((group) => (
              <section key={group.key} aria-label={group.pmid ? `Publication PMID ${group.pmid}` : 'Source without PMID'}>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 font-mono text-[11px] font-semibold text-slate-700">
                    {group.pmid ? `PMID ${group.pmid}` : 'No stable PMID returned'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {group.records.length} passage record{group.records.length === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="space-y-2.5">
                  {group.records.map((record) => (
                    <EvidenceRecord key={record.key} record={record} onOpenCitation={onOpenCitation} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-[11px] leading-5 text-amber-950">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>
            <strong>Interpretation boundary.</strong> Source identity verification checks the record reference; quotation verification checks returned text. Neither establishes candidate relevance beyond the backend's matching, validates the study interpretation, or proves clinical efficacy or safety.
            {availableDirections.length > 0 && ' Direction labels are rule-based backend outputs and are not expert-adjudicated.'}
          </p>
        </div>
      </div>
    </section>
  );
};
