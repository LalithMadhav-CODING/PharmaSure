import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Activity,
  AlertTriangle,
  Info,
  ExternalLink,
  ShieldAlert,
  MinusCircle,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import {
  EvidenceAudit,
  AuditCounterfactual,
  AuditDirectionLabel,
  AuditStatus,
} from '../types';

interface EvidenceAuditProps {
  audit?: EvidenceAudit;
  /** Opens the existing citation drawer for a passage. */
  onOpenCitation: (citationId: string | number, relatedQuote?: string) => void;
}

/** Human-readable status text. Colour is never the only signal. */
const STATUS_LABEL: Record<string, string> = {
  complete: 'Audit complete',
  partial: 'Audit partial — some scenarios could not be calculated',
  not_auditable: 'Not auditable',
  insufficient_independent_studies_for_stability_test:
    'Only one study unit — stability not assessed',
  audit_failed: 'Audit failed',
  unavailable_for_cached_result: 'Audit unavailable for this cached result',
};

const STATUS_TONE: Record<string, string> = {
  complete: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  partial: 'bg-amber-50 text-amber-900 border-amber-200',
  not_auditable: 'bg-slate-100 text-slate-700 border-slate-300',
  insufficient_independent_studies_for_stability_test:
    'bg-slate-100 text-slate-700 border-slate-300',
  audit_failed: 'bg-rose-50 text-rose-800 border-rose-200',
  unavailable_for_cached_result: 'bg-slate-100 text-slate-700 border-slate-300',
};

const DIRECTION_LABEL: Record<AuditDirectionLabel, string> = {
  supportive: 'Supportive',
  contradictory: 'Contradictory',
  null_finding: 'Null finding',
  uncertain: 'Mixed / uncertain',
  not_classified: 'Not classified',
};

const DIRECTION_TONE: Record<AuditDirectionLabel, string> = {
  supportive: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  contradictory: 'bg-rose-50 text-rose-800 border-rose-200',
  null_finding: 'bg-sky-50 text-sky-800 border-sky-200',
  uncertain: 'bg-amber-50 text-amber-900 border-amber-200',
  not_classified: 'bg-slate-100 text-slate-600 border-slate-300',
};

const fmt = (v: number | null | undefined, digits = 3): string =>
  v === null || v === undefined ? '—' : v.toFixed(digits);

const signed = (v: number | null | undefined, digits = 3): string => {
  if (v === null || v === undefined) return '—';
  const s = v.toFixed(digits);
  return v > 0 ? `+${s}` : s;
};

const signedInt = (v: number | null | undefined): string => {
  if (v === null || v === undefined) return '—';
  return v > 0 ? `+${v}` : `${v}`;
};

const statusLabel = (status: string | undefined): string =>
  STATUS_LABEL[status || ''] || 'Audit status unavailable';

export const EvidenceAuditPanel: React.FC<EvidenceAuditProps> = ({ audit, onOpenCitation }) => {
  const [open, setOpen] = useState(false);

  if (!audit) {
    return (
      <div className="border-t border-slate-100 bg-slate-50/60 px-4 sm:px-5 py-2.5 text-[11px] text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 text-slate-400" />
          <span>Evidence stability audit unavailable for this result.</span>
        </span>
      </div>
    );
  }

  const status = audit.status || 'not_auditable';
  const counts = audit.study_counts || {};
  const stability = audit.stability;
  const counterfactuals = audit.counterfactuals || [];
  const warnings = audit.warnings || [];
  const baseline = audit.baseline;
  const isAuditable = status === 'complete' || status === 'partial';

  const conflict = Boolean(counts.conflicting_evidence_present);
  const classified = counts.classified ?? 0;
  const units = counts.study_units ?? counts.eligible_independent_studies ?? 0;

  return (
    <div className="border-t border-slate-100 bg-slate-50/60">
      {/* Collapsed summary row */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls={`evidence-audit-panel`}
        className="w-full px-4 sm:px-5 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-700 hover:text-navy-900 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <span className="flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-brand-600" />
          <span>Evidence stability audit</span>
          <span
            className={`ml-1 inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium ${
              STATUS_TONE[status] || STATUS_TONE.not_auditable
            }`}
          >
            {statusLabel(status)}
          </span>
        </span>

        <span className="flex items-center gap-3 text-[11px] text-slate-500 font-normal">
          {isAuditable && (
            <>
              <span>
                {units} study {units === 1 ? 'unit' : 'units'}
              </span>
              <span className="hidden sm:inline">
                {classified} direction-classified
              </span>
              {conflict && (
                <span className="inline-flex items-center gap-1 text-amber-800 font-medium">
                  <AlertTriangle className="w-3 h-3" />
                  conflicting evidence
                </span>
              )}
            </>
          )}
          <span className="flex items-center gap-1">
            {open ? 'Collapse' : 'Inspect source influence'}
            {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </span>
      </button>

      {open && (
        <div
          id="evidence-audit-panel"
          className="px-4 sm:px-5 pb-4 pt-1 text-xs text-slate-700 space-y-3 border-t border-slate-200/60 bg-white"
        >
          {/* Non-auditable states: explain, never fabricate */}
          {!isAuditable && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
              <p className="font-semibold text-navy-900">{statusLabel(status)}</p>
              {audit.reason && (
                <p className="text-slate-600 text-[11px]">
                  Reason: <span className="font-mono">{audit.reason}</span>
                </p>
              )}
              <p className="text-slate-600 text-[11px]">
                No counterfactual scenarios are reported because a leave-one-study-out
                test needs at least two independent study units.
              </p>
            </div>
          )}

          {/* Baseline + stability headline */}
          {baseline && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">
                  Baseline evidence score
                </span>
                <span className="font-mono font-bold text-navy-900">
                  {fmt(baseline.evidence_score)}
                </span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">
                  Evidence rank
                </span>
                <span className="font-mono font-medium text-slate-800">
                  #{baseline.evidence_rank}
                </span>
                <span className="block text-[10px] text-slate-400">
                  displayed rank #{baseline.displayed_kg_rank}
                </span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">
                  Max score change
                </span>
                <span className="font-mono font-medium text-slate-800">
                  {fmt(stability?.max_absolute_score_change)}
                </span>
              </div>
              <div className="p-2 bg-slate-50 rounded border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">
                  Max rank movement
                </span>
                <span className="font-mono font-medium text-slate-800">
                  {stability?.max_rank_movement ?? '—'}
                </span>
                {stability?.rank_range !== null && stability?.rank_range !== undefined && (
                  <span className="block text-[10px] text-slate-400">
                    rank range {stability.rank_range}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Direction counts */}
          <div>
            <h6 className="font-semibold text-navy-900 mb-1.5">
              Evidence direction across study units
            </h6>
            <div className="flex flex-wrap gap-1.5">
              {(['supportive', 'contradictory', 'null_finding', 'uncertain', 'not_classified'] as AuditDirectionLabel[]).map(
                (label) => (
                  <span
                    key={label}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium ${DIRECTION_TONE[label]}`}
                  >
                    <span>{DIRECTION_LABEL[label]}:</span>
                    <span className="font-mono">{counts[label] ?? 0}</span>
                  </span>
                )
              )}
            </div>
            <p className="mt-1.5 text-[10px] text-slate-500 leading-relaxed">
              {counts.caveat ||
                'Direction labels are machine-generated by unvalidated rules; unclassified sources are not evidence of consistency.'}
            </p>
          </div>

          {/* Counterfactual table */}
          {counterfactuals.length > 0 && (
            <div>
              <h6 className="font-semibold text-navy-900 mb-1.5">
                Leave-one-study-out results
                <span className="ml-1 font-normal text-slate-500">
                  ({stability?.successful_counterfactuals ?? 0} calculated
                  {stability?.failed_counterfactuals
                    ? `, ${stability.failed_counterfactuals} failed`
                    : ''}
                  )
                </span>
              </h6>

              <div className="overflow-x-auto -mx-1 px-1">
                <table className="w-full text-[11px] border-collapse min-w-[640px]">
                  <caption className="sr-only">
                    Effect of removing each study unit on the candidate evidence score and
                    evidence rank.
                  </caption>
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Study (PMID)</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Year / type</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Direction</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Score</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Score without</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Δ score</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Rank</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Rank without</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Δ rank</th>
                      <th scope="col" className="py-1.5 pr-2 font-semibold">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {counterfactuals.map((cf: AuditCounterfactual) => {
                      const label = (cf.evidence_direction || 'not_classified') as AuditDirectionLabel;
                      const scoreDown = (cf.score_delta ?? 0) > 0;
                      const rankDown = (cf.rank_delta ?? 0) > 0;
                      const failed = cf.status !== 'ok';
                      return (
                        <tr
                          key={cf.study_group_id}
                          className="border-b border-slate-100 last:border-0 align-top"
                        >
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            {(cf.pmids || []).length ? cf.pmids.join(', ') : '(no PMID)'}
                          </td>
                          <td className="py-1.5 pr-2 text-slate-600">
                            {cf.publication_year ?? '—'}
                            {cf.publication_types?.length
                              ? ` · ${cf.publication_types.join(', ').replace(/_/g, ' ')}`
                              : ''}
                          </td>
                          <td className="py-1.5 pr-2">
                            <span
                              className={`inline-flex px-1.5 py-0.5 rounded border text-[10px] font-medium ${DIRECTION_TONE[label]}`}
                            >
                              {DIRECTION_LABEL[label]}
                            </span>
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            {fmt(cf.baseline_score)}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            {failed ? '—' : fmt(cf.counterfactual_score)}
                          </td>
                          <td className="py-1.5 pr-2 font-mono">
                            {failed ? (
                              <span className="text-slate-400" title={cf.error || 'not calculated'}>
                                —
                              </span>
                            ) : (
                              <span
                                className={`inline-flex items-center gap-0.5 ${
                                  scoreDown ? 'text-rose-700' : 'text-slate-600'
                                }`}
                              >
                                {scoreDown ? (
                                  <TrendingDown className="w-3 h-3" aria-hidden="true" />
                                ) : (
                                  <TrendingUp className="w-3 h-3" aria-hidden="true" />
                                )}
                                {signed(cf.score_delta)}
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            #{cf.baseline_rank}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            {failed || cf.counterfactual_rank === null
                              ? '—'
                              : `#${cf.counterfactual_rank}`}
                          </td>
                          <td className="py-1.5 pr-2 font-mono text-slate-700">
                            {failed ? '—' : signedInt(cf.rank_delta)}
                          </td>
                          <td className="py-1.5 pr-2">
                            {cf.passage_ids?.length ? (
                              <button
                                type="button"
                                onClick={() => onOpenCitation(cf.passage_ids[0])}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded font-mono text-[10px] font-semibold text-brand-700 bg-brand-50 border border-brand-300 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                                aria-label={`Open source passage ${cf.passage_ids[0]} for study ${cf.pmids.join(', ') || 'without PMID'}`}
                              >
                                [{cf.passage_ids[0]}]
                              </button>
                            ) : (
                              <MinusCircle className="w-3 h-3 text-slate-300" aria-hidden="true" />
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <p className="mt-1.5 text-[10px] text-slate-500 leading-relaxed">
                Δ score = baseline − score without the study (positive means removing the study
                lowered the score). Δ rank = rank without the study − baseline rank (positive
                means the candidate moved down). Ranks are evidence ranks over the retrieved
                candidate set, not the displayed knowledge-graph order.
              </p>
            </div>
          )}

          {/* Source list with direction provenance */}
          {(audit.sources || []).length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-[11px] font-semibold text-slate-700 hover:text-navy-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
                Source records in this audit ({(audit.sources || []).length})
              </summary>
              <ul className="mt-2 space-y-1.5">
                {(audit.sources || []).map((src) => {
                  const label = (src.evidence_direction || 'not_classified') as AuditDirectionLabel;
                  return (
                    <li
                      key={src.source_id}
                      className="p-2 bg-slate-50 rounded border border-slate-200 text-[11px]"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-slate-700">
                          {src.pmid ? `PMID ${src.pmid}` : 'no PMID'}
                        </span>
                        <span
                          className={`inline-flex px-1.5 py-0.5 rounded border text-[10px] font-medium ${DIRECTION_TONE[label]}`}
                        >
                          {DIRECTION_LABEL[label]}
                        </span>
                        {src.safety_signal && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-amber-200 bg-amber-50 text-amber-900 text-[10px] font-medium">
                            <ShieldAlert className="w-3 h-3" aria-hidden="true" />
                            safety signal (separate from direction)
                          </span>
                        )}
                        {src.pubmed_url && (
                          <a
                            href={src.pubmed_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-brand-700 hover:underline"
                            aria-label={`Open PubMed record ${src.pmid} in a new tab`}
                          >
                            PubMed
                            <ExternalLink className="w-3 h-3" aria-hidden="true" />
                          </a>
                        )}
                      </div>
                      {src.direction_snippet && (
                        <blockquote className="mt-1 pl-2 border-l-2 border-slate-300 italic text-slate-600">
                          {src.direction_snippet}
                        </blockquote>
                      )}
                      {(src.metadata_warnings || []).length > 0 && (
                        <p className="mt-1 text-[10px] text-amber-800">
                          Metadata warnings: {src.metadata_warnings!.join(', ').replace(/_/g, ' ')}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="p-2.5 bg-amber-50/60 rounded border border-amber-200 text-[11px] text-amber-900">
              <p className="font-semibold mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
                Audit caveats
              </p>
              <ul className="list-disc pl-4 space-y-0.5">
                {warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Mandatory limitation statement */}
          <p className="text-[10px] text-slate-500 leading-relaxed border-t border-slate-100 pt-2">
            <strong>What this does and does not show.</strong> This audit is a sensitivity test of
            the currently retrieved evidence set. It shows how the score and evidence rank move
            when a study is removed. Stability under removal is <em>not</em> evidence of clinical
            efficacy, causal validity, or scientific truth, and the absence of evidence in this
            corpus is not evidence of ineffectiveness.
          </p>
        </div>
      )}
    </div>
  );
};
