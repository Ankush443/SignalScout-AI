import type { Diagnostics, SourceReport } from "../api";

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="diag-metric">
      <span className="diag-value">{value}</span>
      <span className="diag-label">{label}</span>
    </div>
  );
}

/**
 * Ingestion diagnostics for the most recent refresh: what was fetched,
 * what was normalized, what stayed unmatched and what failed.
 */
export default function DiagnosticsPanel({
  diagnostics,
  sources,
}: {
  diagnostics: Diagnostics;
  sources: SourceReport[];
}) {
  return (
    <section className="panel diagnostics" aria-label="Ingestion diagnostics">
      <div className="panel-header">
        <h2>Ingestion diagnostics</h2>
        <span className="muted">
          last refresh · {diagnostics.sources_succeeded}/
          {diagnostics.sources_configured} sources ok
        </span>
      </div>

      <div className="diag-grid">
        <Metric
          label="Sources configured"
          value={diagnostics.sources_configured}
        />
        <Metric
          label="Sources failed"
          value={diagnostics.sources_failed}
        />
        <Metric
          label="Feed entries fetched"
          value={diagnostics.feed_entries_fetched}
        />
        <Metric
          label="Entries normalized"
          value={diagnostics.entries_normalized}
        />
        <Metric
          label="Funding signals"
          value={diagnostics.funding_signals}
        />
        <Metric label="Hiring signals" value={diagnostics.hiring_signals} />
        <Metric
          label="Unmatched signals"
          value={diagnostics.unmatched_signals}
        />
        <Metric
          label="Duplicates removed"
          value={diagnostics.duplicate_records_removed}
        />
        <Metric
          label="Processing errors"
          value={diagnostics.processing_errors}
        />
      </div>

      <p className="muted diag-note">
        Unmatched signals keep no guessed company — they stay listed in{" "}
        <code>GET /signals</code> with <code>company_name: null</code> for
        inspection. One failed feed never stops the others.
      </p>

      <ul className="diag-sources">
        {sources.map((source) => (
          <li key={source.name} className="diag-source">
            <span
              className={`dot ${
                source.status === "ok" ? "dot-ok" : "dot-error"
              }`}
              aria-hidden="true"
            />
            <span className="diag-source-name">{source.name}</span>
            <span className="muted">
              {source.status === "ok"
                ? `${source.classified}/${source.entries} entries classified`
                : source.error}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
