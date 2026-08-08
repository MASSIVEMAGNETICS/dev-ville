"""Executable integration/E2E beta organ for Dev-Ville.

Unlike the legacy beta simulator, this organ never invents bugs or UX scores.
It executes inspectable scenarios against exact artifact bytes and reports only
observed pass/fail evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    passed: bool
    required: bool
    detail: str
    return_code: Optional[int] = None


@dataclass(frozen=True)
class BetaReceipt:
    artifact_sha256: str
    evidence_sha256: str
    passed: bool
    scenarios: List[Dict[str, Any]]
    ux_score: None = None
    ux_status: str = "not_measured_by_executable_beta"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutableBetaOrgan:
    def __init__(self, timeout_seconds: float = 8.0):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _safe_name(filename: str) -> str:
        normalized = str(filename).replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError(f"unsafe artifact filename: {filename!r}")
        return path.name

    @classmethod
    def artifact_hash(cls, files: Sequence[Dict[str, Any]]) -> str:
        rows = []
        for item in files:
            name = cls._safe_name(item.get("filename", ""))
            content = item.get("content", "")
            if not isinstance(content, str):
                raise ValueError(f"artifact {name!r} content must be text")
            rows.append({"filename": name, "content": content})
        rows.sort(key=lambda x: x["filename"])
        encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _classes(source: str) -> set[str]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return set()
        return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    def _run(self, cwd: str, args: List[str]) -> ScenarioResult:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": cwd,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        try:
            proc = subprocess.run(
                args,
                cwd=cwd,
                env=env,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
            detail = (proc.stdout + "\n" + proc.stderr).strip()[-3000:]
            return ScenarioResult(
                name="subprocess",
                passed=proc.returncode == 0,
                required=True,
                detail=detail,
                return_code=proc.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            return ScenarioResult(
                name="subprocess",
                passed=False,
                required=True,
                detail=f"timeout after {self.timeout_seconds}s: {exc}",
                return_code=None,
            )

    def run(self, files: Sequence[Dict[str, Any]]) -> BetaReceipt:
        scenarios: List[ScenarioResult] = []
        try:
            artifact_sha = self.artifact_hash(files)
        except Exception as exc:
            scenarios.append(ScenarioResult("artifact_safety", False, True, str(exc)))
            return self._receipt("", scenarios)

        with tempfile.TemporaryDirectory(prefix="devville-beta-") as tmp:
            py_files: List[str] = []
            primary_files: List[str] = []
            frontend_module: Optional[str] = None
            backend_module: Optional[str] = None

            for item in files:
                name = self._safe_name(item.get("filename", ""))
                content = item.get("content", "")
                Path(tmp, name).write_text(content, encoding="utf-8")
                if name.endswith(".py"):
                    py_files.append(name)
                    if not name.startswith("test_") and not name.startswith("test_verified_"):
                        primary_files.append(name)
                        classes = self._classes(content)
                        module = name[:-3]
                        if "FrontendController" in classes:
                            frontend_module = module
                        if "BackendService" in classes:
                            backend_module = module

            if not py_files:
                scenarios.append(ScenarioResult("python_artifacts_present", False, True, "no Python artifacts found"))
                return self._receipt(artifact_sha, scenarios)

            compile_result = self._run(tmp, [sys.executable, "-m", "py_compile", *py_files])
            scenarios.append(ScenarioResult("compile_all", compile_result.passed, True, compile_result.detail, compile_result.return_code))

            test_files = [name for name in py_files if name.startswith("test_") or name.startswith("test_verified_")]
            if test_files:
                test_result = self._run(tmp, [sys.executable, "-m", "unittest", "discover", "-v"])
                scenarios.append(ScenarioResult("test_suite", test_result.passed, True, test_result.detail, test_result.return_code))
            else:
                scenarios.append(ScenarioResult("test_suite", False, True, "no executable test artifacts present"))

            for name in primary_files:
                result = self._run(tmp, [sys.executable, name])
                scenarios.append(ScenarioResult(f"entrypoint:{name}", result.passed, True, result.detail, result.return_code))

            if frontend_module and backend_module:
                harness = f'''\nimport importlib\nfront = importlib.import_module({frontend_module!r})\nback = importlib.import_module({backend_module!r})\nservice = back.BackendService()\nassert service.start() is True\ncreated = service.process_request("POST", "/e2e", {{"value": 7}})\nassert created.get("status") == 201, created\nfetched = service.process_request("GET", "/e2e")\nassert fetched.get("status") == 200, fetched\ncontroller = front.FrontendController()\nassert controller.initialize() is True\nview = controller.render_view("e2e", fetched)\nassert view["data"]["data"]["value"] == 7, view\nprint("E2E_OK")\n'''
                Path(tmp, "_devville_e2e.py").write_text(harness, encoding="utf-8")
                result = self._run(tmp, [sys.executable, "_devville_e2e.py"])
                scenarios.append(ScenarioResult("frontend_backend_e2e", result.passed, True, result.detail, result.return_code))
            else:
                scenarios.append(ScenarioResult(
                    "frontend_backend_e2e",
                    True,
                    False,
                    "not applicable: both FrontendController and BackendService were not present in this bundle",
                ))

        return self._receipt(artifact_sha, scenarios)

    @staticmethod
    def _receipt(artifact_sha: str, scenarios: List[ScenarioResult]) -> BetaReceipt:
        rows = [asdict(s) for s in scenarios]
        passed = bool(rows) and all(row["passed"] for row in rows if row["required"])
        evidence_core = {"artifact_sha256": artifact_sha, "passed": passed, "scenarios": rows}
        evidence_sha = hashlib.sha256(
            json.dumps(evidence_core, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return BetaReceipt(artifact_sha, evidence_sha, passed, rows)
