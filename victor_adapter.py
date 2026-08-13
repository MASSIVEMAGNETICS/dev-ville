from __future__ import annotations

import argparse
from contextvars import ContextVar
import hashlib
import json
import os
import re
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from company import Company


JOB_SCHEMA = "victor.organ.job.v1"
RECEIPT_SCHEMA = "victor.organ.receipt.v1"
ORGAN_NAME = "dev-ville"
CAPABILITY = "devville.project.build"
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
DEFAULT_MAX_CYCLES = 250
DEFAULT_TIME_DELTA = 5.0
MAX_CYCLES = 500
MAX_TIME_DELTA = 20.0
DEFAULT_MAX_FILES = 128
DEFAULT_MAX_TOTAL_BYTES = 2_000_000
MAX_DIRECTIVE_CHARS = 12_000

_ACTIVE_OUTPUT_ROOT: ContextVar[Path | None] = ContextVar(
    "victor_adapter_active_output_root",
    default=None,
)
_AUDIT_HOOK_INSTALLED = False
_AUDIT_HOOK_LOCK = threading.Lock()


class ContractError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not IDENTIFIER_RE.fullmatch(text):
        raise ContractError(f"invalid {field}")
    return text


def _parse_expiry(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ContractError("expires_at is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ContractError("expires_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ContractError("expires_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_relative_filename(value: Any) -> Path:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise ContractError("generated artifact has an invalid filename")
    rel = Path(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ContractError(f"generated artifact path is unsafe: {raw!r}")
    return rel


def _limits(job: Dict[str, Any]) -> Dict[str, Any]:
    raw = job.get("limits") or {}
    max_cycles = int(raw.get("max_cycles", DEFAULT_MAX_CYCLES))
    time_delta = float(raw.get("time_delta", DEFAULT_TIME_DELTA))
    max_files = int(raw.get("max_files", DEFAULT_MAX_FILES))
    max_total_bytes = int(raw.get("max_total_bytes", DEFAULT_MAX_TOTAL_BYTES))
    if not 1 <= max_cycles <= MAX_CYCLES:
        raise ContractError(f"max_cycles must be between 1 and {MAX_CYCLES}")
    if not 0.1 <= time_delta <= MAX_TIME_DELTA:
        raise ContractError(f"time_delta must be between 0.1 and {MAX_TIME_DELTA}")
    if not 1 <= max_files <= 512:
        raise ContractError("max_files must be between 1 and 512")
    if not 1 <= max_total_bytes <= 20_000_000:
        raise ContractError("max_total_bytes must be between 1 and 20000000")
    return {
        "max_cycles": max_cycles,
        "time_delta": time_delta,
        "max_files": max_files,
        "max_total_bytes": max_total_bytes,
    }


def validate_job(job: Dict[str, Any]) -> Dict[str, Any]:
    if job.get("schema") != JOB_SCHEMA:
        raise ContractError(f"schema must be {JOB_SCHEMA}")
    if job.get("organ") != ORGAN_NAME:
        raise ContractError(f"organ must be {ORGAN_NAME}")
    if job.get("capability") != CAPABILITY:
        raise ContractError(f"capability must be {CAPABILITY}")

    normalized = dict(job)
    normalized["job_id"] = _identifier(job.get("job_id"), "job_id")
    normalized["work_order_id"] = _identifier(job.get("work_order_id"), "work_order_id")
    normalized["lease_id"] = _identifier(job.get("lease_id"), "lease_id")

    directive = str(job.get("directive") or "").strip()
    if not directive:
        raise ContractError("directive is required")
    if len(directive) > MAX_DIRECTIVE_CHARS:
        raise ContractError(f"directive exceeds {MAX_DIRECTIVE_CHARS} characters")
    normalized["directive"] = directive

    expiry = _parse_expiry(job.get("expires_at"))
    if expiry <= datetime.now(timezone.utc):
        raise ContractError("lease has expired")
    normalized["expires_at"] = expiry.isoformat()
    normalized["limits"] = _limits(job)
    return normalized


def _runtime_audit(event: str, args: tuple[Any, ...]) -> None:
    """Enforce the active organ policy only while a run is executing.

    CPython audit hooks are process-global and cannot be removed. The original
    implementation permanently captured one output root, which contaminated
    later jobs/tests and also made a second job with a different output root
    impossible. A ContextVar scopes enforcement to the current execution
    context while retaining the defense-in-depth audit hook.
    """

    root = _ACTIVE_OUTPUT_ROOT.get()
    if root is None:
        return

    denied = {"subprocess.Popen", "os.system", "socket.connect", "socket.connect_ex"}
    if event in denied:
        raise PermissionError(f"Victor organ policy denied audit event: {event}")
    if event != "open" or not args:
        return

    target = args[0]
    if not isinstance(target, (str, bytes, os.PathLike)):
        return
    mode = args[1] if len(args) > 1 else "r"
    flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
    writes = False
    if isinstance(mode, str):
        writes = any(marker in mode for marker in ("w", "a", "x", "+"))
    writes = writes or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
    if writes and not _inside(Path(target), root):
        raise PermissionError(f"Victor organ policy denied write outside output root: {target}")


def _install_runtime_guard() -> None:
    """Install the process-global hook once; activation is context-scoped."""

    global _AUDIT_HOOK_INSTALLED
    if _AUDIT_HOOK_INSTALLED:
        return
    with _AUDIT_HOOK_LOCK:
        if _AUDIT_HOOK_INSTALLED:
            return
        sys.addaudithook(_runtime_audit)
        _AUDIT_HOOK_INSTALLED = True


def _export_generated_files(
    company: Company,
    run_dir: Path,
    *,
    max_files: int,
    max_total_bytes: int,
) -> list[Dict[str, Any]]:
    project = company.current_project
    if project is None:
        raise RuntimeError("Dev-Ville did not create a project")

    files = list(project.files)
    if len(files) > max_files:
        raise ContractError(f"generated file count {len(files)} exceeds limit {max_files}")

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[Dict[str, Any]] = []
    total_bytes = 0
    seen: set[str] = set()

    for file_info in files:
        rel = _safe_relative_filename(file_info.get("filename"))
        rel_key = rel.as_posix()
        if rel_key in seen:
            raise ContractError(f"duplicate generated filename: {rel_key}")
        seen.add(rel_key)

        content = str(file_info.get("content") or "")
        data = content.encode("utf-8")
        total_bytes += len(data)
        if total_bytes > max_total_bytes:
            raise ContractError(f"generated output exceeds {max_total_bytes} bytes")

        target = (artifacts_dir / rel).resolve()
        if not _inside(target, artifacts_dir):
            raise ContractError(f"generated artifact escaped output directory: {rel_key}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        artifacts.append(
            {
                "path": target.relative_to(run_dir).as_posix(),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "description": str(file_info.get("description") or ""),
            }
        )

    return artifacts


def _completed_task_count(tasks: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for task in tasks:
        effort = float(task.get("effort", 0) or 0)
        progress = float(task.get("progress", 0) or 0)
        if effort <= 0 or progress >= effort:
            count += 1
    return count


def _receipt_hash(receipt: Dict[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return sha256_bytes(canonical_json(payload))


def run_job(job: Dict[str, Any], output_root: Path) -> Dict[str, Any]:
    job = validate_job(job)
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = (output_root / job["work_order_id"] / job["job_id"]).resolve()
    if not _inside(run_dir, output_root):
        raise ContractError("run directory escaped output root")
    run_dir.mkdir(parents=True, exist_ok=False)

    _install_runtime_guard()
    policy_token = _ACTIVE_OUTPUT_ROOT.set(output_root)
    try:
        started_at = utc_now()
        company = Company()
        project = company.start_project(job["directive"])
        if project is None:
            raise RuntimeError("Dev-Ville failed to create a project")

        cycles = 0
        limits = job["limits"]
        while project.status != "completed" and cycles < limits["max_cycles"]:
            if _parse_expiry(job["expires_at"]) <= datetime.now(timezone.utc):
                raise ContractError("lease expired during execution")
            company.work_cycle(limits["time_delta"])
            cycles += 1

        project.calculate_progress()
        artifacts = _export_generated_files(
            company,
            run_dir,
            max_files=limits["max_files"],
            max_total_bytes=limits["max_total_bytes"],
        )

        tasks = list(project.tasks)
        completed_tasks = _completed_task_count(tasks)
        status = "completed" if project.status == "completed" and bool(artifacts) else "incomplete"
        receipt: Dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "organ": ORGAN_NAME,
            "capability": CAPABILITY,
            "job_id": job["job_id"],
            "work_order_id": job["work_order_id"],
            "lease_id": job["lease_id"],
            "started_at": started_at,
            "completed_at": utc_now(),
            "status": status,
            "cycles": cycles,
            "limits": limits,
            "project": {
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "progress": round(float(project.progress), 6),
                "task_count": len(tasks),
                "completed_tasks": completed_tasks,
                "ticket_count": len(project.tickets),
            },
            "artifacts": artifacts,
            "runtime_policy": {
                "network": "denied-by-audit-hook",
                "subprocess": "denied-by-audit-hook",
                "write_scope": str(output_root),
                "note": "Defense in depth only; this adapter is not an OS security sandbox.",
            },
        }
        receipt["receipt_hash"] = _receipt_hash(receipt)
        receipt_path = run_dir / "ORGAN_RECEIPT.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        receipt["receipt_path"] = str(receipt_path)
        return receipt
    finally:
        _ACTIVE_OUTPUT_ROOT.reset(policy_token)


def load_job(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"unable to read job file: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError("job file must contain a JSON object")
    return value


def probe() -> Dict[str, Any]:
    return {
        "organ": ORGAN_NAME,
        "status": "ready",
        "job_schema": JOB_SCHEMA,
        "receipt_schema": RECEIPT_SCHEMA,
        "capabilities": [CAPABILITY],
        "network_required": False,
        "external_packages_required": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded Victor adapter for Dev-Ville")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="Report adapter capabilities")
    run = sub.add_parser("run", help="Execute one bounded Victor organ job")
    run.add_argument("--job", required=True, type=Path)
    run.add_argument("--output-root", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "probe":
            result = probe()
        else:
            result = run_job(load_job(args.job), args.output_root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        error = {
            "organ": ORGAN_NAME,
            "status": "error",
            "error": type(exc).__name__,
            "message": str(exc),
        }
        if os.environ.get("VICTOR_ORGAN_DEBUG") == "1":
            error["traceback"] = traceback.format_exc()
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
