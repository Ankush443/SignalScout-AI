
import unittest

from src.normalizer import (
    canonical_company_name,
    extract_amount_key,
    normalize_company_name,
    normalize_signal,
    normalize_signals,
    normalize_signal_type,
    normalize_title,
    normalize_title_tokens,
    parse_date,
    to_iso_date,
)


class TestNormalizeSignalType(unittest.TestCase):

    def test_lowercase_funding(self):
        self.assertEqual(normalize_signal_type("funding"), "funding")

    def test_case_normalization(self):
        self.assertEqual(normalize_signal_type("  FuNdInG "), "funding")
        self.assertEqual(normalize_signal_type("HIRING"), "hiring")

    def test_whitespace_normalization(self):
        self.assertEqual(normalize_signal_type("  hiring\t"), "hiring")

    def test_common_synonyms(self):
        self.assertEqual(normalize_signal_type("fundraising"), "funding")
        self.assertEqual(normalize_signal_type("Recruiting"), "hiring")

    def test_unknown_type_returns_none(self):
        self.assertIsNone(normalize_signal_type("partnership"))

    def test_missing_value_returns_none(self):
        self.assertIsNone(normalize_signal_type(None))
        self.assertIsNone(normalize_signal_type("   "))


class TestCompanyNames(unittest.TestCase):

    def test_display_name_collapses_whitespace(self):
        self.assertEqual(
            normalize_company_name("  NovaAI   Technologies "),
            "NovaAI Technologies",
        )

    def test_missing_name_returns_none(self):
        self.assertIsNone(normalize_company_name(None))
        self.assertIsNone(normalize_company_name("   "))

    def test_canonical_strips_legal_suffixes(self):
        self.assertEqual(
            canonical_company_name("Acme Inc."), "acme")
        self.assertEqual(
            canonical_company_name("Acme Ltd"), "acme")
        self.assertEqual(
            canonical_company_name("ACME, LLC"), "acme")

    def test_canonical_is_case_insensitive(self):
        self.assertEqual(
            canonical_company_name("NovaAI Technologies"),
            canonical_company_name("novaai   technologies"),
        )

    def test_canonical_missing_returns_none(self):
        self.assertIsNone(canonical_company_name(None))
        self.assertIsNone(canonical_company_name("  ,  "))


class TestTitles(unittest.TestCase):

    def test_title_whitespace_cleaned(self):
        self.assertEqual(
            normalize_title("  Series   A  "), "Series A")

    def test_missing_title_returns_none(self):
        self.assertIsNone(normalize_title(None))
        self.assertIsNone(normalize_title(""))


class TestTitleTokens(unittest.TestCase):

    def test_money_amounts_normalize_identically(self):
        left = normalize_title_tokens(
            "NovaAI raises $12 million in Series A")
        right = normalize_title_tokens(
            "NovaAI Technologies secures $12M Series A funding")
        # The money expression becomes the same comparable token even
        # though the rest of the wording differs.
        self.assertIn("12m", left)
        self.assertIn("12m", right)
        self.assertNotIn("million", left | right)
        # Shared core tokens drive the containment score in the
        # deduplicator; the titles are intentionally not identical.
        self.assertTrue({"novaai", "series"} <= (left & right))

    def test_punctuation_and_case_ignored(self):
        left = normalize_title_tokens("Seed round closed!")
        right = normalize_title_tokens("seed round closed")
        self.assertEqual(left, right)

    def test_stopwords_removed(self):
        tokens = normalize_title_tokens("The funding round of the company")
        self.assertNotIn("the", tokens)
        self.assertIn("funding", tokens)

    def test_missing_title_gives_empty_set(self):
        self.assertEqual(normalize_title_tokens(None), frozenset())


class TestAmountKeys(unittest.TestCase):

    def test_equivalent_amounts_match(self):
        self.assertEqual(
            extract_amount_key("$12 million"),
            extract_amount_key("$12M"),
        )
        self.assertEqual(
            extract_amount_key("$12 million"),
            extract_amount_key("$12,000,000"),
        )

    def test_different_amounts_differ(self):
        self.assertNotEqual(
            extract_amount_key("$4.5 million"),
            extract_amount_key("$45 million"),
        )

    def test_missing_or_invalid_amount_returns_none(self):
        self.assertIsNone(extract_amount_key(None))
        self.assertIsNone(extract_amount_key("no number here"))


class TestDates(unittest.TestCase):

    def test_iso_date(self):
        self.assertEqual(parse_date("2026-10-19"),
                         parse_date("2026-10-19"))

    def test_slash_date_supported(self):
        parsed = parse_date("2026/10/24")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2026-10-24")

    def test_written_date_supported(self):
        parsed = parse_date("October 19, 2026")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2026-10-19")

    def test_invalid_date_returns_none(self):
        self.assertIsNone(parse_date("not a date"))
        self.assertIsNone(parse_date("2026-13-45"))

    def test_non_string_returns_none(self):
        self.assertIsNone(parse_date(12345))
        self.assertIsNone(parse_date(None))

    def test_to_iso_date(self):
        self.assertEqual(to_iso_date("2026/10/24"), "2026-10-24")
        self.assertIsNone(to_iso_date("garbage"))


class TestNormalizeSignal(unittest.TestCase):

    def test_full_record_to_schema(self):
        record = {
            "signal_id": " FUNDING001 ",
            "signal_type": "Funding",
            "title": "Series A announced",
            "description": "Round to expand products.",
            "amount": "$12 million",
            "detected_at": "2026-10-19",
            "source_name": "Example News",
            "source_url": " https://example.com/article ",
            "source_published_at": "2026-10-18",
        }
        signal = normalize_signal(record, "NovaAI Technologies")

        self.assertEqual(signal["signal_id"], "FUNDING001")
        self.assertEqual(signal["company_name"], "NovaAI Technologies")
        self.assertEqual(signal["signal_type"], "funding")
        self.assertEqual(signal["amount"], "$12 million")
        self.assertEqual(signal["detected_at"], "2026-10-19")
        self.assertEqual(signal["source_published_at"], "2026-10-18")
        self.assertEqual(signal["source_url"], "https://example.com/article")
        self.assertEqual(signal["verification_status"], "unverified")
        self.assertEqual(signal["data_origin"], "sample")

    def test_missing_optional_fields_become_none(self):
        signal = normalize_signal(
            {"signal_type": "hiring", "title": "AI engineer"},
            "Acme",
        )
        self.assertIsNone(signal["description"])
        self.assertIsNone(signal["amount"])
        self.assertIsNone(signal["source_url"])
        self.assertIsNone(signal["detected_at"])
        self.assertIsNone(signal["signal_id"])

    def test_invalid_date_becomes_none(self):
        signal = normalize_signal(
            {"signal_type": "funding", "title": "x",
             "detected_at": "not-a-date"},
            "Acme",
        )
        self.assertIsNone(signal["detected_at"])

    def test_untrusted_verification_status_is_discarded(self):
        signal = normalize_signal(
            {"signal_type": "funding", "title": "x",
             "verification_status": "verified"},
            "Acme",
        )
        self.assertEqual(signal["verification_status"], "unverified")

    def test_non_dict_record_returns_none(self):
        self.assertIsNone(normalize_signal("not a record", "Acme"))
        self.assertIsNone(normalize_signal(None, "Acme"))

    def test_unknown_signal_type_returns_none(self):
        self.assertIsNone(
            normalize_signal({"signal_type": "update", "title": "x"},
                             "Acme"))

    def test_company_taken_from_record_when_not_given(self):
        signal = normalize_signal(
            {"signal_type": "funding", "title": "x",
             "company_name": "From Record"},
        )
        self.assertEqual(signal["company_name"], "From Record")

    def test_data_origin_live_preserved(self):
        signal = normalize_signal(
            {"signal_type": "funding", "title": "x",
             "data_origin": "live"},
            "Acme",
        )
        self.assertEqual(signal["data_origin"], "live")

    def test_normalize_signals_skips_malformed(self):
        records = [
            {"signal_type": "funding", "title": "ok"},
            "junk",
            None,
            {"signal_type": "unknown", "title": "skip"},
        ]
        result = normalize_signals(records, "Acme")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["signal_type"], "funding")

    def test_normalize_signals_handles_non_list(self):
        self.assertEqual(normalize_signals(None), [])
        self.assertEqual(normalize_signals("nope"), [])


if __name__ == "__main__":
    unittest.main()
