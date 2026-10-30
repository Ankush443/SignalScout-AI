
import unittest

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


def sample_client() -> TestClient:
    settings = Settings(include_sample_data=True, feed_urls=[])
    return TestClient(create_app(settings))


def empty_client() -> TestClient:
    settings = Settings(include_sample_data=False, feed_urls=[])
    return TestClient(create_app(settings))


class TestHealthEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = sample_client()

    def test_root_returns_project_info(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "SignalScout AI")
        self.assertIn("endpoints", payload)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_stats_overview_matches_list_endpoints(self):
        stats = self.client.get("/stats").json()
        signals = self.client.get("/signals").json()
        companies = self.client.get("/companies").json()
        opportunities = self.client.get("/opportunities").json()

        self.assertEqual(stats["total_signals"], signals["count"])
        self.assertEqual(stats["companies"], companies["count"])
        self.assertEqual(stats["opportunities"], opportunities["count"])
        self.assertEqual(
            stats["funding_signals"] + stats["hiring_signals"],
            stats["total_signals"],
        )
        self.assertGreater(stats["total_signals"], 0)

    def test_sample_data_is_labeled(self):
        signals = self.client.get("/signals").json()["signals"]
        self.assertTrue(all(
            s.get("data_origin") == "sample" for s in signals))

    def test_stats_include_ingestion_diagnostics(self):
        stats = self.client.get("/stats").json()
        diag = stats.get("diagnostics")
        self.assertIsInstance(diag, dict)
        for key in ("sources_configured", "sources_succeeded",
                    "sources_failed", "feed_entries_fetched",
                    "entries_normalized", "funding_signals",
                    "hiring_signals", "unmatched_signals",
                    "duplicate_records_removed", "processing_errors"):
            self.assertIn(key, diag)
        self.assertEqual(diag["sources_failed"], 0)
        self.assertEqual(diag["processing_errors"], 0)
        self.assertEqual(diag["funding_signals"],
                         stats["funding_signals"])
        self.assertEqual(diag["hiring_signals"], stats["hiring_signals"])


class TestSignalEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = sample_client()

    def test_company_listing(self):
        payload = self.client.get("/companies").json()
        self.assertGreater(payload["count"], 0)
        for company in payload["companies"]:
            self.assertIn("company", company)
            self.assertIn("opportunity", company)
            self.assertIn("opportunity_score",
                          company["opportunity"])

    def test_signal_listing(self):
        payload = self.client.get("/signals").json()
        self.assertGreater(payload["count"], 0)
        for signal in payload["signals"]:
            self.assertIn(signal["signal_type"],
                          ("funding", "hiring"))
            self.assertIn("source_reliability", signal)

    def test_opportunity_listing_sorted_by_score(self):
        payload = self.client.get("/opportunities").json()
        self.assertGreater(payload["count"], 0)
        scores = [o["opportunity_score"]
                  for o in payload["opportunities"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("notice", payload)

    def test_filter_by_signal_type(self):
        payload = self.client.get(
            "/signals?signal_type=funding").json()
        self.assertGreater(payload["count"], 0)
        self.assertTrue(all(
            s["signal_type"] == "funding" for s in payload["signals"]))

    def test_filter_by_company(self):
        payload = self.client.get(
            "/signals?company=quantumleap").json()
        self.assertGreater(payload["count"], 0)
        self.assertTrue(all(
            "QuantumLeap" in s["company_name"]
            for s in payload["signals"]))

    def test_filter_companies_by_type_and_score(self):
        only_funding = self.client.get(
            "/companies?signal_type=funding").json()
        self.assertTrue(all(
            c["funding_signals"] >= 1
            for c in only_funding["companies"]))

        both = self.client.get(
            "/companies?signal_type=both").json()
        self.assertTrue(all(
            c["funding_signals"] >= 1 and c["hiring_signals"] >= 1
            for c in both["companies"]))

        high_score = self.client.get(
            "/companies?min_score=50").json()
        self.assertTrue(all(
            c["opportunity"]["opportunity_score"] >= 50
            for c in high_score["companies"]))

    def test_search_by_company_name(self):
        payload = self.client.get("/companies?q=nova").json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["companies"][0]["company"],
                         "NovaAI Technologies")


class TestCompanyDetail(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = sample_client()

    def test_known_company_returns_details(self):
        response = self.client.get(
            "/companies/NovaAI%20Technologies")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["company"], "NovaAI Technologies")
        self.assertGreater(len(payload["signals"]), 0)
        self.assertIn("score_breakdown",
                      payload["opportunity"])
        for signal in payload["signals"]:
            self.assertIn("source_reliability", signal)

    def test_company_lookup_is_case_insensitive(self):
        response = self.client.get("/companies/novaai%20technologies")
        self.assertEqual(response.status_code, 200)

    def test_unknown_company_returns_404(self):
        response = self.client.get("/companies/Nope%20Corp")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())


class TestInvalidFilters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = sample_client()

    def assert_rejected(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 422, path)
        self.assertIn("error", response.json())

    def test_invalid_signal_type_rejected(self):
        self.assert_rejected("/signals?signal_type=crypto")
        self.assert_rejected("/companies?signal_type=crypto")

    def test_min_score_out_of_range_rejected(self):
        self.assert_rejected("/opportunities?min_score=101")
        self.assert_rejected("/opportunities?min_score=-1")
        self.assert_rejected("/companies?min_score=500")

    def test_invalid_days_rejected(self):
        self.assert_rejected("/signals?days=0")

    def test_invalid_limit_rejected(self):
        self.assert_rejected("/signals?limit=0")

    def test_invalid_sort_rejected(self):
        self.assert_rejected("/opportunities?sort=magic")


class TestEmptyDataset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = empty_client()

    def test_empty_company_list_is_200(self):
        payload = self.client.get("/companies").json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["companies"], [])

    def test_empty_signal_list_is_200(self):
        payload = self.client.get("/signals").json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["signals"], [])

    def test_empty_opportunity_list_is_200(self):
        payload = self.client.get("/opportunities").json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["opportunities"], [])

    def test_unknown_company_on_empty_dataset_404(self):
        response = self.client.get("/companies/AnyCo")
        self.assertEqual(response.status_code, 404)


class TestIngestEndpoint(unittest.TestCase):

    def test_ingest_reruns_pipeline(self):
        client = sample_client()
        first = client.get("/stats").json()
        response = client.post("/ingest")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stats"]["total_signals"],
                         first["total_signals"])
        self.assertEqual(payload["sources"][0]["status"], "ok")

    def test_ingest_never_fetches_arbitrary_urls(self):
        # The endpoint accepts no URL parameters by design.
        client = sample_client()
        response = client.post("/ingest", json={"url": "http://evil"})
        self.assertEqual(response.status_code, 200)
        for source in response.json()["sources"]:
            self.assertNotIn("evil", source["name"])


class TestCors(unittest.TestCase):

    def test_dashboard_origin_allowed(self):
        client = sample_client()
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
