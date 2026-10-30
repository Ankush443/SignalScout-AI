
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from src.ingestion import (
    BaseSource,
    IngestionError,
    RSSFeedSource,
    SampleSource,
    classify_text,
    deduplicate_records,
    safe_fetch,
)
from src.ingestion.rss_ingestion import extract_company_name
from src.normalizer import normalize_signal, to_iso_date

RSS_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Tech News Feed</title>
    <link>https://tech.example.com</link>
    <item>
      <title>NovaAI raises $12 million in Series A</title>
      <description>&lt;p&gt;The startup closed its round.&lt;/p&gt;</description>
      <link>https://tech.example.com/novaai-series-a</link>
      <pubDate>Thu, 29 Oct 2026 08:00:00 GMT</pubDate>
      <guid>https://tech.example.com/novaai-series-a</guid>
    </item>
    <item>
      <title>Initech hiring AI engineers</title>
      <description>Three new openings listed.</description>
      <link>https://tech.example.com/initech-jobs</link>
      <pubDate>Wed, 28 Oct 2026 09:30:00 GMT</pubDate>
      <guid>initech-jobs-1</guid>
    </item>
    <item>
      <title>Quarterly market update</title>
      <description>Indexes closed mixed today.</description>
      <link>https://tech.example.com/markets</link>
      <pubDate>Tue, 27 Oct 2026 16:00:00 GMT</pubDate>
      <guid>markets-1</guid>
    </item>
  </channel>
</rss>
"""

ATOM_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom VC Wire</title>
  <entry>
    <title>BrightPath secures seed funding</title>
    <summary>The company secured an early seed round.</summary>
    <link href="https://atom.example.com/brightpath"/>
    <published>2026-10-26T10:00:00Z</published>
    <id>entry-1</id>
  </entry>
</feed>
"""


def _mock_urlopen(payload: bytes):
    """Build a context-manager mock for urllib.request.urlopen."""
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = payload
    return mock.patch(
        "src.ingestion.rss_ingestion.urllib.request.urlopen",
        return_value=response,
    )


class _FailingSource(BaseSource):
    name = "always fails"

    def fetch(self, timeout: float = 0.0):
        raise OSError("network unreachable")


class _BadSource(BaseSource):
    name = "bad shape"

    def fetch(self, timeout: float = 0.0):
        return "not a list"


class _GoodSource(BaseSource):
    name = "good"

    def fetch(self, timeout: float = 0.0):
        return [{"title": "ok", "source_name": "good"}]


class TestClassifyText(unittest.TestCase):

    def test_funding_keywords(self):
        self.assertEqual(
            classify_text("NovaAI raises $12M in Series A"), "funding")
        self.assertEqual(
            classify_text("Company announces seed funding round"),
            "funding")
        self.assertEqual(
            classify_text("Venture capital investment completed"),
            "funding")

    def test_hiring_keywords(self):
        self.assertEqual(
            classify_text("Initech hiring AI engineers"), "hiring")
        self.assertEqual(
            classify_text("Looking for a machine learning engineer"),
            "hiring")
        self.assertEqual(
            classify_text("Openings for LLM engineers"), "hiring")

    def test_funding_wins_when_both_present(self):
        text = "Raises Series A to hire AI engineers"
        self.assertEqual(classify_text(text), "funding")

    def test_non_matching_text(self):
        self.assertIsNone(classify_text("Quarterly market update"))
        self.assertIsNone(classify_text(None))
        self.assertIsNone(classify_text("   "))


class TestExtractCompanyName(unittest.TestCase):

    def test_text_before_trigger_is_company(self):
        self.assertEqual(
            extract_company_name("NovaAI raises $12 million in Series A"),
            "NovaAI")
        self.assertEqual(
            extract_company_name("CloudStack is hiring backend engineers"),
            "CloudStack")

    def test_no_guessing_when_title_has_no_trigger(self):
        self.assertIsNone(
            extract_company_name("Quarterly market update"))
        self.assertIsNone(extract_company_name(None))
        self.assertIsNone(extract_company_name("  "))

    def test_generic_leads_rejected(self):
        self.assertIsNone(
            extract_company_name("AI startups raising funding fast"))

    def test_more_announcement_verbs_extracted(self):
        # Valuation, acquisition and banked-round headlines (verified
        # against real TechCrunch Venture feed titles).
        self.assertEqual(
            extract_company_name(
                "Blacksmith hits unicorn valuation after Sequoia "
                "leads Series C"),
            "Blacksmith")
        self.assertEqual(
            extract_company_name(
                "Warhound raises $200M to engineer war dogs"),
            "Warhound")
        self.assertEqual(
            extract_company_name(
                "Acme reaches $1B valuation amid AI demand"),
            "Acme")
        self.assertEqual(
            extract_company_name("Vantage nabs $40M seed round"),
            "Vantage")

    def test_descriptor_prefix_removed(self):
        # "Legal AI startup Legora ..." -> the real name after the
        # descriptor noun (verified against a live feed title).
        self.assertEqual(
            extract_company_name(
                "Legal AI startup Legora raises $550M Series E"),
            "Legora")
        self.assertEqual(
            extract_company_name(
                "Fintech firm PayFlow secures $30M Series A"),
            "PayFlow")
        # A descriptor with nothing after it stays ambiguous.
        self.assertIsNone(
            extract_company_name("That startup raises another round"))

    def test_location_and_backing_tags_dropped(self):
        self.assertEqual(
            extract_company_name(
                "OpenAI-backed Thrive Holdings acquires ADT"),
            "Thrive Holdings")
        self.assertEqual(
            extract_company_name(
                "NYC-based Robotix raises $12M Series A"),
            "Robotix")

    def test_punctuation_and_suffixes_handled(self):
        self.assertEqual(
            extract_company_name(
                "Nebula Robotics, Inc. raises $50M in Series B!"),
            "Nebula Robotics, Inc")
        self.assertEqual(
            extract_company_name(
                '"QuoteCo" secures $8M seed round'),
            "QuoteCo")

    def test_sentence_titles_rejected_not_guessed(self):
        # Verified against live feed titles that must stay unmatched.
        self.assertIsNone(extract_company_name(
            "Investors break down how founders can raise a Series A "
            "today"))
        self.assertIsNone(extract_company_name(
            "From 8VC to Benchmark, here\u2019s what\u2019s hiding "
            "in October SEC filings"))
        self.assertIsNone(extract_company_name(
            "What founders should know before they raise a Series A"))
        self.assertIsNone(extract_company_name(
            "Series A raises questions for the whole market"))
        # Possessives are sentences, not names.
        self.assertIsNone(extract_company_name(
            "Anthropic\u2019s backers raise questions before its IPO"))

    def test_general_news_noise_rejected_as_names(self):
        # Titles from public general-news feeds that must not produce a
        # guessed company name.
        self.assertIsNone(extract_company_name(
            "Police hiring clash, CARE funding, Cal Anderson meals"))
        self.assertIsNone(extract_company_name(
            "Financial services hiring is looking up, if you look at it "
            "right"))
        self.assertIsNone(extract_company_name(
            "Recruitment funding alone will not address construction's "
            "long-term skills shortage"))
        self.assertIsNone(extract_company_name(
            "Delaware retirement program raises questions about "
            "transparency in state hiring, oversight"))
        self.assertIsNone(extract_company_name(
            "Singapore merges 3 disability hiring grants to chase "
            "40% employment goal"))
        self.assertIsNone(extract_company_name(
            "Five Things I Learned in Hiring a Financial Adviser"))
        self.assertIsNone(extract_company_name(
            "Top Tech News Today: BlueChip Laptop, AI Finance Funding, "
            "Karnataka Hiring Row, Crypto Bankruptcy"))
        self.assertIsNone(extract_company_name(
            "School starts with new funds for teacher hiring, new "
            "standardized tests, more"))
        self.assertIsNone(extract_company_name(
            "U.S. Sen. Bernie Moreno is furious Columbus is recruiting "
            "nurses in Ghana"))
        self.assertIsNone(extract_company_name(
            "$10,000: Employers can apply for funding to hire "
            "apprentices in Canada"))
        self.assertIsNone(extract_company_name(
            "AI in finance hiring faces deep scepticism, ACCA survey "
            "finds"))

    def test_real_startup_announcement_extracted(self):
        # A genuine announcement headline names the company correctly.
        self.assertEqual(
            extract_company_name(
                "Metaview wants to eliminate recruiting grunt work and "
                "speed up hiring after raising $60M"),
            "Metaview")


class TestRSSFeedSource(unittest.TestCase):

    def test_invalid_url_rejected(self):
        with self.assertRaises(ValueError):
            RSSFeedSource("")
        with self.assertRaises(ValueError):
            RSSFeedSource("   ")

    def test_parses_rss_items_and_skips_unrelated(self):
        source = RSSFeedSource("https://tech.example.com/feed.xml")
        with _mock_urlopen(RSS_XML):
            records = source.fetch(timeout=1)

        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual(first["signal_type"], "funding")
        self.assertEqual(first["company_name"], "NovaAI")
        self.assertEqual(
            first["source_url"],
            "https://tech.example.com/novaai-series-a")
        self.assertEqual(first["source_name"], "Tech News Feed")
        self.assertEqual(first["signal_id"],
                         "https://tech.example.com/novaai-series-a")
        self.assertEqual(first["data_origin"], "live")
        # HTML in descriptions is stripped.
        self.assertNotIn("<p>", first["description"])

        second = records[1]
        self.assertEqual(second["signal_type"], "hiring")
        self.assertEqual(second["company_name"], "Initech")

    def test_fetch_stats_report_parsed_and_classified(self):
        source = RSSFeedSource("https://tech.example.com/feed.xml")
        with _mock_urlopen(RSS_XML):
            source.fetch(timeout=1)
        self.assertEqual(source.last_fetch_stats["items_parsed"], 3)
        self.assertEqual(source.last_fetch_stats["items_classified"], 2)

    def test_parses_atom_entries(self):
        source = RSSFeedSource("https://atom.example.com/feed",
                               name="Atom VC Wire")
        with _mock_urlopen(ATOM_XML):
            records = source.fetch(timeout=1)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["signal_type"], "funding")
        self.assertEqual(records[0]["company_name"], "BrightPath")
        self.assertEqual(records[0]["source_url"],
                         "https://atom.example.com/brightpath")
        self.assertEqual(records[0]["signal_id"], "entry-1")

    def test_network_failure_raises_ingestion_error(self):
        source = RSSFeedSource("https://down.example.com/feed")
        with mock.patch(
            "src.ingestion.rss_ingestion.urllib.request.urlopen",
            side_effect=urllib.error.URLError("no route to host"),
        ):
            with self.assertRaises(IngestionError):
                source.fetch(timeout=1)
        # Failure resets the counters instead of reporting stale data.
        self.assertEqual(source.last_fetch_stats,
                         {"items_parsed": 0, "items_classified": 0})

    def test_malformed_xml_raises_ingestion_error(self):
        source = RSSFeedSource("https://tech.example.com/feed")
        with _mock_urlopen(b"this is not <<xml"):
            with self.assertRaises(IngestionError):
                source.fetch(timeout=1)

    def test_unsupported_root_raises_ingestion_error(self):
        source = RSSFeedSource("https://tech.example.com/page")
        with _mock_urlopen(b"<html><body>hi</body></html>"):
            with self.assertRaises(IngestionError):
                source.fetch(timeout=1)

    def test_empty_feed_returns_no_records(self):
        empty = (b'<?xml version="1.0"?>'
                 b'<rss version="2.0"><channel><title>Empty</title>'
                 b'</channel></rss>')
        source = RSSFeedSource("https://tech.example.com/empty")
        with _mock_urlopen(empty):
            self.assertEqual(source.fetch(timeout=1), [])


class TestSampleSource(unittest.TestCase):

    def test_default_sample_file_loads(self):
        records = SampleSource().fetch()
        self.assertGreater(len(records), 0)
        self.assertTrue(all(
            r.get("data_origin") == "sample" for r in records))
        self.assertTrue(all(
            isinstance(r.get("company_name"), str) for r in records))

    def test_missing_file_raises_ingestion_error(self):
        source = SampleSource(Path("/nonexistent/sample.json"))
        with self.assertRaises(IngestionError):
            source.fetch()

    def test_malformed_json_raises_ingestion_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as handle:
            handle.write("{not json")
            path = Path(handle.name)
        try:
            with self.assertRaises(IngestionError):
                SampleSource(path).fetch()
        finally:
            path.unlink()

    def test_non_list_json_raises_ingestion_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as handle:
            json.dump({"companies": []}, handle)
            path = Path(handle.name)
        try:
            with self.assertRaises(IngestionError):
                SampleSource(path).fetch()
        finally:
            path.unlink()

    def test_null_signals_and_malformed_entries_skipped(self):
        payload = [
            {"name": "NoSignalsField"},
            {"name": "NullSignals", "signals": None},
            {"name": "Mixed",
             "signals": [{"signal_id": "1", "signal_type": "funding",
                          "title": "ok"}, "junk", None]},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as handle:
            json.dump(payload, handle)
            path = Path(handle.name)
        try:
            records = SampleSource(path).fetch()
        finally:
            path.unlink()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["company_name"], "Mixed")


class TestSafeFetch(unittest.TestCase):

    def test_source_failure_does_not_raise(self):
        records, error = safe_fetch(_FailingSource())
        self.assertEqual(records, [])
        self.assertIn("network unreachable", error)

    def test_non_list_result_reported_as_error(self):
        records, error = safe_fetch(_BadSource())
        self.assertEqual(records, [])
        self.assertIn("non-list", error)

    def test_successful_fetch(self):
        records, error = safe_fetch(_GoodSource())
        self.assertIsNone(error)
        self.assertEqual(records, [{"title": "ok",
                                    "source_name": "good"}])


class TestRecordDeduplication(unittest.TestCase):

    def test_same_url_ingested_once(self):
        records = [
            {"title": "A", "source_url": "https://a.example.com/x"},
            {"title": "A copy", "source_url": "https://a.example.com/x"},
        ]
        fresh, seen = deduplicate_records(records)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(len(seen), 1)

    def test_content_key_fallback_without_url(self):
        records = [
            {"title": "Same", "source_name": "Feed",
             "source_published_at": "2026-10-29"},
            {"title": "Same", "source_name": "Feed",
             "source_published_at": "2026-10-29"},
        ]
        fresh, _ = deduplicate_records(records)
        self.assertEqual(len(fresh), 1)

    def test_seen_set_persists_across_calls(self):
        seen = set()
        first, seen = deduplicate_records(
            [{"title": "A", "source_url": "https://a"}], seen)
        second, seen = deduplicate_records(
            [{"title": "A again", "source_url": "https://a"}], seen)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_records_without_identity_kept(self):
        fresh, _ = deduplicate_records([{"title": None}, {"other": 1}])
        self.assertEqual(len(fresh), 2)

    def test_invalid_input(self):
        self.assertEqual(deduplicate_records(None), ([], set()))
        self.assertEqual(deduplicate_records("nope"), ([], set()))


class TestIngestedDates(unittest.TestCase):

    def test_rss_pubdate_parses_to_iso(self):
        self.assertEqual(
            to_iso_date("Thu, 29 Oct 2026 08:00:00 GMT"),
            "2026-10-29")

    def test_atom_timestamp_parses_to_iso(self):
        self.assertEqual(
            to_iso_date("2026-10-26T10:00:00Z"),
            "2026-10-26")

    def test_invalid_ingested_date_becomes_none(self):
        signal = normalize_signal(
            {"signal_type": "funding", "title": "x",
             "detected_at": "yesterday-ish",
             "source_published_at": "sometime in october"},
            "Acme",
        )
        self.assertIsNone(signal["detected_at"])
        self.assertIsNone(signal["source_published_at"])


if __name__ == "__main__":
    unittest.main()
