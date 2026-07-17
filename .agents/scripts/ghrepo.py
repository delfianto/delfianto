from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProjectType = Literal["rust", "python", "obsidian-plugin", "browser-extension", "unknown"]


class GhError(RuntimeError):
    pass


def gh(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        raise GhError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str, cwd: Path | None = None) -> Any:
    return json.loads(gh(*args, cwd=cwd))


def require_auth() -> None:
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        raise GhError("gh is not authenticated; run `gh auth login` first.")


def current_login() -> str:
    return str(gh_json("api", "user")["login"])


@dataclass(frozen=True)
class RepoInfo:
    name: str
    url: str
    language: str
    description: str
    pushed_at: str


def list_personal_repos(
    login: str,
    *,
    exclude_prefixes: tuple[str, ...] = (),
    limit: int = 300,
) -> list[RepoInfo]:
    raw = gh_json(
        "repo",
        "list",
        login,
        "--source",
        "--limit",
        str(limit),
        "--json",
        "name,url,isArchived,primaryLanguage,description,pushedAt",
    )
    repos: list[RepoInfo] = []
    for entry in raw:
        if entry["isArchived"]:
            continue
        name = entry["name"]
        if any(name.startswith(prefix) for prefix in exclude_prefixes):
            continue
        language = entry["primaryLanguage"]["name"] if entry["primaryLanguage"] else "—"
        repos.append(
            RepoInfo(
                name=name,
                url=entry["url"],
                language=language,
                description=(entry["description"] or "").strip(),
                pushed_at=entry["pushedAt"],
            )
        )
    repos.sort(key=lambda r: r.name.lower())
    return repos


def has_ci(owner: str, repo: str) -> bool:
    data = gh_json("api", f"repos/{owner}/{repo}/actions/workflows")
    return int(data["total_count"]) > 0


def list_workflow_runs(
    owner: str,
    repo: str,
    *,
    limit: int = 20,
    branch: str | None = None,
    workflow: str | None = None,
) -> list[dict[str, Any]]:
    args = [
        "run",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--limit",
        str(limit),
        "--json",
        "databaseId,name,status,conclusion,headBranch,event,createdAt,url,workflowName",
    ]
    if branch:
        args += ["--branch", branch]
    if workflow:
        args += ["--workflow", workflow]
    return list(gh_json(*args))


def get_run_log_failed(owner: str, repo: str, run_id: str) -> str:
    return gh("run", "view", run_id, "--repo", f"{owner}/{repo}", "--log-failed", check=False)


def list_pull_requests(
    owner: str,
    repo: str,
    *,
    author: str | None = None,
    state: str = "open",
    limit: int = 50,
) -> list[dict[str, Any]]:
    args = [
        "pr",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,author,headRefName,baseRefName,isDraft,mergeable,statusCheckRollup,url,labels,createdAt",
    ]
    if author:
        args += ["--author", author]
    return list(gh_json(*args))


def detect_project_type(path: Path) -> ProjectType:
    if (path / "Cargo.toml").is_file():
        return "rust"

    manifest = path / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            data = {}
        if "minAppVersion" in data:
            return "obsidian-plugin"
        if "manifest_version" in data:
            return "browser-extension"

    if (path / "pyproject.toml").is_file() or (path / "setup.py").is_file():
        return "python"

    return "unknown"
