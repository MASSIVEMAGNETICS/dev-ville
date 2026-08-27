#!/usr/bin/env python3
"""Cross-repository closed-loop synchronization verifier for the Massive Magnetics control plane."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "empire_sync" / "manifest.json"
LEDGER_PATH = ROOT / "chronos" / "canonical_execution.jsonl"
MAP_PATH = ROOT / "CANONICAL_EXECUTION_MAP.md"
RAW_BASE = "https://raw.githubusercontent.com"
API_BASE = "https://api.github.com"


class CheckFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CheckFailure(f"{path.relative_to(ROOT)} must be a JSON object")
    return value


def request_bytes(url: str) -> bytes:
    headers = {
        "User-Agent": "massive-magnetics-empire-sync/1.0",
        "Accept": "application/vnd.github+json",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token and url.startswith(API_BASE):
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return response.read()


def remote_raw(repo: str, branch: str, path: str) -> bytes:
    return request_bytes(f"{RAW_BASE}/{repo}/{branch}/{path}")


def record(checks: dict, name: str, ok: bool, detail: str) -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}


def validate_local(manifest: dict, checks: dict) -> None:
    if manifest.get("schema_version") != "empire-sync/1.0":
        record(checks, "manifest_schema", False, "unsupported manifest schema")
        return
    record(checks, "manifest_schema", True, manifest["schema_version"])

    lines = [
        line
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous_chain = None
    expected_sequence = 1
    try:
        for line in lines:
            item = json.loads(line)
            event = item["event"]
            receipt = item["receipt"]
            if event["sequence"] != expected_sequence or receipt["sequence"] != expected_sequence:
                raise CheckFailure(f"sequence {expected_sequence} is missing or reordered")
            if receipt.get("previous_chain_hash") != previous_chain:
                raise CheckFailure(f"sequence {expected_sequence} breaks previous_chain_hash")
            previous_chain = receipt.get("chain_hash")
            if not previous_chain:
                raise CheckFailure(f"sequence {expected_sequence} has no chain_hash")
            expected_sequence += 1
    except (KeyError, json.JSONDecodeError, CheckFailure) as exc:
        record(checks, "chronos_append_chain", False, str(exc))
    else:
        record(
            checks,
            "chronos_append_chain",
            True,
            f"{len(lines)} contiguous append-only receipts; head={previous_chain}",
        )

    execution_map = MAP_PATH.read_text(encoding="utf-8")
    missing = [
        anchor["sha"]
        for anchor in manifest.get("canonical_anchors", [])
        if anchor["sha"] not in execution_map
    ]
    record(
        checks,
        "execution_map_anchors",
        not missing,
        "all canonical anchors present" if not missing else f"missing anchors: {missing}",
    )


def validate_anchor_existence(manifest: dict, checks: dict) -> None:
    missing: list[str] = []
    for anchor in manifest.get("canonical_anchors", []):
        repo = anchor["repository"]
        sha = anchor["sha"]
        url = f"{API_BASE}/repos/{repo}/commits/{sha}"
        try:
            data = json.loads(request_bytes(url).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            missing.append(f"{repo}@{sha}")
            continue
        if data.get("sha") != sha:
            missing.append(f"{repo}@{sha}")
    record(
        checks,
        "immutable_anchor_existence",
        not missing,
        "all immutable anchors resolve" if not missing else f"unresolved: {missing}",
    )


def validate_remote_surface(manifest: dict, checks: dict) -> None:
    surface = manifest["remote_surface"]
    repo = surface["repository"]
    branch = surface["branch"]
    payloads: dict[str, bytes] = {}
    missing: list[str] = []
    for path in surface["required_paths"]:
        try:
            payloads[path] = remote_raw(repo, branch, path)
        except (HTTPError, URLError, TimeoutError):
            missing.append(path)
    if missing:
        record(checks, "remote_surface_reachable", False, f"missing/unreachable: {missing}")
        return
    record(checks, "remote_surface_reachable", True, f"{len(payloads)} required surfaces readable")

    try:
        contract = json.loads(payloads["store/sync-contract.json"])
        registry = json.loads(payloads["store/assets/assets.json"])
        commerce = json.loads(payloads["store/commerce.json"])
        json.loads(payloads["proof/ledger.json"])
        radar = json.loads(payloads["frontier-radar/data/status.json"])
        html = payloads["store/index.html"].decode("utf-8")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        record(checks, "remote_surface_parse", False, str(exc))
        return
    record(checks, "remote_surface_parse", True, "remote JSON/HTML parsed")

    releases = contract.get("releases") or []
    contract_skus = {item.get("sku") for item in releases}
    assets = {item.get("id"): item for item in registry.get("assets", [])}
    products = {item.get("sku"): item for item in registry.get("products", [])}

    mismatches: list[str] = []
    if contract.get("schema_version") != "store-sync/1.0":
        mismatches.append("sync contract schema")
    if commerce.get("status") != "active":
        mismatches.append("commerce status")
    if set(commerce.get("catalog_skus") or []) != contract_skus:
        mismatches.append("commerce SKU set")
    if set(products) != contract_skus:
        mismatches.append("product SKU set")

    storefront = registry.get("storefront") or {}
    if storefront.get("checkout_state") != commerce.get("status"):
        mismatches.append("storefront checkout_state")
    if storefront.get("canonical_path") != commerce.get("canonical_path"):
        mismatches.append("storefront canonical_path")

    for release in releases:
        sku = release.get("sku")
        asset_id = release.get("art_asset")
        public_path = release.get("public_art_path")
        product = products.get(sku) or {}
        asset = assets.get(asset_id) or {}
        if product.get("art_asset") != asset_id:
            mismatches.append(f"{sku}:art_asset")
        if product.get("checkout_state") != commerce.get("status"):
            mismatches.append(f"{sku}:checkout_state")
        if asset.get("path") != public_path:
            mismatches.append(f"{sku}:registry_art")
        marker = f'data-sku="{sku}"'
        if marker not in html:
            mismatches.append(f"{sku}:missing_card")
            continue
        start = html.index(marker)
        end = html.find("</article>", start)
        block = html[start:end if end >= 0 else len(html)]
        if f'src="{public_path}"' not in block:
            mismatches.append(f"{sku}:rendered_art")

    record(
        checks,
        "storefront_closed_loop",
        not mismatches,
        "contract -> registry -> commerce -> HTML agree"
        if not mismatches
        else f"drift: {mismatches}",
    )

    proof_text = payloads["proof/ledger.json"].decode("utf-8")
    proof_missing = [
        anchor["sha"]
        for anchor in manifest.get("canonical_anchors", [])
        if anchor.get("must_appear_in_public_proof") and anchor["sha"] not in proof_text
    ]
    record(
        checks,
        "public_proof_projection",
        not proof_missing,
        "all required canonical anchors are publicly projected"
        if not proof_missing
        else f"proof ledger missing: {proof_missing}",
    )

    radar_ok = (
        radar.get("healthy") is True
        and int(radar.get("healthy_source_count", 0)) >= 2
        and int(radar.get("error_count", 1)) == 0
    )
    record(
        checks,
        "frontier_radar_health",
        radar_ok,
        f"healthy={radar.get('healthy')} sources={radar.get('healthy_source_count')} errors={radar.get('error_count')}",
    )


def build_report(local_only: bool) -> tuple[dict, bool]:
    manifest = load_json(MANIFEST_PATH)
    checks: dict[str, dict] = {}
    validate_local(manifest, checks)
    if not local_only:
        validate_anchor_existence(manifest, checks)
        validate_remote_surface(manifest, checks)
    ok = all(item["ok"] for item in checks.values())
    report = {
        "schema_version": "empire-sync-status/1.0",
        "manifest_revision": manifest.get("revision"),
        "mode": "local" if local_only else "strict",
        "overall": "PASS" if ok else "FAIL",
        "checks": checks,
    }
    return report, ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()

    try:
        report, ok = build_report(args.local_only)
    except (OSError, json.JSONDecodeError, CheckFailure) as exc:
        report = {
            "schema_version": "empire-sync-status/1.0",
            "mode": "local" if args.local_only else "strict",
            "overall": "FAIL",
            "checks": {"bootstrap": {"ok": False, "detail": str(exc)}},
        }
        ok = False

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.write_report:
        target = args.write_report
        if not target.is_absolute():
            target = ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
