import React from 'react';
import { AlertCircle, ArrowRight, RefreshCw, WifiOff } from 'lucide-react';
import { ResponseStatus } from '../types';

interface StatusAlertProps {
  status: ResponseStatus | 'network_error';
  message?: string;
  query?: string;
  supportedDiseases?: string[];
  onSelectDisease?: (disease: string) => void;
  onRetry?: () => void;
}

export const StatusAlert: React.FC<StatusAlertProps> = ({
  status,
  message,
  query,
  supportedDiseases = [],
  onSelectDisease,
  onRetry,
}) => {
  if (status === 'network_error') {
    return (
      <section className="rounded-2xl border border-rose-200 bg-rose-50 p-5" role="alert" aria-labelledby="backend-error-heading">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-white p-2 text-rose-700"><WifiOff className="h-5 w-5" aria-hidden="true" /></span>
          <div className="min-w-0 flex-1">
            <h2 id="backend-error-heading" className="text-base font-semibold text-rose-950">Could not reach the query service</h2>
            <p className="mt-1 text-sm leading-5 text-rose-900">{message || 'The PharmaSure backend request failed.'}</p>
            {onRetry && (
              <button type="button" onClick={onRetry} className="mt-3 inline-flex min-h-9 items-center gap-2 rounded-lg border border-rose-300 bg-white px-3 py-2 text-xs font-semibold text-rose-900 hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-700">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />Retry query
              </button>
            )}
          </div>
        </div>
      </section>
    );
  }

  if (status === 'unsupported_disease') {
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5" role="status" aria-labelledby="unresolved-heading">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-white p-2 text-amber-800"><AlertCircle className="h-5 w-5" aria-hidden="true" /></span>
          <div className="min-w-0 flex-1">
            <h2 id="unresolved-heading" className="text-base font-semibold text-amber-950">Disease not resolved by the backend</h2>
            <p className="mt-1 text-sm leading-5 text-amber-950">{message || `The backend did not resolve “${query || 'this query'}” to a supported disease entity.`}</p>
            <p className="mt-2 text-xs leading-5 text-amber-900">This is a disease-resolution state, not evidence that the disease has no treatment or no literature.</p>
            {supportedDiseases.length > 0 && onSelectDisease && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold text-amber-950">Try a disease name reported by this backend:</p>
                <div className="flex flex-wrap gap-2">
                  {supportedDiseases.slice(0, 6).map((disease) => (
                    <button key={disease} type="button" onClick={() => onSelectDisease(disease)} className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-800 hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-700">
                      {disease}<ArrowRight className="h-3 w-3" aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    );
  }

  if (status === 'insufficient_evidence') {
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5" role="status" aria-labelledby="abstention-heading">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-white p-2 text-amber-800"><AlertCircle className="h-5 w-5" aria-hidden="true" /></span>
          <div>
            <h2 id="abstention-heading" className="text-base font-semibold text-amber-950">Backend abstention: insufficient evidence</h2>
            <p className="mt-1 text-sm leading-5 text-amber-950">{message || `The backend reported insufficient evidence for “${query || 'this query'}”.`}</p>
            <p className="mt-2 text-xs leading-5 text-amber-900">The response does not establish whether the cause is graph coverage, corpus coverage, or an evidence threshold. No unrelated papers are substituted as support.</p>
          </div>
        </div>
      </section>
    );
  }

  if (status === 'unknown') {
    return (
      <section className="rounded-2xl border border-slate-300 bg-slate-50 p-5" role="alert" aria-labelledby="malformed-heading">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-white p-2 text-slate-700"><AlertCircle className="h-5 w-5" aria-hidden="true" /></span>
          <div>
            <h2 id="malformed-heading" className="text-base font-semibold text-slate-900">Unexpected backend response</h2>
            <p className="mt-1 text-sm text-slate-700">{message || 'The query endpoint returned an unrecognized or missing status. The response was not treated as a successful analysis.'}</p>
          </div>
        </div>
      </section>
    );
  }

  return null;
};
