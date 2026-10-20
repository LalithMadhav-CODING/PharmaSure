import React, { FormEvent, useEffect, useState } from 'react';
import { AlertCircle, ArrowRight, LoaderCircle, Search } from 'lucide-react';

interface SearchSectionProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  activeQuery?: string;
  initialQuery?: string;
  examples?: string[];
}

export const SearchSection: React.FC<SearchSectionProps> = ({
  onSearch,
  isLoading,
  activeQuery = '',
  initialQuery = '',
  examples = [],
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [validationError, setValidationError] = useState<string | null>(null);
  const submittingSameQuery = isLoading && query.trim().toLowerCase() === activeQuery.trim().toLowerCase();

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const submitQuery = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setValidationError('Enter a disease or condition name to begin.');
      return;
    }
    if (isLoading && trimmed.toLowerCase() === activeQuery.trim().toLowerCase()) return;
    setValidationError(null);
    setQuery(trimmed);
    onSearch(trimmed);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuery(query);
  };

  return (
    <section className="search-hero border-b border-slate-200" aria-labelledby="search-heading">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-teal-800">
            <span className="h-1.5 w-1.5 rounded-full bg-teal-700" aria-hidden="true" />
            Evidence-first research workspace
          </div>
          <h2 id="search-heading" className="max-w-3xl text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl lg:text-[2.15rem]">
            Trace the evidence. Challenge the ranking. Understand the uncertainty.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
            Explore knowledge-graph candidates, inspect candidate-linked literature, and test how rankings change when a source is removed.
          </p>

          <form onSubmit={handleSubmit} className="mt-6" noValidate>
            <label htmlFor="disease-search" className="mb-2 block text-xs font-semibold text-slate-700">
              Disease or condition
            </label>
            <div className="flex flex-col gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-teal-700 focus-within:ring-2 focus-within:ring-teal-700/15 sm:flex-row">
              <div className="flex min-w-0 flex-1 items-center gap-3 px-2 sm:px-3">
                <Search className="h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" />
                <input
                  id="disease-search"
                  name="disease"
                  type="search"
                  autoComplete="off"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  placeholder="Enter a disease name"
                  className="min-w-0 flex-1 bg-transparent py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 sm:text-base"
                  aria-invalid={Boolean(validationError)}
                  aria-describedby={validationError ? 'disease-search-error' : 'disease-search-help'}
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => {
                      setQuery('');
                      setValidationError(null);
                    }}
                    className="rounded px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                    aria-label="Clear disease name"
                  >
                    Clear
                  </button>
                )}
              </div>
              <button
                type="submit"
                disabled={submittingSameQuery}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-70 sm:min-w-44"
              >
                {submittingSameQuery ? (
                  <>
                    <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                    <span>Waiting for API</span>
                  </>
                ) : (
                  <>
                    <span>{isLoading ? 'Analyze new query' : 'Analyze disease'}</span>
                    <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </>
                )}
              </button>
            </div>
            <p id="disease-search-help" className="mt-2 text-xs text-slate-500">
              Queries are sent to the configured PharmaSure backend. A graph candidate is a hypothesis—not evidence of treatment efficacy.
            </p>
            {validationError && (
              <p id="disease-search-error" className="mt-2 flex items-center gap-1.5 text-xs font-medium text-rose-700" role="alert">
                <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                {validationError}
              </p>
            )}
          </form>

          {examples.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="Backend-supported disease examples">
              <span className="mr-1 text-xs font-medium text-slate-500">Examples from backend:</span>
              {examples.slice(0, 5).map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => submitQuery(example)}
                  disabled={isLoading && example.trim().toLowerCase() === activeQuery.trim().toLowerCase()}
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:border-teal-700 hover:text-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-60"
                >
                  {example}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
