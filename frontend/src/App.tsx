import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchCompanies,
  fetchCompanyDetail,
  fetchStats,
  triggerIngest,
  type CompanyDetail,
  type CompanyProfile,
  type Stats,
} from "./api";
import CompanyDetailView from "./components/CompanyDetail";
import DiagnosticsPanel from "./components/Diagnostics";
import OpportunityFeed from "./components/OpportunityFeed";
import Overview from "./components/Overview";
import { EmptyState, ErrorState, LoadingState } from "./components/States";

type SignalFilter = "all" | "funding" | "hiring" | "both";

interface Filters {
  signalFilter: SignalFilter;
  minScore: number;
  query: string;
}

const DEFAULT_FILTERS: Filters = {
  signalFilter: "all",
  minScore: 0,
  query: "",
};

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const loadAll = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [nextStats, nextCompanies] = await Promise.all([
        fetchStats(),
        fetchCompanies(),
      ]);
      setStats(nextStats);
      setCompanies(nextCompanies);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError("");
    try {
      await triggerIngest();
      const [nextStats, nextCompanies] = await Promise.all([
        fetchStats(),
        fetchCompanies(),
      ]);
      setStats(nextStats);
      setCompanies(nextCompanies);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setRefreshing(false);
    }
  }, []);

  const openCompany = useCallback(async (name: string) => {
    setSelected(name);
    setDetail(null);
    setDetailError("");
    setDetailLoading(true);
    try {
      setDetail(await fetchCompanyDetail(name));
    } catch (cause) {
      setDetailError(cause instanceof Error ? cause.message : "Unknown error");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const filteredCompanies = useMemo(() => {
    const query = filters.query.trim().toLowerCase();
    const result = companies.filter((company) => {
      const score = company.opportunity?.opportunity_score ?? 0;
      if (score < filters.minScore) return false;
      if (query && !company.company.toLowerCase().includes(query)) {
        return false;
      }
      switch (filters.signalFilter) {
        case "funding":
          return company.funding_signals > 0;
        case "hiring":
          return company.hiring_signals > 0;
        case "both":
          return company.funding_signals > 0 && company.hiring_signals > 0;
        default:
          return true;
      }
    });
    return result.sort(
      (a, b) =>
        (b.opportunity?.opportunity_score ?? 0) -
        (a.opportunity?.opportunity_score ?? 0),
    );
  }, [companies, filters]);

  const hasActiveFilters =
    filters.signalFilter !== "all" ||
    filters.minScore > 0 ||
    filters.query.trim() !== "";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ◎
          </span>
          <div>
            <h1>SignalScout AI</h1>
            <p>Business opportunity intelligence — funding &amp; AI hiring signals</p>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="badge api-badge" title="Backend base URL">
            API
          </span>
          <button
            className="btn"
            onClick={() => void refresh()}
            disabled={refreshing || loading}
          >
            {refreshing ? "Refreshing…" : "Refresh data"}
          </button>
        </div>
      </header>

      {stats && stats.errors.length > 0 ? (
        <div className="banner banner-warn" role="alert">
          {stats.errors.length} source(s) failed on the last run:{" "}
          {stats.errors.join(" · ")}
        </div>
      ) : null}

      {error ? (
        <ErrorState message={error} onRetry={() => void loadAll()} />
      ) : loading ? (
        <LoadingState label="Running the signal pipeline…" />
      ) : stats ? (
        <main>
          <Overview stats={stats} />

          {stats.diagnostics ? (
            <DiagnosticsPanel
              diagnostics={stats.diagnostics}
              sources={stats.sources}
            />
          ) : null}

          <section className="filters" aria-label="Filters">
            <div className="filter-group">
              <span className="filter-label">Signals</span>
              <div className="segmented">
                {(
                  [
                    ["all", "All"],
                    ["funding", "Funding"],
                    ["hiring", "Hiring"],
                    ["both", "Both"],
                  ] as [SignalFilter, string][]
                ).map(([value, label]) => (
                  <button
                    key={value}
                    className={
                      filters.signalFilter === value ? "active" : ""
                    }
                    onClick={() =>
                      setFilters((f) => ({ ...f, signalFilter: value }))
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <label className="filter-label" htmlFor="min-score">
                Min score: <strong>{filters.minScore}</strong>
              </label>
              <input
                id="min-score"
                type="range"
                min={0}
                max={100}
                step={5}
                value={filters.minScore}
                onChange={(event) =>
                  setFilters((f) => ({
                    ...f,
                    minScore: Number(event.target.value),
                  }))
                }
              />
            </div>

            <div className="filter-group grow">
              <label className="filter-label" htmlFor="company-search">
                Search
              </label>
              <input
                id="company-search"
                type="search"
                placeholder="Search by company name…"
                value={filters.query}
                onChange={(event) =>
                  setFilters((f) => ({ ...f, query: event.target.value }))
                }
              />
            </div>

            {hasActiveFilters ? (
              <button
                className="btn btn-ghost"
                onClick={() => setFilters(DEFAULT_FILTERS)}
              >
                Clear
              </button>
            ) : null}
          </section>

          <section className="panel" aria-label="Opportunity feed">
            <div className="panel-header">
              <h2>Opportunity feed</h2>
              <span className="muted">
                {filteredCompanies.length} of {companies.length} companies ·
                sorted by score
              </span>
            </div>
            <OpportunityFeed
              companies={filteredCompanies}
              onSelect={(name) => void openCompany(name)}
              hasActiveFilters={hasActiveFilters}
              onClearFilters={() => setFilters(DEFAULT_FILTERS)}
            />
          </section>

          <section className="panel legend" aria-label="How to read this">
            <h2>Reading the dashboard</h2>
            <ul>
              <li>
                <strong>Score</strong> — a transparent rule-based priority
                heuristic (0–100), not a prediction of purchase intent.
              </li>
              <li>
                <strong>Source reliability</strong> —{" "}
                <em>Unverified</em> means a usable URL exists but nobody has
                independently confirmed the claim; a URL is never treated as
                proof.
              </li>
              <li>
                <strong>SAMPLE</strong> — records come from the bundled demo
                dataset; LIVE records were collected from configured feeds.
              </li>
            </ul>
          </section>
        </main>
      ) : (
        <EmptyState
          title="No data loaded"
          hint="Start the backend and refresh the dashboard."
        />
      )}

      {selected ? (
        <CompanyDetailView
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onRetry={() => void openCompany(selected)}
          onClose={() => {
            setSelected(null);
            setDetail(null);
            setDetailError("");
          }}
        />
      ) : null}
    </div>
  );
}
