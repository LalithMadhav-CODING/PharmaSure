import React from 'react';
import { AlertCircle, HelpCircle, WifiOff, RefreshCw, ArrowRight } from 'lucide-react';
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
  if (status === 'insufficient_evidence') {
    return (
      <div className="bg-amber-50/70 border border-amber-300 rounded-xl p-6 text-left shadow-2xs mb-8">
        <div className="flex items-start gap-3.5">
          <div className="p-2 rounded-lg bg-amber-100 text-amber-800 shrink-0 mt-0.5">
            <AlertCircle className="w-5 h-5 text-amber-700" />
          </div>
          <div className="space-y-2 flex-1">
            <h4 className="text-base sm:text-lg font-bold text-amber-950">
              Insufficient evidence for this disease
            </h4>
            <p className="text-sm text-amber-900 leading-relaxed">
              {message || `The available literature did not yield repurposing candidates meeting the system's evidence criteria for "${query}".`}
            </p>
            <p className="text-xs text-amber-800">
              This typically reflects rare disease indications, sparse PubMed coverage in the indexed corpus, or lack of statistically validated off-label signals in the EveryCure knowledge graph.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'unsupported_disease') {
    return (
      <div className="bg-slate-50 border border-slate-300 rounded-xl p-6 text-left shadow-2xs mb-8">
        <div className="flex items-start gap-3.5">
          <div className="p-2 rounded-lg bg-slate-200 text-slate-800 shrink-0 mt-0.5">
            <HelpCircle className="w-5 h-5 text-slate-700" />
          </div>
          <div className="space-y-3 flex-1">
            <div>
              <h4 className="text-base sm:text-lg font-bold text-navy-900">
                Disease Not In Supported Corpus
              </h4>
              <p className="mt-1 text-sm text-slate-700 leading-relaxed">
                {message || `"${query}" is not currently indexed in our demonstration corpus.`}
              </p>
            </div>

            {supportedDiseases.length > 0 && onSelectDisease && (
              <div className="pt-2">
                <span className="text-xs font-semibold text-slate-600 block mb-2">
                  Try one of our verified demonstration diseases:
                </span>
                <div className="flex flex-wrap gap-2">
                  {supportedDiseases.map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => onSelectDisease(d)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-brand-800 bg-brand-50 border border-brand-200 hover:bg-brand-100 hover:border-brand-300 transition-colors shadow-2xs"
                    >
                      <span>{d}</span>
                      <ArrowRight className="w-3 h-3 text-brand-600" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (status === 'network_error') {
    return (
      <div className="bg-rose-50/70 border border-rose-300 rounded-xl p-6 text-left shadow-2xs mb-8">
        <div className="flex items-start gap-3.5">
          <div className="p-2 rounded-lg bg-rose-100 text-rose-800 shrink-0 mt-0.5">
            <WifiOff className="w-5 h-5 text-rose-700" />
          </div>
          <div className="space-y-3 flex-1">
            <div>
              <h4 className="text-base sm:text-lg font-bold text-rose-950">
                Backend Connection Error
              </h4>
              <p className="mt-1 text-sm text-rose-900 leading-relaxed">
                {message || 'Unable to communicate with the PharmaSure backend API.'}
              </p>
            </div>

            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-white bg-rose-700 hover:bg-rose-800 transition-colors shadow-xs"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Request</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
};
