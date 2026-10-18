import React from 'react';
import { Database, Activity, ExternalLink, Info } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  onOpenAbout: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, onOpenAbout }) => {
  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm transition-all">
      {/* Disclaimer Banner (PRD Requirement: Persistent, visible across all states) */}
      <div className="bg-amber-500/10 border-b border-amber-300/40 px-4 py-1.5 text-xs text-amber-900 flex items-center justify-center font-medium gap-2">
        <span className="inline-block text-sm" aria-hidden="true">⚠️</span>
        <span>
          <strong>Research hypotheses only, not medical advice.</strong> Findings require clinical validation before investigational or off-label use.
        </span>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Product Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-700 to-teal-500 flex items-center justify-center text-white shadow-sm ring-1 ring-black/5">
              <span className="text-xl" role="img" aria-label="pill">💊</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg sm:text-xl font-bold tracking-tight text-navy-900">
                  Telemedicon
                </h1>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-brand-50 text-brand-800 border border-brand-200">
                  Literature RAG v1.2
                </span>
              </div>
              <p className="text-xs text-slate-700 hidden sm:block">
                Drug Repurposing &amp; Evidence Verification Assistant
              </p>
            </div>
          </div>

          {/* Right Navigation & Backend Health status */}
          <div className="flex items-center gap-3">
            {health && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-slate-50 border border-slate-200 rounded-full text-xs text-slate-600">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true"></span>
                <span>Corpus: <strong>{health.corpus_size.toLocaleString()}</strong> passages</span>
              </div>
            )}

            <button
              onClick={onOpenAbout}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-colors shadow-2xs"
              aria-label="Open About and Data information"
            >
              <Database className="w-3.5 h-3.5 text-slate-700" />
              <span>About / Data</span>
            </button>

            <a
              href="/gradio"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden lg:inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Open legacy Gradio ML testbed"
            >
              <span>Legacy Gradio</span>
              <ExternalLink className="w-3 h-3 text-slate-600" />
            </a>
          </div>
        </div>
      </div>
    </header>
  );
};
