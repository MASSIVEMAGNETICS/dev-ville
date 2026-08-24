from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

# Install a small compatibility stub for the existing repository's canonical
# trace0_chronos module. Production RCP imports the real module already present
# in dev-ville; this stub exists only for isolated tests in this build workspace.
_FAKE_LEDGER_BY_PATH = {}


@dataclass(frozen=True)
class _Receipt:
    sequence: int
    event_id: str
    event_hash: str
    previous_chain_hash: str | None
    chain_hash: str
    def to_dict(self):
        return self.__dict__.copy()


@dataclass(frozen=True)
class _Event:
    sequence: int
    action: str
    entity_id: str
    payload: dict
    evidence: dict
    provenance: dict
    authority: str
    event_id: str
    def to_dict(self):
        return self.__dict__.copy()


class _ChronosLedger:
    def __init__(self, jsonl_path=None):
        self.path = str(jsonl_path or "memory")
        state = _FAKE_LEDGER_BY_PATH.setdefault(self.path, {"events": [], "receipts": []})
        self._events = state["events"]
        self._receipts = state["receipts"]
    def events(self): return [x.to_dict() if hasattr(x, "to_dict") else dict(x) for x in self._events]
    def receipts(self): return [x.to_dict() if hasattr(x, "to_dict") else dict(x) for x in self._receipts]
    def verify_chain(self): return len(self._events) == len(self._receipts)


class _Trace0Observer:
    def __init__(self, ledger): self.ledger = ledger
    def observe(self, *, actor, action, entity_id, payload=None, provenance=None, evidence=None, authority="observation_only"):
        import hashlib
        seq = len(self.ledger._events) + 1
        core = json.dumps({"seq":seq,"action":action,"entity":entity_id,"payload":payload or {}}, sort_keys=True)
        event_id = hashlib.sha256(core.encode()).hexdigest()
        event = _Event(seq, action, entity_id, payload or {}, evidence or {}, provenance or {}, authority, event_id)
        prev = self.ledger._receipts[-1].chain_hash if self.ledger._receipts else None
        event_hash = hashlib.sha256(json.dumps(event.to_dict(), sort_keys=True).encode()).hexdigest()
        chain_hash = hashlib.sha256(f"{prev}:{event_hash}".encode()).hexdigest()
        receipt = _Receipt(seq, event_id, event_hash, prev, chain_hash)
        self.ledger._events.append(event)
        self.ledger._receipts.append(receipt)
        return event, receipt


fake_trace = types.ModuleType("trace0_chronos")
fake_trace.ChronosLedger = _ChronosLedger
fake_trace.Trace0Observer = _Trace0Observer
if importlib.util.find_spec("trace0_chronos") is None:
    sys.modules["trace0_chronos"] = fake_trace

from rcp.config import RCPConfig
from rcp.engine import RemediationEngine
from rcp.github_client import GitHubError, GitHubRestClient
from rcp.models import CaseState, Finding, RemediationCase, RepositoryEvidence, RiskTier
from rcp.policy import PolicyDenied, PolicyGate
from rcp.repair import RepairWorker
from rcp.scanner import findings_for_repo
from rcp.truth_adapter import load_truth_compiler_jsonl
from rcp.verifier import IndependentVerifier


class RCPTests(unittest.TestCase):
    def make_repo_evidence(self):
        return RepositoryEvidence(
            repository_id="REPO-1",
            name="sample",
            full_name="MASSIVEMAGNETICS/sample",
            source="github",
            default_branch="main",
            head_sha="abc123",
            classification="UNKNOWN",
            root_files=("README.md", "LICENSE", "app.py"),
            metadata={"root_inspected": True},
        )

    def test_missing_gitignore_is_deterministic_r1_case(self):
        repo = self.make_repo_evidence()
        findings1 = findings_for_repo(repo)
        findings2 = findings_for_repo(repo)
        target1 = next(f for f in findings1 if f.rule_id == "repo.missing_gitignore")
        target2 = next(f for f in findings2 if f.rule_id == "repo.missing_gitignore")
        self.assertEqual(target1.finding_id, target2.finding_id)
        self.assertEqual(target1.risk, RiskTier.R1)
        self.assertTrue(target1.remediable)
        self.assertEqual(RemediationCase.from_finding(target1).case_id, RemediationCase.from_finding(target2).case_id)

    def test_policy_is_fail_closed_and_signed(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_repo_evidence()
            finding = next(f for f in findings_for_repo(repo) if f.rule_id == "repo.missing_gitignore")
            case = RemediationCase.from_finding(finding)
            gate = PolicyGate(td)
            lease = gate.issue(case)
            gate.verify(lease, case=case)
            tampered = lease.__class__(**{**lease.to_dict(), "signature": "00" * 32, "risk": RiskTier(lease.to_dict()["risk"])})
            with self.assertRaises(PolicyDenied):
                gate.verify(tampered, case=case)

    def test_independent_verifier_rejects_worker_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_repo_evidence()
            finding = next(f for f in findings_for_repo(repo) if f.rule_id == "repo.missing_gitignore")
            case = RemediationCase.from_finding(finding)
            gate = PolicyGate(td)
            lease = gate.issue(case)
            worker = RepairWorker(gate, td)
            plan = worker.build_plan(case, lease)
            worker_dir = worker.materialize(plan, lease)
            (worker_dir / ".gitignore").write_text("*\n", encoding="utf-8")
            verification = IndependentVerifier(gate).verify(plan, lease, worker_dir=worker_dir)
            self.assertFalse(verification.passed)
            failed = {c["name"] for c in verification.checks if not c["passed"]}
            self.assertIn("worker_materialization_matches_plan", failed)

    def test_local_closed_loop_reaches_pr_ready_without_touching_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "estate"
            repo = root / "sample"
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "RCP Test"], cwd=repo, check=True)
            (repo / "README.md").write_text("# sample\n", encoding="utf-8")
            (repo / "LICENSE").write_text("test\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md", "LICENSE"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            config = RCPConfig(state_dir=str(Path(td) / "state"), publish_draft_pr=False)
            engine = RemediationEngine(config)
            try:
                scan = engine.scan_local(root)
                self.assertEqual(scan["repositories"], 1)
                queue = engine.store.list_cases(states=[CaseState.TRIAGED], limit=100)
                target = next(c for c in queue if c.rule_id == "repo.missing_gitignore")
                result = engine.run_case(target.case_id, publish=False)
                self.assertEqual(result["state"], CaseState.PR_READY.value)
                self.assertTrue(result["verification"]["passed"])
                self.assertTrue(result["chronos_valid"])
                self.assertFalse((repo / ".gitignore").exists(), "worker must never modify source checkout directly")
            finally:
                engine.close()

    def test_github_publication_is_one_commit_and_draft_pr(self):
        calls = []
        def transport(method, path, payload):
            calls.append((method, path, payload))
            if method == "GET" and path == "/repos/MASSIVEMAGNETICS/sample":
                return {"default_branch": "main"}
            if method == "GET" and path.endswith("/git/ref/heads/main"):
                return {"object": {"sha": "abc123"}}
            if method == "GET" and "/git/ref/heads/rcp%2F" in path:
                raise GitHubError("GitHub GET fake failed: HTTP 404: missing")
            if method == "GET" and "/git/commits/abc123" in path:
                return {"tree": {"sha": "treebase"}}
            if method == "POST" and path.endswith("/git/blobs"):
                return {"sha": "blob1"}
            if method == "POST" and path.endswith("/git/trees"):
                return {"sha": "tree1"}
            if method == "POST" and path.endswith("/git/commits"):
                return {"sha": "commit1"}
            if method == "POST" and path.endswith("/git/refs"):
                return {"ref": payload["ref"]}
            if method == "POST" and path.endswith("/pulls"):
                self.assertTrue(payload["draft"])
                return {"number": 7, "html_url": "https://example/pr/7", "draft": True}
            raise AssertionError((method, path, payload))

        with tempfile.TemporaryDirectory() as td:
            repo = self.make_repo_evidence()
            finding = next(f for f in findings_for_repo(repo) if f.rule_id == "repo.missing_gitignore")
            case = RemediationCase.from_finding(finding)
            gate = PolicyGate(td)
            lease = gate.issue(case)
            plan = RepairWorker(gate, td).build_plan(case, lease)
            client = GitHubRestClient(transport=transport)
            pub = client.publish_plan(plan, title="RCP test", body="verified")
            self.assertEqual(pub["pr_number"], 7)
            self.assertTrue(pub["draft"])
            paths = [path for _, path, _ in calls]
            self.assertFalse(any("merge" in path for path in paths))
            self.assertFalse(any("deploy" in path for path in paths))
            self.assertFalse(any(method == "DELETE" for method, _, _ in calls))

    def test_truth_adapter_preserves_unknown_state(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "findings.jsonl"
            p.write_text(json.dumps({
                "repository_full_name": "MASSIVEMAGNETICS/x",
                "head_sha": "abc",
                "rule_id": "proof.gap",
                "title": "gap",
                "evidence": {"observed": False},
                "truth_state": "UNKNOWN",
                "risk": "R0"
            }) + "\n", encoding="utf-8")
            rows = load_truth_compiler_jsonl(p)
            self.assertEqual(rows[0][1].evidence["truth_state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
