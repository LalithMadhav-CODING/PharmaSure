import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SearchSection } from './components/SearchSection';
import { SearchSummary } from './components/SearchSummary';
import { CandidateCard } from './components/CandidateCard';
import { CitationDrawer } from './components/CitationDrawer';
import { KnownIndications } from './components/KnownIndications';
import { AboutModal } from './components/AboutModal';
import { StatusAlert } from './components/StatusAlert';
import { fetchHealth, queryDisease } from './services/api';
import { QueryResponse, HealthResponse } from './types';
import { Loader2, FlaskConical, AlertCircle, FileSearch, Sparkles } from 'lucide-react';

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<string>('');
  const [clientDurationMs, setClientDurationMs] = useState<number | null>(null);

  // Citation Drawer state
  const [selectedCitationId, setSelectedCitationId] = useState<string | number | null>(null);
  const [targetQuote, setTargetQuote] = useState<string>('');
  const [isCitationOpen, setIsCitationOpen] = useState(false);

  // About modal state
  const [isAboutOpen, setIsAboutOpen] = useState(false);

  // Initial load: fetch health metadata and auto-populate demo query
  useEffect(() => {
    let isMounted = true;
    fetchHealth()
      .then((h) => {
        if (isMounted) setHealth(h);
      })
      .catch((err) => {
        console.warn('Backend health check error:', err);
      });

    // Auto-load default demo query for instant judge/user review
    handleSearch("Alzheimer's disease");

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSearch = async (query: string) => {
    if (!query.trim()) return;

    setIsLoading(true);
    setNetworkError(null);
    setLastQuery(query);
    const startTs = performance.now();

    try {
      const { data, isLatest } = await queryDisease(query);
      if (!isLatest) return; // avoid out-of-order race conditions

      const endTs = performance.now();
      setClientDurationMs(Math.round(endTs - startTs));
      setResponse(data);
    } catch (err: any) {
      if (err.name === 'AbortError') return; // ignore aborts
      setNetworkError(err.message || 'Failed to connect to the research API.');
      setResponse(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenCitation = (citationId: string | number, quote?: string) => {
    setSelectedCitationId(citationId);
    setTargetQuote(quote || '');
    setIsCitationOpen(true);
  };

  const candidates = response?.results || [];
  const knownIndications = response?.known_indications || [];
  const passages = response?.passages || [];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Persistent Top Navigation & Disclaimer */}
      <Header health={health} onOpenAbout={() => setIsAboutOpen(true)} />

      {/* Main Search Panel */}
      <SearchSection
        onSearch={handleSearch}
        isLoading={isLoading}
        initialQuery={lastQuery}
        onOpenAbout={() => setIsAboutOpen(true)}
      />

      {/* Main Content Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Loading State with Honest Neutral Message (PRD §8.C) */}
        {isLoading && (
          <div className="py-16 text-center space-y-4">
            <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-brand-50 border border-brand-200 shadow-sm animate-pulse">
              <Loader2 className="w-8 h-8 text-brand-700 animate-spin" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-navy-900">
                Analyzing literature and verifying evidence...
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Resolving disease ontology, scanning knowledge-graph repurposing signals, and conducting two-stage citation checks.
              </p>
            </div>
          </div>
        )}

        {/* Network or Server Error State */}
        {!isLoading && networkError && (
          <StatusAlert
            status="network_error"
            message={networkError}
            onRetry={() => handleSearch(lastQuery)}
          />
        )}

        {/* Unsupported Disease State */}
        {!isLoading && response && response.status === 'unsupported_disease' && (
          <StatusAlert
            status="unsupported_disease"
            message={response.message}
            query={response.query || lastQuery}
            supportedDiseases={health?.supported_diseases || [
              "Alzheimer's disease",
              "Parkinson's disease",
              "Multiple myeloma",
              "Type 2 diabetes",
              "Asthma"
            ]}
            onSelectDisease={(d) => handleSearch(d)}
          />
        )}

        {/* Insufficient Evidence State */}
        {!isLoading && response && response.status === 'insufficient_evidence' && (
          <div className="space-y-6">
            <StatusAlert
              status="insufficient_evidence"
              message={response.message}
              query={response.disease?.name || response.query || lastQuery}
            />

            {/* Display known indications if any were identified even under sparse repurposing evidence */}
            {knownIndications.length > 0 && (
              <KnownIndications
                indications={knownIndications}
                diseaseName={response.disease?.name || lastQuery}
              />
            )}
          </div>
        )}

        {/* Successful Query Results */}
        {!isLoading && response && response.status === 'ok' && (
          <div className="space-y-6">
            {/* Search Summary Header & Diagnostic Latencies */}
            <SearchSummary
              response={response}
              clientDurationMs={clientDurationMs}
            />

            {/* Section 1: Known Indications (PRD §11: Strictly separated from candidates) */}
            <KnownIndications
              indications={knownIndications}
              diseaseName={response.disease?.name || lastQuery}
            />

            {/* Section 2: Ranked Repurposing Candidates */}
            <section aria-labelledby="candidates-heading">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-brand-700 text-white">
                    <FlaskConical className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 id="candidates-heading" className="text-lg font-bold text-navy-900">
                      Ranked Repurposing Candidates
                    </h3>
                    <p className="text-xs text-slate-500">
                      Evaluated by evidence heuristic (study quality, support count, and semantic retrieval)
                    </p>
                  </div>
                </div>

                <span className="text-xs text-slate-500">
                  Showing <strong>{candidates.length}</strong> ranked hypotheses
                </span>
              </div>

              {candidates.length === 0 ? (
                <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
                  <FileSearch className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No candidates returned</p>
                  <p className="text-xs text-slate-500 mt-1">
                    The literature search returned 0 candidates matching the query criteria.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {candidates.map((candidate) => (
                    <CandidateCard
                      key={candidate.rank}
                      candidate={candidate}
                      onOpenCitation={handleOpenCitation}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </main>

      {/* Citation Viewer Drawer (PRD §10) */}
      <CitationDrawer
        isOpen={isCitationOpen}
        onClose={() => setIsCitationOpen(false)}
        citationId={selectedCitationId}
        passages={passages}
        targetQuote={targetQuote}
      />

      {/* About & Metadata Modal (PRD §12) */}
      <AboutModal
        isOpen={isAboutOpen}
        onClose={() => setIsAboutOpen(false)}
        health={health}
        onSelectDisease={(d) => handleSearch(d)}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-center text-xs text-slate-500 space-y-1">
        <p>
          Telemedicon 2026 Hackathon · <strong>PharmaSure / Telemedicon</strong> · Biomedical Literature RAG
        </p>
        <p className="text-slate-400 text-[11px]">
          Knowledge Graph: EveryCure matrix-scores · Dense Retrieval: nomic-embed-text · LLM: Gemini Flash · Verification: Two-Stage Substring Check
        </p>
      </footer>
    </div>
  );
}

export default App;
