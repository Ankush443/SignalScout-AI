import type { CompanyProfile, Signal } from "../api";
import { OriginBadge, ReliabilityBadge, ScoreBadge, TagChip } from "./badges";
import { EmptyState } from "./States";

function latestFundingAmount(signals: Signal[]): string | null {
  const funding = signals
    .filter((s) => s.signal_type === "funding" && s.amount)
    .sort((a, b) => (b.detected_at ?? "").localeCompare(a.detected_at ?? ""));
  return funding.length > 0 ? funding[0].amount : null;
}

function uniqueReliabilities(signals: Signal[]): string[] {
  return [...new Set(signals.map((s) => s.source_reliability))];
}

export default function OpportunityFeed({
  companies,
  onSelect,
  hasActiveFilters,
  onClearFilters,
}: {
  companies: CompanyProfile[];
  onSelect: (name: string) => void;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
}) {
  if (companies.length === 0) {
    return (
      <EmptyState
        title={
          hasActiveFilters
            ? "No companies match the current filters"
            : "No signals have been detected yet"
        }
        hint={
          hasActiveFilters
            ? "Try lowering the minimum score or clearing the search."
            : "Configure data sources or enable the sample dataset, then refresh."
        }
      />
    );
  }

  return (
    <div className="table-wrap">
      <table className="feed-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Company</th>
            <th>Score</th>
            <th>Funding</th>
            <th>AI hiring</th>
            <th>Evidence</th>
            <th>Latest signal</th>
            <th>Source reliability</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((company, index) => {
            const opportunity = company.opportunity;
            const amount = latestFundingAmount(company.signals);
            const reliabilities = uniqueReliabilities(company.signals);
            const isSample = company.data_origins.includes("sample");
            return (
              <tr
                key={company.company_key}
                onClick={() => onSelect(company.company)}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter") onSelect(company.company);
                }}
                title={`Open details for ${company.company}`}
              >
                <td className="rank">{index + 1}</td>
                <td>
                  <div className="company-cell">
                    <span className="company-name">{company.company}</span>
                    <div className="chip-row">
                      {isSample ? <OriginBadge origin="sample" /> : null}
                      {company.data_origins.includes("live") ? (
                        <OriginBadge origin="live" />
                      ) : null}
                      {company.opportunity_tags.map((tag) => (
                        <TagChip key={tag} tag={tag} />
                      ))}
                    </div>
                  </div>
                </td>
                <td>
                  <ScoreBadge score={opportunity?.opportunity_score ?? 0} />
                </td>
                <td>
                  {company.funding_signals > 0 ? (
                    <span title={`${company.funding_signals} funding signal(s)`}>
                      {company.funding_signals}
                      {amount ? ` · ${amount}` : ""}
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  {company.ai_hiring_signals > 0 ? (
                    <span
                      title={`${company.ai_hiring_signals} AI-related hiring signal(s) out of ${company.hiring_signals} hiring signal(s)`}
                    >
                      {company.ai_hiring_signals} AI role
                      {company.ai_hiring_signals > 1 ? "s" : ""}
                      {company.ai_hiring_signals < company.hiring_signals
                        ? ` / ${company.hiring_signals}`
                        : ""}
                    </span>
                  ) : company.hiring_signals > 0 ? (
                    <span className="muted" title="Hiring signals present, none AI-specific">
                      {company.hiring_signals} non-AI
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  {opportunity ? (
                    <span title="Number of supporting signals">
                      {opportunity.evidence_count} signal
                      {opportunity.evidence_count === 1 ? "" : "s"}
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="date-cell">{company.latest_signal_date ?? "—"}</td>
                <td>
                  <div className="chip-row">
                    {reliabilities.map((value) => (
                      <ReliabilityBadge key={value} value={value} />
                    ))}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {hasActiveFilters ? (
        <div className="table-footer">
          <button className="btn btn-ghost" onClick={onClearFilters}>
            Clear filters
          </button>
        </div>
      ) : null}
    </div>
  );
}
