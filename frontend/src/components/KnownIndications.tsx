import React, { useState } from 'react';
import { ShieldCheck, ChevronDown, ChevronUp, AlertCircle, Pill } from 'lucide-react';
import { KnownIndication } from '../types';

interface KnownIndicationsProps {
  indications: KnownIndication[];
  diseaseName: string;
}

export const KnownIndications: React.FC<KnownIndicationsProps> = ({ indications, diseaseName }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Default display preview count
  const PREVIEW_COUNT = 8;
  const hasMore = indications.length > PREVIEW_COUNT;
  const displayed = isExpanded ? indications : indications.slice(0, PREVIEW_COUNT);

  return (
    <section
      className="bg-slate-50 border border-slate-200/90 rounded-xl p-5 mb-8 transition-all"
      aria-labelledby="known-indications-heading"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-navy-900 text-white">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h4 id="known-indications-heading" className="text-base font-bold text-navy-900">
              Already indicated for this disease
            </h4>
            <p className="text-xs text-slate-500">
              Established clinical indications excluded from repurposing candidate rankings
            </p>
          </div>
        </div>

        <span className="text-xs font-mono font-semibold text-slate-600 bg-white px-2.5 py-1 rounded-full border border-slate-200 w-fit">
          {indications.length} {indications.length === 1 ? 'drug' : 'drugs'} identified
        </span>
      </div>

      {indications.length === 0 ? (
        <div className="py-4 text-center text-xs text-slate-500 italic">
          No known indications recorded in the knowledge graph for {diseaseName}.
        </div>
      ) : (
        <div className="mt-4">
          <div className="flex flex-wrap gap-2">
            {displayed.map((item, idx) => (
              <div
                key={idx}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-800 shadow-2xs hover:border-slate-300 transition-colors"
              >
                <Pill className="w-3.5 h-3.5 text-slate-400" />
                <span>{item.drug_name}</span>
                {item.drug_id && (
                  <span className="text-[10px] font-mono text-slate-400">
                    ({item.drug_id})
                  </span>
                )}
              </div>
            ))}
          </div>

          {hasMore && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-3.5 inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-900 focus:outline-none transition-colors"
            >
              <span>{isExpanded ? 'Show fewer indications' : `View all ${indications.length} known indications`}</span>
              {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          <div className="mt-4 pt-3 border-t border-slate-200/60 text-[11px] text-slate-500 flex items-start gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
            <span>
              <strong>Indication Scope:</strong> These drugs have established medical or on-label use for {diseaseName} according to the EveryCure Knowledge Graph. They are cataloged here to prevent redundant rediscovery.
            </span>
          </div>
        </div>
      )}
    </section>
  );
};
