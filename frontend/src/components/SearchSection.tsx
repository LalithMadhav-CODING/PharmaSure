import React, { useState, FormEvent } from 'react';
import { Search, Loader2, Sparkles, AlertCircle } from 'lucide-react';

interface SearchSectionProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  initialQuery?: string;
  onOpenAbout: () => void;
}

const PRIMARY_EXAMPLES = [
  "Alzheimer's disease",
  "Parkinson's disease",
  "Multiple myeloma"
];

const SECONDARY_EXAMPLES = [
  "Type 2 diabetes",
  "Asthma",
  "Huntington's disease (Abstain Test)"
];

export const SearchSection: React.FC<SearchSectionProps> = ({
  onSearch,
  isLoading,
  initialQuery = '',
  onOpenAbout
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setValidationError('Please enter a disease or condition name.');
      return;
    }
    setValidationError(null);
    onSearch(trimmed);
  };

  const handleExampleClick = (example: string) => {
    // Clean string if it contains test hint
    const cleanQuery = example.split(' (')[0];
    setQuery(cleanQuery);
    setValidationError(null);
    onSearch(cleanQuery);
  };

  return (
    <section className="bg-white border-b border-slate-200 py-6 sm:py-8 transition-all" aria-labelledby="search-heading">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <h2 id="search-heading" className="text-xl sm:text-2xl font-bold tracking-tight text-navy-900">
            Investigate Drug Repurposing Hypotheses
          </h2>
          <p className="mt-1 text-sm text-slate-700">
            Dense vector retrieval over biomedical literature with knowledge-graph candidate generation &amp; two-stage citation verification.
          </p>

          {/* Search Bar Form */}
          <form onSubmit={handleSubmit} className="mt-5 relative">
            <div className="flex flex-col sm:flex-row items-stretch gap-2.5 shadow-sm rounded-xl p-1 bg-white border-2 border-slate-200 focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-100 transition-all">
              <div className="relative flex-1 flex items-center pl-3">
                <Search className="w-5 h-5 text-slate-500 mr-2 shrink-0" aria-hidden="true" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  disabled={isLoading}
                  placeholder="e.g. Alzheimer's disease"
                  className="w-full text-sm sm:text-base bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none py-2 pr-3 disabled:opacity-50"
                  aria-label="Disease name input"
                />
                {query && !isLoading && (
                  <button
                    type="button"
                    onClick={() => setQuery('')}
                    className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 mr-1"
                    aria-label="Clear search input"
                  >
                    Clear
                  </button>
                )}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold text-white bg-brand-700 hover:bg-brand-800 active:bg-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-all shadow-xs"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white" aria-hidden="true" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-brand-200" aria-hidden="true" />
                    <span>Search Candidates</span>
                  </>
                )}
              </button>
            </div>

            {validationError && (
              <p className="mt-2 text-xs text-rose-600 flex items-center justify-center gap-1 font-medium">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>{validationError}</span>
              </p>
            )}
          </form>

          {/* Example Queries */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="text-slate-600 font-medium mr-1">Examples:</span>
            {PRIMARY_EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => handleExampleClick(example)}
                disabled={isLoading}
                className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
              >
                {example}
              </button>
            ))}
            <span className="text-slate-400">|</span>
            {SECONDARY_EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => handleExampleClick(example)}
                disabled={isLoading}
                className="px-2.5 py-1 rounded-md bg-white hover:bg-slate-50 text-slate-600 font-normal transition-colors border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
