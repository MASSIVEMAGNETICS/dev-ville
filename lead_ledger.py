"""Durable private lead/contact and consent ledger primitives."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from typing import Any, Mapping, Optional

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
CONSENT_TEXTS = {
    "signal-capture-v1": (
        "I agree to receive occasional automated promotional texts from IAMBANDOBANDZ. "
        "Consent is not a condition of purchase. Message and data rates may apply. "
        "Reply STOP to opt out."
    )
}


class ValidationError(ValueError):
    pass


class ConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeadSubmission:
    email: Optional[str]
    phone: Optional[str]
    sms_consent: bool
    consent_text_version: str
    source: str
    idempotency_key: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LeadSubmission":
        email = normalize_email(raw.get("email"))
        phone = normalize_phone(raw.get("phone"))
        if not email and not phone:
            raise ValidationError("email or phone is required")
        sms_consent = raw.get("sms_consent") is True
        if phone and not sms_consent:
            raise ValidationError("sms_consent must be true when a phone number is submitted")
        version = str(raw.get("consent_text_version", "")).strip()
        if not version or len(version) > 64:
            raise ValidationError("consent_text_version is required")
        if version not in CONSENT_TEXTS:
            raise ValidationError("unknown consent_text_version")
        source = str(raw.get("source", "")).strip()
        if not source or len(source) > 160:
            raise ValidationError("source is required")
        idem = str(raw.get("idempotency_key", "")).strip()
        if not (16 <= len(idem) <= 128) or not re.fullmatch(r"[A-Za-z0-9._:-]+", idem):
            raise ValidationError("idempotency_key must be 16-128 safe characters")
        return cls(email, phone, sms_consent, version, source, idem)


def normalize_email(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if len(text) > 254 or not EMAIL_RE.fullmatch(text):
        raise ValidationError("invalid email address")
    return text


def normalize_phone(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    compact = re.sub(r"[\s().-]", "", text)
    if compact.startswith("1") and len(compact) == 11:
        compact = "+" + compact
    elif len(compact) == 10 and compact.isdigit():
        compact = "+1" + compact
    if not PHONE_RE.fullmatch(compact):
        raise ValidationError("phone must normalize to E.164")
    return compact


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class LeadLedger:
    """SQLite WAL ledger with PII separated from sanitized hash-chained audit events."""

    def __init__(self, db_path: str | Path, *, privacy_hash_key: bytes):
        if len(privacy_hash_key) < 16:
            raise ValueError("privacy_hash_key must be at least 16 bytes")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.privacy_hash_key = privacy_hash_key
        self._write_lock = threading.Lock()
        self._init_db()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def _session(self):
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    contact_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE,
                    phone TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consent_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    contact_id TEXT NOT NULL REFERENCES contacts(contact_id),
                    sms_consent INTEGER NOT NULL CHECK (sms_consent IN (0,1)),
                    email_submitted INTEGER NOT NULL CHECK (email_submitted IN (0,1)),
                    consent_text_version TEXT NOT NULL,
                    source TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    ip_hash TEXT NOT NULL,
                    user_agent_hash TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    consent_text_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_receipts_contact ON consent_receipts(contact_id);
                CREATE INDEX IF NOT EXISTS idx_audit_subject ON audit_events(subject_id, seq);
                """
            )

    def privacy_hash(self, value: str) -> str:
        return hmac.new(self.privacy_hash_key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def ingest(self, submission: LeadSubmission, *, remote_ip: str, user_agent: str) -> dict[str, Any]:
        payload_for_hash = {
            "email": submission.email,
            "phone": submission.phone,
            "sms_consent": submission.sms_consent,
            "consent_text_version": submission.consent_text_version,
            "source": submission.source,
            "idempotency_key": submission.idempotency_key,
        }
        payload_hash = hashlib.sha256(
            canonical_json(payload_for_hash).encode("utf-8")
        ).hexdigest()
        consent_text_hash = hashlib.sha256(
            CONSENT_TEXTS[submission.consent_text_version].encode("utf-8")
        ).hexdigest()
        with self._write_lock, self._session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT receipt_id, contact_id, captured_at, payload_hash FROM consent_receipts WHERE idempotency_key=?",
                    (submission.idempotency_key,),
                ).fetchone()
                if existing:
                    if existing["payload_hash"] != payload_hash:
                        raise ConflictError("idempotency key was already used for different data")
                    conn.execute("COMMIT")
                    return {
                        "receipt_id": existing["receipt_id"],
                        "contact_id": existing["contact_id"],
                        "captured_at": existing["captured_at"],
                        "idempotent_replay": True,
                    }

                email_row = conn.execute(
                    "SELECT contact_id FROM contacts WHERE email=?", (submission.email,)
                ).fetchone() if submission.email else None
                phone_row = conn.execute(
                    "SELECT contact_id FROM contacts WHERE phone=?", (submission.phone,)
                ).fetchone() if submission.phone else None
                if email_row and phone_row and email_row["contact_id"] != phone_row["contact_id"]:
                    raise ConflictError("email and phone resolve to different existing contacts")

                matched_contact = email_row or phone_row
                contact_id = matched_contact["contact_id"] if matched_contact else None
                now = utc_now()
                if not contact_id:
                    contact_id = "contact_" + secrets.token_hex(12)
                    conn.execute(
                        "INSERT INTO contacts(contact_id,email,phone,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (contact_id, submission.email, submission.phone, now, now),
                    )
                else:
                    row = conn.execute(
                        "SELECT email, phone FROM contacts WHERE contact_id=?", (contact_id,)
                    ).fetchone()
                    email = row["email"] or submission.email
                    phone = row["phone"] or submission.phone
                    if row["email"] and submission.email and row["email"] != submission.email:
                        raise ConflictError("contact already has a different email")
                    if row["phone"] and submission.phone and row["phone"] != submission.phone:
                        raise ConflictError("contact already has a different phone")
                    conn.execute(
                        "UPDATE contacts SET email=?, phone=?, updated_at=? WHERE contact_id=?",
                        (email, phone, now, contact_id),
                    )

                receipt_material = canonical_json({
                    "contact_id": contact_id,
                    "captured_at": now,
                    "payload_hash": payload_hash,
                    "idempotency_key": submission.idempotency_key,
                })
                receipt_id = "consent_" + hashlib.sha256(
                    receipt_material.encode("utf-8")
                ).hexdigest()[:24]
                conn.execute(
                    """INSERT INTO consent_receipts(
                        receipt_id,contact_id,sms_consent,email_submitted,consent_text_version,source,
                        captured_at,idempotency_key,ip_hash,user_agent_hash,payload_hash,consent_text_hash
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        receipt_id,
                        contact_id,
                        int(submission.sms_consent),
                        int(bool(submission.email)),
                        submission.consent_text_version,
                        submission.source,
                        now,
                        submission.idempotency_key,
                        self.privacy_hash(remote_ip or "unknown"),
                        self.privacy_hash(user_agent or "unknown"),
                        payload_hash,
                        consent_text_hash,
                    ),
                )
                audit_payload = {
                    "receipt_id": receipt_id,
                    "contact_id": contact_id,
                    "sms_consent": submission.sms_consent,
                    "email_submitted": bool(submission.email),
                    "consent_text_version": submission.consent_text_version,
                    "source": submission.source,
                    "payload_hash": payload_hash,
                    "consent_text_hash": consent_text_hash,
                }
                self._append_audit(conn, "lead.consent.captured", contact_id, audit_payload, now)
                conn.execute("COMMIT")
                return {
                    "receipt_id": receipt_id,
                    "contact_id": contact_id,
                    "captured_at": now,
                    "idempotent_replay": False,
                }
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def _append_audit(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        subject_id: str,
        payload: Mapping[str, Any],
        created_at: str,
    ) -> None:
        prior = conn.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prior["event_hash"] if prior else "GENESIS"
        event_id = "event_" + secrets.token_hex(12)
        payload_json = canonical_json(dict(payload))
        material = canonical_json({
            "event_id": event_id,
            "event_type": event_type,
            "subject_id": subject_id,
            "created_at": created_at,
            "payload": json.loads(payload_json),
            "prev_hash": prev_hash,
        })
        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        conn.execute(
            "INSERT INTO audit_events(event_id,event_type,subject_id,created_at,payload_json,prev_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
            (event_id, event_type, subject_id, created_at, payload_json, prev_hash, event_hash),
        )

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        with self._session() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY seq").fetchall()
        prev_hash = "GENESIS"
        for row in rows:
            if row["prev_hash"] != prev_hash:
                return False, int(row["seq"])
            material = canonical_json({
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "subject_id": row["subject_id"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload_json"]),
                "prev_hash": row["prev_hash"],
            })
            if hashlib.sha256(material.encode("utf-8")).hexdigest() != row["event_hash"]:
                return False, int(row["seq"])
            prev_hash = row["event_hash"]
        return True, None

    def stats(self) -> dict[str, Any]:
        ok, broken_at = self.verify_chain()
        with self._session() as conn:
            contacts = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
            receipts = conn.execute("SELECT COUNT(*) FROM consent_receipts").fetchone()[0]
            sms = conn.execute("SELECT COUNT(*) FROM consent_receipts WHERE sms_consent=1").fetchone()[0]
        return {
            "contacts": contacts,
            "consent_receipts": receipts,
            "sms_consents": sms,
            "audit_chain_valid": ok,
            "audit_chain_broken_at": broken_at,
        }
