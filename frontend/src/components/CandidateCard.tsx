import React from 'react';
import { BookOpen, ChevronRight, FlaskConical } from 'lucide-react';
import { Candidate } from '../types';

interface CandidateCardProps {
  candidate: Candidate;
  isSelected: boolean;
  evidenceRecordCount: number;
  distinctPmids: number;
  onSelect: (candidate: Candidate) => void;
}

function scoreLabel(value: number | undefined): string {
  return value === undefined ? 'Not returned' : value.toFixed(3);
}

export const CandidateCard: React.FC<CandidateCardProps> = ({
  candidate,
  isSelected,
  evidenceRecordCount,
  distinctPmids,
  onSelect,
}) => {
  const name = candidate.drug?.trim() || 'Candidate name unavailable';
  const rank = candidate.rank;
  const direction = candidate.direction;
  const tier = candidate.evidence?.tier;

  return (
    <button
      type="button"
      onClick={() => onSelect(candidate)}
      aria-pressed={isSelected}
      className={`candidate-row w-full rounded-xl border p-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2 ${
        isSelected
          ? 'border-teal-700 bg-teal-50/60 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 flex h-8 min-w-8 items-center justify-center rounded-lg border font-mono text-xs font-semibold ${
          isSelected ? 'border-teal-200 bg-white text-teal-800' : 'border-slate-200 bg-slate-50 text-slate-600'
        }`} aria-label={rank === undefined ? 'Knowledge-graph rank not returned' : `Knowledge-graph rank ${rank}`}>
          {rank === undefined ? '—' : `#${rank}`}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-start justify-between gap-2">
            <span className="font-semibold leading-5 text-slate-900">{name}</span>
            <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 ${isSelected ? 'text-teal-700' : 'text-slate-400'}`} aria-hidden="true" />
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-600">
            <span className="inline-flex items-center gap-1 font-medium">
              <FlaskConical className="h-3.5 w-3.5 text-teal-700" aria-hidden="true" />
              <span>Literature score</span>
              <span className="font-mono text-slate-900">{scoreLabel(candidate.evidence?.score)}</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <BookOpen className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
              <span>{evidenceRecordCount} source {evidenceRecordCount === 1 ? 'record' : 'records'}</span>
            </span>
          </span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-slate-500">
            {distinctPmids > 0 && <span>{distinctPmids} distinct PMID{distinctPmids === 1 ? '' : 's'}</span>}
            {candidate.evidence?.support !== undefined && (
              <span>{candidate.evidence.support} passage{candidate.evidence.support === 1 ? '' : 's'} counted by score</span>
            )}
            {candidate.kg_score !== undefined && <span>KG score: {candidate.kg_score === null ? 'not reported' : candidate.kg_score.toFixed(3)}</span>}
            {tier && <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5">{tier} tier</span>}
            {direction && <span>Returned direction: {direction}</span>}
            {evidenceRecordCount === 0 && <span>No candidate-linked source records returned</span>}
          </span>
        </span>
      </div>
    </button>
  );
};
