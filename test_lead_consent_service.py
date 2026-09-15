import hmac
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

from lead_api import ADMIN_SESSION_COOKIE, LeadHTTPServer, ServiceConfig
from lead_ledger import ConflictError, LeadLedger, LeadSubmission, ValidationError


class LeadLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "lead.sqlite3"
        self.ledger = LeadLedger(self.db, privacy_hash_key=b"x" * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def submission(self, **overrides):
        payload = {
            "email": "Person@Example.com",
            "phone": "440-453-4945",
            "sms_consent": True,
            "consent_text_version": "signal-capture-v1",
            "source": "website-pre-redirect",
            "idempotency_key": "test-idempotency-0001",
        }
        payload.update(overrides)
        return LeadSubmission.from_mapping(payload)

    def test_persists_contact_consent_and_valid_chain(self):
        result = self.ledger.ingest(self.submission(), remote_ip="203.0.113.10", user_agent="test-agent")
        self.assertFalse(result["idempotent_replay"])
        self.assertTrue(result["receipt_id"].startswith("consent_"))
        ok, broken = self.ledger.verify_chain()
        self.assertTrue(ok)
        self.assertIsNone(broken)
        stats = self.ledger.stats()
        self.assertEqual(stats["contacts"], 1)
        self.assertEqual(stats["consent_receipts"], 1)
        self.assertEqual(stats["sms_consents"], 1)

    def test_idempotency_does_not_duplicate(self):
        first = self.ledger.ingest(self.submission(), remote_ip="203.0.113.10", user_agent="one")
        second = self.ledger.ingest(self.submission(), remote_ip="203.0.113.11", user_agent="two")
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(self.ledger.stats()["consent_receipts"], 1)

    def test_idempotency_key_reuse_with_different_payload_fails_closed(self):
        self.ledger.ingest(self.submission(), remote_ip="203.0.113.10", user_agent="one")
        changed = self.submission(email="changed@example.com")
        with self.assertRaises(ConflictError):
            self.ledger.ingest(changed, remote_ip="203.0.113.10", user_agent="two")

    def test_phone_requires_sms_consent(self):
        with self.assertRaises(ValidationError):
            self.submission(sms_consent=False)

    def test_email_only_does_not_require_sms_consent(self):
        submission = self.submission(phone="", sms_consent=False)
        result = self.ledger.ingest(submission, remote_ip="127.0.0.1", user_agent="test")
        self.assertTrue(result["receipt_id"].startswith("consent_"))

    def test_audit_chain_contains_no_raw_pii(self):
        submission = self.submission()
        self.ledger.ingest(submission, remote_ip="203.0.113.10", user_agent="test-agent")
        conn = sqlite3.connect(self.db)
        try:
            payload = conn.execute("SELECT payload_json FROM audit_events").fetchone()[0]
        finally:
            conn.close()
        self.assertNotIn("person@example.com", payload.lower())
        self.assertNotIn("+14404534945", payload)
        decoded = json.loads(payload)
        self.assertIn("payload_hash", decoded)
        self.assertIn("receipt_id", decoded)
        self.assertIn("consent_text_hash", decoded)

    def test_tamper_detection(self):
        self.ledger.ingest(self.submission(), remote_ip="203.0.113.10", user_agent="test-agent")
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("UPDATE audit_events SET payload_json='{}' WHERE seq=1")
            conn.commit()
        finally:
            conn.close()
        ok, broken = self.ledger.verify_chain()
        self.assertFalse(ok)
        self.assertEqual(broken, 1)

    def test_conflicting_existing_identities_fail_closed(self):
        a = self.submission(phone="", idempotency_key="test-idempotency-0002")
        self.ledger.ingest(a, remote_ip="1.1.1.1", user_agent="a")
        b = self.submission(email="other@example.com", phone="440-453-4945", idempotency_key="test-idempotency-0003")
        self.ledger.ingest(b, remote_ip="1.1.1.2", user_agent="b")
        c = self.submission(email="person@example.com", phone="440-453-4945", idempotency_key="test-idempotency-0004")
        with self.assertRaises(ConflictError):
            self.ledger.ingest(c, remote_ip="1.1.1.3", user_agent="c")


class LeadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session_secret = b"session-secret-for-tests-32bytes!!"
        config = ServiceConfig(
            db_path=Path(self.tmp.name) / "http.sqlite3",
            bind_host="127.0.0.1",
            bind_port=0,
            allowed_origins=frozenset({"https://iambandobandz.com"}),
            privacy_hash_key=b"y" * 32,
            admin_token="admin-secret",
            ingest_token="server-secret",
            trust_proxy=False,
            admin_session_secret=self.session_secret,
            admin_session_ttl_seconds=3600,
        )
        self.server = LeadHTTPServer(("127.0.0.1", 0), config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method, path, *, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        hdrs = dict(headers or {})
        if payload is not None:
            hdrs.setdefault("Content-Type", "application/json")
            hdrs.setdefault("Content-Length", str(len(payload)))
        conn.request(method, path, body=payload, headers=hdrs)
        response = conn.getresponse()
        data = response.read()
        response_headers = response.headers
        status = response.status
        conn.close()
        return status, response_headers, json.loads(data) if data else None

    def valid_payload(self):
        return {
            "email": "person@example.com",
            "phone": "",
            "sms_consent": False,
            "consent_text_version": "signal-capture-v1",
            "source": "website-pre-redirect",
            "idempotency_key": "http-idempotency-0001",
        }

    def login(self, token="admin-secret", origin="https://iambandobandz.com"):
        status, headers, body = self.request(
            "POST",
            "/api/v1/admin/login",
            body={"token": token},
            headers={"Origin": origin},
        )
        return status, headers, body

    def cookie_from_headers(self, headers):
        raw = headers.get("Set-Cookie", "")
        return raw.split(";", 1)[0]

    def signed_session(self, issued_at, expires_at, nonce="testnonce"):
        unsigned = f"v1.{issued_at}.{expires_at}.{nonce}"
        sig = hmac.new(self.session_secret, unsigned.encode("ascii"), "sha256").hexdigest()
        return f"{unsigned}.{sig}"

    def test_browser_ingest_accepts_exact_origin(self):
        status, headers, body = self.request(
            "POST", "/api/v1/leads", body=self.valid_payload(),
            headers={"Origin": "https://iambandobandz.com", "User-Agent": "browser-test"},
        )
        self.assertEqual(status, 201)
        self.assertTrue(body["ok"])
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "https://iambandobandz.com")

    def test_browser_ingest_rejects_untrusted_origin(self):
        status, _, body = self.request(
            "POST", "/api/v1/leads", body=self.valid_payload(),
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "origin_not_allowed")

    def test_server_to_server_requires_ingest_token_without_origin(self):
        status, _, _ = self.request("POST", "/api/v1/leads", body=self.valid_payload())
        self.assertEqual(status, 403)
        payload = self.valid_payload(); payload["idempotency_key"] = "http-idempotency-0002"
        status, _, body = self.request(
            "POST", "/api/v1/leads", body=payload,
            headers={"X-Lead-Ingest-Token": "server-secret"},
        )
        self.assertEqual(status, 201)
        self.assertTrue(body["ok"])

    def test_admin_stats_require_bearer_token(self):
        status, _, body = self.request("GET", "/api/v1/admin/stats")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")
        status, _, body = self.request(
            "GET", "/api/v1/admin/stats",
            headers={"Authorization": "Bearer admin-secret"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["audit_chain_valid"])

    def test_admin_login_sets_hardened_cookie_and_session_unlocks_stats(self):
        status, headers, body = self.login()
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["expires_in"], 3600)
        set_cookie = headers.get("Set-Cookie", "")
        self.assertIn(f"{ADMIN_SESSION_COOKIE}=", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)
        self.assertIn("Path=/", set_cookie)
        self.assertEqual(headers.get("Access-Control-Allow-Credentials"), "true")
        cookie = self.cookie_from_headers(headers)
        status, _, body = self.request(
            "GET",
            "/api/v1/admin/session",
            headers={"Origin": "https://iambandobandz.com", "Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["authenticated"])
        status, _, body = self.request(
            "GET",
            "/api/v1/admin/stats",
            headers={"Origin": "https://iambandobandz.com", "Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["audit_chain_valid"])

    def test_admin_login_rejects_wrong_token_and_hostile_origin(self):
        status, headers, body = self.login(token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")
        self.assertIsNone(headers.get("Set-Cookie"))
        status, _, body = self.login(origin="https://evil.example")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "origin_not_allowed")

    def test_admin_session_rejects_tampered_and_expired_cookie(self):
        now = int(time.time())
        valid = self.signed_session(now - 10, now + 600)
        tampered = valid[:-1] + ("0" if valid[-1] != "0" else "1")
        for token in [tampered, self.signed_session(now - 7200, now - 3600)]:
            status, _, body = self.request(
                "GET",
                "/api/v1/admin/session",
                headers={
                    "Origin": "https://iambandobandz.com",
                    "Cookie": f"{ADMIN_SESSION_COOKIE}={token}",
                },
            )
            self.assertEqual(status, 401)
            self.assertEqual(body["error"], "unauthorized")

    def test_admin_session_cookie_requires_exact_origin(self):
        status, headers, _ = self.login()
        self.assertEqual(status, 200)
        cookie = self.cookie_from_headers(headers)
        status, _, body = self.request(
            "GET",
            "/api/v1/admin/session",
            headers={"Origin": "https://evil.example", "Cookie": cookie},
        )
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")

    def test_admin_logout_clears_cookie(self):
        status, headers, _ = self.login()
        self.assertEqual(status, 200)
        cookie = self.cookie_from_headers(headers)
        status, headers, body = self.request(
            "POST",
            "/api/v1/admin/logout",
            body={},
            headers={"Origin": "https://iambandobandz.com", "Cookie": cookie},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertIn(f"{ADMIN_SESSION_COOKIE}=", headers.get("Set-Cookie", ""))
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))

    def test_admin_preflight_allows_credentials_only_for_exact_origin(self):
        status, headers, _ = self.request(
            "OPTIONS",
            "/api/v1/admin/login",
            headers={"Origin": "https://iambandobandz.com"},
        )
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "https://iambandobandz.com")
        self.assertEqual(headers.get("Access-Control-Allow-Credentials"), "true")
        status, _, body = self.request(
            "OPTIONS",
            "/api/v1/admin/login",
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "origin_not_allowed")

    def test_healthz_exposes_no_pii(self):
        status, _, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True, "audit_chain_broken_at": None})


if __name__ == "__main__":
    unittest.main()