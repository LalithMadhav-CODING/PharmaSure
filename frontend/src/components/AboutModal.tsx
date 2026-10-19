import React, { useEffect } from 'react';
import { X, Database, ShieldCheck, BookOpen, Layers, CheckCircle2, ExternalLink } from 'lucide-react';
import { HealthResponse } from '../types';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: HealthResponse | null;
  onSelectDisease: (disease: string) => void;
}

export const AboutModal: React.FC<AboutModalProps> = ({
  isOpen,
  onClose,
  health,
  onSelectDisease,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true" aria-labelledby="about-modal-title">
      <div className="flex min-h-screen items-center justify-center p-4 text-center sm:p-0">
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity" onClick={onClose} />

        <div className="relative transform overflow-hidden rounded-2xl bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-2xl border border-slate-200">
          {/* Header */}
          <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-brand-600 text-white shadow-xs">
                <Database className="w-5 h-5" />
              </span>
              <div>
                <h3 id="about-modal-title" className="text-lg font-bold text-navy-900">
                  About PharmaSure &amp; Biomedical Data
                </h3>
                <p className="text-xs text-slate-500">
                  Architecture, literature corpus provenance, and supported diseases
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-5 space-y-6 text-sm text-slate-700">
            {/* System Status & Corpus Size */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>Backend Health Status</span>
                </div>
                <div className="text-base font-bold text-navy-900 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>{health?.status === 'ok' ? 'Online & Healthy' : 'Connecting...'}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  FastAPI service with in-memory dense vector similarity index.
                </p>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-brand-600" />
                  <span>Literature Corpus Size</span>
                </div>
                <div className="text-base font-bold text-navy-900 font-mono">
                  {health ? health.corpus_size.toLocaleString() : '7,500'} passages
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Curated biomedical abstracts and knowledge-graph associations.
                </p>
              </div>
            </div>

            {/* Data Sources */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-brand-700" />
                <span>Primary Data Sources</span>
              </h4>
              <ul className="space-y-2 text-xs">
                <li className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-2.5">
                  <span className="font-bold text-navy-900 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                    EveryCure KG
                  </span>
                  <div>
                    <span className="font-medium text-slate-800">matrix-scores (39.4M drug-disease pairs)</span>
                    <p className="text-slate-500 text-[11px] mt-0.5">
                      Used for initial hypothesis candidate generation, known-indication filtering, and trial outcome labels.
                    </p>
                  </div>
                </li>

                <li className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-2.5">
                  <span className="font-bold text-navy-900 bg-white px-2 py-0.5 rounded border border-slate-200 shrink-0">
                    PubMed
                  </span>
                  <div>
                    <span className="font-medium text-slate-800">NCBI E-utilities &amp; Medline Abstracts</span>
                    <p className="text-slate-500 text-[11px] mt-0.5">
                      Peer-reviewed literature passages providing the exact textual basis for citation extraction and quote verification.
                    </p>
                  </div>
                </li>
              </ul>
            </div>

            {/* Supported Diseases */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Supported Diseases in Current Release:
              </h4>
              <div className="flex flex-wrap gap-2">
                {(health?.supported_diseases && health.supported_diseases.length > 0 ? health.supported_diseases : [
                  "Alzheimer's disease",
                  "Parkinson's disease",
                  "Multiple myeloma",
                  "Type 2 diabetes",
                  "Asthma"
                ]).map((dis) => (
                  <button
                    key={dis}
                    onClick={() => {
                      onSelectDisease(dis);
                      onClose();
                    }}
                    className="px-3 py-1.5 rounded-lg bg-brand-50 hover:bg-brand-100 text-brand-900 border border-brand-200 font-medium text-xs transition-colors flex items-center gap-1.5 group"
                  >
                    <span>{dis}</span>
                    <span className="text-[10px] text-brand-500 group-hover:text-brand-800">→</span>
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 mt-2">
                Click any disease above to immediately populate the search query and evaluate results.
              </p>
            </div>

            {/* Literature Note (PRD §12: Explicit statement) */}
            <div className="p-3 bg-amber-50/60 rounded-lg border border-amber-200/60 text-[11px] text-amber-900 space-y-1">
              <strong>Corpus inspection note:</strong> Example raw passages are not directly exposed by the health metadata endpoint. Use the query workflow to inspect verified excerpts.
            </div>
          </div>

          {/* Footer */}
          <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex items-center justify-between">
            <span className="text-xs text-slate-400">PharmaSure · Telemedicon 2026 · Digital Health Hackathon</span>
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-900 rounded-lg transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
