import React, { useEffect, useRef } from 'react';
import { AlertCircle, BookOpen, ExternalLink, FileCode, X } from 'lucide-react';
import { Passage } from '../types';
import { pubmedUrlFor, safeSourceUrl } from '../services/evidence';

interface CitationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citationId: string | number | null;
  passages: Passage[];
  targetQuote?: string;
  sourceUrl?: string;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  isOpen,
  onClose,
  citationId,
  passages,
  targetQuote = '',
  sourceUrl,
}) => {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const drawer = document.getElementById('citation-drawer');
        const focusable = drawer?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])');
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

  if (!isOpen || citationId === null) return null;

  const matchedPassage = passages.find((passage) => String(passage.id) === String(citationId));
  const matchingSourceUrl = safeSourceUrl(sourceUrl)
    || safeSourceUrl(matchedPassage?.source_url)
    || pubmedUrlFor(matchedPassage?.pmid);
  const validQuote = targetQuote.trim();
  const passageText = matchedPassage?.text || '';
  const exactQuoteIndex = validQuote ? passageText.indexOf(validQuote) : -1;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="citation-drawer-title">
      <button type="button" className="absolute inset-0 bg-slate-950/40" onClick={onClose} aria-label="Close source passage viewer" />
      <aside id="citation-drawer" tabIndex={-1} className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col border-l border-slate-200 bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 bg-slate-50 px-4 py-4 sm:px-6">
          <div className="flex min-w-0 items-start gap-3">
            <span className="rounded-lg border border-slate-200 bg-white p-2 text-teal-800"><BookOpen className="h-5 w-5" aria-hidden="true" /></span>
            <div className="min-w-0">
              <h2 id="citation-drawer-title" className="break-words text-base font-semibold text-slate-950">
                {matchedPassage?.title || `Source passage [${citationId}]`}
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                {matchedPassage?.source || 'Source name not returned'}
                {matchedPassage?.pmid ? ` · PMID ${matchedPassage.pmid}` : ''}
              </p>
            </div>
          </div>
          <button ref={closeButtonRef} type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700" aria-label="Close citation drawer">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6">
          {!matchedPassage ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 text-amber-700" aria-hidden="true" />
                <div>
                  <h3 className="text-sm font-semibold text-amber-950">Passage not included in this response</h3>
                  <p className="mt-1 text-xs leading-5 text-amber-950">The returned identifier [{citationId}] is not present in the response&apos;s passage collection. No source text is fabricated here.</p>
                  {matchingSourceUrl && (
                    <a href={matchingSourceUrl} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-teal-800 hover:underline">
                      Open returned source link <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <>
              <dl className="grid gap-2 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Publication year</dt>
                  <dd className="mt-1 text-sm font-medium text-slate-900">{matchedPassage.year ?? 'Not returned'}</dd>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Publication type</dt>
                  <dd className="mt-1 text-sm font-medium capitalize text-slate-900">{matchedPassage.pub_type?.replace(/_/g, ' ') || 'Not returned'}</dd>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Stable identifier</dt>
                  <dd className="mt-1 break-all font-mono text-sm font-medium text-slate-900">{matchedPassage.pmid ? `PMID ${matchedPassage.pmid}` : 'PMID not returned'}</dd>
                </div>
              </dl>

              {validQuote && (
                <section className="rounded-xl border border-teal-200 bg-teal-50/60 p-4" aria-labelledby="returned-quote-heading">
                  <h3 id="returned-quote-heading" className="text-xs font-semibold text-teal-950">Exact returned quotation</h3>
                  <blockquote className="mt-2 border-l-2 border-teal-700 pl-3 text-sm leading-6 text-slate-800">“{validQuote}”</blockquote>
                  {exactQuoteIndex < 0 && <p className="mt-2 text-[11px] leading-4 text-teal-950">This quotation was not found as an exact contiguous substring in the passage returned to the browser. It is shown as supplied by the API; no source offset is inferred.</p>}
                </section>
              )}

              <section aria-labelledby="passage-text-heading">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h3 id="passage-text-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-600">Returned passage text</h3>
                  {matchingSourceUrl && (
                    <a href={matchingSourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-teal-800 hover:underline">
                      Open source <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  )}
                </div>
                <div className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-800">
                  {exactQuoteIndex >= 0 && validQuote ? (
                    <>
                      {passageText.slice(0, exactQuoteIndex)}
                      <mark className="rounded bg-amber-200 px-0.5 text-slate-950">{passageText.slice(exactQuoteIndex, exactQuoteIndex + validQuote.length)}</mark>
                      {passageText.slice(exactQuoteIndex + validQuote.length)}
                    </>
                  ) : passageText || 'Passage text was not returned.'}
                </div>
              </section>

              <div className="rounded-xl border border-slate-200 bg-white p-3 text-[11px] leading-5 text-slate-600">
                <p className="flex items-center gap-1.5 font-semibold text-slate-800"><FileCode className="h-3.5 w-3.5" aria-hidden="true" />Verification boundary</p>
                <p className="mt-1">The evidence record shows the verification state returned by the backend. A source identity or quotation match does not establish candidate relevance, validate an interpretation, or demonstrate clinical efficacy or safety.</p>
              </div>
            </>
          )}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 sm:px-6">
          {matchingSourceUrl ? (
            <a href={matchingSourceUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-teal-900 hover:bg-teal-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
              Read source <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            </a>
          ) : <span className="text-xs text-slate-500">No safe external source URL returned</span>}
          <button type="button" onClick={onClose} className="min-h-9 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Close</button>
        </footer>
      </aside>
    </div>
  );
};
