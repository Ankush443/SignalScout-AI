
import unittest
from datetime import date

from src.company_matcher import match_companies
from src.opportunity_scorer import (
    SCORING_WEIGHTS,
    rank_opportunities,
    score_opportunity,
)

REFERENCE = date(2026, 10, 30)


def make_signals(company, funding_dates=(), ai_hiring=0,
                 plain_hiring=0, reliability="unverified"):
    signals = []
    for i, day in enumerate(funding_dates):
        signals.append({
            "signal_id": f"F{i}",
            "company_name": company,
            "signal_type": "funding",
            "title": f"Funding round {i}",
            "detected_at": day,
            "source_url": "https://example.com/funding",
            "source_reliability": reliability,
            "data_origin": "sample",
        })
    for i in range(ai_hiring):
        signals.append({
            "signal_id": f"HAI{i}",
            "company_name": company,
            "signal_type": "hiring",
            "title": "Hiring AI engineers",
            "detected_at": "2026-10-18",
            "source_url": "https://example.com/jobs",
            "source_reliability": reliability,
            "data_origin": "sample",
        })
    for i in range(plain_hiring):
        signals.append({
            "signal_id": f"H{i}",
            "company_name": company,
            "signal_type": "hiring",
            "title": "Hiring backend engineers",
            "detected_at": "2026-10-17",
            "source_url": "https://example.com/jobs",
            "source_reliability": reliability,
            "data_origin": "sample",
        })
    return signals


def profile_for(company, **kwargs):
    signals = make_signals(company, **kwargs)
    profiles = match_companies(signals, reference_date=REFERENCE)
    return profiles[0]


class TestScoreOpportunity(unittest.TestCase):

    def test_weights_total_100(self):
        self.assertEqual(sum(SCORING_WEIGHTS.values()), 100)

    def test_full_signal_company_score(self):
        # Recent funding (30) + 2 AI hires (30) + both types (25)
        # + usable URL evidence (8) = 93.
        profile = profile_for("StrongCo", funding_dates=("2026-10-15",),
                              ai_hiring=2)
        result = score_opportunity(profile, reference_date=REFERENCE)
        self.assertEqual(result["opportunity_score"], 93)
        self.assertEqual(result["evidence_count"], 3)

    def test_old_funding_gets_partial_credit_only(self):
        profile = profile_for("OldCo", funding_dates=("2026-01-05",))
        result = score_opportunity(profile, reference_date=REFERENCE)
        # 15 (old funding) + 8 (URL evidence) = 23 < full 30+8.
        self.assertEqual(result["opportunity_score"], 23)

    def test_missing_evidence_earns_nothing(self):
        # A company profile with no signals at all (built directly,
        # since the matcher only emits profiles that have signals).
        profile = {
            "company": "EmptyCo",
            "company_key": "emptyco",
            "funding_signals": 0,
            "hiring_signals": 0,
            "ai_hiring_signals": 0,
            "recent_funding": False,
            "signals": [],
            "opportunity_tags": [],
            "latest_signal_date": None,
            "data_origins": [],
        }
        result = score_opportunity(profile, reference_date=REFERENCE)
        self.assertEqual(result["opportunity_score"], 0)
        self.assertEqual(result["evidence_count"], 0)

    def test_missing_source_url_scores_no_evidence_points(self):
        signals = [{
            "signal_id": "F1",
            "company_name": "NoUrlCo",
            "signal_type": "funding",
            "title": "Funding announced",
            "detected_at": "2026-10-20",
            "source_reliability": "missing_source",
            "data_origin": "sample",
        }]
        profile = match_companies(signals,
                                  reference_date=REFERENCE)[0]
        result = score_opportunity(profile, reference_date=REFERENCE)
        # 30 (recent funding) + 0 evidence.
        self.assertEqual(result["opportunity_score"], 30)

    def test_invalid_url_scores_no_evidence_points(self):
        signals = [{
            "signal_id": "F1",
            "company_name": "BadUrlCo",
            "signal_type": "funding",
            "title": "Funding announced",
            "detected_at": "2026-10-20",
            "source_reliability": "invalid_source_url",
            "data_origin": "sample",
        }]
        profile = match_companies(signals,
                                  reference_date=REFERENCE)[0]
        result = score_opportunity(profile, reference_date=REFERENCE)
        self.assertEqual(result["opportunity_score"], 30)

    def test_verified_sources_get_full_evidence_points(self):
        profile = profile_for("VerifiedCo",
                              funding_dates=("2026-10-15",),
                              reliability="verified")
        result = score_opportunity(profile, reference_date=REFERENCE)
        # 30 (recent) + 8 (URL) + 7 (verified) = 45.
        self.assertEqual(result["opportunity_score"], 45)

    def test_url_is_not_proof_only_partial_credit(self):
        profile = profile_for("UrlOnlyCo",
                              funding_dates=("2026-10-15",))
        result = score_opportunity(profile, reference_date=REFERENCE)
        breakdown = {b["factor"]: b for b in result["score_breakdown"]}
        self.assertEqual(breakdown["source_evidence"]["points"], 8)
        self.assertLess(breakdown["source_evidence"]["points"],
                        breakdown["source_evidence"]["max_points"])
        self.assertIn("not proof",
                      breakdown["source_evidence"]["explanation"])

    def test_breakdown_explains_every_factor(self):
        profile = profile_for("StrongCo", funding_dates=("2026-10-15",),
                              ai_hiring=2)
        result = score_opportunity(profile, reference_date=REFERENCE)

        self.assertEqual(len(result["score_breakdown"]), 4)
        total = sum(item["points"]
                    for item in result["score_breakdown"])
        self.assertEqual(total, result["opportunity_score"])
        for item in result["score_breakdown"]:
            self.assertTrue(item["explanation"])
            self.assertLessEqual(item["points"], item["max_points"])

    def test_reasons_include_positive_factors(self):
        profile = profile_for("StrongCo", funding_dates=("2026-10-15",),
                              ai_hiring=2)
        result = score_opportunity(profile, reference_date=REFERENCE)
        joined = " ".join(result["reasons"])
        self.assertIn("Recent funding", joined)
        self.assertIn("Multiple AI-related hiring", joined)
        self.assertIn("Both funding and hiring", joined)

    def test_score_is_bounded_0_100(self):
        profile = profile_for("StrongCo", funding_dates=("2026-10-15",),
                              ai_hiring=3, plain_hiring=3)
        result = score_opportunity(profile, reference_date=REFERENCE)
        self.assertGreaterEqual(result["opportunity_score"], 0)
        self.assertLessEqual(result["opportunity_score"], 100)


class TestRankOpportunities(unittest.TestCase):

    def _two_profiles(self):
        strong = profile_for("StrongCo", funding_dates=("2026-10-15",),
                             ai_hiring=2)
        weak = profile_for("WeakCo", plain_hiring=1)
        return [weak, strong]

    def test_ranking_sorts_by_score_desc(self):
        ranked = rank_opportunities(self._two_profiles(),
                                    reference_date=REFERENCE)
        self.assertEqual([r["company"] for r in ranked],
                         ["StrongCo", "WeakCo"])
        self.assertGreater(ranked[0]["opportunity_score"],
                           ranked[1]["opportunity_score"])

    def test_sort_by_recency(self):
        ranked = rank_opportunities(
            self._two_profiles(),
            reference_date=REFERENCE,
            sort_by="recency",
        )
        self.assertEqual([r["company"] for r in ranked],
                         ["StrongCo", "WeakCo"])

    def test_ranking_handles_empty_and_invalid(self):
        self.assertEqual(rank_opportunities([]), [])
        self.assertEqual(rank_opportunities(None), [])
        self.assertEqual(rank_opportunities([None, "junk"]), [])


if __name__ == "__main__":
    unittest.main()
