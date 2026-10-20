import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowDown, LoaderCircle, Microscope } from 'lucide-react';
import { AboutModal } from './components/AboutModal';
import { CandidateCard } from './components/CandidateCard';
import { CitationDrawer } from './components/CitationDrawer';
import { CoverageStatus } from './components/CoverageStatus';
import { EvidenceExplorer } from './components/EvidenceExplorer';
import { EvidenceFragilityProfile } from './components/EvidenceFragilityProfile';
import { RankingBenchmarkPanel } from './components/RankingBenchmarkPanel';
import { Header } from './components/Header';
import { KnownIndications } from './components/KnownIndications';
import { SearchSection } from './components/SearchSection';
import { SearchSummary } from './components/SearchSummary';
import { StatusAlert } from './components/StatusAlert';
import { queryDisease, fetchHealth } from './services/api';
import { distinctPmidCount, getCandidateEvidenceRecords } from './services/evidence';
import { Candidate, HealthResponse, Passage, QueryResponse } from './types';

const EMPTY_PASSAGES: Passage[] = [];

function candidateKey(candidate: Candidate, index: number): string {
  return `${candidate.rank ?? 'rank-na'}::${candidate.drug ?? 'name-na'}::${index}`;
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState('');
  const [activeQuery, setActiveQuery] = useState('');
  const [selectedCandidateKey, setSelectedCandidateKey] = useState<string | null>(null);
  const [clientDurationMs, setClientDurationMs] = useState<number | null>(null);
  const [isCitationOpen, setIsCitationOpen] = useState(false);
  const [selectedCitationId, setSelectedCitationId] = useState<string | number | null>(null);
  const [targetQuote, setTargetQuote] = useState('');
  const [citationSourceUrl, setCitationSourceUrl] = useState<string | undefined>();
  const [isAboutOpen, setIsAboutOpen] = useState(false);

  const requestNumberRef = useRef(0);
  const isLoadingRef = useRef(false);
  const activeQueryRef = useRef('');
  const initialDemoStartedRef = useRef(false);

  const handleSearch = async (query: string) => {
    const normalized = query.trim();
    if (!normalized) return;
    if (isLoadingRef.current && activeQueryRef.current.toLowerCase() === normalized.toLowerCase()) return;

    const requestNumber = ++requestNumberRef.current;
    activeQueryRef.current = normalized;
    isLoadingRef.current = true;
    setActiveQuery(normalized);
    setLastQuery(normalized);
    setIsLoading(true);
    setNetworkError(null);
    setResponse(null);
    setSelectedCandidateKey(null);
    setClientDurationMs(null);
    const startTime = performance.now();

    try {
      const result = await queryDisease(normalized);
      if (requestNumber !== requestNumberRef.current || !result.isLatest) return;
      setClientDurationMs(Math.round(performance.now() - startTime));
      setResponse(result.data);
    } catch (error) {
      if (requestNumber !== requestNumberRef.current) return;
      if (error instanceof DOMException && error.name === 'AbortError') return;
      const message = error instanceof Error ? error.message : 'The query request failed unexpectedly.';
      setNetworkError(message);
      setResponse(null);
    } finally {
      if (requestNumber === requestNumberRef.current) {
        isLoadingRef.current = false;
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    let mounted = true;
    fetchHealth()
      .then((metadata) => {
        if (!mounted) return;
        setHealth(metadata);
        setHealthError(null);
        setHealthLoading(false);
        const firstBackendExample = metadata.supported_diseases?.find((item) => item.trim());
        if (!initialDemoStartedRef.current && firstBackendExample) {
          initialDemoStartedRef.current = true;
          void handleSearch(firstBackendExample);
        }
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        setHealthError(error instanceof Error ? error.message : 'Backend health endpoint is unavailable.');
        setHealthLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const candidates = response?.results || [];
  const passages: Passage[] = response?.passages ?? EMPTY_PASSAGES;
  const knownIndications = response?.known_indications || [];
  const selectedCandidateIndex = candidates.findIndex(
    (candidate, index) => candidateKey(candidate, index) === selectedCandidateKey,
  );
  const selectedCandidate = selectedCandidateIndex >= 0 ? candidates[selectedCandidateIndex] : candidates[0];
  const selectedEvidenceRecords = useMemo(
    () => selectedCandidate ? getCandidateEvidenceRecords(selectedCandidate, passages) : [],
    [selectedCandidate, passages],
  );
  const selectedDistinctPmidCount = distinctPmidCount(selectedEvidenceRecords);
  const backendExamples = health?.supported_diseases?.filter((item) => item.trim()) || [];

  const handleOpenCitation = (citationId: string | number, quote?: string, sourceUrl?: string) => {
    setSelectedCitationId(citationId);
    setTargetQuote(quote || '');
    setCitationSourceUrl(sourceUrl);
    setIsCitationOpen(true);
  };

  const handleSelectCandidate = (candidate: Candidate) => {
    const index = candidates.indexOf(candidate);
    setSelectedCandidateKey(candidateKey(candidate, index));
  };

  const renderQueryState = () => {
    if (isLoading) {
      return (
        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-10 text-center shadow-sm" aria-live="polite" aria-busy="true">
          <LoaderCircle className="mx-auto h-7 w-7 animate-spin text-teal-800" aria-hidden="true" />
          <h2 className="mt-3 text-sm font-semibold text-slate-900">Waiting for the PharmaSure query API</h2>
          <p className="mt-1 text-xs text-slate-600">Query: <span className="font-medium">{activeQuery}</span></p>
          <p className="mx-auto mt-2 max-w-xl text-[11px] leading-5 text-slate-500">The interface will display the backend response when it arrives. No completion stage or source retrieval is assumed while the request is running.</p>
        </section>
      );
    }

    if (networkError) {
      return <StatusAlert status="network_error" message={networkError} onRetry={() => void handleSearch(lastQuery)} />;
    }

    if (!response) {
      if (healthLoading) {
        return (
          <section className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-center shadow-sm" aria-live="polite">
            <LoaderCircle className="mx-auto h-6 w-6 animate-spin text-slate-500" aria-hidden="true" />
            <p className="mt-2 text-sm font-medium text-slate-700">Checking backend health metadata</p>
            <p className="mt-1 text-xs text-slate-500">A health response does not imply disease-specific literature coverage.</p>
          </section>
        );
      }
      return (
        <section className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-9 text-center shadow-sm">
          <Microscope className="mx-auto h-7 w-7 text-teal-800" aria-hidden="true" />
          <h2 className="mt-3 text-base font-semibold text-slate-900">Start an evidence review</h2>
          <p className="mx-auto mt-1 max-w-xl text-xs leading-5 text-slate-600">Enter a disease to request graph candidates and inspect the returned candidate-specific literature and audit status.</p>
          {healthError && <p className="mx-auto mt-3 flex max-w-xl items-start justify-center gap-1.5 text-[11px] leading-5 text-amber-900"><AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />Health check unavailable: {healthError} You can still try the query endpoint.</p>}
        </section>
      );
    }

    if (response.status !== 'ok') {
      return (
        <div className="space-y-4">
          <CoverageStatus
            response={response}
            selectedRecordCount={0}
            distinctPmids={0}
            health={health}
          />
          <StatusAlert
            status={response.status}
            message={response.message || (response.reported_status ? `Backend status: ${response.reported_status}` : undefined)}
            query={response.disease?.name || response.query || lastQuery}
            supportedDiseases={backendExamples}
            onSelectDisease={(disease) => void handleSearch(disease)}
          />
          {knownIndications.length > 0 && (
            <KnownIndications indications={knownIndications} diseaseName={response.disease?.name || response.query || lastQuery} />
          )}
        </div>
      );
    }

    if (!Array.isArray(response.results)) {
      return (
        <div className="space-y-4">
          <CoverageStatus response={response} selectedRecordCount={0} distinctPmids={0} health={health} />
          <StatusAlert status="unknown" message="The backend marked the query as successful but did not return a candidate list. No empty candidate set is inferred from the missing field." />
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <SearchSummary response={response} />
        <CoverageStatus
          response={response}
          selectedCandidate={selectedCandidate}
          selectedRecordCount={selectedEvidenceRecords.length}
          distinctPmids={selectedDistinctPmidCount}
          health={health}
        />

        {knownIndications.length > 0 && (
          <KnownIndications indications={knownIndications} diseaseName={response.disease?.name || response.query || lastQuery} />
        )}

        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3 pt-2">
          <div>
            <h2 className="text-base font-semibold text-slate-950">Candidate investigation</h2>
            <p className="mt-0.5 text-xs text-slate-600">Knowledge-graph order and literature evidence score remain distinct.</p>
          </div>
          <nav aria-label="Candidate evidence sections" className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <a href="#candidate-ranking" className="rounded-lg px-2.5 py-1.5 font-medium text-teal-900 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Ranking</a>
            {selectedCandidate && <a href="#evidence-explorer" className="rounded-lg px-2.5 py-1.5 font-medium text-teal-900 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Evidence</a>}
            {selectedCandidate && <a href="#evidence-fragility" className="rounded-lg px-2.5 py-1.5 font-medium text-teal-900 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">Fragility profile</a>}
          </nav>
        </div>

        {candidates.length === 0 ? (
          <section id="candidate-ranking" className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center">
            <h3 className="text-sm font-semibold text-slate-900">No graph candidates returned</h3>
            <p className="mx-auto mt-1 max-w-xl text-xs leading-5 text-slate-600">This is the candidate list returned by the backend for this resolved query. It does not establish that the disease has no treatments or that no relevant literature exists.</p>
          </section>
        ) : (
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(17rem,0.84fr)_minmax(0,1.7fr)] xl:gap-5">
            <section id="candidate-ranking" aria-labelledby="candidate-ranking-heading" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-slate-50/70 p-3 sm:p-4">
              <div className="mb-3 flex items-end justify-between gap-2">
                <div>
                  <h3 id="candidate-ranking-heading" className="text-sm font-semibold text-slate-950">Candidate ranking</h3>
                  <p className="mt-0.5 text-[11px] text-slate-500">KG order · evidence score</p>
                </div>
                <span className="font-mono text-[11px] text-slate-500">{candidates.length} returned</span>
              </div>
              <div className="space-y-2">
                {candidates.map((candidate, index) => {
                  const key = candidateKey(candidate, index);
                  const evidenceRecords = getCandidateEvidenceRecords(candidate, passages);
                  const isSelected = selectedCandidateKey === key || (!selectedCandidateKey && index === 0);
                  return (
                    <CandidateCard
                      key={key}
                      candidate={candidate}
                      isSelected={isSelected}
                      evidenceRecordCount={evidenceRecords.length}
                      distinctPmids={distinctPmidCount(evidenceRecords)}
                      onSelect={handleSelectCandidate}
                    />
                  );
                })}
              </div>
              <p className="mt-3 rounded-lg border border-slate-200 bg-white p-2.5 text-[10px] leading-4 text-slate-600">
                The API returns candidate rank but no knowledge-graph numeric score in this response. Literature scores are experimental heuristics, not probabilities.
              </p>
            </section>

            {selectedCandidate ? (
              <div className="min-w-0 space-y-4">
                <EvidenceExplorer
                  candidate={selectedCandidate}
                  records={selectedEvidenceRecords}
                  onOpenCitation={handleOpenCitation}
                />
                <EvidenceFragilityProfile
                  candidateName={selectedCandidate.drug?.trim() || 'Candidate name unavailable'}
                  audit={selectedCandidate.evidence_audit}
                  auditSummary={response.evidence_audit_summary}
                  onOpenCitation={handleOpenCitation}
                />
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">
                Select a candidate to inspect its returned evidence.
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div id="top" className="min-h-screen bg-[#f5f7f7] text-slate-900">
      <Header health={health} healthError={healthError} onOpenAbout={() => setIsAboutOpen(true)} />
      <SearchSection
        onSearch={(query) => void handleSearch(query)}
        isLoading={isLoading}
        activeQuery={activeQuery}
        initialQuery={lastQuery}
        examples={backendExamples}
      />

      <main className="mx-auto w-full max-w-7xl space-y-5 px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
        {renderQueryState()}

        {response?.status === 'ok' && Array.isArray(response.results) && (
          <section id="methodology" className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
            <details>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
                <span>Methodology, limitations &amp; benchmark availability</span>
                <ArrowDown className="h-4 w-4 text-slate-500" aria-hidden="true" />
              </summary>
              <div className="mt-4 grid gap-4 border-t border-slate-200 pt-4 md:grid-cols-2">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">What each stage means</h3>
                  <ol className="mt-2 list-decimal space-y-1.5 pl-4 text-xs leading-5 text-slate-700">
                    <li><strong>Knowledge graph:</strong> generates drug–disease hypotheses and the displayed candidate order.</li>
                    <li><strong>Literature retrieval and score:</strong> ranks returned candidate-associated passages using a backend heuristic; not an efficacy probability.</li>
                    <li><strong>Citation and quotation checks:</strong> support source traceability only; they do not validate the clinical interpretation.</li>
                    <li><strong>Fragility analysis:</strong> recomputes the evidence score and evidence rank after removing each eligible source unit.</li>
                    <li><strong>Live retrieval:</strong> provider provenance and retrieval status are shown only when the query API returns them; absent fields are treated as unknown.</li>
                  </ol>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">Limitations &amp; comparisons</h3>
                  <ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-5 text-slate-700">
                    <li>Missing literature does not prove ineffectiveness; graph coverage does not guarantee literature coverage.</li>
                    <li>Distinct PMIDs do not necessarily mean independent experiments; independence is not established by PMID alone.</li>
                    <li>Ranking stability is not proof of efficacy or safety. Findings are not treatment recommendations.</li>
                    <li>Ranking or general-AI comparisons are shown only when the backend supplies a declared protocol and measured results; the interface does not infer a winner.</li>
                    <li>Benchmark conclusions apply only to the tested queries and conditions declared by the backend.</li>
                  </ul>
                  <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-5 text-slate-600">
                    Backend query runtime: {clientDurationMs === null ? 'not measured' : `${clientDurationMs} ms end-to-end in this browser`}. This is a client observation, not a benchmark result.
                  </p>
                </div>
              </div>
            </details>
            <div className="mt-4">
              <RankingBenchmarkPanel benchmark={response.ranking_benchmark} />
            </div>
          </section>
        )}
      </main>

      <footer className="mt-8 border-t border-slate-200 bg-white px-4 py-5 text-center text-[11px] text-slate-500">
        PharmaSure · TELEMEDICON 2026 · Evidence-aware drug repurposing
      </footer>

      <CitationDrawer
        isOpen={isCitationOpen}
        onClose={() => setIsCitationOpen(false)}
        citationId={selectedCitationId}
        passages={passages}
        targetQuote={targetQuote}
        sourceUrl={citationSourceUrl}
      />
      <AboutModal
        isOpen={isAboutOpen}
        onClose={() => setIsAboutOpen(false)}
        health={health}
        onSelectDisease={(disease) => void handleSearch(disease)}
      />
    </div>
  );
}

export default App;
