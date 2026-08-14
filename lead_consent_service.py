"""Private IAMBANDOBANDZ lead/consent service entrypoint.

Raw PII belongs only in the private SQLite runtime volume. Sanitized audit events
can later bridge into Chronos without copying email, phone, IP, or user-agent data.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Optional

from lead_api import LeadHTTPServer, ServiceConfig
from lead_ledger import LeadLedger


def run_server(config: ServiceConfig) -> None:
    server = LeadHTTPServer((config.bind_host, config.bind_port), config)
    logging.getLogger("lead_consent_service").info(
        "lead consent service listening on %s:%s", config.bind_host, config.bind_port
    )
    server.serve_forever()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Durable private lead/consent ledger")
    parser.add_argument("--verify", action="store_true", help="verify the local audit hash chain and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = ServiceConfig.from_env()
    if args.verify:
        ledger = LeadLedger(config.db_path, privacy_hash_key=config.privacy_hash_key)
        ok, broken = ledger.verify_chain()
        print(json.dumps({"ok": ok, "broken_at": broken, "stats": ledger.stats()}, indent=2))
        return 0 if ok else 2
    run_server(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
