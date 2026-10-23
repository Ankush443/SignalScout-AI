
import unittest

from src.source_reliability import assess_source


class TestSourceReliability(unittest.TestCase):

    def test_missing_source_url(self):
        signal = {"signal_type": "funding"}

        self.assertEqual(
            assess_source(signal),
            "missing_source"
        )

    def test_empty_source_url(self):
        signal = {"source_url": "   "}

        self.assertEqual(
            assess_source(signal),
            "missing_source"
        )

    def test_invalid_source_url(self):
        signal = {"source_url": "not-a-url"}

        self.assertEqual(
            assess_source(signal),
            "invalid_source_url"
        )

    def test_unsupported_url_scheme(self):
        signal = {"source_url": "ftp://example.com/file"}

        self.assertEqual(
            assess_source(signal),
            "invalid_source_url"
        )

    def test_valid_url_is_unverified_by_default(self):
        signal = {
            "source_url": "https://example.com/news"
        }

        self.assertEqual(
            assess_source(signal),
            "unverified"
        )

    def test_explicitly_verified_source(self):
        signal = {
            "source_url": "https://example.com/news",
            "verification_status": "verified"
        }

        self.assertEqual(
            assess_source(signal),
            "verified"
        )

    def test_non_dictionary_signal_raises_type_error(self):
        with self.assertRaises(TypeError):
            assess_source(None)


if __name__ == "__main__":
    unittest.main()
