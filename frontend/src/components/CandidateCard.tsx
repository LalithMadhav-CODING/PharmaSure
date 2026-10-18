import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  FileText,
  ChevronDown,
  ChevronUp,
  BookmarkCheck,
  FlaskConical,
  BookOpen,
  Info
} from 'lucide-react';
import { Candidate, Claim, EvidenceTier, EvidenceDirection } from '../types';

interface CandidateCardProps {
  candidate: Candidate;
  onOpenCitation: (citationId: string | number, relatedQuote?: string) => void;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({ candidate, onOpenCitation }) => {
  const [isWhyExpanded, setIsWhyExpanded] = useState(false);

  // Direction badge styling
  const renderDirectionBadge = (dir: EvidenceDirection) => {
    switch (dir) {
      case 'Positive':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Positive Evidence</span>
          </span>
        );
      case 'Negative':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-300">
            <XCircle className="w-3.5 h-3.5 text-rose-600" />
            <span>Negative Evidence</span>
          </span>
        );
      case 'Mixed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-300">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Mixed Evidence</span>
          </span>
        );
      case 'Uncertain':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
            <span>Uncertain</span>
          </span>
        );
    }
  };

  // Tier badge styling
  const renderTierBadge = (tier: EvidenceTier) => {
    switch (tier) {
      case 'Strong':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Strong Tier</span>
          </span>
        );
      case 'Moderate':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Moderate Tier</span>
          </span>
        );
      case 'Preliminary':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-800 border border-rose-200">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>Preliminary Tier</span>
          </span>
        );
    }
  };

  const scoreFormatted = (candidate.evidence.score ?? 0).toFixed(3);
  const scorePct = Math.round((candidate.evidence.score ?? 0) * 100);

  return (
    <article className="bg-white border border-slate-200 rounded-xl shadow-2xs hover:shadow-sm transition-all overflow-hidden mb-4">
      {/* Card Header Bar */}
      <div className="p-4 sm:p-5 border-b border-slate-100">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-sm font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
              #{candidate.rank}
            </span>
            <h4 className="text-xl font-bold text-navy-900 tracking-tight">
              {candidate.drug}
            </h4>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {renderDirectionBadge(candidate.direction)}
            {renderTierBadge(candidate.evidence.tier)}
          </div>
        </div>

        {/* Primary Scientific Rationale */}
        <p className="mt-3 text-sm text-slate-800 leading-relaxed font-normal bg-slate-50/70 p-3 rounded-lg border border-slate-100">
          {candidate.reason}
        </p>

        {/* Metadata Badges & Evidence Score */}
        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1 bg-slate-100 px-2.5 py-1 rounded text-slate-700 font-medium">
              <BookOpen className="w-3.5 h-3.5 text-slate-500" />
              <span>{candidate.evidence.support} supporting {candidate.evidence.support === 1 ? 'study' : 'studies'}</span>
            </span>

            <span className="inline-flex items-center gap-1 bg-slate-100 px-2.5 py-1 rounded text-slate-700 font-medium capitalize">
              <FlaskConical className="w-3.5 h-3.5 text-slate-500" />
              <span>Best study: {candidate.evidence.best_study_type.replace('_', ' ')}</span>
            </span>
          </div>

          {/* Evidence Score Indicator */}
          <div className="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200/80">
            <div>
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Evidence Score:
                </span>
                <span className="font-mono font-bold text-navy-900 text-xs">
                  {scoreFormatted}
                </span>
              </div>
              <span className="text-[10px] text-slate-400 block -mt-0.5">
                Experimental heuristic (not probability)
              </span>
            </div>
            <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden shrink-0">
              <div
                className={`h-full rounded-full ${
                  candidate.evidence.tier === 'Strong'
                    ? 'bg-emerald-500'
                    : candidate.evidence.tier === 'Moderate'
                    ? 'bg-amber-500'
                    : 'bg-rose-500'
                }`}
                style={{ width: `${scorePct}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Claims and Citations List (PRD §9.G: Visible by default) */}
      <div className="p-4 sm:p-5 bg-white space-y-3">
        <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
          <BookmarkCheck className="w-4 h-4 text-brand-600" />
          <span>Factual Claims &amp; Verified Literature Citations</span>
        </h5>

        {candidate.claims.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No specific literature claims returned for this candidate.</p>
        ) : (
          <div className="space-y-2.5">
            {candidate.claims.map((claim, idx) => (
              <div
                key={idx}
                className="text-xs sm:text-sm bg-slate-50/50 rounded-lg p-3 border border-slate-200/80 hover:border-slate-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <p className="text-slate-800 leading-normal">
                      {claim.text}
                    </p>

                    {/* Verification Status Banner */}
                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      {claim.verification_status === 'verified' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Verified against source</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                          <AlertTriangle className="w-3 h-3 text-amber-600" />
                          <span>Needs review: {claim.verification_reason || 'Paraphrase or mismatch'}</span>
                        </span>
                      )}

                      {/* Clickable Citation Badges */}
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] text-slate-400 font-medium">Source:</span>
                        {claim.citations.map((cid, cIdx) => (
                          <button
                            key={cIdx}
                            type="button"
                            onClick={() => onOpenCitation(cid, claim.quote)}
                            className="inline-flex items-center px-1.5 py-0.5 rounded font-mono text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-300 hover:bg-brand-100 hover:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-500 transition-colors"
                            title={`Inspect source passage [${cid}]`}
                          >
                            [{cid}]
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Expandable "Why this drug?" Section (PRD §9.H) */}
      <div className="border-t border-slate-100 bg-slate-50/60">
        <button
          onClick={() => setIsWhyExpanded(!isWhyExpanded)}
          className="w-full px-4 sm:px-5 py-2.5 flex items-center justify-between text-xs font-semibold text-slate-700 hover:text-navy-900 transition-colors focus:outline-none"
          aria-expanded={isWhyExpanded}
        >
          <span className="flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-brand-600" />
            <span>Why this drug? (Deep Evidence Breakdown &amp; Limitations)</span>
          </span>
          <span className="flex items-center gap-1 text-slate-500 text-[11px]">
            {isWhyExpanded ? 'Collapse analysis' : 'Expand analysis'}
            {isWhyExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </button>

        {isWhyExpanded && (
          <div className="px-4 sm:px-5 pb-4 pt-1 text-xs text-slate-700 space-y-3 border-t border-slate-200/60 bg-white">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <h6 className="font-semibold text-navy-900 mb-1 flex items-center gap-1">
                  <span>Evidence Formula Breakdown</span>
                </h6>
                <p className="text-slate-600 text-[11px] leading-relaxed">
                  Calculated as: <strong>0.25 × Semantic Relevance + 0.35 × Passage Support + 0.40 × Study Quality</strong>.
                  Clinical trial evidence is weighted at 1.0, cohort studies at 0.7, preclinical at 0.4, and reviews at 0.3.
                </p>
              </div>

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <h6 className="font-semibold text-navy-900 mb-1 flex items-center gap-1">
                  <span>Reported Direction &amp; Nuance</span>
                </h6>
                <p className="text-slate-600 text-[11px] leading-relaxed">
                  Candidate is tagged as <strong>{candidate.direction}</strong> based on trial outcome flags and retrieved abstracts.
                  {candidate.direction === 'Mixed' && ' Trials or observational studies report conflicting clinical or cognitive endpoints.'}
                  {candidate.direction === 'Negative' && ' Rigorous phase II/III trials demonstrated lack of efficacy or safety futility.'}
                  {candidate.direction === 'Positive' && ' Significant therapeutic benefit reported across evaluated study designs.'}
                  {candidate.direction === 'Uncertain' && ' Evidence is primarily early preclinical or lacking prospective human confirmation.'}
                </p>
              </div>
            </div>

            {/* Verbatim Excerpts Table */}
            <div>
              <h6 className="font-semibold text-navy-900 mb-1.5">Supporting Quotations from Corpus:</h6>
              <div className="space-y-1.5">
                {candidate.claims.map((claim, qIdx) => (
                  <div key={qIdx} className="p-2.5 bg-amber-50/40 rounded border border-amber-200/50 text-[11px]">
                    <div className="flex items-center justify-between text-amber-900 font-medium mb-1">
                      <span>Passage quote for Citation {claim.citations.map(c => `[${c}]`).join(' ')}:</span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {claim.verification_status === 'verified' ? '✓ exact match' : '⚠️ review required'}
                      </span>
                    </div>
                    <blockquote className="italic text-slate-700 pl-2 border-l-2 border-amber-400">
                      &ldquo;{claim.quote || 'No explicit verbatim quotation supplied by model.'}&rdquo;
                    </blockquote>
                  </div>
                ))}
              </div>
            </div>

            {/* Scientific Caveat */}
            <div className="text-[11px] text-slate-500 pt-1 border-t border-slate-100 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              <span>
                <strong>Research Note:</strong> Higher citation counts or higher evidence scores do not equate to regulatory approval or established clinical efficacy.
              </span>
            </div>
          </div>
        )}
      </div>
    </article>
  );
};
