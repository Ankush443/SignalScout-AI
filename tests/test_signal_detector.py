
import unittest

from src.signal_detector import detect_signals


def make_signal(kind, detail="example"):
    return {"signal_type": kind, "detail": detail}


class TestDetectSignals(unittest.TestCase):

    def test_funding_signal_goes_into_funding_not_hiring(self):
        company = {
            "name": "B",
            "signals": [make_signal("funding")]
        }

        result = detect_signals(company)

        self.assertEqual(len(result["funding"]), 1)
        self.assertEqual(result["hiring"], [])

    def test_hiring_signal_goes_into_hiring_not_funding(self):
        company = {
            "name": "A",
            "signals": [make_signal("hiring")]
        }

        result = detect_signals(company)

        self.assertEqual(len(result["hiring"]), 1)
        self.assertEqual(result["funding"], [])

    def test_both_signals_types_are_classified_correctly(self):
        funding = make_signal("funding", "Series A")
        hiring = make_signal("hiring", "5 AI engineering openings")
        company = {"name": "C", "signals": [hiring, funding]}

        result = detect_signals(company)

        # Funding records appear only in result["funding"].
        self.assertEqual(len(result["funding"]), 1)
        self.assertEqual(result["funding"][0]["signal_type"], "funding")
        self.assertEqual(result["funding"][0]["detail"], "Series A")
        self.assertEqual(
            result["funding"][0]["source_reliability"],
            "missing_source"
        )

        # Hiring records appear only in result["hiring"].
        self.assertEqual(len(result["hiring"]), 1)
        self.assertEqual(result["hiring"][0]["signal_type"], "hiring")
        self.assertEqual(
            result["hiring"][0]["detail"],
            "5 AI engineering openings"
        )
        self.assertEqual(
            result["hiring"][0]["source_reliability"],
            "missing_source"
        )

    def test_empty_signals_list_produces_empty_results(self):
        company = {"name": "D", "signals": []}

        result = detect_signals(company)

        self.assertEqual(result["funding"], [])
        self.assertEqual(result["hiring"], [])

    def test_missing_signals_field_does_not_crash(self):
        company = {"name": "E"}

        result = detect_signals(company)

        self.assertEqual(result["funding"], [])
        self.assertEqual(result["hiring"], [])

    def test_non_list_signals_raise_value_error(self):
        company = {"name": "InvalidCo", "signals": "funding"}

        with self.assertRaises(ValueError):
            detect_signals(company)

    def test_non_dictionary_signal_is_skipped(self):
        company = {
            "name": "TestCo",
            "signals": [
                None,
                {"signal_type": "funding"}
            ]
        }

        result = detect_signals(company)

        self.assertEqual(len(result["funding"]), 1)
        self.assertEqual(result["hiring"], [])

    # Test for Duplicate
    def test_duplicate_signal_ids_are_removed(self):
        first = {
            "signal_id": "F001",
            "signal_type" : "funding",
            "title": "Series A"
        }
        duplicate = {
            "signal_id": "F001",
            "signal_type" : "funding",
            "title": "Series A reposted"
        }

        result = detect_signals({
            "name": "TestCo",
            "signals": [first, duplicate]
        })

        # Only the first record with the duplicate ID survives,
        # and source reliability enrichment is added.
        self.assertEqual(len(result["funding"]), 1)
        self.assertEqual(result["funding"][0]["signal_id"], "F001")
        self.assertEqual(result["funding"][0]["title"], "Series A")
        self.assertEqual(
            result["funding"][0]["source_reliability"],
            "missing_source"
        )
    
    def test_signal_without_ids_are_preserved(self):
        first = {
            "signal_type" : "hiring",
            "title": "Python Engineer"
        }
        second = {
            "signal_type" : "hiring",
            "title": "Backend Engineer"
        }

        result = detect_signals({
            "name": "TestCo",
            "signals": [first, second]
        })

        # Both records without IDs are kept, with their identifying
        # fields preserved and reliability enrichment added.
        self.assertEqual(len(result["hiring"]), 2)
        self.assertEqual(
            [item["title"] for item in result["hiring"]],
            ["Python Engineer", "Backend Engineer"]
        )
        self.assertTrue(
            all("signal_id" not in item or item.get("signal_id") is None
                for item in result["hiring"])
        )
        self.assertTrue(
            all(item["source_reliability"] == "missing_source"
                for item in result["hiring"])
        )

    def test_different_signal_ids_are_preserved(self):
        first = {
            "signal_id": "F001",
            "signal_type" : "funding"
        }
        second = {
            "signal_id": "F002",
            "signal_type" : "funding"
        }

        result = detect_signals({
            "name": "TestCo",
            "signals": [first, second]
        })

        # Both distinct IDs remain present, in order.
        self.assertEqual(len(result["funding"]), 2)
        self.assertEqual(
            [item["signal_id"] for item in result["funding"]],
            ["F001", "F002"]
        )
        self.assertTrue(
            all(item["source_reliability"] == "missing_source"
                for item in result["funding"])
        )

    # Tests for Source Reliability Integration
    def test_detected_signal_includes_source_reliability(self):
        company = {
            "name": "TestCo",
            "signals": [
                {
                    "signal_id": "F001",
                    "signal_type": "funding",
                    "source_url": "https://example.com/news"
                }
            ]
        }

        result = detect_signals(company)

        self.assertEqual(
            result["funding"][0]["source_reliability"],
            "unverified"
        )


    def test_missing_source_is_flagged(self):
        company = {
            "name": "TestCo",
            "signals": [
                {
                    "signal_id": "H001",
                    "signal_type": "hiring"
                }
            ]
        }

        result = detect_signals(company)

        self.assertEqual(
            result["hiring"][0]["source_reliability"],
            "missing_source"
        )


if __name__ == "__main__":
    unittest.main()
