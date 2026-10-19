import React, { useEffect } from 'react';
import { X, ExternalLink, BookOpen, AlertCircle, CheckCircle2, Calendar, FileCode, Tag } from 'lucide-react';
import { Passage } from '../types';

interface CitationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citationId: string | number | null;
  passages: Passage[];
  targetQuote?: string;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  isOpen,
  onClose,
  citationId,
  passages,
  targetQuote = '',
}) => {
  // Handle Escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Resolve matching passage by id
  // Support both string and number comparisons (e.g. "1" == 1)
  const matchedPassage = passages.find(
    (p) => String(p.id).trim().toLowerCase() === String(citationId).trim().toLowerCase()
  );

  // Quote matching & highlighting algorithm
  const renderHighlightedPassage = (passageText: string, quote: string) => {
    if (!quote || !quote.trim()) {
      return <span>{passageText}</span>;
    }

    // Attempt direct case-insensitive match
    const lowerPassage = passageText.toLowerCase();
    const lowerQuote = quote.trim().toLowerCase();
    const index = lowerPassage.indexOf(lowerQuote);

    if (index !== -1) {
      const before = passageText.substring(0, index);
      const match = passageText.substring(index, index + quote.trim().length);
      const after = passageText.substring(index + quote.trim().length);

      return (
        <>
          <span>{before}</span>
          <mark className="quote-highlight font-medium">
            {match}
          </mark>
          <span>{after}</span>
        </>
      );
    }

    // Attempt normalized whitespace fuzzy match
    const normalize = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase();
    const normP = normalize(passageText);
    const normQ = normalize(quote);

    if (normP.includes(normQ)) {
      // Find approximate span in original text
      const firstWord = normQ.split(' ')[0];
      const lastWord = normQ.split(' ').slice(-1)[0];
      const startIdx = lowerPassage.indexOf(firstWord);
      const endWordIdx = lowerPassage.indexOf(lastWord, startIdx !== -1 ? startIdx : 0);

      if (startIdx !== -1 && endWordIdx !== -1 && endWordIdx + lastWord.length > startIdx) {
        const before = passageText.substring(0, startIdx);
        const match = passageText.substring(startIdx, endWordIdx + lastWord.length);
        const after = passageText.substring(endWordIdx + lastWord.length);

        return (
          <>
            <span>{before}</span>
            <mark className="quote-highlight font-medium">
              {match}
            </mark>
            <span>{after}</span>
          </>
        );
      }
    }

    // Match not found
    return (
      <div>
        <p className="mb-3 text-slate-800 leading-relaxed">{passageText}</p>
        <div className="p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            <strong>Quotation notice:</strong> Supporting quotation could not be matched exactly to the displayed passage.
          </span>
        </div>
      </div>
    );
  };

  const hasValidPmid = matchedPassage?.pmid && /^\d+$/.test(String(matchedPassage.pmid).trim());

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-white shadow-2xl border-l border-slate-200 flex flex-col h-full transform transition-all duration-300 ease-in-out">
          {/* Drawer Header */}
          <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-lg bg-brand-100 text-brand-800">
                <BookOpen className="w-5 h-5 text-brand-700" />
              </span>
              <div>
                <h3 id="drawer-title" className="text-base sm:text-lg font-bold text-navy-900 flex items-center gap-2">
                  <span>Source Passage [{citationId}]</span>
                  {matchedPassage && (
                    <span className="text-xs font-normal text-slate-500 uppercase tracking-wider bg-slate-200 px-2 py-0.5 rounded">
                      {matchedPassage.source}
                    </span>
                  )}
                </h3>
                <p className="text-xs text-slate-500">
                  Primary literature grounding for drug repurposing claims
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-colors"
              aria-label="Close citation drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
            {!matchedPassage ? (
              <div className="p-6 bg-slate-50 rounded-xl border border-slate-200 text-center space-y-2">
                <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-800">Passage Unavailable</h4>
                <p className="text-xs text-slate-500">
                  Citation identifier [{citationId}] was referenced in a claim, but is not present in the returned passage collection.
                </p>
              </div>
            ) : (
              <>
                {/* Passage Metadata Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Study Type</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {matchedPassage.pub_type?.replace('_', ' ') || 'Unspecified'}
                    </span>
                  </div>

                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Year Published</span>
                    <span className="font-semibold text-slate-800 font-mono">
                      {matchedPassage.year || 'N/A'}
                    </span>
                  </div>

                  <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 col-span-2 sm:col-span-1">
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">PubMed Identifier</span>
                    {hasValidPmid ? (
                      <a
                        href={`https://pubmed.ncbi.nlm.nih.gov/${matchedPassage.pmid}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono font-bold text-brand-700 hover:text-brand-900 inline-flex items-center gap-1 hover:underline"
                        title="Open citation directly in PubMed"
                      >
                        <span>PMID: {matchedPassage.pmid}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="font-mono text-slate-500">
                        {matchedPassage.pmid || 'No PMID available'}
                      </span>
                    )}
                  </div>
                </div>

                {/* Target Quote Highlighted Callout */}
                {targetQuote && (
                  <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-semibold text-amber-900">
                      <span className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-amber-600" />
                        <span>Supporting Claim Quote</span>
                      </span>
                      <span className="text-[10px] font-mono text-amber-700 uppercase bg-amber-100 px-1.5 py-0.5 rounded">
                        Target Quote
                      </span>
                    </div>
                    <blockquote className="text-xs text-amber-950 italic leading-relaxed pl-2 border-l-2 border-amber-400">
                      &ldquo;{targetQuote}&rdquo;
                    </blockquote>
                  </div>
                )}

                {/* Full Passage Text */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Corpus Passage Text
                  </h4>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-sm leading-relaxed text-slate-800 font-normal">
                    {renderHighlightedPassage(matchedPassage.text, targetQuote)}
                  </div>
                </div>

                {/* Verification Integrity Notice */}
                <div className="p-3 bg-slate-100 rounded-lg text-xs text-slate-600 space-y-1 border border-slate-200">
                  <div className="font-semibold text-navy-900 flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-slate-500" />
                    <span>Citation Verification Architecture</span>
                  </div>
                  <p className="text-[11px] leading-relaxed text-slate-500">
                    The PharmaSure verification engine validates that the cited drug and disease appear within the passage and checks claim substrings against indexed tokens before presentation.
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            {hasValidPmid ? (
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/${matchedPassage.pmid}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-300 rounded-lg hover:bg-brand-100 transition-colors"
              >
                <span>Read Full Paper on PubMed</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            ) : (
              <span className="text-xs text-slate-400">No external link available</span>
            )}

            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
