# IAMBANDOBANDZ Lead + Consent Ledger

## Purpose

This service is the authoritative first-party ledger for website lead capture. It replaces email relay as the system of record.

The public website may submit contact information, but raw PII must live only on a private runtime volume. Git history, public JSON, Chronos, and audit payloads must never contain raw email addresses, phone numbers, IP addresses, or user-agent strings.

## Invariant

```text
Browser -> HTTPS reverse proxy -> lead_consent_service.py -> SQLite WAL
                                      |                     |
                                      |                     +-> private contacts + consent receipts
                                      +-> sanitized hash chain -> future Chronos bridge
                                      +-> optional SMTP notification
```

Email notification is secondary. A notification failure never rolls back an already committed lead.

## Security boundary

- Browser ingestion is restricted to exact configured origins and rate-limited. It is not called cryptographically authenticated because browser code cannot protect a shared secret.
- Server-to-server ingestion without an `Origin` header requires `X-Lead-Ingest-Token`.
- Admin statistics require `Authorization: Bearer <LEAD_ADMIN_TOKEN>` and return counts only, never contact records.
- Raw IP and user-agent values are not persisted. They are HMAC-SHA256 pseudonyms keyed by `LEAD_PRIVACY_HASH_KEY`.
- The append-only audit chain contains contact IDs, receipt IDs, consent facts, and payload hashes only. It excludes raw PII.
- SQLite runs in WAL mode with `synchronous=FULL`, foreign keys enabled, an exclusive writer lock, idempotency keys, and a verifiable SHA-256 event chain.
- The database file is chmod `0600` where supported and must live on an encrypted private host/volume.
- No secret is committed to this repository.

## Canonical consent text

`signal-capture-v1` is pinned in code. The receipt stores its SHA-256 hash so the backend can prove which exact SMS disclosure was authoritative when consent was captured.

## API

### POST `/api/v1/leads`

```json
{
  "email": "person@example.com",
  "phone": "+14405551234",
  "sms_consent": true,
  "consent_text_version": "signal-capture-v1",
  "source": "website-pre-redirect",
  "idempotency_key": "web-20260814-6a8e7cb235c84269"
}
```

A successful first commit returns HTTP `201`; an idempotent replay returns `200` with the original receipt ID.

### GET `/healthz`

Returns only audit-chain health.

### GET `/api/v1/admin/stats`

Requires the admin bearer token. Returns counts and audit-chain state, not PII.

## Production install

The intended public edge is `https://api.iambandobandz.com`, terminating TLS at Caddy and proxying only to `127.0.0.1:8787`.

Create runtime directories:

```bash
sudo install -d -m 700 /etc/iambandobandz /var/lib/iambandobandz
sudo install -d -m 755 /opt/dev-ville
sudo useradd --system --home /var/lib/iambandobandz --shell /usr/sbin/nologin iambandobandz 2>/dev/null || true
sudo chown -R iambandobandz:iambandobandz /var/lib/iambandobandz
```

Generate three independent secrets and write the root-owned environment file without committing any secret:

```bash
PRIVACY_HASH_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
INGEST_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

sudo tee /etc/iambandobandz/lead-ledger.env >/dev/null <<EOF
LEAD_REQUIRE_SECRETS=1
LEAD_DB_PATH=/var/lib/iambandobandz/lead_consent.sqlite3
LEAD_BIND_HOST=127.0.0.1
LEAD_BIND_PORT=8787
LEAD_ALLOWED_ORIGINS=https://iambandobandz.com,https://www.iambandobandz.com
LEAD_TRUST_PROXY=1
LEAD_PRIVACY_HASH_KEY=$PRIVACY_HASH_KEY
LEAD_ADMIN_TOKEN=$ADMIN_TOKEN
LEAD_INGEST_TOKEN=$INGEST_TOKEN
EOF
sudo chmod 600 /etc/iambandobandz/lead-ledger.env
unset PRIVACY_HASH_KEY ADMIN_TOKEN INGEST_TOKEN
```

SMTP notification is optional and disabled by default. To enable it, add the real `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `LEAD_NOTIFY_TO` values directly to the same root-owned environment file on the runtime host.

Install `deploy/lead-consent.service` under systemd and `deploy/Caddyfile.lead-consent` into the Caddy configuration, then start the service.

## Verification gate before website cutover

Do **not** replace the production FormSubmit client until every gate below is proven against the real HTTPS endpoint:

1. `GET https://api.iambandobandz.com/healthz` returns `{"ok":true,...}`.
2. A synthetic POST from the allowed production origin returns a receipt ID.
3. The SQLite database contains exactly one receipt for that idempotency key after replay.
4. `python lead_consent_service.py --verify` reports a valid audit chain on the runtime host.
5. The admin stats endpoint works only with the bearer token.
6. An untrusted origin is rejected.
7. The runtime database, WAL, environment file, and backups are absent from Git and from the Pages artifact.

Only after those checks pass should the website client be changed to `https://api.iambandobandz.com/api/v1/leads` and FormSubmit removed from the authoritative path.

## Chronos rule

Chronos may receive a sanitized event containing `receipt_id`, `contact_id`, `consent_text_hash`, `payload_hash`, timestamp, source, and audit-chain hash. Chronos must not receive raw email, phone, IP, or user-agent data.
