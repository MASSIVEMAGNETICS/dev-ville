from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Iterable, Optional

from .github_client import GitHubError, GitHubRestClient
from .models import Finding, RepositoryEvidence, RiskTier, sha256_json


DEFAULT_CANONICAL = {
    "dev-ville",
    "truth-compiler-ai",
    "omni",
    "victor_empire",
    "MASSIVEMAGNETICS.github.io",
}

VICTORISH = re.compile(r"(?:^|[-_.])(victor|godcore|agi|ssi|cortex|swarm|omega|fractal)(?:$|[-_.])", re.I)
LICENSE_NAMES = {"license", "license.md", "license.txt", "copying", "copying.md", "copying.txt"}
README_NAMES = {"readme", "readme.md", "readme.rst", "readme.txt"}


def _repo_id(full_name: str, source: str) -> str:
    return "REPO-" + hashlib.sha256(f"{source}:{full_name}".encode("utf-8")).hexdigest()[:24]


def classify_repo(name: str, *, archived: bool, fork: bool, canonical: set[str]) -> str:
    if archived:
        return "ARCHIVE"
    if fork:
        return "FORK"
    if name in canonical:
        return "CORE"
    if VICTORISH.search(name):
        return "EXPERIMENT"
    return "UNKNOWN"


class LocalEstateScanner:
    def __init__(self, root: str | Path, *, canonical: Optional[Iterable[str]] = None):
        self.root = Path(root).expanduser().resolve()
        self.canonical = set(canonical or DEFAULT_CANONICAL)

    @staticmethod
    def _git(path: Path, *args: str) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["git", "-C", str(path), *args],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip() or None

    def scan(self) -> list[RepositoryEvidence]:
        if not self.root.exists():
            raise FileNotFoundError(self.root)
        candidates = [self.root] if (self.root / ".git").exists() else [p for p in self.root.iterdir() if p.is_dir()]
        repos: list[RepositoryEvidence] = []
        for path in sorted(candidates, key=lambda p: p.name.lower()):
            if not (path / ".git").exists():
                continue
            head = self._git(path, "rev-parse", "HEAD") or "UNKNOWN"
            branch = self._git(path, "branch", "--show-current") or "main"
            remote = self._git(path, "remote", "get-url", "origin") or ""
            full_name = path.name
            match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
            if match:
                full_name = match.group(1)
            root_files = tuple(sorted(p.name for p in path.iterdir()))
            dirty = bool(self._git(path, "status", "--porcelain"))
            name = path.name
            repos.append(
                RepositoryEvidence(
                    repository_id=_repo_id(full_name, "local"),
                    name=name,
                    full_name=full_name,
                    source="local",
                    default_branch=branch,
                    head_sha=head,
                    classification=classify_repo(name, archived=False, fork=False, canonical=self.canonical),
                    local_path=str(path),
                    root_files=root_files,
                    metadata={"remote": remote, "dirty": dirty, "root_inspected": True},
                )
            )
        return repos


class GitHubEstateScanner:
    def __init__(self, client: GitHubRestClient, org: str, *, canonical: Optional[Iterable[str]] = None):
        self.client = client
        self.org = org
        self.canonical = set(canonical or DEFAULT_CANONICAL)

    def scan(self, *, inspect_root: bool = True) -> list[RepositoryEvidence]:
        repos: list[RepositoryEvidence] = []
        for item in self.client.list_org_repos(self.org):
            name = str(item["name"])
            full_name = str(item.get("full_name") or f"{self.org}/{name}")
            branch = str(item.get("default_branch") or "main")
            head = "UNKNOWN"
            root_names: tuple[str, ...] = ()
            root_inspected = False
            errors: list[str] = []
            try:
                head = self.client.head_sha(full_name, branch)
            except GitHubError as exc:
                errors.append(f"head:{exc}")
            if inspect_root:
                try:
                    root_names = tuple(sorted(str(entry.get("name", "")) for entry in self.client.root_entries(full_name, branch)))
                    root_inspected = True
                except GitHubError as exc:
                    errors.append(f"root:{exc}")
            repos.append(
                RepositoryEvidence(
                    repository_id=_repo_id(full_name, "github"),
                    name=name,
                    full_name=full_name,
                    source="github",
                    default_branch=branch,
                    head_sha=head,
                    classification=classify_repo(
                        name,
                        archived=bool(item.get("archived")),
                        fork=bool(item.get("fork")),
                        canonical=self.canonical,
                    ),
                    archived=bool(item.get("archived")),
                    fork=bool(item.get("fork")),
                    size_kb=int(item.get("size") or 0),
                    root_files=root_names,
                    metadata={
                        "private": bool(item.get("private")),
                        "language": item.get("language"),
                        "disabled": bool(item.get("disabled")),
                        "root_inspected": root_inspected,
                        "errors": errors,
                    },
                )
            )
        return repos


def findings_for_repo(repo: RepositoryEvidence) -> list[Finding]:
    names = {name.lower() for name in repo.root_files}
    findings: list[Finding] = []

    if repo.head_sha == "UNKNOWN":
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="evidence.head_unknown",
                title="Repository head SHA is not verified",
                severity=8,
                risk=RiskTier.R0,
                blast_radius=4,
                revenue_block=2,
                proof_gap=10,
                dependency_unlock=7,
                irreversibility=0,
                evidence={"head_sha": repo.head_sha, "errors": repo.metadata.get("errors", [])},
            )
        )

    if not bool(repo.metadata.get("root_inspected")):
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="evidence.source_inspection_gap",
                title="Repository is metadata-only; root source evidence is missing",
                severity=5,
                risk=RiskTier.R0,
                blast_radius=3,
                revenue_block=2,
                proof_gap=9,
                dependency_unlock=6,
                irreversibility=0,
                evidence={"source": repo.source, "root_inspected": False},
            )
        )
        return findings

    if repo.classification == "EXPERIMENT":
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="estate.victor_fragmentation_candidate",
                title="Victor-named repository is outside the canonical core",
                severity=7,
                risk=RiskTier.R3,
                blast_radius=7,
                revenue_block=4,
                proof_gap=6,
                dependency_unlock=8,
                irreversibility=8,
                evidence={"classification": repo.classification, "name": repo.name},
            )
        )

    if not (names & README_NAMES) and not repo.archived:
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="repo.missing_readme",
                title="Repository has no root README",
                severity=2,
                risk=RiskTier.R2,
                blast_radius=1,
                revenue_block=1,
                proof_gap=3,
                dependency_unlock=2,
                irreversibility=1,
                evidence={"root_files_hash": sha256_json(sorted(names))},
            )
        )

    if ".gitignore" not in names and not repo.archived:
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="repo.missing_gitignore",
                title="Repository has no .gitignore",
                severity=3,
                risk=RiskTier.R1,
                blast_radius=2,
                revenue_block=1,
                proof_gap=2,
                dependency_unlock=3,
                irreversibility=1,
                evidence={"root_files_hash": sha256_json(sorted(names)), "missing": ".gitignore"},
                remediable=True,
                recipe="safe_gitignore_v1",
                required_paths=(".gitignore",),
            )
        )

    if not (names & LICENSE_NAMES) and not repo.archived:
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="repo.missing_license",
                title="Repository has no detected root license file",
                severity=4,
                risk=RiskTier.R3,
                blast_radius=4,
                revenue_block=4,
                proof_gap=4,
                dependency_unlock=3,
                irreversibility=8,
                evidence={"root_files_hash": sha256_json(sorted(names))},
            )
        )

    has_python = any(name.endswith(".py") for name in names) or "pyproject.toml" in names or "requirements.txt" in names
    has_tests = any(name.startswith("test_") and name.endswith(".py") for name in names) or "tests" in names
    has_ci = ".github" in names
    if has_python and has_tests and not has_ci and not repo.archived:
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="repo.python_tests_without_ci",
                title="Python tests exist but no .github CI directory was detected",
                severity=5,
                risk=RiskTier.R2,
                blast_radius=3,
                revenue_block=3,
                proof_gap=7,
                dependency_unlock=5,
                irreversibility=2,
                evidence={"has_python": True, "has_tests": True, "has_ci": False},
            )
        )

    if bool(repo.metadata.get("dirty")):
        findings.append(
            Finding.build(
                repo=repo,
                rule_id="local.dirty_worktree",
                title="Local repository contains uncommitted changes",
                severity=6,
                risk=RiskTier.R0,
                blast_radius=5,
                revenue_block=2,
                proof_gap=5,
                dependency_unlock=6,
                irreversibility=0,
                evidence={"dirty": True},
            )
        )

    return findings
