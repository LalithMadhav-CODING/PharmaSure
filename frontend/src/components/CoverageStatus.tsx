import React from 'react';
import { Activity, BookOpenCheck, CircleHelp, Database, FlaskConical, LibraryBig } from 'lucide-react';
import { Candidate, HealthResponse, QueryResponse } from '../types';

interface CoverageStatusProps {
  response: QueryResponse;
  selectedCandidate?: Candidate;
  selectedRecordCount: number;
  distinctPmids: number;
  health: HealthResponse | null;
}

function resolutionLabel(response: QueryResponse): { title: string; detail: string; tone: string } {
  const reported = response.coverage?.disease_resolution_status;
  if (reported === 'unresolved') {
    return { title: 'Disease unresolved', detail: response.message || 'The backend reports that this query did not resolve to a disease.', tone: 'text-amber-900 bg-amber-50 border-amber-200' };
  }
  if (reported === 'resolved') {
    return { title: 'Disease resolved', detail: response.disease?.name || 'Resolved entity name not returned.', tone: 'text-teal-900 bg-teal-50 border-teal-200' };
  }
  if (response.status === 'unsupported_disease') {
    return { title: 'Disease not resolved / supported', detail: response.message || 'The backend did not return a resolved disease entity.', tone: 'text-amber-900 bg-amber-50 border-amber-200' };
  }
  if (response.disease?.name && response.disease.id !== 'INSUFFICIENT') {
    return { title: 'Disease resolved', detail: response.disease.name, tone: 'text-teal-900 bg-teal-50 border-teal-200' };
  }
  return { title: 'Resolution not reported', detail: 'The response did not include a resolved disease entity.', tone: 'text-slate-700 bg-slate-50 border-slate-200' };
}

function graphState(response: QueryResponse): { title: string; detail: string } {
  const reported = response.coverage?.graph_candidate_status;
  if (reported === 'available') {
    return { title: Array.isArray(response.results) ? `${response.results.length} graph candidate${response.results.length === 1 ? '' : 's'} returned` : 'Candidates available; list not returned', detail: 'Knowledge-graph hypotheses; not treatment recommendations.' };
  }
  if (reported === 'none') return { title: 'No graph candidates returned', detail: 'The backend explicitly reports no candidates for this query.' };
  if (reported === 'unavailable') return { title: 'Candidate generation unavailable', detail: 'The backend reports that candidate generation could not be completed.' };
  if (response.status === 'unsupported_disease') return { title: 'Candidate generation not assessed', detail: 'The disease was not resolved; graph coverage cannot be inferred.' };
  if (response.status === 'insufficient_evidence') return { title: 'No candidate records returned', detail: 'The backend abstained; the cause is not specified by the current response.' };
  if (!Array.isArray(response.results)) return { title: 'Candidate list not returned', detail: 'Candidate coverage cannot be inferred from a missing field.' };
  if (response.results.length === 0) return { title: 'No graph candidates returned', detail: 'This is the candidate list returned for the resolved query.' };
  return { title: `${response.results.length} graph candidate${response.results.length === 1 ? '' : 's'} returned`, detail: 'Knowledge-graph hypotheses; not treatment recommendations.' };
}

function statusText(value: string | undefined): string {
  return value ? value.replace(/_/g, ' ') : 'Not reported';
}

function literatureText(response: QueryResponse): { title: string; detail: string } {
  const value = response.coverage?.literature_status;
  const labels: Record<string, string> = {
    available: 'Literature records available',
    none: 'No local literature records reported',
    insufficient: 'Literature evidence insufficient',
    unavailable: 'Literature coverage unavailable',
    unknown: 'Coverage unknown',
  };
  return {
    title: value ? labels[value] || statusText(value) : 'Per-disease coverage not reported',
    detail: value ? 'Disease-level literature status as reported by the query API.' : 'Returned passages alone do not establish disease-level local corpus coverage.',
  };
}

function sourceModeText(response: QueryResponse): string {
  switch (response.coverage?.source_mode) {
    case 'local': return 'Local corpus';
    case 'live': return 'Live retrieval';
    case 'mixed': return 'Mixed local + live';
    case 'unknown': return 'Source mode unknown';
    default: return 'Source mode not reported';
  }
}

export const CoverageStatus: React.FC<CoverageStatusProps> = ({
  response,
  selectedCandidate,
  selectedRecordCount,
  distinctPmids,
  health,
}) => {
  const resolution = resolutionLabel(response);
  const graph = graphState(response);
  const literature = literatureText(response);
  const candidateCoverage = selectedCandidate?.literature_coverage;
  const reportedCandidateRecords = candidateCoverage?.source_record_count;
  const candidateEvidenceTitle = (() => {
    if (!selectedCandidate) return 'No candidate selected';
    if (selectedRecordCount > 0) return `${selectedRecordCount} linked source record${selectedRecordCount === 1 ? '' : 's'}`;
    if (reportedCandidateRecords !== null && reportedCandidateRecords !== undefined) {
      return `${reportedCandidateRecords} source record${reportedCandidateRecords === 1 ? '' : 's'} reported`;
    }
    if (candidateCoverage?.status === 'none') return 'Backend reports no linked records';
    if (candidateCoverage?.status === 'insufficient') return 'Candidate evidence insufficient';
    if (candidateCoverage?.status === 'available') return 'Candidate evidence reported available';
    return 'No candidate-linked citation records';
  })();
  const candidateEvidenceDetail = (() => {
    if (!selectedCandidate) return 'Select a returned candidate to inspect its evidence.';
    if (selectedRecordCount > 0) {
      const caveat = candidateCoverage?.status === 'none' ? ' The coverage field conflicts with returned candidate evidence.' : '';
      return `${distinctPmids} distinct PMID${distinctPmids === 1 ? '' : 's'} among the returned candidate evidence records.${caveat}`;
    }
    if (reportedCandidateRecords !== null && reportedCandidateRecords !== undefined && reportedCandidateRecords > 0) {
      return 'The backend reports candidate-linked records, but their passage details were not included in this response.';
    }
    if (candidateCoverage?.status === 'none') return 'No candidate-specific records are reported. This does not establish that no relevant literature exists.';
    if (candidateCoverage?.status === 'available') return 'The backend reports evidence available, but no linked passage details were included in this response.';
    return 'No citation-linked passage was returned for this candidate. This does not establish that no literature exists.';
  })();

  const retrievalStatus = response.coverage?.retrieval_status;
  const retrievalError = ['rate_limited', 'timeout', 'unavailable', 'failed'].includes(retrievalStatus || '');
  const configuredSources = health?.data_sources ?? [];
  const sourceDetail = [
    response.coverage?.provider ? `Provider: ${response.coverage.provider}` : undefined,
    retrievalStatus ? `Retrieval: ${statusText(retrievalStatus)}` : undefined,
    response.coverage?.retrieved_record_count !== null && response.coverage?.retrieved_record_count !== undefined
      ? `${response.coverage.retrieved_record_count} retrieved records`
      : undefined,
    response.coverage?.distinct_pmid_count !== null && response.coverage?.distinct_pmid_count !== undefined
      ? `${response.coverage.distinct_pmid_count} distinct PMIDs`
      : undefined,
    response.coverage?.retrieved_at ? `Retrieved at ${response.coverage.retrieved_at}` : undefined,
  ].filter(Boolean).join(' · ');

  return (
    <section aria-labelledby="coverage-heading" className="coverage-panel rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="coverage-heading" className="text-sm font-semibold text-slate-900">Coverage &amp; source status</h2>
          <p className="mt-0.5 text-xs text-slate-500">Graph candidates and candidate-linked literature are displayed separately; per-disease corpus coverage is not currently reported.</p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-medium text-slate-600">
          <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
          {response.from_cache === true ? 'Cached result' : response.from_cache === false ? 'Backend request' : 'Query origin not reported'}
        </span>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
        <div className={`min-w-0 rounded-xl border p-3 ${resolution.tone}`}>
          <div className="flex items-center gap-2 text-[11px] font-semibold"><Activity className="h-4 w-4 shrink-0" aria-hidden="true" />Disease resolution</div>
          <p className="mt-1.5 text-sm font-semibold leading-5">{resolution.title}</p>
          <p className="mt-1 break-words text-[11px] leading-4 opacity-80">{resolution.detail}</p>
        </div>

        <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-600"><FlaskConical className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />Knowledge graph</div>
          <p className="mt-1.5 text-sm font-semibold leading-5 text-slate-900">{graph.title}</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-600">{graph.detail}</p>
        </div>

        <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-600"><LibraryBig className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />Disease literature</div>
          <p className="mt-1.5 text-sm font-semibold leading-5 text-slate-900">{literature.title}</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-600">{literature.detail}</p>
        </div>

        <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-600"><BookOpenCheck className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />Selected candidate</div>
          <p className="mt-1.5 text-sm font-semibold leading-5 text-slate-900">{candidateEvidenceTitle}</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-600">{candidateEvidenceDetail}</p>
          {candidateCoverage?.verification_status && <p className="mt-1 text-[10px] text-slate-500">Verification status: {candidateCoverage.verification_status}</p>}
        </div>

        <div className={`min-w-0 rounded-xl border p-3 ${retrievalError ? 'border-amber-200 bg-amber-50/60' : 'border-slate-200 bg-slate-50'}`}>
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-600"><Database className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />Source / retrieval</div>
          <p className="mt-1.5 text-sm font-semibold leading-5 text-slate-900">{sourceModeText(response)}</p>
          <p className="mt-1 text-[11px] leading-4 text-slate-600">{sourceDetail || (response.coverage ? 'No additional retrieval metadata returned.' : 'Live-provider status is not included in this query response.')}</p>
          {response.coverage?.provider_message && <p className="mt-1 text-[10px] leading-4 text-amber-950">{response.coverage.provider_message}</p>}
          {!response.coverage && configuredSources.length > 0 && <p className="mt-1 text-[10px] leading-4 text-slate-500">Configured sources (health endpoint): {configuredSources.join('; ')}</p>}
        </div>
      </div>
    </section>
  );
};
