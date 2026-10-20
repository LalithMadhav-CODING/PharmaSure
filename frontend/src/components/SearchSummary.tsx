import React from 'react';
import { Clock3, Database, FileText, FlaskConical } from 'lucide-react';
import { QueryResponse } from '../types';

interface SearchSummaryProps {
  response: QueryResponse;
}

export const SearchSummary: React.FC<SearchSummaryProps> = ({ response }) => {
  const diseaseName = response.disease?.name || response.query || 'Disease name not returned';
  const candidateCount = Array.isArray(response.results) ? response.results.length : undefined;
  const passageCount = Array.isArray(response.passages) ? response.passages.length : undefined;
  const totalBackendMs = response.timings_ms?.total_ms;
  const isCached = response.from_cache === true;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm sm:px-5" aria-label="Query result summary">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${response.disease?.name ? 'border-teal-200 bg-teal-50 text-teal-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
              {response.disease?.name ? 'Resolved disease' : 'Disease entity not returned'}
            </span>
            {response.disease?.id && (
              <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[10px] text-slate-600">{response.disease.id}</span>
            )}
            {isCached && (
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[10px] font-medium text-slate-700">
                <Database className="h-3 w-3" aria-hidden="true" /> Cached precomputation
              </span>
            )}
          </div>
          <h2 className="mt-2 break-words text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">{diseaseName}</h2>
          {response.disease?.synonyms && <p className="mt-1 text-xs text-slate-500">Synonyms: {response.disease.synonyms}</p>}
        </div>
        <dl className="grid grid-cols-2 gap-2 text-xs sm:min-w-[19rem] sm:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <dt className="flex items-center gap-1.5 text-slate-500"><FlaskConical className="h-3.5 w-3.5" aria-hidden="true" />KG candidates</dt>
            <dd className="mt-1 font-mono text-base font-semibold text-slate-900">{candidateCount === undefined ? '—' : candidateCount}</dd>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <dt className="flex items-center gap-1.5 text-slate-500"><FileText className="h-3.5 w-3.5" aria-hidden="true" />Returned passages</dt>
            <dd className="mt-1 font-mono text-base font-semibold text-slate-900">{passageCount === undefined ? '—' : passageCount}</dd>
          </div>
          {totalBackendMs !== undefined && (
            <div className="col-span-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 sm:col-span-1">
              <dt className="flex items-center gap-1.5 text-slate-500"><Clock3 className="h-3.5 w-3.5" aria-hidden="true" />Backend time</dt>
              <dd className="mt-1 font-mono text-base font-semibold text-slate-900">{totalBackendMs} ms</dd>
            </div>
          )}
        </dl>
      </div>
      <p className="mt-3 border-t border-slate-100 pt-3 text-[11px] leading-5 text-slate-600">
        Knowledge-graph rank is candidate discovery; the literature evidence score is a separate heuristic. Neither represents a probability of efficacy.
      </p>
    </section>
  );
};
