"""HTTP boundary, owner authentication, and optional notification adapter for the private lead ledger."""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import hmac
from http import HTTPStatus
from http.cookies import SimpleCookie
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
MAX_ADMIN_BODY_BYTES = 4096
ADMIN_SESSION_COOKIE = "__Host-iambandobandz_admin"
ADMIN_SESSION_VERSION = "v1"
MIN_ADMIN_SESSION_SECRET_BYTES = 32


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
    admin_session_secret: bytes = b""
    admin_session_ttl_seconds: int = 8 * 60 * 60

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
        ttl = int(os.getenv("LEAD_ADMIN_SESSION_TTL_SECONDS", str(8 * 60 * 60)))
        if ttl < 300 or ttl > 7 * 24 * 60 * 60:
            raise RuntimeError("LEAD_ADMIN_SESSION_TTL_SECONDS must be between 300 and 604800")
        admin_token = os.getenv("LEAD_ADMIN_TOKEN", "")
        admin_session_secret_raw = os.getenv("LEAD_ADMIN_SESSION_SECRET", "")
        admin_session_secret = admin_session_secret_raw.encode("utf-8")
        if admin_session_secret and len(admin_session_secret) < MIN_ADMIN_SESSION_SECRET_BYTES:
            raise RuntimeError(
                f"LEAD_ADMIN_SESSION_SECRET must be at least {MIN_ADMIN_SESSION_SECRET_BYTES} bytes"
            )
        if admin_session_secret_raw and admin_token and admin_session_secret_raw == admin_token:
            raise RuntimeError("LEAD_ADMIN_SESSION_SECRET must be independent from LEAD_ADMIN_TOKEN")
        return cls(
            db_path=Path(os.getenv("LEAD_DB_PATH", "state/private/lead_consent.sqlite3")),
            bind_host=os.getenv("LEAD_BIND_HOST", "127.0.0.1"),
            bind_port=int(os.getenv("LEAD_BIND_PORT", "8787")),
            allowed_origins=origins,
            privacy_hash_key=hash_key,
            admin_token=admin_token,
            ingest_token=os.getenv("LEAD_INGEST_TOKEN", ""),
            trust_proxy=os.getenv("LEAD_TRUST_PROXY", "0") == "1",
            admin_session_secret=admin_session_secret,
            admin_session_ttl_seconds=ttl,
        )


class LeadHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: ServiceConfig):
        self.config = config
        self.ledger = LeadLedger(config.db_path, privacy_hash_key=config.privacy_hash_key)
        self.limiter = SlidingWindowLimiter()
        self.admin_limiter = SlidingWindowLimiter(limit=8, window_seconds=60)
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

    def _admin_origin_allowed(self) -> bool:
        return self._origin() in self.server.config.allowed_origins

    def _remote_ip(self) -> str:
        remote_ip = self.client_address[0]
        if self.server.config.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                remote_ip = forwarded
        return remote_ip

    def _cors(self, *, admin: bool = False) -> None:
        origin = self._origin()
        if origin in self.server.config.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS" if admin else "POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization" if admin else "Content-Type, X-Idempotency-Key",
            )
            if admin:
                self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Max-Age", "600")

    def _json(
        self,
        status: int,
        payload: Mapping[str, Any],
        *,
        admin: bool = False,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self._cors(admin=admin)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self, max_bytes: int) -> Mapping[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("invalid_content_length") from exc
        if content_length <= 0 or content_length > max_bytes:
            raise ValidationError("invalid_body_size")
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValidationError("json_required")
        raw = json.loads(self.rfile.read(content_length))
        if not isinstance(raw, dict):
            raise ValidationError("JSON body must be an object")
        return raw

    def _session_signature(self, unsigned: str) -> str:
        secret = self.server.config.admin_session_secret
        return hmac.new(secret, unsigned.encode("ascii"), "sha256").hexdigest()

    def _mint_admin_session(self) -> tuple[str, int]:
        issued_at = int(time.time())
        expires_at = issued_at + self.server.config.admin_session_ttl_seconds
        nonce = secrets.token_urlsafe(18)
        unsigned = f"{ADMIN_SESSION_VERSION}.{issued_at}.{expires_at}.{nonce}"
        return f"{unsigned}.{self._session_signature(unsigned)}", expires_at

    def _session_cookie_value(self) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        try:
            parsed = SimpleCookie()
            parsed.load(raw)
            morsel = parsed.get(ADMIN_SESSION_COOKIE)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def _verify_admin_session(self, token: str) -> bool:
        secret = self.server.config.admin_session_secret
        if not secret or not token:
            return False
        parts = token.split(".")
        if len(parts) != 5 or parts[0] != ADMIN_SESSION_VERSION:
            return False
        version, issued_raw, expires_raw, nonce, supplied_sig = parts
        try:
            issued_at = int(issued_raw)
            expires_at = int(expires_raw)
        except ValueError:
            return False
        now = int(time.time())
        if issued_at > now + 60 or expires_at <= now or expires_at <= issued_at:
            return False
        if expires_at - issued_at > self.server.config.admin_session_ttl_seconds:
            return False
        if not nonce or len(nonce) > 128:
            return False
        unsigned = f"{version}.{issued_at}.{expires_at}.{nonce}"
        expected_sig = self._session_signature(unsigned)
        return hmac.compare_digest(supplied_sig, expected_sig)

    def _authorized_admin(self) -> bool:
        expected = self.server.config.admin_token
        auth = self.headers.get("Authorization", "")
        supplied = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
        if expected and supplied and hmac.compare_digest(supplied, expected):
            return True
        if not self._admin_origin_allowed():
            return False
        return self._verify_admin_session(self._session_cookie_value())

    def _set_admin_cookie_header(self, token: str, max_age: int) -> str:
        return (
            f"{ADMIN_SESSION_COOKIE}={token}; Path=/; Max-Age={max_age}; "
            "Secure; HttpOnly; SameSite=Strict"
        )

    def do_OPTIONS(self) -> None:
        if self.path == "/api/v1/leads":
            if not self._admin_origin_allowed():
                self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"})
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._cors(admin=False)
            self.end_headers()
            return
        if self.path in {"/api/v1/admin/login", "/api/v1/admin/logout", "/api/v1/admin/session", "/api/v1/admin/stats"}:
            if not self._admin_origin_allowed():
                self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"}, admin=True)
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._cors(admin=True)
            self.end_headers()
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_GET(self) -> None:
        if self.path == "/healthz":
            ok, broken = self.server.ledger.verify_chain()
            self._json(
                HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE,
                {"ok": ok, "audit_chain_broken_at": broken},
            )
            return
        if self.path == "/api/v1/admin/session":
            if not self._authorized_admin():
                self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}, admin=True)
                return
            self._json(HTTPStatus.OK, {"ok": True, "authenticated": True}, admin=True)
            return
        if self.path == "/api/v1/admin/stats":
            if not self._authorized_admin():
                error = "admin_disabled" if not self.server.config.admin_token else "unauthorized"
                status = HTTPStatus.SERVICE_UNAVAILABLE if error == "admin_disabled" else HTTPStatus.UNAUTHORIZED
                self._json(status, {"error": error}, admin=bool(self._origin()))
                return
            self._json(HTTPStatus.OK, self.server.ledger.stats(), admin=bool(self._origin()))
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/api/v1/admin/login":
            self._handle_admin_login()
            return
        if self.path == "/api/v1/admin/logout":
            if not self._admin_origin_allowed():
                self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"}, admin=True)
                return
            self._json(
                HTTPStatus.OK,
                {"ok": True},
                admin=True,
                headers={"Set-Cookie": self._set_admin_cookie_header("", 0)},
            )
            return
        if self.path != "/api/v1/leads":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._origin_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"})
            return
        remote_ip = self._remote_ip()
        rate_key = self.server.ledger.privacy_hash(remote_ip or "unknown")
        if not self.server.limiter.allow(rate_key):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return
        try:
            raw = dict(self._read_json(MAX_BODY_BYTES))
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
            message = str(exc)
            if message == "json_required":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": message})
            elif message in {"invalid_body_size", "invalid_content_length"}:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE if message == "invalid_body_size" else HTTPStatus.BAD_REQUEST, {"error": message})
            else:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "validation_error", "message": message})
        except ConflictError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": "contact_conflict", "message": str(exc)})
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
        except Exception:
            LOG.exception("ingest failed")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

    def _handle_admin_login(self) -> None:
        if not self._admin_origin_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"}, admin=True)
            return
        config = self.server.config
        if not config.admin_token or not config.admin_session_secret:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "admin_session_disabled"}, admin=True)
            return
        rate_key = "admin:" + self.server.ledger.privacy_hash(self._remote_ip() or "unknown")
        if not self.server.admin_limiter.allow(rate_key):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"}, admin=True)
            return
        try:
            raw = self._read_json(MAX_ADMIN_BODY_BYTES)
            supplied = str(raw.get("token", ""))
        except ValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)}, admin=True)
            return
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"}, admin=True)
            return
        if not supplied or not hmac.compare_digest(supplied, config.admin_token):
            self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}, admin=True)
            return
        session_token, _ = self._mint_admin_session()
        self._json(
            HTTPStatus.OK,
            {"ok": True, "expires_in": config.admin_session_ttl_seconds},
            admin=True,
            headers={"Set-Cookie": self._set_admin_cookie_header(session_token, config.admin_session_ttl_seconds)},
        )