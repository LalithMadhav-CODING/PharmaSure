import React, { useState } from 'react';
import { Clock, Zap, ChevronDown, ChevronUp, CheckCircle, ShieldAlert, FileText, Cpu } from 'lucide-react';
import { QueryResponse } from '../types';

interface SearchSummaryProps {
  response: QueryResponse;
  clientDurationMs: number | null;
}

export const SearchSummary: React.FC<SearchSummaryProps> = ({ response, clientDurationMs }) => {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const diseaseName = response.disease?.name || response.query || 'Selected Disease';
  const diseaseId = response.disease?.id;
  const candidateCount = response.results?.length || 0;
  const knownCount = response.known_indications?.length || 0;
  const passageCount = response.passages?.length || 0;

  const timings = response.timings_ms || {};
  const totalBackendMs = timings.total_ms ?? timings.cache_hit ?? 0;
  const isCached = Boolean(response.from_cache);

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 shadow-2xs mb-6 transition-all">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Disease Entity Info */}
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold tracking-wide uppercase text-brand-700 bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
              Resolved Disease
            </span>
            {diseaseId && (
              <span className="text-xs font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                {diseaseId}
              </span>
            )}
            {isCached && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                <Zap className="w-3 h-3 text-emerald-600 fill-emerald-600" />
                Cached Precomputation
              </span>
            )}
          </div>
          <h3 className="text-xl sm:text-2xl font-bold text-navy-900 tracking-tight">
            {diseaseName}
          </h3>
          {response.disease?.synonyms && (
            <p className="text-xs text-slate-700 truncate max-w-xl">
              Synonyms: {response.disease.synonyms}
            </p>
          )}
        </div>

        {/* Quick Metrics & Latency */}
        <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-xs">
          <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-center min-w-[85px]">
            <div className="text-base sm:text-lg font-bold text-navy-900">{candidateCount}</div>
            <div className="text-slate-700 font-medium">Candidates</div>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-center min-w-[85px]">
            <div className="text-base sm:text-lg font-bold text-slate-700">{knownCount}</div>
            <div className="text-slate-700 font-medium">Already Indicated</div>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-center min-w-[85px]">
            <div className="text-base sm:text-lg font-bold text-slate-700">{passageCount}</div>
            <div className="text-slate-700 font-medium">Source Passages</div>
          </div>

          <div className="bg-brand-50/60 border border-brand-200/60 rounded-lg px-3 py-2 text-center min-w-[100px]">
            <div className="flex items-center justify-center gap-1 text-base sm:text-lg font-bold text-brand-900 font-mono">
              <Clock className="w-3.5 h-3.5 text-brand-700" />
              <span>{totalBackendMs}ms</span>
            </div>
            <div className="text-brand-800 font-medium">Backend Time</div>
          </div>
        </div>
      </div>

      {/* Expandable Technical Details Button */}
      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
        <button
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 hover:text-navy-900 focus:outline-none transition-colors"
          aria-expanded={showTechnicalDetails}
        >
          <Cpu className="w-3.5 h-3.5 text-slate-600" />
          <span>{showTechnicalDetails ? 'Hide RAG Pipeline Diagnostics' : 'Inspect Pipeline Latency & Timings'}</span>
          {showTechnicalDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>

        {clientDurationMs !== null && (
          <span className="text-[11px] text-slate-600">
            Frontend end-to-end: <strong className="font-mono text-slate-700">{clientDurationMs}ms</strong> (includes network &amp; rendering)
          </span>
        )}
      </div>

      {/* Technical Details Panel */}
      {showTechnicalDetails && (
        <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-xs">
          <div className="p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-slate-600 block text-[10px] uppercase font-semibold">1. Disease Resolve</span>
            <span className="font-mono font-medium text-slate-800">{timings.resolve ?? 0} ms</span>
          </div>
          <div className="p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-slate-600 block text-[10px] uppercase font-semibold">2. Query Embed</span>
            <span className="font-mono font-medium text-slate-800">{timings.embed ?? 0} ms</span>
          </div>
          <div className="p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-slate-600 block text-[10px] uppercase font-semibold">3. Dense Retrieval</span>
            <span className="font-mono font-medium text-slate-800">{timings.retrieve ?? 0} ms</span>
          </div>
          <div className="p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-slate-600 block text-[10px] uppercase font-semibold">4. Answer Synthesis</span>
            <span className="font-mono font-medium text-slate-800">{timings.generate ?? 0} ms</span>
          </div>
          <div className="p-2 bg-slate-50 rounded border border-slate-200">
            <span className="text-slate-600 block text-[10px] uppercase font-semibold">5. Citation Verify</span>
            <span className="font-mono font-medium text-slate-800">{timings.verify ?? 0} ms</span>
          </div>
          <div className="p-2 bg-brand-50 rounded border border-brand-200">
            <span className="text-brand-700 block text-[10px] uppercase font-semibold">Total Pipeline</span>
            <span className="font-mono font-bold text-brand-900">{totalBackendMs} ms</span>
          </div>
        </div>
      )}
    </div>
  );
};
