import os
from unittest.mock import patch
import unittest

from lead_api import MIN_ADMIN_SESSION_SECRET_BYTES, ServiceConfig


class AdminSessionConfigTests(unittest.TestCase):
    def env(self, **overrides):
        values = {
            "LEAD_REQUIRE_SECRETS": "1",
            "LEAD_PRIVACY_HASH_KEY": "privacy-key-material-for-tests-32bytes",
            "LEAD_ADMIN_TOKEN": "admin-token-independent-from-session-key",
            "LEAD_ADMIN_SESSION_SECRET": "s" * MIN_ADMIN_SESSION_SECRET_BYTES,
            "LEAD_ADMIN_SESSION_TTL_SECONDS": "3600",
        }
        values.update(overrides)
        return values

    def test_rejects_short_admin_session_secret(self):
        with patch.dict(os.environ, self.env(LEAD_ADMIN_SESSION_SECRET="too-short"), clear=True):
            with self.assertRaisesRegex(RuntimeError, "at least 32 bytes"):
                ServiceConfig.from_env()

    def test_rejects_session_secret_reused_as_admin_token(self):
        reused = "same-secret-material-must-not-be-reused"
        with patch.dict(
            os.environ,
            self.env(LEAD_ADMIN_TOKEN=reused, LEAD_ADMIN_SESSION_SECRET=reused),
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "must be independent"):
                ServiceConfig.from_env()

    def test_accepts_independent_session_secret_with_minimum_key_material(self):
        secret = "z" * MIN_ADMIN_SESSION_SECRET_BYTES
        with patch.dict(os.environ, self.env(LEAD_ADMIN_SESSION_SECRET=secret), clear=True):
            config = ServiceConfig.from_env()
        self.assertEqual(config.admin_session_secret, secret.encode("utf-8"))
        self.assertNotEqual(config.admin_session_secret, config.admin_token.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
