
import unittest
from datetime import date

from src.config import Settings
from src.ingestion.base import BaseSource, IngestionError
from src.pipeline import build_sources, run_pipeline

REFERENCE = date(2026, 10, 30)


class _BrokenSource(BaseSource):
    name = "broken live source"

    def fetch(self, timeout: float = 0.0):
        raise IngestionError("feed unreachable")


def sample_settings() -> Settings:
    return Settings(include_sample_data=True, feed_urls=[])


class TestSampleModePipeline(unittest.TestCase):
    """Sample mode must work offline with no feeds configured."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_pipeline(sample_settings(),
                                  reference_date=REFERENCE)

    def test_pipeline_produces_all_sections(self):
        for key in ("signals", "companies", "opportunities", "stats",
                    "sources", "errors", "generated_at"):
            self.assertIn(key, self.result)

    def test_sample_mode_has_no_errors(self):
        self.assertEqual(self.result["errors"], [])
        self.assertEqual(self.result["sources"][0]["status"], "ok")

    def test_stats_consistent_with_lists(self):
        stats = self.result["stats"]
        self.assertEqual(stats["total_signals"],
                         len(self.result["signals"]))
        self.assertEqual(stats["companies"],
                         len(self.result["companies"]))
        self.assertEqual(stats["opportunities"],
                         len(self.result["opportunities"]))
        self.assertEqual(
            stats["funding_signals"] + stats["hiring_signals"],
            stats["total_signals"],
        )

    def test_all_data_labeled_as_sample(self):
        self.assertEqual(self.result["stats"]["data_origins"],
                         {"sample": self.result["stats"]["total_signals"]})
        for signal in self.result["signals"]:
            self.assertEqual(signal["data_origin"], "sample")

    def test_cross_source_duplicate_merged(self):
        merged = [s for s in self.result["signals"]
                  if s.get("duplicate_count", 1) > 1]
        self.assertEqual(len(merged), 1)
        novaai = merged[0]
        self.assertEqual(novaai["company_name"], "NovaAI Technologies")
        self.assertEqual(len(novaai["supporting_sources"]), 2)
        self.assertGreaterEqual(
            self.result["stats"]["duplicates_merged"], 1)

    def test_id_duplicates_removed_before_output(self):
        ids = [s["signal_id"] for s in self.result["signals"]
               if s.get("signal_id")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_signals_sorted_newest_first(self):
        dates = [s["detected_at"] for s in self.result["signals"]
                 if s.get("detected_at")]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_reliability_labels_present(self):
        allowed = {"missing_source", "invalid_source_url",
                   "unverified", "verified"}
        for signal in self.result["signals"]:
            self.assertIn(signal["source_reliability"], allowed)

    def test_invalid_sample_url_flagged(self):
        frostline = [s for s in self.result["signals"]
                     if s["company_name"] == "Frostline Cold Chain"]
        self.assertEqual(len(frostline), 1)
        self.assertEqual(frostline[0]["source_reliability"],
                         "invalid_source_url")

    def test_missing_source_url_flagged(self):
        cloudstack = [s for s in self.result["signals"]
                      if s["company_name"] == "CloudStack Solutions"]
        self.assertEqual(cloudstack[0]["source_reliability"],
                         "missing_source")

    def test_opportunities_ranked_by_score(self):
        scores = [o["opportunity_score"]
                  for o in self.result["opportunities"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_opportunity_has_breakdown(self):
        for item in self.result["opportunities"]:
            self.assertEqual(len(item["score_breakdown"]), 4)
            total = sum(b["points"] for b in item["score_breakdown"])
            self.assertEqual(total, item["opportunity_score"])
            self.assertTrue(item["reasons"])


class TestPipelineResilience(unittest.TestCase):

    def test_one_broken_source_does_not_crash_pipeline(self):
        result = run_pipeline(
            Settings(include_sample_data=True, feed_urls=[]),
            sources=[_BrokenSource(),
                     *[s for s in build_sources(
                         sample_settings())]],
            reference_date=REFERENCE,
        )
        # Sample data still loads, failure is reported, not raised.
        self.assertGreater(result["stats"]["total_signals"], 0)
        self.assertTrue(any(
            "feed unreachable" in error for error in result["errors"]))
        broken = next(r for r in result["sources"]
                      if r["name"] == "broken live source")
        self.assertEqual(broken["status"], "error")

    def test_no_sources_returns_empty_not_crash(self):
        result = run_pipeline(sample_settings(), sources=[],
                              reference_date=REFERENCE)
        self.assertEqual(result["signals"], [])
        self.assertEqual(result["companies"], [])
        self.assertEqual(result["opportunities"], [])

    def test_all_failure_modes_isolated_in_one_run(self):
        # invalid URL string + broken source together: every failure is
        # reported, none is raised, sample data still loads.
        bad_settings = Settings(include_sample_data=True,
                                feed_urls=["not a valid url"])
        result = run_pipeline(
            bad_settings,
            sources=[_BrokenSource(), *build_sources(bad_settings)],
            reference_date=REFERENCE,
        )
        diag = result["diagnostics"]
        self.assertEqual(diag["sources_failed"], 2)
        self.assertEqual(diag["processing_errors"], 2)
        self.assertEqual(diag["sources_succeeded"], 1)
        self.assertGreater(result["stats"]["total_signals"], 0)

    def test_build_sources_respects_settings(self):
        self.assertEqual(build_sources(Settings(
            include_sample_data=False, feed_urls=[])), [])
        sources = build_sources(Settings(
            include_sample_data=True,
            feed_urls=["https://a.example.com/feed",
                       "not a url",
                       "https://b.example.com/feed"]))
        # Sample source + all three configured URLs: non-empty URLs are
        # accepted at construction and fail safely at fetch time.
        self.assertEqual(len(sources), 4)
        self.assertIn("sample", sources[0].name)

    def test_repeated_runs_stay_consistent(self):
        settings = sample_settings()
        first = run_pipeline(settings, reference_date=REFERENCE)
        second = run_pipeline(settings, reference_date=REFERENCE)
        self.assertEqual(first["stats"]["total_signals"],
                         second["stats"]["total_signals"])
        self.assertEqual(first["stats"]["records_skipped_duplicate"],
                         second["stats"]["records_skipped_duplicate"])


class _FeedStatsSource(BaseSource):
    """Simulates an RSS source that parsed more entries than it
    classified (real RSSFeedSource behavior via last_fetch_stats)."""

    name = "feed with stats"

    def fetch(self, timeout: float = 0.0):
        self.last_fetch_stats = {"items_parsed": 10,
                                 "items_classified": 3}
        return [
            {"signal_id": f"fs-{i}", "company_name": f"Test Co {i}",
             "signal_type": "funding", "title": f"Test Co {i} raises $5M",
             "source_url": f"https://example.com/{i}",
             "source_name": "feed with stats",
             "detected_at": "2026-10-01"}
            for i in range(3)
        ]


class TestIngestionDiagnostics(unittest.TestCase):
    """Every refresh must report structured diagnostics (spec 4)."""

    def test_sample_mode_diagnostics_complete(self):
        result = run_pipeline(sample_settings(),
                              reference_date=REFERENCE)
        diag = result["diagnostics"]
        self.assertEqual(diag["sources_configured"], 1)
        self.assertEqual(diag["sources_succeeded"], 1)
        self.assertEqual(diag["sources_failed"], 0)
        self.assertEqual(diag["processing_errors"], 0)
        self.assertEqual(diag["errors"], [])
        self.assertGreater(diag["feed_entries_fetched"], 0)
        self.assertGreater(diag["entries_normalized"], 0)
        self.assertGreater(diag["funding_signals"], 0)
        self.assertGreater(diag["hiring_signals"], 0)
        # Ingestion dedup + ID dedup + cross-source merges.
        self.assertGreaterEqual(diag["duplicate_records_removed"], 1)

    def test_unmatched_signals_reported_not_discarded(self):
        result = run_pipeline(sample_settings(),
                              reference_date=REFERENCE)
        unmatched = [s for s in result["signals"]
                     if not s.get("company_name")]
        self.assertEqual(result["diagnostics"]["unmatched_signals"],
                         len(unmatched))
        # The unmatched records themselves stay visible in /signals.
        for signal in unmatched:
            self.assertIn(signal, result["signals"])

    def test_failed_source_counted_not_fatal(self):
        result = run_pipeline(
            sample_settings(),
            sources=[_BrokenSource(),
                     *build_sources(sample_settings())],
            reference_date=REFERENCE,
        )
        diag = result["diagnostics"]
        self.assertEqual(diag["sources_configured"], 2)
        self.assertEqual(diag["sources_succeeded"], 1)
        self.assertEqual(diag["sources_failed"], 1)
        self.assertEqual(diag["processing_errors"], 1)
        self.assertEqual(len(diag["errors"]), 1)
        # Remaining sources still produced output.
        self.assertGreater(result["stats"]["total_signals"], 0)

    def test_feed_entry_counters_from_source_stats(self):
        result = run_pipeline(sample_settings(),
                              sources=[_FeedStatsSource()],
                              reference_date=REFERENCE)
        diag = result["diagnostics"]
        self.assertEqual(diag["feed_entries_fetched"], 10)
        self.assertEqual(diag["entries_normalized"], 3)
        report = result["sources"][0]
        self.assertEqual(report["entries"], 10)
        self.assertEqual(report["classified"], 3)
        self.assertEqual(report["unclassified"], 7)
        self.assertEqual(diag["processing_errors"], 0)


if __name__ == "__main__":
    unittest.main()
