
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

        self.assertEqual(result["funding"], [funding])
        self.assertEqual(result["hiring"], [hiring])

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

        self.assertEqual(result["funding"], [first])
    
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

        self.assertEqual(result["hiring"], [first, second])

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

        self.assertEqual(result["funding"], [first, second])



if __name__ == "__main__":
    unittest.main()
