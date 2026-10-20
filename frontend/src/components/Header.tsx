import React from 'react';
import { Activity, ExternalLink, Info } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  healthError?: string | null;
  onOpenAbout: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, healthError, onOpenAbout }) => {
  const healthIsOk = health?.status === 'ok';
  const healthLabel = healthIsOk ? 'API reachable' : healthError ? 'API health unavailable' : 'API status unknown';

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-[11px] leading-4 text-amber-950">
        <strong>Research hypotheses only—not treatment recommendations.</strong>
        <span className="hidden sm:inline"> Clinical efficacy and safety require independent validation.</span>
      </div>
      <div className="mx-auto flex min-h-[4.25rem] max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <a href="#top" className="group flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700" aria-label="PharmaSure home">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-teal-300">
            <Activity className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block text-lg font-semibold tracking-tight text-slate-950">PharmaSure</span>
            <span className="hidden text-[11px] text-slate-600 sm:block">Evidence-aware drug repurposing</span>
          </span>
        </a>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] text-slate-600 md:flex" aria-live="polite">
            <span className={`h-2 w-2 rounded-full ${healthIsOk ? 'bg-emerald-600' : healthError ? 'bg-rose-500' : 'bg-slate-400'}`} aria-hidden="true" />
            <span>{healthLabel}</span>
            {health?.corpus_size !== undefined && <span className="text-slate-400">· {health.corpus_size.toLocaleString()} passages in corpus</span>}
          </div>
          <button
            type="button"
            onClick={onOpenAbout}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
            aria-label="Open methodology and data information"
          >
            <Info className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">Methodology &amp; data</span>
            <span className="sm:hidden">About</span>
          </button>
          <a
            href="/gradio"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden min-h-9 items-center gap-1 rounded-lg px-2.5 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 lg:inline-flex"
            title="Open the preserved legacy Gradio interface"
          >
            Legacy interface <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        </div>
      </div>
    </header>
  );
};
