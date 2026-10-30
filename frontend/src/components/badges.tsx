import type { Reliability } from "../api";

export function ReliabilityBadge({ value }: { value: Reliability | string }) {
  const label: Record<string, string> = {
    verified: "Verified",
    unverified: "Unverified",
    missing_source: "No source",
    invalid_source_url: "Invalid URL",
  };
  return (
    <span className={`badge rel-${value}`} title={reliabilityHint(value)}>
      {label[value] ?? value}
    </span>
  );
}

function reliabilityHint(value: string): string {
  switch (value) {
    case "verified":
      return "Passed an explicit trusted verification process.";
    case "unverified":
      return "A usable source URL exists, but the claim has not been independently checked.";
    case "missing_source":
      return "No source URL was provided for this signal.";
    case "invalid_source_url":
      return "The source URL is malformed or uses an unsupported scheme.";
    default:
      return value;
  }
}

export function OriginBadge({ origin }: { origin: "sample" | "live" }) {
  if (origin === "sample") {
    return (
      <span className="badge origin-sample" title="Bundled demo dataset, not a live discovery">
        SAMPLE
      </span>
    );
  }
  return (
    <span className="badge origin-live" title="Collected from a live configured source">
      LIVE
    </span>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  const tier = score >= 70 ? "high" : score >= 40 ? "mid" : "low";
  return <span className={`badge score-${tier}`}>{score}</span>;
}

export function TagChip({ tag }: { tag: string }) {
  const label = tag.replace(/_/g, " ");
  return <span className="chip">{label}</span>;
}
