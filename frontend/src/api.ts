/**
 * API client and data types for the SignalScout AI dashboard.
 *
 * The backend base URL comes from VITE_API_URL (defaults to the deployed
 * SignalScout AI backend at https://signalscout-ai.onrender.com).
 * All types mirror the JSON returned by src/api/routes.py.
 */

const BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  "https://signalscout-ai.onrender.com";

export const apiBase = BASE;

export type SignalType = "funding" | "hiring";
export type Reliability =
  | "missing_source"
  | "invalid_source_url"
  | "unverified"
  | "verified";

export interface SourceRef {
  source_name: string | null;
  source_url: string | null;
  source_published_at: string | null;
  source_reliability?: Reliability;
}

export interface Signal {
  signal_id: string | null;
  company_name: string | null;
  signal_type: SignalType;
  title: string | null;
  description: string | null;
  amount: string | null;
  detected_at: string | null;
  source_name: string | null;
  source_url: string | null;
  source_published_at: string | null;
  verification_status: string;
  data_origin: "sample" | "live";
  source_reliability: Reliability;
  duplicate_count?: number;
  merged_signal_ids?: string[];
  supporting_sources?: SourceRef[];
  duplicate_records?: Signal[];
  merge_reason?: string;
}

export interface ScoreBreakdown {
  factor: string;
  points: number;
  max_points: number;
  explanation: string;
}

export interface Opportunity {
  company: string;
  company_key: string;
  opportunity_score: number;
  reasons: string[];
  score_breakdown: ScoreBreakdown[];
  evidence_count: number;
  funding_signals: number;
  hiring_signals: number;
  ai_hiring_signals: number;
  latest_signal_date: string | null;
  opportunity_tags: string[];
  data_origins: string[];
}

export interface CompanyProfile {
  company: string;
  company_key: string;
  funding_signals: number;
  hiring_signals: number;
  ai_hiring_signals: number;
  recent_funding: boolean;
  signals: Signal[];
  data_origins: string[];
  latest_signal_date: string | null;
  opportunity_tags: string[];
  opportunity?: Opportunity;
}

export interface SourceReport {
  name: string;
  records: number;
  entries: number;
  classified: number;
  unclassified: number;
  status: "ok" | "error";
  error: string | null;
}

export interface Diagnostics {
  sources_configured: number;
  sources_succeeded: number;
  sources_failed: number;
  feed_entries_fetched: number;
  entries_normalized: number;
  funding_signals: number;
  hiring_signals: number;
  unmatched_signals: number;
  duplicate_records_removed: number;
  processing_errors: number;
  errors: string[];
}

export interface Stats {
  generated_at: string;
  reference_date: string;
  total_signals: number;
  funding_signals: number;
  hiring_signals: number;
  unmatched_signals: number;
  companies: number;
  opportunities: number;
  duplicates_merged: number;
  records_ingested: number;
  records_skipped_duplicate: number;
  records_skipped_malformed: number;
  data_origins: Record<string, number>;
  diagnostics: Diagnostics;
  sources: SourceReport[];
  errors: string[];
}

export interface CompanyDetail {
  company: string;
  profile: CompanyProfile;
  opportunity: Opportunity | null;
  signals: Signal[];
  generated_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new Error(
      `Cannot reach the SignalScout API at ${BASE}. ` +
        "Is the backend running?",
    );
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* keep the status code as the message */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function fetchStats(): Promise<Stats> {
  return request<Stats>("/stats");
}

export async function fetchCompanies(): Promise<CompanyProfile[]> {
  const body = await request<{ count: number; companies: CompanyProfile[] }>(
    "/companies?limit=500",
  );
  return body.companies;
}

export async function fetchCompanyDetail(name: string): Promise<CompanyDetail> {
  return request<CompanyDetail>(`/companies/${encodeURIComponent(name)}`);
}

export async function triggerIngest(): Promise<void> {
  await request("/ingest", { method: "POST" });
}
