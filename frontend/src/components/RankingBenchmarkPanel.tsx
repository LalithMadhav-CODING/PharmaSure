import React, { useMemo } from 'react';
import { BarChart3, CircleHelp } from 'lucide-react';
import { RankingBenchmark, RankingBenchmarkMethod } from '../types';

interface RankingBenchmarkPanelProps {
  benchmark?: RankingBenchmark;
}

function displayMetric(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return 'Not reported';
  return typeof value === 'number' ? String(value) : value;
}

function MethodNotes({ method }: { method: RankingBenchmarkMethod }) {
  const hasNotes = Boolean(method.failures?.length || method.limitations?.length);
  if (!hasNotes) return null;
  return (
    <div className="mt-2 grid gap-2 sm:grid-cols-2">
      {method.failures && method.failures.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-950">Reported failures</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] leading-4 text-amber-950">{method.failures.map((failure, index) => <li key={`${index}-${failure}`}>{failure}</li>)}</ul>
        </div>
      )}
      {method.limitations && method.limitations.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-600">Reported limitations</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] leading-4 text-slate-700">{method.limitations.map((limitation, index) => <li key={`${index}-${limitation}`}>{limitation}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

export const RankingBenchmarkPanel: React.FC<RankingBenchmarkPanelProps> = ({ benchmark }) => {
  const methods = benchmark?.methods || [];
  const metricNames = useMemo(
    () => [...new Set(methods.flatMap((method) => Object.keys(method.outcomes || {})))],
    [methods],
  );

  return (
    <section id="ranking-benchmark" aria-labelledby="ranking-benchmark-heading" className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-slate-600"><BarChart3 className="h-4 w-4" aria-hidden="true" /></span>
        <div className="min-w-0 flex-1">
          <h3 id="ranking-benchmark-heading" className="text-sm font-semibold text-slate-950">Ranking benchmark</h3>
          {!benchmark ? (
            <p className="mt-1 text-xs leading-5 text-slate-600">Benchmark not available: the current query API did not return evaluation results. No placeholder metrics or superiority claims are shown.</p>
          ) : (
            <>
              <p className="mt-1 text-xs text-slate-600">Status: <strong className="font-medium text-slate-800">{benchmark.status || 'not reported'}</strong>{benchmark.protocol_id ? ` · Protocol ${benchmark.protocol_id}` : ''}</p>
              {methods.length === 0 ? (
                <p className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">No benchmark method outcomes were returned. The status and protocol metadata above are shown as supplied.</p>
              ) : (
                <>
                  <dl className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2 xl:grid-cols-3">
                    <div><dt className="text-slate-500">Evaluation date</dt><dd className="font-medium text-slate-800">{benchmark.evaluation_date || 'Not reported'}</dd></div>
                    <div><dt className="text-slate-500">Queries / trials</dt><dd className="font-medium text-slate-800">{benchmark.query_count ?? 'Not reported'} / {benchmark.trial_count ?? 'Not reported'}</dd></div>
                    <div><dt className="text-slate-500">Verification mode</dt><dd className="font-medium capitalize text-slate-800">{benchmark.verification_mode || 'Not reported'}</dd></div>
                    <div className="sm:col-span-2 xl:col-span-3"><dt className="text-slate-500">Source access conditions</dt><dd className="mt-0.5 text-slate-800">{benchmark.source_access_conditions || 'Not reported'}</dd></div>
                    <div className="sm:col-span-2 xl:col-span-3"><dt className="text-slate-500">Evaluation rubric</dt><dd className="mt-0.5 text-slate-800">{benchmark.evaluation_rubric || 'Not reported'}</dd></div>
                  </dl>

                  <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
                    <table className="min-w-[640px] w-full border-collapse text-left text-[11px]">
                      <caption className="sr-only">Benchmark outcomes returned for each named method</caption>
                      <thead className="bg-slate-50 text-slate-600">
                        <tr>
                          <th scope="col" className="px-3 py-2 font-semibold">Method / comparator</th>
                          {metricNames.map((metric) => <th key={metric} scope="col" className="px-3 py-2 font-semibold">{metric.replace(/_/g, ' ')}</th>)}
                          <th scope="col" className="px-3 py-2 font-semibold">Runtime (ms)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {methods.map((method, index) => (
                          <tr key={`${method.name || 'method'}-${index}`} className="border-t border-slate-100 align-top">
                            <th scope="row" className="px-3 py-2 font-medium text-slate-900">
                              {method.name || 'Method name not returned'}
                              <span className="mt-0.5 block max-w-xs break-words font-normal text-slate-500">{method.product_or_model_id || 'Exact model / product ID not returned'}</span>
                            </th>
                            {metricNames.map((metric) => <td key={metric} className="px-3 py-2 font-mono text-slate-700">{displayMetric(method.outcomes?.[metric])}</td>)}
                            <td className="px-3 py-2 font-mono text-slate-700">{displayMetric(method.runtime_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {methods.map((method, index) => <MethodNotes key={`${method.name || 'method'}-notes-${index}`} method={method} />)}
                  <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-5 text-slate-600"><CircleHelp className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />Results are limited to this declared evaluation protocol, query set, source access, rubric, and verification process. No method is labeled superior by the interface.</p>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
};
