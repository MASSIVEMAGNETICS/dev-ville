"""Evidence-backed verification boundary for Dev-Ville.

This module intentionally uses only the Python standard library. It turns
software-artifact acceptance into a deterministic process:

1. validate artifact paths;
2. hash the exact artifact bundle;
3. compile every Python source;
4. run generated behavioral tests in an isolated temporary directory;
5. emit a hash-bound verification receipt.

A receipt is evidence, not a score. There are no random approvals, random
confidence values, or synthetic pass/fail decisions in this module.
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
class CheckResult:
    """One deterministic verification check."""

    name: str
    passed: bool
    required: bool
    detail: str


@dataclass(frozen=True)
class VerificationReceipt:
    """Immutable evidence summary for one verification attempt."""

    ticket_id: int
    ticket_title: str
    artifact_sha256: str
    evidence_sha256: str
    passed: bool
    checks: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VerificationBoundary:
    """Deterministic verification gate for generated Python artifacts."""

    def __init__(self, timeout_seconds: float = 10.0):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Reject absolute paths, traversal, nested paths, and NUL bytes."""
        if not isinstance(filename, str) or not filename:
            raise ValueError("artifact filename must be a non-empty string")
        if "\x00" in filename:
            raise ValueError("artifact filename contains NUL byte")

        normalized = filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError(f"unsafe artifact filename: {filename!r}")
        return path.name

    @classmethod
    def artifact_hash(cls, files: Sequence[Dict[str, Any]]) -> str:
        """Hash an artifact bundle deterministically by filename and content."""
        canonical: List[Dict[str, str]] = []
        for item in files:
            filename = cls._safe_filename(str(item.get("filename", "")))
            content = item.get("content", "")
            if not isinstance(content, str):
                raise ValueError(f"artifact content for {filename!r} must be text")
            canonical.append({"filename": filename, "content": content})

        canonical.sort(key=lambda row: row["filename"])
        encoded = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _module_profile(source: str) -> Optional[str]:
        """Determine which deterministic behavioral test profile applies."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        class_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        if "FrontendController" in class_names:
            return "frontend"
        if "BackendService" in class_names:
            return "backend"
        if "SystemArchitecture" in class_names:
            return "architecture"

        generic = sorted(name for name in class_names if name.endswith("Module"))
        if len(generic) == 1:
            return f"generic:{generic[0]}"
        return None

    @staticmethod
    def _render_test(module_name: str, profile: str) -> str:
        """Create executable behavioral tests for a known artifact contract."""
        if profile == "frontend":
            body = f'''from {module_name} import FrontendController\n\n\nclass TestVerifiedFrontend(unittest.TestCase):\n    def test_initialize_render_action_and_health(self):\n        controller = FrontendController()\n        self.assertTrue(controller.initialize())\n        rendered = controller.render_view("home", {{"title": "verified"}})\n        self.assertEqual(rendered["view"], "home")\n        self.assertEqual(rendered["data"]["title"], "verified")\n        action = controller.handle_user_action("ping", {{"value": 1}})\n        self.assertEqual(action["status"], "processed")\n        health = controller.get_health()\n        self.assertEqual(health["status"], "healthy")\n        self.assertGreaterEqual(health["components_loaded"], 1)\n'''
        elif profile == "backend":
            body = f'''from {module_name} import BackendService\n\n\nclass TestVerifiedBackend(unittest.TestCase):\n    def test_crud_and_health_contract(self):\n        service = BackendService()\n        self.assertTrue(service.start())\n        created = service.process_request("POST", "/users", {{"name": "verified"}})\n        self.assertEqual(created["status"], 201)\n        fetched = service.process_request("GET", "/users")\n        self.assertEqual(fetched["status"], 200)\n        self.assertEqual(fetched["data"]["name"], "verified")\n        updated = service.process_request("PUT", "/users", {{"name": "updated"}})\n        self.assertEqual(updated["status"], 200)\n        fetched = service.process_request("GET", "/users")\n        self.assertEqual(fetched["data"]["name"], "updated")\n        deleted = service.process_request("DELETE", "/users")\n        self.assertEqual(deleted["status"], 200)\n        missing = service.process_request("GET", "/users")\n        self.assertEqual(missing["status"], 404)\n        self.assertEqual(service.health_check()["status"], "healthy")\n'''
        elif profile == "architecture":
            body = f'''from {module_name} import SystemArchitecture\n\n\nclass TestVerifiedArchitecture(unittest.TestCase):\n    def test_blueprint_contract(self):\n        architecture = SystemArchitecture("verified")\n        architecture.add_component("Frontend", "ui")\n        architecture.add_component("Backend", "service")\n        architecture.add_connection("Frontend", "Backend")\n        blueprint = architecture.generate_blueprint()\n        self.assertEqual(blueprint["project"], "verified")\n        self.assertEqual(blueprint["component_count"], 2)\n        self.assertEqual(len(blueprint["connections"]), 1)\n'''
        elif profile.startswith("generic:"):
            class_name = profile.split(":", 1)[1]
            body = f'''from {module_name} import {class_name}\n\n\nclass TestVerifiedGenericModule(unittest.TestCase):\n    def test_initialize_execute_and_status(self):\n        module = {class_name}()\n        self.assertTrue(module.initialize())\n        result = module.execute("verify", {{"value": 1}})\n        self.assertEqual(result["status"], "completed")\n        self.assertEqual(result["action"], "verify")\n        status = module.get_status()\n        self.assertTrue(status["initialized"])\n'''
        else:
            raise ValueError(f"unsupported verification profile: {profile}")

        return (
            '"""Auto-generated deterministic acceptance tests.\n\n'
            "Generated by Dev-Ville's evidence-backed verification boundary.\n"
            '"""\n'
            "import unittest\n\n"
            + body
            + "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
        )

    def generate_test_artifacts(
        self, files: Sequence[Dict[str, Any]], description: str
    ) -> List[Dict[str, Any]]:
        """Generate real behavioral tests for the latest supported Python artifact."""
        primaries = [
            item
            for item in files
            if str(item.get("filename", "")).endswith(".py")
            and not str(item.get("filename", "")).startswith("test_")
        ]
        if not primaries:
            return []

        primary = primaries[-1]
        filename = self._safe_filename(str(primary["filename"]))
        source = str(primary.get("content", ""))
        profile = self._module_profile(source)
        if profile is None:
            return []

        module_name = Path(filename).stem
        test_filename = f"test_verified_{module_name}.py"
        return [
            {
                "filename": test_filename,
                "content": self._render_test(module_name, profile),
                "description": f"Verified tests for {description}",
            }
        ]

    @staticmethod
    def _placeholder_test_check(files: Sequence[Dict[str, Any]]) -> CheckResult:
        """Detect legacy tests that cannot constitute verification evidence."""
        offenders: List[str] = []
        for item in files:
            filename = str(item.get("filename", ""))
            if not filename.startswith("test_"):
                continue
            content = str(item.get("content", ""))
            if "assertTrue(True" in content.replace(" ", ""):
                offenders.append(filename)
        if offenders:
            return CheckResult(
                name="legacy_placeholder_test_scan",
                passed=False,
                required=False,
                detail="Non-authoritative placeholder tests detected: " + ", ".join(offenders),
            )
        return CheckResult(
            name="legacy_placeholder_test_scan",
            passed=True,
            required=False,
            detail="No unconditional assertTrue(True) placeholder tests detected.",
        )

    def verify(
        self,
        files: Sequence[Dict[str, Any]],
        ticket_id: int,
        ticket_title: str,
    ) -> VerificationReceipt:
        """Verify an artifact bundle and emit a hash-bound receipt."""
        checks: List[CheckResult] = []

        try:
            artifact_sha = self.artifact_hash(files)
            checks.append(
                CheckResult(
                    name="artifact_bundle_hash",
                    passed=True,
                    required=True,
                    detail=f"SHA-256 {artifact_sha}",
                )
            )
        except Exception as exc:
            artifact_sha = hashlib.sha256(b"invalid-artifact-bundle").hexdigest()
            checks.append(
                CheckResult(
                    name="artifact_bundle_hash",
                    passed=False,
                    required=True,
                    detail=f"Artifact validation failed: {exc}",
                )
            )

        checks.append(self._placeholder_test_check(files))

        if not files:
            checks.append(
                CheckResult(
                    name="artifact_presence",
                    passed=False,
                    required=True,
                    detail="No artifact files were associated with this ticket.",
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="artifact_presence",
                    passed=True,
                    required=True,
                    detail=f"{len(files)} artifact file(s) supplied.",
                )
            )

        with tempfile.TemporaryDirectory(prefix="devville-verify-") as temp_dir:
            root = Path(temp_dir)
            write_failed = False
            for item in files:
                try:
                    filename = self._safe_filename(str(item.get("filename", "")))
                    content = item.get("content", "")
                    if not isinstance(content, str):
                        raise ValueError("content is not text")
                    (root / filename).write_text(content, encoding="utf-8")
                except Exception as exc:
                    write_failed = True
                    checks.append(
                        CheckResult(
                            name="artifact_materialization",
                            passed=False,
                            required=True,
                            detail=str(exc),
                        )
                    )
                    break

            if not write_failed:
                checks.append(
                    CheckResult(
                        name="artifact_materialization",
                        passed=True,
                        required=True,
                        detail="Artifact bundle materialized in an isolated temporary directory.",
                    )
                )

                python_files = sorted(root.glob("*.py"))
                if not python_files:
                    checks.append(
                        CheckResult(
                            name="python_source_presence",
                            passed=False,
                            required=True,
                            detail="No Python sources found in verification bundle.",
                        )
                    )
                else:
                    compile_errors: List[str] = []
                    for source_path in python_files:
                        proc = subprocess.run(
                            [sys.executable, "-m", "py_compile", source_path.name],
                            cwd=root,
                            capture_output=True,
                            text=True,
                            timeout=self.timeout_seconds,
                            env={
                                "PATH": os.environ.get("PATH", ""),
                                "PYTHONPATH": str(root),
                                "PYTHONDONTWRITEBYTECODE": "1",
                            },
                            check=False,
                        )
                        if proc.returncode != 0:
                            compile_errors.append(
                                f"{source_path.name}: {(proc.stderr or proc.stdout).strip()}"
                            )
                    checks.append(
                        CheckResult(
                            name="python_compile",
                            passed=not compile_errors,
                            required=True,
                            detail=(
                                "All Python sources compiled successfully."
                                if not compile_errors
                                else " | ".join(compile_errors)
                            ),
                        )
                    )

                    verified_tests = sorted(root.glob("test_verified_*.py"))
                    if not verified_tests:
                        checks.append(
                            CheckResult(
                                name="behavioral_tests_present",
                                passed=False,
                                required=True,
                                detail="No authoritative test_verified_*.py acceptance test was supplied.",
                            )
                        )
                    else:
                        checks.append(
                            CheckResult(
                                name="behavioral_tests_present",
                                passed=True,
                                required=True,
                                detail=f"{len(verified_tests)} authoritative behavioral test file(s) supplied.",
                            )
                        )
                        try:
                            proc = subprocess.run(
                                [
                                    sys.executable,
                                    "-m",
                                    "unittest",
                                    "discover",
                                    "-s",
                                    ".",
                                    "-p",
                                    "test_verified_*.py",
                                    "-v",
                                ],
                                cwd=root,
                                capture_output=True,
                                text=True,
                                timeout=self.timeout_seconds,
                                env={
                                    "PATH": os.environ.get("PATH", ""),
                                    "PYTHONPATH": str(root),
                                    "PYTHONDONTWRITEBYTECODE": "1",
                                },
                                check=False,
                            )
                            output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                            if len(output) > 4000:
                                output = output[-4000:]
                            checks.append(
                                CheckResult(
                                    name="behavioral_test_execution",
                                    passed=proc.returncode == 0,
                                    required=True,
                                    detail=output or f"unittest exited {proc.returncode}",
                                )
                            )
                        except subprocess.TimeoutExpired:
                            checks.append(
                                CheckResult(
                                    name="behavioral_test_execution",
                                    passed=False,
                                    required=True,
                                    detail=f"Verification exceeded {self.timeout_seconds:.1f}s timeout.",
                                )
                            )

        passed = all(check.passed for check in checks if check.required)
        check_dicts = [asdict(check) for check in checks]
        evidence_payload = {
            "ticket_id": int(ticket_id),
            "ticket_title": str(ticket_title),
            "artifact_sha256": artifact_sha,
            "passed": passed,
            "checks": check_dicts,
        }
        evidence_sha = hashlib.sha256(
            json.dumps(
                evidence_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        return VerificationReceipt(
            ticket_id=int(ticket_id),
            ticket_title=str(ticket_title),
            artifact_sha256=artifact_sha,
            evidence_sha256=evidence_sha,
            passed=passed,
            checks=check_dicts,
        )
