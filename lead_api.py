"""HTTP boundary and optional notification adapter for the private lead ledger."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import secrets
import smtplib
import ssl
import threading
import time
from typing import Any, Mapping

from lead_ledger import ConflictError, LeadLedger, LeadSubmission, ValidationError

LOG = logging.getLogger("lead_consent_service")
MAX_BODY_BYTES = 8192


class SlidingWindowLimiter:
    def __init__(self, limit: int = 12, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._hits) > 4096:
                self._hits = {
                    candidate: stamps
                    for candidate, stamps in self._hits.items()
                    if stamps and stamps[-1] >= cutoff
                }
            hits = [stamp for stamp in self._hits.get(key, []) if stamp >= cutoff]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


class Notifier:
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "").strip()
        self.port = int(os.getenv("SMTP_PORT", "465"))
        self.user = os.getenv("SMTP_USER", "").strip()
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.notify_to = os.getenv("LEAD_NOTIFY_TO", "").strip()
        self.from_addr = os.getenv("SMTP_FROM", self.user).strip()

    @property
    def enabled(self) -> bool:
        return all([self.host, self.user, self.password, self.notify_to, self.from_addr])

    def send(self, submission: LeadSubmission, receipt: Mapping[str, Any]) -> bool:
        if not self.enabled:
            return False
        msg = EmailMessage()
        msg["Subject"] = "New IAMBANDOBANDZ signal signup"
        msg["From"] = self.from_addr
        msg["To"] = self.notify_to
        msg.set_content(
            "A new lead was durably recorded.\n\n"
            f"Receipt: {receipt['receipt_id']}\n"
            f"Email: {submission.email or '-'}\n"
            f"Phone: {submission.phone or '-'}\n"
            f"SMS consent: {submission.sms_consent}\n"
            f"Source: {submission.source}\n"
        )
        context = ssl.create_default_context()
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=10) as smtp:
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.user, self.password)
                    smtp.send_message(msg)
            return True
        except Exception:
            LOG.exception("lead persisted but notification email failed")
            return False


@dataclass(frozen=True)
class ServiceConfig:
    db_path: Path
    bind_host: str
    bind_port: int
    allowed_origins: frozenset[str]
    privacy_hash_key: bytes
    admin_token: str
    ingest_token: str
    trust_proxy: bool

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        require_secrets = os.getenv("LEAD_REQUIRE_SECRETS", "1") != "0"
        hash_key = os.getenv("LEAD_PRIVACY_HASH_KEY", "").encode("utf-8")
        if not hash_key:
            if require_secrets:
                raise RuntimeError("LEAD_PRIVACY_HASH_KEY is required")
            hash_key = secrets.token_bytes(32)
        origins = frozenset(
            item.strip().rstrip("/")
            for item in os.getenv(
                "LEAD_ALLOWED_ORIGINS",
                "https://iambandobandz.com,https://www.iambandobandz.com",
            ).split(",")
            if item.strip()
        )
        return cls(
            db_path=Path(os.getenv("LEAD_DB_PATH", "state/private/lead_consent.sqlite3")),
            bind_host=os.getenv("LEAD_BIND_HOST", "127.0.0.1"),
            bind_port=int(os.getenv("LEAD_BIND_PORT", "8787")),
            allowed_origins=origins,
            privacy_hash_key=hash_key,
            admin_token=os.getenv("LEAD_ADMIN_TOKEN", ""),
            ingest_token=os.getenv("LEAD_INGEST_TOKEN", ""),
            trust_proxy=os.getenv("LEAD_TRUST_PROXY", "0") == "1",
        )


class LeadHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: ServiceConfig):
        self.config = config
        self.ledger = LeadLedger(config.db_path, privacy_hash_key=config.privacy_hash_key)
        self.limiter = SlidingWindowLimiter()
        self.notifier = Notifier()
        super().__init__(address, LeadHandler)


class LeadHandler(BaseHTTPRequestHandler):
    server: LeadHTTPServer

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _origin(self) -> str:
        return self.headers.get("Origin", "").strip().rstrip("/")

    def _origin_allowed(self) -> bool:
        origin = self._origin()
        if origin:
            return origin in self.server.config.allowed_origins
        supplied = self.headers.get("X-Lead-Ingest-Token", "")
        expected = self.server.config.ingest_token
        return bool(expected and hmac.compare_digest(supplied, expected))

    def _cors(self) -> None:
        origin = self._origin()
        if origin in self.server.config.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Idempotency-Key")
            self.send_header("Access-Control-Max-Age", "600")

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        if self.path != "/api/v1/leads" or self._origin() not in self.server.config.allowed_origins:
            self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/healthz":
            ok, broken = self.server.ledger.verify_chain()
            self._json(
                HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE,
                {"ok": ok, "audit_chain_broken_at": broken},
            )
            return
        if self.path == "/api/v1/admin/stats":
            expected = self.server.config.admin_token
            auth = self.headers.get("Authorization", "")
            if not expected:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "admin_disabled"})
                return
            supplied = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
            if not supplied or not hmac.compare_digest(supplied, expected):
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            self._json(HTTPStatus.OK, self.server.ledger.stats())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/api/v1/leads":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._origin_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"})
            return
        remote_ip = self.client_address[0]
        if self.server.config.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                remote_ip = forwarded
        rate_key = self.server.ledger.privacy_hash(remote_ip or "unknown")
        if not self.server.limiter.allow(rate_key):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid_body_size"})
            return
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "json_required"})
            return
        try:
            raw = json.loads(self.rfile.read(content_length))
            if not isinstance(raw, dict):
                raise ValidationError("JSON body must be an object")
            if "idempotency_key" not in raw:
                raw["idempotency_key"] = self.headers.get("X-Idempotency-Key", "")
            submission = LeadSubmission.from_mapping(raw)
            result = self.server.ledger.ingest(
                submission,
                remote_ip=remote_ip,
                user_agent=self.headers.get("User-Agent", ""),
            )
            notified = False
            if not result["idempotent_replay"]:
                notified = self.server.notifier.send(submission, result)
            self._json(
                HTTPStatus.CREATED if not result["idempotent_replay"] else HTTPStatus.OK,
                {
                    "ok": True,
                    "receipt_id": result["receipt_id"],
                    "captured_at": result["captured_at"],
                    "idempotent_replay": result["idempotent_replay"],
                    "notification_sent": notified,
                },
            )
        except ValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "validation_error", "message": str(exc)})
        except ConflictError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": "contact_conflict", "message": str(exc)})
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
        except Exception:
            LOG.exception("ingest failed")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})
