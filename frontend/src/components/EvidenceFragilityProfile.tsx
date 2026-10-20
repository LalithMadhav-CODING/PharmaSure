import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, ExternalLink, FileSearch } from 'lucide-react';
import { AuditCounterfactual, AuditSource, AuditSummary, EvidenceAudit } from '../types';
import { safeSourceUrl } from '../services/evidence';

interface EvidenceFragilityProfileProps {
  candidateName: string;
  audit?: EvidenceAudit;
  auditSummary?: AuditSummary;
  onOpenCitation: (citationId: string | number, relatedQuote?: string, sourceUrl?: string) => void;
}

function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toFixed(3);
}

function formatSignedScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}`;
}

function formatSignedInteger(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return `${value > 0 ? '+' : ''}${value}`;
}

function statusPresentation(status: string | undefined): { label: string; tone: string; explanation: string } {
  switch (status) {
    case 'complete':
      return { label: 'Audit complete', tone: 'border-emerald-200 bg-emerald-50 text-emerald-900', explanation: 'All reported leave-one-study-out scenarios completed.' };
    case 'partial':
      return { label: 'Partial audit', tone: 'border-amber-200 bg-amber-50 text-amber-950', explanation: 'Some scenarios could not be calculated; inspect each row status.' };
    case 'not_auditable':
      return { label: 'Not auditable', tone: 'border-slate-200 bg-slate-100 text-slate-800', explanation: 'The backend did not have source records sufficient to run this audit.' };
    case 'insufficient_independent_studies_for_stability_test':
      return { label: 'Insufficient study units', tone: 'border-amber-200 bg-amber-50 text-amber-950', explanation: 'The returned evidence set does not support a meaningful stability test.' };
    case 'audit_failed':
      return { label: 'Audit failed', tone: 'border-rose-200 bg-rose-50 text-rose-900', explanation: 'The audit computation failed; no robustness conclusion should be drawn.' };
    case 'unavailable_for_cached_result':
      return { label: 'Unavailable for cached result', tone: 'border-slate-200 bg-slate-100 text-slate-800', explanation: 'This cached result does not include a current audit payload.' };
    default:
      return { label: status ? `Status: ${status}` : 'Audit status not reported', tone: 'border-slate-200 bg-slate-100 text-slate-800', explanation: 'The response does not provide a recognized audit status.' };
  }
}

function idForCounterfactual(counterfactual: AuditCounterfactual, index: number): string {
  return counterfactual.study_group_id || `${(counterfactual.pmids || []).join(',') || 'no-pmid'}-${index}`;
}

function sourceMatchesCounterfactual(source: AuditSource, counterfactual: AuditCounterfactual): boolean {
  if (counterfactual.study_group_id && source.study_group_id === counterfactual.study_group_id) return true;
  if (source.pmid && counterfactual.pmids?.includes(source.pmid)) return true;
  if (source.passage_id !== null && source.passage_id !== undefined) {
    return counterfactual.passage_ids?.some((id) => String(id) === String(source.passage_id)) ?? false;
  }
  return false;
}

function sourceLabel(counterfactual: AuditCounterfactual): string {
  const pmids = counterfactual.pmids?.filter(Boolean) || [];
  if (pmids.length > 0) return pmids.map((pmid) => `PMID ${pmid}`).join(', ');
  return counterfactual.study_group_id || 'Source identifier not returned';
}

function MostInfluential({
  label,
  counterfactual,
  metric,
}: {
  label: string;
  counterfactual?: AuditCounterfactual;
  metric: 'score' | 'rank';
}) {
  if (!counterfactual) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-xs text-slate-600">No measured value returned</p>
      </div>
    );
  }
  const delta = metric === 'score' ? counterfactual.score_delta : counterfactual.rank_delta;
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 break-words text-xs font-semibold text-slate-900">{sourceLabel(counterfactual)}</p>
      <p className="mt-1 font-mono text-xs text-slate-700">Measured Δ {metric}: {metric === 'score' ? formatSignedScore(delta) : formatSignedInteger(delta)}</p>
    </div>
  );
}

export const EvidenceFragilityProfile: React.FC<EvidenceFragilityProfileProps> = ({
  candidateName,
  audit,
  auditSummary,
  onOpenCitation,
}) => {
  const counterfactuals = audit?.counterfactuals || [];
  const sources = audit?.sources || [];
  const status = audit?.status ?? (auditSummary?.status === 'unavailable_for_cached_result'
    ? auditSummary.status
    : undefined);
  const presentation = statusPresentation(status);
  const studyCount = audit?.study_counts?.study_units ?? audit?.study_counts?.eligible_independent_studies;
  const baseline = audit?.baseline;
  const completeMethod = audit?.method === 'leave_one_independent_study_out';
  const documentedEvidenceRank = audit?.ranking_scope === 'evidence_rank_over_retrieved_candidates';
  const successfulCounterfactuals = counterfactuals.filter((item) => item.status === 'ok');
  const scoreInfluences = useMemo(
    () => successfulCounterfactuals
      .filter((item) => item.score_delta !== null && item.score_delta !== undefined)
      .sort((a, b) => Math.abs(b.score_delta!) - Math.abs(a.score_delta!)),
    [audit],
  );
  const rankInfluences = useMemo(
    () => successfulCounterfactuals
      .filter((item) => item.rank_delta !== null && item.rank_delta !== undefined)
      .sort((a, b) => Math.abs(b.rank_delta!) - Math.abs(a.rank_delta!)),
    [audit],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const scoreInfluenceId = scoreInfluences[0]
      ? idForCounterfactual(scoreInfluences[0], counterfactuals.indexOf(scoreInfluences[0]))
      : undefined;
    const firstId = counterfactuals[0] ? idForCounterfactual(counterfactuals[0], 0) : undefined;
    setSelectedId(scoreInfluenceId || firstId || null);
  }, [audit, counterfactuals, scoreInfluences]);

  const selectedCounterfactual = counterfactuals.find(
    (item, index) => idForCounterfactual(item, index) === selectedId,
  );
  const selectedSources = selectedCounterfactual
    ? sources.filter((source) => sourceMatchesCounterfactual(source, selectedCounterfactual))
    : [];
  const canExplainDeltas = completeMethod;
  const auditUnavailable = !audit;
  const reportedDirections = [
    { label: 'Supportive', count: audit?.study_counts?.supportive },
    { label: 'Contradictory', count: audit?.study_counts?.contradictory },
    { label: 'Null finding', count: audit?.study_counts?.null_finding },
    { label: 'Uncertain', count: audit?.study_counts?.uncertain },
    { label: 'Not classified', count: audit?.study_counts?.not_classified },
  ].filter((item): item is { label: string; count: number } => typeof item.count === 'number');
  const conflictFlag = audit?.study_counts?.conflicting_evidence_present;

  return (
    <section id="evidence-fragility" aria-labelledby="fragility-heading" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 rounded-lg border border-teal-200 bg-teal-50 p-2 text-teal-800">
              <Activity className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h2 id="fragility-heading" className="text-lg font-semibold text-slate-950">Evidence Fragility Profile</h2>
              <p className="mt-1 text-xs leading-5 text-slate-600">Test how sensitive a candidate&apos;s ranking is to individual studies.</p>
              <p className="mt-1 text-[11px] text-slate-500">Selected candidate: <strong className="text-slate-700">{candidateName}</strong></p>
            </div>
          </div>
          <span className={`w-fit rounded-full border px-2.5 py-1 text-[11px] font-semibold ${presentation.tone}`}>
            {presentation.label}
          </span>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Baseline evidence score</p>
            <p className="mt-1 font-mono text-sm font-semibold text-slate-900">{formatScore(baseline?.evidence_score)}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Baseline evidence rank</p>
            <p className="mt-1 font-mono text-sm font-semibold text-slate-900">{baseline?.evidence_rank == null ? '—' : `#${baseline.evidence_rank}`}</p>
            {baseline?.displayed_kg_rank != null && <p className="mt-0.5 text-[10px] text-slate-500">KG display rank #{baseline.displayed_kg_rank}</p>}
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Study units tested</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{studyCount === undefined ? 'Not reported' : studyCount}</p>
            <p className="mt-0.5 text-[10px] text-slate-500">{audit ? `${successfulCounterfactuals.length} successful of ${counterfactuals.length} returned scenarios` : 'Counterfactual count not reported'}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Largest measured score change</p>
            <p className="mt-1 font-mono text-sm font-semibold text-slate-900">
              {scoreInfluences[0] ? formatScore(Math.abs(scoreInfluences[0].score_delta!)) : 'Not calculated'}
            </p>
            {scoreInfluences[0] && <p className="mt-0.5 truncate text-[10px] text-slate-500">{sourceLabel(scoreInfluences[0])}</p>}
          </div>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-slate-600">{presentation.explanation}</p>
        {audit?.reason && (
          <p className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-[11px] text-slate-700">
            Backend reason: <span className="font-mono">{audit.reason}</span>
          </p>
        )}
      </div>

      <div className="space-y-4 px-4 py-4 sm:px-5">
        {auditUnavailable ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-xs leading-5 text-slate-700">
            <p className="font-semibold">{status === 'unavailable_for_cached_result' ? 'Audit unavailable for this cached result' : 'Audit payload not returned'}</p>
            <p className="mt-1">
              The current API response did not include this candidate&apos;s leave-one-study-out values. No synthetic values are substituted.
              {auditSummary?.note ? ` ${auditSummary.note}` : ''}
            </p>
          </div>
        ) : counterfactuals.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-xs leading-5 text-slate-700">
            <p className="font-semibold">No counterfactual scenarios returned</p>
            <p className="mt-1">This may reflect insufficient evidence, missing stable source identifiers, an unavailable audit, or a computation failure. Review the backend status and reason above.</p>
          </div>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-2">
              <MostInfluential label="Largest absolute score influence" counterfactual={scoreInfluences[0]} metric="score" />
              <MostInfluential label="Largest absolute rank movement" counterfactual={rankInfluences[0]} metric="rank" />
            </div>

            {audit && reportedDirections.length === 0 && (
              <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-600">
                Per-study evidence-direction counts were not returned by the backend.
                {typeof conflictFlag === 'boolean' ? ` Conflict flag: ${conflictFlag ? 'present' : 'not flagged'} by its classifier.` : ''}
              </p>
            )}
            {reportedDirections.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-slate-900">Backend-classified finding directions</h3>
                  {typeof conflictFlag === 'boolean' && (
                    <span className="text-[10px] text-slate-600">Conflict flag: {conflictFlag ? 'present' : 'not flagged'}</span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {reportedDirections.map(({ label, count }) => (
                    <span key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px] text-slate-700">
                      {label}: <strong className="font-mono">{count}</strong>
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[10px] leading-4 text-slate-500">These are rule-based labels returned by the backend, not expert-adjudicated efficacy assessments. A missing category is not treated as a zero count.</p>
              </div>
            )}

            <div>
              <div className="mb-2 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Leave-one-study-out results</h3>
                  <p className="mt-0.5 text-[11px] text-slate-500">Ordered by absolute score change where a score delta was measured. Select a source to inspect its record.</p>
                </div>
                {audit?.method && <span className="font-mono text-[10px] text-slate-500">Method: {audit.method}</span>}
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="min-w-[780px] w-full border-collapse text-left text-[11px]">
                  <caption className="sr-only">Baseline and counterfactual evidence scores and ranks after removing each returned study unit</caption>
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-semibold">Study / source</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Score baseline</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Score without</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Δ score</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Rank baseline</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Rank without</th>
                      <th scope="col" className="px-3 py-2 font-semibold">Δ rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {counterfactuals.map((counterfactual, index) => {
                      const key = idForCounterfactual(counterfactual, index);
                      return (
                        <tr key={key} className={`border-t border-slate-100 ${selectedId === key ? 'bg-teal-50/70' : 'bg-white'}`}>
                          <td className="px-3 py-2 align-top">
                            <button
                              type="button"
                              onClick={() => setSelectedId(key)}
                              aria-pressed={selectedId === key}
                              className="rounded font-mono font-semibold text-teal-800 underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                            >
                              {sourceLabel(counterfactual)}
                            </button>
                            <span className="mt-1 block text-[10px] text-slate-500">{counterfactual.status === 'ok' ? 'Calculated' : `Not calculated: ${counterfactual.status || 'status unavailable'}`}</span>
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-700">{formatScore(counterfactual.baseline_score)}</td>
                          <td className="px-3 py-2 font-mono text-slate-700">{counterfactual.status === 'ok' ? formatScore(counterfactual.counterfactual_score) : '—'}</td>
                          <td className="px-3 py-2 font-mono">
                            {counterfactual.status !== 'ok' || counterfactual.score_delta == null ? '—' : (
                              <span className={`inline-flex items-center gap-1 ${counterfactual.score_delta > 0 ? 'text-amber-800' : 'text-slate-700'}`}>
                                {counterfactual.score_delta > 0 ? <ArrowDownRight className="h-3 w-3" aria-hidden="true" /> : <ArrowUpRight className="h-3 w-3" aria-hidden="true" />}
                                {formatSignedScore(counterfactual.score_delta)}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono text-slate-700">{counterfactual.baseline_rank == null ? '—' : `#${counterfactual.baseline_rank}`}</td>
                          <td className="px-3 py-2 font-mono text-slate-700">{counterfactual.status !== 'ok' || counterfactual.counterfactual_rank == null ? '—' : `#${counterfactual.counterfactual_rank}`}</td>
                          <td className="px-3 py-2 font-mono text-slate-700">{counterfactual.status !== 'ok' ? '—' : formatSignedInteger(counterfactual.rank_delta)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {canExplainDeltas && (
                <p className="mt-2 text-[10px] leading-4 text-slate-500">
                  Δ score = baseline score − score after removal; positive means removing the source lowered the score. Δ rank = rank after removal − baseline rank; positive means the candidate moved down when rank 1 is best. The rank is an evidence rank over the returned candidate set, not the knowledge-graph rank.
                </p>
              )}
            </div>

            {selectedCounterfactual && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Selected source impact</p>
                    <h4 className="mt-1 text-sm font-semibold text-slate-900">{sourceLabel(selectedCounterfactual)}</h4>
                    {selectedCounterfactual.publication_year && <p className="mt-0.5 text-[11px] text-slate-600">Publication year: {selectedCounterfactual.publication_year}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded border border-slate-200 bg-white px-2 py-1 font-mono">Δ score {formatSignedScore(selectedCounterfactual.score_delta)}</span>
                    <span className="rounded border border-slate-200 bg-white px-2 py-1 font-mono">Δ rank {formatSignedInteger(selectedCounterfactual.rank_delta)}</span>
                  </div>
                </div>

                {selectedSources.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {selectedSources.map((source, index) => {
                      const sourceUrl = safeSourceUrl(source.pubmed_url);
                      return (
                        <div key={source.source_id || `${source.pmid || 'source'}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
                          <div className="flex flex-wrap items-center gap-2 text-[11px]">
                            <span className="font-mono font-semibold text-slate-800">{source.pmid ? `PMID ${source.pmid}` : source.source_id || 'Source ID not returned'}</span>
                            {source.publication_year && <span className="text-slate-500">{source.publication_year}</span>}
                            {source.publication_types?.length ? <span className="text-slate-500">{source.publication_types.join(', ').replace(/_/g, ' ')}</span> : null}
                            {sourceUrl && (
                              <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-teal-800 hover:underline">
                                Open publication <ExternalLink className="h-3 w-3" aria-hidden="true" />
                              </a>
                            )}
                          </div>
                          <div className="mt-2 grid gap-1 text-[10px] text-slate-600 sm:grid-cols-2">
                            <span>Source identity: {source.source_identity_status || 'not reported separately'}</span>
                            <span>Quotation match: {source.quote_verification_status || source.citation_verified || 'not reported separately'}</span>
                          </div>
                          {source.quote && <blockquote className="mt-2 border-l-2 border-teal-700 pl-3 text-xs leading-5 text-slate-700">“{source.quote}”</blockquote>}
                          {source.passage_id !== null && source.passage_id !== undefined && (
                            <button
                              type="button"
                              onClick={() => onOpenCitation(source.passage_id!, source.quote || undefined, sourceUrl)}
                              className="mt-2 inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] font-semibold text-teal-800 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                            >
                              <FileSearch className="h-3.5 w-3.5" aria-hidden="true" />
                              Inspect passage [{source.passage_id}]
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-slate-600">No matching source metadata was included for this counterfactual. The measured deltas above are shown as returned by the backend.</p>
                )}
              </div>
            )}
          </>
        )}

        {audit?.warnings && audit.warnings.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3">
            <h3 className="text-xs font-semibold text-amber-950">Audit warnings and limitations</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-[11px] leading-4 text-amber-950">
              {audit.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
            </ul>
          </div>
        )}

        {audit?.study_counts?.study_independence_verified === false && (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-5 text-slate-700">
            <strong>Independence not established.</strong> Distinct PMIDs are treated as separate units for this sensitivity test only; they do not necessarily represent independent experiments.
          </p>
        )}
        {audit?.study_counts?.conflicting_evidence_present === true && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] leading-5 text-amber-950">
            <strong>Conflicting findings flagged by the backend.</strong> This classification is not an expert adjudication; inspect the source records.
          </p>
        )}
      </div>

      <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 sm:px-5">
        <p className="text-[11px] leading-5 text-slate-700">
          <strong>Evidence sensitivity measures ranking robustness under specified study-removal tests. It does not establish clinical efficacy or safety.</strong>
          {documentedEvidenceRank && ' Evidence rank is calculated within the returned candidate set and is distinct from the knowledge-graph display rank.'}
        </p>
        {audit?.scoring_function && <p className="mt-1 font-mono text-[10px] text-slate-500">Scoring function: {audit.scoring_function}</p>}
      </div>
    </section>
  );
};
