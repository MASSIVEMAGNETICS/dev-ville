from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import RepairPlan


class GitHubError(RuntimeError):
    pass


Transport = Callable[[str, str, Optional[dict[str, Any]]], Any]


class GitHubRestClient:
    """Minimal GitHub REST client with exactly the capabilities RCP needs.

    It can inventory repositories and create a commit on a new branch followed by
    a draft pull request. There is intentionally no merge/delete/deploy API here.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        api_base: str = "https://api.github.com",
        transport: Optional[Transport] = None,
        timeout: float = 20.0,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.api_base = api_base.rstrip("/")
        self.transport = transport
        self.timeout = float(timeout)

    @property
    def authenticated(self) -> bool:
        return bool(self.token or self.transport)

    def _request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> Any:
        if self.transport is not None:
            return self.transport(method, path, payload)
        if not self.token:
            raise GitHubError("GitHub token is required; set GITHUB_TOKEN or GH_TOKEN")
        url = path if path.startswith("http") else self.api_base + path
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            method=method,
            data=body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "massive-magnetics-remediation-control-plane/1",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read()
                return json.loads(data.decode("utf-8")) if data else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GitHubError(f"GitHub {method} {url} failed: HTTP {exc.code}: {detail[:1200]}") from exc
        except URLError as exc:
            raise GitHubError(f"GitHub {method} {url} failed: {exc}") from exc

    def _try_request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> Any:
        try:
            return self._request(method, path, payload)
        except GitHubError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def file_content(self, full_name: str, path: str, ref: str) -> str:
        data = self._request(
            "GET",
            f"/repos/{full_name}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}",
        )
        if not isinstance(data, dict) or data.get("type") != "file":
            raise GitHubError(f"{full_name}:{path}@{ref} is not a file")
        if data.get("encoding") != "base64":
            raise GitHubError(f"unsupported GitHub content encoding for {path}: {data.get('encoding')!r}")
        try:
            return base64.b64decode(str(data.get("content") or "")).decode("utf-8")
        except Exception as exc:
            raise GitHubError(f"failed to decode GitHub file {path}: {exc}") from exc

    def get_repo(self, full_name: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/repos/{full_name}"))

    def list_org_repos(self, org: str) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request("GET", f"/orgs/{quote(org)}/repos?per_page=100&page={page}&type=all&sort=full_name")
            if not isinstance(batch, list):
                raise GitHubError("unexpected GitHub repository-list response")
            repos.extend(dict(item) for item in batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def root_entries(self, full_name: str, ref: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/repos/{full_name}/contents?ref={quote(ref, safe='')}")
        if not isinstance(data, list):
            raise GitHubError(f"root contents for {full_name} were not a list")
        return [dict(item) for item in data]

    def head_sha(self, full_name: str, branch: str) -> str:
        data = self._request("GET", f"/repos/{full_name}/git/ref/heads/{quote(branch, safe='')}")
        return str(data["object"]["sha"])

    @staticmethod
    def _branch_name(plan: RepairPlan) -> str:
        case = re.sub(r"[^a-zA-Z0-9._-]+", "-", plan.case_id.lower())[:32]
        suffix = plan.plan_id.replace("PLAN-", "").lower()[:10]
        return f"rcp/{case}-{suffix}"

    def publish_plan(
        self,
        plan: RepairPlan,
        *,
        title: str,
        body: str,
        base_branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """Publish a verified repair as one commit on a new branch and draft PR."""
        if not self.authenticated:
            raise GitHubError("authenticated GitHub access is required to publish")
        if not plan.operations:
            raise GitHubError("refusing to publish an empty repair plan")
        for op in plan.operations:
            if op.op != "write":
                raise GitHubError(f"unsupported GitHub publication operation: {op.op}")

        repo = self.get_repo(plan.repository_full_name)
        base = base_branch or str(repo.get("default_branch") or "main")
        base_sha = self.head_sha(plan.repository_full_name, base)
        branch = self._branch_name(plan)

        existing_ref = self._try_request(
            "GET",
            f"/repos/{plan.repository_full_name}/git/ref/heads/{quote(branch, safe='')}",
        )
        if existing_ref is not None:
            for op in plan.operations:
                actual = self.file_content(plan.repository_full_name, op.path, branch)
                if actual != op.content:
                    raise GitHubError(
                        f"existing publication branch {branch} does not match verified plan at {op.path}"
                    )
            owner = plan.repository_full_name.split("/", 1)[0]
            pulls = self._request(
                "GET",
                f"/repos/{plan.repository_full_name}/pulls?head={quote(owner + ':' + branch, safe=':')}&state=open",
            )
            if isinstance(pulls, list) and pulls:
                pr = pulls[0]
                return {
                    "repository": plan.repository_full_name,
                    "branch": branch,
                    "base": base,
                    "base_sha": base_sha,
                    "commit_sha": str(existing_ref["object"]["sha"]),
                    "pr_number": int(pr["number"]),
                    "pr_url": str(pr.get("html_url") or ""),
                    "draft": bool(pr.get("draft", True)),
                    "recovered": True,
                }
            pr = self._request(
                "POST",
                f"/repos/{plan.repository_full_name}/pulls",
                {
                    "title": title,
                    "head": branch,
                    "base": base,
                    "body": body,
                    "draft": True,
                    "maintainer_can_modify": True,
                },
            )
            return {
                "repository": plan.repository_full_name,
                "branch": branch,
                "base": base,
                "base_sha": base_sha,
                "commit_sha": str(existing_ref["object"]["sha"]),
                "pr_number": int(pr["number"]),
                "pr_url": str(pr.get("html_url") or ""),
                "draft": bool(pr.get("draft", True)),
                "recovered": True,
            }
        if plan.base_sha and plan.base_sha not in {"UNKNOWN", base_sha}:
            raise GitHubError(
                f"base SHA moved for {plan.repository_full_name}: planned {plan.base_sha}, current {base_sha}"
            )

        base_commit = self._request("GET", f"/repos/{plan.repository_full_name}/git/commits/{base_sha}")
        base_tree_sha = str(base_commit["tree"]["sha"])

        tree_items: list[dict[str, str]] = []
        for op in plan.operations:
            blob = self._request(
                "POST",
                f"/repos/{plan.repository_full_name}/git/blobs",
                {"content": op.content, "encoding": "utf-8"},
            )
            tree_items.append({"path": op.path, "mode": "100644", "type": "blob", "sha": str(blob["sha"])})

        tree = self._request(
            "POST",
            f"/repos/{plan.repository_full_name}/git/trees",
            {"base_tree": base_tree_sha, "tree": tree_items},
        )
        commit = self._request(
            "POST",
            f"/repos/{plan.repository_full_name}/git/commits",
            {
                "message": f"rcp: remediate {plan.case_id}",
                "tree": str(tree["sha"]),
                "parents": [base_sha],
            },
        )
        self._request(
            "POST",
            f"/repos/{plan.repository_full_name}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": str(commit["sha"])},
        )
        pr = self._request(
            "POST",
            f"/repos/{plan.repository_full_name}/pulls",
            {
                "title": title,
                "head": branch,
                "base": base,
                "body": body,
                "draft": True,
                "maintainer_can_modify": True,
            },
        )
        return {
            "repository": plan.repository_full_name,
            "branch": branch,
            "base": base,
            "base_sha": base_sha,
            "commit_sha": str(commit["sha"]),
            "pr_number": int(pr["number"]),
            "pr_url": str(pr.get("html_url") or ""),
            "draft": bool(pr.get("draft", True)),
        }
