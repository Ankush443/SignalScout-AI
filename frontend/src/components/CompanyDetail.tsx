import type { CompanyDetail, Signal, SourceRef } from "../api";
import { OriginBadge, ReliabilityBadge, ScoreBadge, TagChip } from "./badges";

function SignalCard({ signal }: { signal: Signal }) {
  const sources = signal.supporting_sources ?? [];
  const evidence: SourceRef[] = sources.length > 0
    ? sources
    : [
        {
          source_name: signal.source_name,
          source_url: signal.source_url,
          source_published_at: signal.source_published_at,
        },
      ];
  const isMerged = (signal.duplicate_count ?? 1) > 1;
  return (
    <article className="signal-card">
      <header className="signal-header">
        <span className={`pill pill-${signal.signal_type}`}>
          {signal.signal_type}
        </span>
        <h4>{signal.title ?? "Untitled signal"}</h4>
        <OriginBadge origin={signal.data_origin} />
        <ReliabilityBadge value={signal.source_reliability} />
      </header>
      {signal.description ? <p>{signal.description}</p> : null}
      <dl className="signal-meta">
        {signal.amount ? (
          <div>
            <dt>Amount</dt>
            <dd>{signal.amount}</dd>
          </div>
        ) : null}
        <div>
          <dt>Date</dt>
          <dd>{signal.detected_at ?? "unknown"}</dd>
        </div>
        {signal.signal_id ? (
          <div>
            <dt>Signal ID</dt>
            <dd className="mono">{signal.signal_id}</dd>
          </div>
        ) : null}
      </dl>

      <div className="evidence">
        <h5>Source evidence</h5>
        {evidence.map((source, index) => (
          <div className="evidence-row" key={index}>
            <span className="evidence-name">{source.source_name ?? "Unnamed source"}</span>
            {source.source_url ? (
              <a
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {source.source_url}
              </a>
            ) : (
              <span className="muted">no URL provided</span>
            )}
            <span className="muted">{source.source_published_at ?? ""}</span>
            {source.source_reliability ? (
              <ReliabilityBadge value={source.source_reliability} />
            ) : null}
          </div>
        ))}
        {isMerged ? (
          <p className="merge-note">
            Grouped from {signal.duplicate_count} reports
            {signal.merged_signal_ids?.length
              ? ` (IDs: ${signal.merged_signal_ids.join(", ")})`
              : ""}
            . {signal.merge_reason}
          </p>
        ) : null}
        <p className="verification-note">
          Verification status: <strong>{signal.verification_status}</strong>.
          A URL alone does not verify a claim.
        </p>
      </div>
    </article>
  );
}

export default function CompanyDetailView({
  detail,
  onClose,
  loading,
  error,
  onRetry,
}: {
  detail: CompanyDetail | null;
  onClose: () => void;
  loading: boolean;
  error: string;
  onRetry: () => void;
}) {
  return (
    <div className="overlay" onClick={onClose} role="presentation">
      <aside
        className="detail-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-label="Company details"
      >
        <header className="detail-header">
          <div>
            {loading ? (
              <p className="muted">Loading company…</p>
            ) : detail ? (
              <>
                <h2>{detail.company}</h2>
                <div className="chip-row">
                  {detail.profile.data_origins.includes("sample") ? (
                    <OriginBadge origin="sample" />
                  ) : null}
                  {detail.profile.data_origins.includes("live") ? (
                    <OriginBadge origin="live" />
                  ) : null}
                  {detail.profile.opportunity_tags.map((tag) => (
                    <TagChip key={tag} tag={tag} />
                  ))}
                </div>
              </>
            ) : null}
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </header>

        {error ? (
          <div className="state-block error" role="alert">
            <p className="state-title">Could not load company details</p>
            <p className="state-hint">{error}</p>
            <button className="btn" onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : null}

        {!error && !loading && detail ? (
          <>
            <section className="detail-section">
              <h3>Overview</h3>
              <div className="overview-grid">
                <div>
                  <span className="metric-value">
                    {detail.opportunity?.opportunity_score ?? 0}
                  </span>
                  <span className="metric-label">Opportunity score</span>
                </div>
                <div>
                  <span className="metric-value">
                    {detail.profile.funding_signals}
                  </span>
                  <span className="metric-label">Funding signals</span>
                </div>
                <div>
                  <span className="metric-value">
                    {detail.profile.hiring_signals}
                  </span>
                  <span className="metric-label">Hiring signals</span>
                </div>
                <div>
                  <span className="metric-value">
                    {detail.profile.ai_hiring_signals}
                  </span>
                  <span className="metric-label">AI hiring signals</span>
                </div>
              </div>
              <p className="muted">
                Latest signal: {detail.profile.latest_signal_date ?? "unknown"}
              </p>
            </section>

            {detail.opportunity ? (
              <section className="detail-section">
                <h3>
                  Score breakdown{" "}
                  <ScoreBadge score={detail.opportunity.opportunity_score} />
                </h3>
                <table className="breakdown-table">
                  <tbody>
                    {detail.opportunity.score_breakdown.map((row) => (
                      <tr key={row.factor}>
                        <td className="factor">{row.factor.replace(/_/g, " ")}</td>
                        <td className="points">
                          {row.points}/{row.max_points}
                        </td>
                        <td>{row.explanation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="score-note">
                  The score is a transparent priority heuristic (0-100),
                  not a prediction of commercial intent.
                </p>
              </section>
            ) : null}

            <section className="detail-section">
              <h3>Detected signals ({detail.signals.length})</h3>
              {detail.signals.map((signal, index) => (
                <SignalCard key={signal.signal_id ?? index} signal={signal} />
              ))}
            </section>
          </>
        ) : null}
      </aside>
    </div>
  );
}
