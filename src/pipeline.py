"""End-to-end pipeline orchestration for SignalScout AI.

Flow (spec section 5):

    Data Sources -> Ingestion -> Normalization -> Signal Detection
        -> Deduplication (ID-based, then cross-source)
        -> Source Reliability -> Company Matching
        -> Opportunity Evaluation -> API / Dashboard

The pipeline is pure orchestration: detection, deduplication, matching
and scoring stay in their own independently testable modules.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from src.company_matcher import match_companies
from src.config import Settings, load_settings
from src.deduplicator import deduplicate_cross_source
from src.ingestion import (
    BaseSource,
    RSSFeedSource,
    SampleSource,
    deduplicate_records,
    safe_fetch,
)
from src.normalizer import normalize_signals
from src.opportunity_scorer import rank_opportunities
from src.signal_detector import detect_signals, enrich_signals
from src.source_reliability import assess_source

logger = logging.getLogger(__name__)


def build_sources(settings: Settings) -> list[BaseSource]:
    """Assemble the configured source list (sample + RSS feeds)."""
    sources: list[BaseSource] = []
    if settings.include_sample_data:
        sources.append(SampleSource(settings.data_file))
    for url in settings.feed_urls:
        try:
            sources.append(RSSFeedSource(url))
        except ValueError:
            logger.warning("ignoring invalid feed URL from config: %r", url)
    return sources


def run_pipeline(settings: Optional[Settings] = None,
                 *, sources: Optional[Iterable[BaseSource]] = None,
                 seen_records: Optional[set] = None,
                 reference_date: Optional[date] = None) -> dict:
    """Run the full pipeline and return a JSON-serializable result.

    ``seen_records`` is a persistent identity set that prevents the same
    record from being ingested twice across runs (pass the same set to
    consecutive calls).  Source failures are collected, never raised.
    """
    settings = settings or load_settings()
    if sources is None:
        sources = build_sources(settings)
    seen = seen_records if seen_records is not None else set()

    source_reports: list[dict] = []
    errors: list[str] = []
    raw_records: list[dict] = []

    for source in sources:
        records, error = safe_fetch(source,
                                    timeout=settings.ingest_timeout_seconds)
        # RSS sources report how many feed entries they parsed vs. how
        # many classified as signals; the sample source emits typed
        # signal records directly.
        stats_attr = getattr(source, "last_fetch_stats", None)
        entries = (stats_attr or {}).get("items_parsed", len(records))
        classified = (stats_attr or {}).get("items_classified", len(records))
        report = {
            "name": source.name,
            "records": len(records),
            "entries": entries,
            "classified": max(classified, len(records)),
            "unclassified": max(0, entries - max(classified, len(records))),
            "status": "ok" if error is None else "error",
            "error": error,
        }
        source_reports.append(report)
        if error:
            errors.append(error)
        raw_records.extend(records)

    # Ingestion-level dedup: identical records are only processed once.
    fresh_records, _ = deduplicate_records(raw_records, seen)
    skipped_raw = len(raw_records) - len(fresh_records)

    # Normalization -> normalized signal schema.
    normalized = normalize_signals(fresh_records)
    skipped_malformed = len(fresh_records) - len(normalized)

    # Signal detection (classification + ID-based dedup + reliability
    # enrichment) using the existing, tested detector.
    detected = detect_signals({
        "name": None,
        "signals": normalized,
    })
    flat_signals: list[dict] = list(detected["funding"]) + list(
        detected["hiring"]
    )

    # Second stage: cross-source duplicate detection.
    deduplicated = deduplicate_cross_source(flat_signals)

    # Merged signals keep their primary record's reliability; supporting
    # sources get their own assessment computed from their URL only.
    for signal in deduplicated:
        for source_ref in signal.get("supporting_sources", []):
            source_ref["source_reliability"] = _assess_url(
                source_ref.get("source_url")
            )
    final_signals = enrich_signals(deduplicated)
    final_signals.sort(
        key=lambda s: (s.get("detected_at") or "", s.get("title") or ""),
        reverse=True,
    )

    duplicates_merged = sum(
        max(0, signal.get("duplicate_count", 1) - 1)
        for signal in final_signals
    )

    # Company matching and opportunity evaluation.
    profiles = match_companies(final_signals, reference_date=reference_date,
                               recent_window_days=settings.recent_window_days)
    opportunities = rank_opportunities(
        profiles, reference_date=reference_date,
        recent_window_days=settings.recent_window_days,
    )

    funding_count = sum(1 for s in final_signals
                        if s.get("signal_type") == "funding")
    hiring_count = sum(1 for s in final_signals
                       if s.get("signal_type") == "hiring")
    unmatched_count = sum(1 for s in final_signals
                          if not s.get("company_name"))
    origins: dict[str, int] = {}
    for signal in final_signals:
        origin = signal.get("data_origin") or "unknown"
        origins[origin] = origins.get(origin, 0) + 1

    # Observability: one flat block describing what this refresh did.
    sources_failed = sum(1 for r in source_reports
                         if r["status"] != "ok")
    entries_fetched = sum(r["entries"] for r in source_reports)
    id_duplicates_removed = len(normalized) - len(flat_signals)
    duplicate_records_removed = (skipped_raw + id_duplicates_removed
                                 + duplicates_merged)
    diagnostics = {
        "sources_configured": len(source_reports),
        "sources_succeeded": len(source_reports) - sources_failed,
        "sources_failed": sources_failed,
        "feed_entries_fetched": entries_fetched,
        "entries_normalized": len(normalized),
        "funding_signals": funding_count,
        "hiring_signals": hiring_count,
        "unmatched_signals": unmatched_count,
        "duplicate_records_removed": duplicate_records_removed,
        "processing_errors": len(errors),
        "errors": list(errors),
    }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_date": (reference_date or date.today()).isoformat(),
        "signals": final_signals,
        "companies": profiles,
        "opportunities": opportunities,
        "stats": {
            "total_signals": len(final_signals),
            "funding_signals": funding_count,
            "hiring_signals": hiring_count,
            "unmatched_signals": unmatched_count,
            "companies": len(profiles),
            "opportunities": len(opportunities),
            "duplicates_merged": duplicates_merged,
            "records_ingested": len(fresh_records),
            "records_skipped_duplicate": skipped_raw,
            "records_skipped_malformed": skipped_malformed,
            "data_origins": origins,
        },
        "diagnostics": diagnostics,
        "sources": source_reports,
        "errors": errors,
    }
    logger.info(
        "pipeline complete: %d signals, %d companies, %d opportunities, "
        "%d duplicate(s) merged",
        len(final_signals), len(profiles), len(opportunities),
        duplicates_merged,
    )
    return result


def _assess_url(url: Optional[str]) -> str:
    """Reliability label for a bare URL (no other signal fields)."""
    return assess_source({"source_url": url})
