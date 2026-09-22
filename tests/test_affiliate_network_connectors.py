import json
from pathlib import Path
import tempfile
import unittest

from scripts import affiliate_network_connectors as connectors


class AffiliateNetworkConnectorTests(unittest.TestCase):
    def test_classifies_direct_saas_platforms(self):
        self.assertEqual(
            connectors.classify_application_platform("https://acme.getrewardful.com/signup"),
            ("direct-rewardful", "Rewardful"),
        )
        self.assertEqual(
            connectors.classify_application_platform("https://acme.firstpromoter.com/"),
            ("direct-firstpromoter", "FirstPromoter"),
        )
        self.assertEqual(
            connectors.classify_application_platform("https://vendor.example/affiliates"),
            ("direct-vendor", "Direct vendor"),
        )

    def test_missing_credentials_are_actionable_not_fatal(self):
        rows, status = connectors.discover({}, [])
        self.assertEqual(rows, [])
        self.assertEqual(len(status["networks"]), 4)
        self.assertTrue(all(not item["connected"] for item in status["networks"]))
        self.assertTrue(all(item["missing_credentials"] for item in status["networks"]))

    def test_status_file_contains_no_secret_values(self):
        env = {
            "AWIN_PUBLISHER_ID": "publisher-123", "AWIN_API_TOKEN": "secret-awin",
            "SOVRN_COMMERCE_API_KEY": "secret-sovrn",
            "CJ_PUBLISHER_CID": "cid-123", "CJ_PERSONAL_ACCESS_TOKEN": "secret-cj",
            "RAKUTEN_ACCESS_TOKEN": "secret-rakuten",
        }
        originals = connectors._awin, connectors._cj, connectors._rakuten, connectors._sovrn_check
        try:
            connectors._awin = lambda _env: []
            connectors._cj = lambda _env: []
            connectors._rakuten = lambda _env: []
            connectors._sovrn_check = lambda *_args: None
            _rows, status = connectors.discover(env, [])
        finally:
            connectors._awin, connectors._cj, connectors._rakuten, connectors._sovrn_check = originals
        text = json.dumps(status)
        for secret in ("secret-awin", "secret-sovrn", "secret-cj", "secret-rakuten"):
            self.assertNotIn(secret, text)

    def test_provider_errors_redact_credentials(self):
        env = {"AWIN_PUBLISHER_ID": "123", "AWIN_API_TOKEN": "top-secret"}
        message = connectors._safe_error(
            RuntimeError("request failed: https://api.example/?accessToken=top-secret"), env, "awin"
        )
        self.assertNotIn("top-secret", message)
        self.assertIn("[redacted]", message)

    def test_writes_public_connection_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            _rows, status = connectors.discover({}, [])
            connectors.write_status(root, status)
            saved = json.loads((root / "data/affiliate_network_status.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["version"], 1)
            self.assertIn("owner action", saved["legal_gate"])


if __name__ == "__main__":
    unittest.main()
