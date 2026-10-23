
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

if __name__ == "__main__":
    unittest.main()
