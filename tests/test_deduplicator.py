
import unittest

from src.deduplicator import (
    DATE_TOLERANCE_DAYS,
    are_duplicates,
    deduplicate_cross_source,
)


def funding_signal(**overrides):
    base = {
        "signal_id": "A1",
        "company_name": "NovaAI",
        "signal_type": "funding",
        "title": "NovaAI raises $12 million in Series A",
        "amount": "$12 million",
        "detected_at": "2026-10-19",
        "source_name": "Source A",
        "source_url": "https://a.example.com/article",
        "source_published_at": "2026-10-19",
        "data_origin": "sample",
    }
    base.update(overrides)
    return base


class TestAreDuplicates(unittest.TestCase):

    def test_same_signal_id_content_merges(self):
        left = funding_signal()
        right = funding_signal(signal_id="A1",
                               source_url="https://a.example.com/article")
        is_dup, reason = are_duplicates(left, right)
        self.assertTrue(is_dup)
        self.assertTrue(reason)

    def test_same_announcement_different_ids_merges(self):
        left = funding_signal()
        right = funding_signal(
            signal_id="B7",
            company_name="NovaAI Technologies",
            title="NovaAI Technologies secures $12M Series A funding",
            amount="$12M",
            detected_at="2026-10-20",
            source_name="Source B",
            source_url="https://b.example.com/story",
            source_published_at="2026-10-20",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertTrue(is_dup)
        self.assertIn("title similarity", reason)

    def test_same_company_different_announcements_not_merged(self):
        left = funding_signal(
            title="Seed round closed",
            detected_at="2026-04-12",
            source_published_at="2026-04-12",
        )
        right = funding_signal(
            signal_id="A2",
            title="Series A funding announced",
            detected_at="2026-10-20",
            source_published_at="2026-10-20",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertFalse(is_dup)
        self.assertIn("dates", reason)

    def test_similar_titles_different_companies_not_merged(self):
        left = funding_signal(company_name="NovaAI")
        right = funding_signal(
            company_name="OrbitPay",
            source_url="https://c.example.com/story",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertFalse(is_dup)
        self.assertEqual(reason, "different companies")

    def test_paraphrased_title_same_announcement_merges(self):
        # Same round reported with different wording and amount format.
        left = funding_signal()
        right = funding_signal(
            signal_id="B9",
            title="NovaAI banks $12M in Series A round",
            amount="$12M",
            source_url="https://b.example.com/story",
            source_published_at="2026-10-21",
            detected_at="2026-10-21",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertTrue(is_dup, reason)
        self.assertIn("title", reason)

    def test_same_company_same_date_unrelated_titles_not_merged(self):
        # Matching company + identical dates is NOT enough: the title
        # must also describe the same announcement.
        left = funding_signal(
            title="NovaAI raises $12 million in Series A",
        )
        right = funding_signal(
            signal_id="A2",
            title="NovaAI opens a new research office in Lisbon",
            source_url="https://b.example.com/story",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertFalse(is_dup)
        self.assertIn("title", reason)

    def test_below_threshold_titles_not_merged_even_with_date_match(self):
        # Title overlap below 0.60 must never merge, even with the same
        # company, same type and identical dates.
        left = funding_signal(
            title="Hiring spree begins for backend engineers")
        right = funding_signal(
            signal_id="A2",
            title="NovaAI expands sales team in Europe",
            source_url="https://b.example.com/story",
        )
        is_dup, _ = are_duplicates(left, right)
        self.assertFalse(is_dup)

    def test_company_suffix_ignored(self):
        left = funding_signal(company_name="Acme Inc")
        right = funding_signal(company_name="Acme")
        is_dup, _ = are_duplicates(left, right)
        self.assertTrue(is_dup)

    def test_company_name_containment_matches(self):
        left = funding_signal(company_name="NovaAI")
        right = funding_signal(company_name="NovaAI Technologies")
        is_dup, _ = are_duplicates(left, right)
        self.assertTrue(is_dup)

    def test_different_signal_types_never_merge(self):
        left = funding_signal()
        right = funding_signal(signal_type="hiring")
        is_dup, reason = are_duplicates(left, right)
        self.assertFalse(is_dup)
        self.assertEqual(reason, "different signal types")

    def test_dates_outside_tolerance_not_merged(self):
        left = funding_signal(detected_at="2026-10-01",
                              source_published_at="2026-10-01")
        right = funding_signal(
            signal_id="A2",
            title="NovaAI raises $12 million in Series A follow-on",
            detected_at="2026-10-25",
            source_published_at="2026-10-25",
        )
        is_dup, reason = are_duplicates(left, right)
        self.assertFalse(is_dup)
        self.assertIn("dates", reason)

    def test_dates_within_tolerance_merge(self):
        left = funding_signal()
        right = funding_signal(
            signal_id="A2",
            source_url="https://b.example.com/story",
            detected_at="2026-10-22",
            source_published_at="2026-10-22",
        )
        is_dup, _ = are_duplicates(
            left, right,
            date_tolerance_days=DATE_TOLERANCE_DAYS,
        )
        self.assertTrue(is_dup)

    def test_missing_dates_require_strong_title_match(self):
        left = funding_signal(detected_at=None,
                              source_published_at=None)
        # Nearly identical title -> conservative merge allowed.
        right = funding_signal(
            signal_id="A2",
            title=left["title"],
            detected_at=None,
            source_published_at=None,
            source_url="https://b.example.com/story",
        )
        is_dup, _ = are_duplicates(left, right)
        self.assertTrue(is_dup)

        # Weak title overlap with missing dates -> kept separate.
        weak = funding_signal(
            signal_id="A3",
            title="Hiring spree announced by the company",
            detected_at=None,
            source_published_at=None,
            source_url="https://c.example.com/story",
        )
        is_dup, _ = are_duplicates(left, weak)
        self.assertFalse(is_dup)

    def test_missing_dates_with_matching_amount_still_strict(self):
        left = funding_signal(detected_at=None,
                              source_published_at=None)
        right = funding_signal(
            signal_id="A2",
            title="NovaAI Technologies closes $12M Series A round",
            detected_at=None,
            source_published_at=None,
            source_url="https://b.example.com/story",
        )
        is_dup, _ = are_duplicates(left, right)
        self.assertTrue(is_dup)

    def test_non_dictionary_input_not_duplicate(self):
        is_dup, reason = are_duplicates(funding_signal(), None)
        self.assertFalse(is_dup)
        self.assertIn("not dictionaries", reason)


class TestDeduplicateCrossSource(unittest.TestCase):

    def test_merges_cross_source_pair_and_keeps_all_urls(self):
        first = funding_signal()
        second = funding_signal(
            signal_id="B7",
            company_name="NovaAI Technologies",
            title="NovaAI Technologies secures $12M Series A funding",
            amount="$12M",
            detected_at="2026-10-20",
            source_name="Source B",
            source_url="https://b.example.com/story",
            source_published_at="2026-10-20",
        )
        result = deduplicate_cross_source([first, second])

        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertEqual(merged["signal_id"], "A1")
        self.assertEqual(merged["merged_signal_ids"], ["A1", "B7"])
        urls = [s["source_url"] for s in merged["supporting_sources"]]
        self.assertEqual(
            urls,
            ["https://a.example.com/article",
             "https://b.example.com/story"],
        )
        self.assertEqual(merged["duplicate_count"], 2)
        # Original duplicate data is preserved, not thrown away.
        self.assertEqual(len(merged["duplicate_records"]), 1)
        self.assertEqual(merged["duplicate_records"][0]["signal_id"], "B7")
        self.assertTrue(merged["merge_reason"])

    def test_three_sources_one_announcement_keep_all_urls(self):
        # Three independent outlets report the same round: all three
        # source URLs must survive on the merged record.
        second = funding_signal(
            signal_id="B7",
            title="NovaAI Technologies secures $12M Series A funding",
            amount="$12M",
            detected_at="2026-10-20",
            source_name="Source B",
            source_url="https://b.example.com/story",
            source_published_at="2026-10-20",
        )
        third = funding_signal(
            signal_id="C3",
            title="NovaAI closes $12M Series A",
            amount="$12M",
            detected_at="2026-10-21",
            source_name="Source C",
            source_url="https://c.example.com/round",
            source_published_at="2026-10-21",
        )
        result = deduplicate_cross_source([funding_signal(), second,
                                           third])
        self.assertEqual(len(result), 1)
        merged = result[0]
        urls = {s["source_url"] for s in merged["supporting_sources"]}
        self.assertEqual(urls, {"https://a.example.com/article",
                                "https://b.example.com/story",
                                "https://c.example.com/round"})
        self.assertEqual(merged["duplicate_count"], 3)
        self.assertEqual(sorted(merged["merged_signal_ids"]),
                         ["A1", "B7", "C3"])

    def test_unrelated_signals_kept_separate(self):
        first = funding_signal(
            title="Seed round closed",
            detected_at="2026-04-12",
            source_published_at="2026-04-12",
        )
        second = funding_signal(
            signal_id="A2",
            title="Series A funding announced",
            detected_at="2026-10-20",
            source_published_at="2026-10-20",
        )
        result = deduplicate_cross_source([first, second])
        self.assertEqual(len(result), 2)

    def test_no_ids_required_for_cross_source_merge(self):
        first = funding_signal(signal_id=None)
        second = funding_signal(
            signal_id=None,
            title="NovaAI Technologies secures $12M Series A funding",
            detected_at="2026-10-20",
            source_published_at="2026-10-20",
            source_url="https://b.example.com/story",
        )
        result = deduplicate_cross_source([first, second])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["supporting_sources"]), 2)

    def test_signals_without_sources_still_merge_on_content(self):
        first = funding_signal(source_url=None, source_name=None)
        second = funding_signal(
            signal_id="B7",
            title=first["title"],
            source_url=None,
            source_name=None,
        )
        result = deduplicate_cross_source([first, second])
        self.assertEqual(len(result), 1)

    def test_empty_and_invalid_inputs(self):
        self.assertEqual(deduplicate_cross_source([]), [])
        self.assertEqual(deduplicate_cross_source(None), [])
        self.assertEqual(deduplicate_cross_source("nope"), [])
        self.assertEqual(
            deduplicate_cross_source([None, "junk", 42]), [])

    def test_single_signal_returned_untouched(self):
        signal = funding_signal()
        result = deduplicate_cross_source([signal])
        self.assertEqual(result, [signal])


if __name__ == "__main__":
    unittest.main()
