import type { Stats } from "../api";

function Card({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: string;
}) {
  return (
    <div className="card metric">
      <span className={`metric-value ${accent ?? ""}`}>{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

export default function Overview({ stats }: { stats: Stats }) {
  const sampleCount = stats.data_origins?.sample ?? 0;
  const liveCount = stats.data_origins?.live ?? 0;
  return (
    <section className="overview" aria-label="Overview">
      <Card label="Companies tracked" value={stats.companies} />
      <Card
        label="Funding signals"
        value={stats.funding_signals}
        accent="funding-color"
      />
      <Card
        label="Hiring signals"
        value={stats.hiring_signals}
        accent="hiring-color"
      />
      <Card label="Opportunities" value={stats.opportunities} />
      <Card label="Duplicates merged" value={stats.duplicates_merged} />
      <Card
        label="Data sources"
        value={`${liveCount} live / ${sampleCount} sample`}
      />
    </section>
  );
}
