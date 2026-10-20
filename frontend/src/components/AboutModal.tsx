import React, { useEffect, useRef } from 'react';
import { BookOpen, Database, FlaskConical, ShieldCheck, X } from 'lucide-react';
import { HealthResponse } from '../types';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: HealthResponse | null;
  onSelectDisease: (disease: string) => void;
}

const METHOD_STEPS = [
  ['Candidate generation', 'The knowledge graph returns drug–disease hypotheses and its candidate order. This is separate from literature evidence.'],
  ['Literature evidence', 'Retrieved passages are associated with candidates, scored with a backend heuristic, and linked to generated claims where available.'],
  ['Citation checks', 'Source identity and quotation matching are shown separately when the API returns those fields. Verification does not validate the scientific interpretation.'],
  ['Fragility audit', 'Leave-one-study-out scenarios recompute the score and evidence rank after removing each eligible source unit.'],
];

const LIMITATIONS = [
  'Candidate rankings are research hypotheses, not treatment recommendations.',
  'Missing evidence does not prove ineffectiveness; graph coverage does not guarantee literature coverage.',
  'Citation verification does not establish clinical validity, safety, or causal relevance.',
  'Distinct PMIDs do not necessarily represent independent experiments.',
  'Ranking stability is not proof of efficacy.',
  'Benchmark results, when available, apply only to the tested queries and conditions.',
];

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose, health, onSelectDisease }) => {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const dialog = document.getElementById('about-modal');
        const focusable = dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])');
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const supportedDiseases = health?.supported_diseases?.filter((disease) => disease.trim()) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5" role="presentation">
      <button type="button" aria-label="Close methodology dialog" className="absolute inset-0 cursor-default bg-slate-950/45" onClick={onClose} />
      <section
        id="about-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="about-modal-title"
        className="relative z-10 flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="rounded-xl border border-slate-200 bg-white p-2 text-teal-800"><Database className="h-5 w-5" aria-hidden="true" /></span>
            <div>
              <h2 id="about-modal-title" className="text-base font-semibold text-slate-950 sm:text-lg">Methodology &amp; data status</h2>
              <p className="text-xs text-slate-500">What PharmaSure calculates—and what it cannot conclude</p>
            </div>
          </div>
          <button ref={closeButtonRef} type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700" aria-label="Close methodology and data dialog">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="overflow-y-auto px-4 py-5 sm:px-6">
          <div className="grid gap-3 sm:grid-cols-2">
            {METHOD_STEPS.map(([title, text], index) => (
              <div key={title} className="rounded-xl border border-slate-200 bg-white p-3.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-teal-900">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-50 font-mono">{index + 1}</span>
                  {title}
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600">{text}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900"><ShieldCheck className="h-4 w-4 text-teal-800" aria-hidden="true" />Response-level backend metadata</h3>
            <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
              <div><dt className="text-slate-500">Health status</dt><dd className="mt-0.5 font-medium text-slate-800">{health?.status || 'Not available'}</dd></div>
              <div><dt className="text-slate-500">Indexed passages reported</dt><dd className="mt-0.5 font-mono font-medium text-slate-800">{health?.corpus_size === undefined ? 'Not reported' : health.corpus_size.toLocaleString()}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-500">Configured data sources (health endpoint)</dt><dd className="mt-0.5 text-slate-800">{health?.data_sources?.length ? health.data_sources.join(' · ') : 'Not reported'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-500">Live literature retrieval / per-query provenance</dt><dd className="mt-0.5 text-slate-800">Not exposed by the current query response. The UI will not claim a live search occurred.</dd></div>
            </dl>
          </div>

          {supportedDiseases.length > 0 && (
            <div className="mt-4">
              <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600"><FlaskConical className="h-4 w-4 text-teal-800" aria-hidden="true" />Examples reported by this backend</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {supportedDiseases.slice(0, 12).map((disease) => (
                  <button key={disease} type="button" onClick={() => { onSelectDisease(disease); onClose(); }} className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:border-teal-700 hover:text-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
                    {disease}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-500">A listed disease is not proof that its literature is covered locally.</p>
            </div>
          )}

          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <h3 className="text-sm font-semibold text-amber-950">Limitations</h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-5 text-amber-950">
              {LIMITATIONS.map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4 text-xs text-slate-600">
            <BookOpen className="h-4 w-4 text-slate-500" aria-hidden="true" />
            <span>Ranking comparisons are shown only when measured outcomes and protocol metadata are returned; no winner is inferred.</span>
          </div>
        </div>

        <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-4 py-3 sm:px-6">
          <button type="button" onClick={onClose} className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2">Close</button>
        </div>
      </section>
    </div>
  );
};
