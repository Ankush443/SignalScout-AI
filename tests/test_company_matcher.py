
import unittest
from datetime import date

from src.company_matcher import apply_criteria, match_companies

REFERENCE = date(2026, 10, 30)


def signal(company, kind="funding", title="Funding announced",
           detected="2026-10-20", **extra):
    record = {
        "signal_id": extra.pop("signal_id", None),
        "company_name": company,
        "signal_type": kind,
        "title": title,
        "detected_at": detected,
        "source_reliability": "unverified",
        "data_origin": "sample",
    }
    record.update(extra)
    return record


class TestMatchCompanies(unittest.TestCase):

    def test_grouping_multiple_signals_one_entry(self):
        signals = [
            signal("Acme Inc"),
            signal("Acme", kind="hiring",
                   title="Hiring backend engineers"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["funding_signals"], 1)
        self.assertEqual(profiles[0]["hiring_signals"], 1)
        self.assertEqual(len(profiles[0]["signals"]), 2)

    def test_duplicate_company_entries_avoided_by_canonical_key(self):
        signals = [
            signal("Acme Inc"),
            signal("ACME"),
            signal("Acme Ltd"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertEqual(len(profiles), 1)

    def test_ai_hiring_tagging(self):
        signals = [
            signal("Helix", kind="hiring",
                   title="Hiring machine learning engineers"),
            signal("Helix", kind="hiring",
                   title="Hiring AI engineers"),
            signal("Helix", kind="hiring",
                   title="Hiring product manager"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        profile = profiles[0]

        self.assertEqual(profile["ai_hiring_signals"], 2)
        self.assertEqual(profile["hiring_signals"], 3)
        self.assertIn("ai_team_expansion", profile["opportunity_tags"])

    def test_single_ai_hiring_gets_smaller_tag(self):
        signals = [signal("Solo", kind="hiring",
                          title="Hiring AI engineers")]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertIn("ai_hiring",
                      profiles[0]["opportunity_tags"])
        self.assertNotIn("ai_team_expansion",
                         profiles[0]["opportunity_tags"])

    def test_recent_funding_tag_uses_reference_date(self):
        recent = match_companies(
            [signal("NewCo", detected="2026-10-20")],
            reference_date=REFERENCE,
        )
        self.assertIn("recent_funding", recent[0]["opportunity_tags"])

        old = match_companies(
            [signal("OldCo", detected="2026-01-01")],
            reference_date=REFERENCE,
        )
        self.assertNotIn("recent_funding", old[0]["opportunity_tags"])
        self.assertIn("funding_detected", old[0]["opportunity_tags"])

    def test_both_signal_types_tag(self):
        signals = [
            signal("BothCo"),
            signal("BothCo", kind="hiring",
                   title="Hiring AI engineers"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertIn("funding_and_hiring",
                      profiles[0]["opportunity_tags"])

    def test_signals_without_company_are_skipped_and_counted(self):
        signals = [signal(None), signal("RealCo")]
        result = match_companies(signals, reference_date=REFERENCE)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["company"], "RealCo")

    def test_latest_signal_date_is_max(self):
        signals = [
            signal("DateCo", detected="2026-10-05"),
            signal("DateCo", kind="hiring",
                   title="Hiring engineers", detected="2026-10-21"),
            signal("DateCo", kind="hiring",
                   title="Hiring interns", detected=None),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertEqual(profiles[0]["latest_signal_date"], "2026-10-21")

    def test_profiles_sorted_by_recency(self):
        signals = [
            signal("Older", detected="2026-09-01"),
            signal("Newer", detected="2026-10-25"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertEqual([p["company"] for p in profiles],
                         ["Newer", "Older"])

    def test_data_origins_reported(self):
        signals = [
            signal("Mixed"),
            signal("Mixed", data_origin="live"),
        ]
        profiles = match_companies(signals, reference_date=REFERENCE)
        self.assertEqual(profiles[0]["data_origins"],
                         ["live", "sample"])

    def test_invalid_signal_records_ignored(self):
        profiles = match_companies(
            [None, "junk", {"signal_type": "funding"}],
            reference_date=REFERENCE,
        )
        # The dictionary without a company name is skipped as orphan.
        self.assertEqual(profiles, [])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(match_companies(None), [])


class TestApplyCriteria(unittest.TestCase):

    def setUp(self):
        self.signals = [
            signal("FundCo"),
            signal("HireCo", kind="hiring",
                   title="Hiring AI engineers"),
            signal("HireCo", kind="hiring",
                   title="Hiring machine learning engineers"),
            signal("BothCo"),
            signal("BothCo", kind="hiring",
                   title="Hiring AI engineers"),
        ]
        self.profiles = match_companies(self.signals,
                                        reference_date=REFERENCE)

    def test_no_criteria_returns_all(self):
        self.assertEqual(len(apply_criteria(self.profiles)), 3)

    def test_funding_criteria(self):
        result = apply_criteria(self.profiles,
                                {"signal_type": "funding"})
        self.assertEqual({p["company"] for p in result},
                         {"FundCo", "BothCo"})

    def test_hiring_criteria(self):
        result = apply_criteria(self.profiles,
                                {"signal_type": "hiring"})
        self.assertEqual({p["company"] for p in result},
                         {"HireCo", "BothCo"})

    def test_both_criteria(self):
        result = apply_criteria(self.profiles,
                                {"signal_type": "both"})
        self.assertEqual([p["company"] for p in result], ["BothCo"])

    def test_min_ai_hiring_criteria(self):
        result = apply_criteria(self.profiles,
                                {"min_ai_hiring": 2})
        self.assertEqual([p["company"] for p in result], ["HireCo"])

    def test_tag_criteria(self):
        result = apply_criteria(self.profiles,
                                {"tags": ["ai_team_expansion"]})
        self.assertEqual([p["company"] for p in result], ["HireCo"])

    def test_invalid_criteria_raises(self):
        with self.assertRaises(ValueError):
            apply_criteria(self.profiles, {"signal_type": "bogus"})

    def test_non_list_profiles_returns_empty(self):
        self.assertEqual(apply_criteria(None), [])


if __name__ == "__main__":
    unittest.main()
