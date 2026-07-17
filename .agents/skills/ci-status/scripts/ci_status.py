from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_THIS = Path(__file__).resolve()
AGENTS_DIR = _THIS.parents[3]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from batch import run_batch
from ghrepo import current_login, list_personal_repos, list_workflow_runs, require_auth

EXCLUDE_PREFIXES = ("saas",)
FAILED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}


@dataclass(frozen=True)
class RepoStatus:
    repo: str
    workflow: str | None
    status: str | None
    conclusion: str | None
    url: str | None

    @property
    def bucket(self) -> str:
        if self.status == "error":
            return "error"
        if self.status is None:
            return "no-ci"
        if self.status != "completed":
            return "pending"
        if self.conclusion == "success":
            return "success"
        if self.conclusion in FAILED_CONCLUSIONS:
            return "failed"
        return self.conclusion or "unknown"


def latest_status(login: str, repo: str) -> RepoStatus:
    runs = list_workflow_runs(login, repo, limit=1)
    if not runs:
        return RepoStatus(repo=repo, workflow=None, status=None, conclusion=None, url=None)
    run = runs[0]
    return RepoStatus(
        repo=repo,
        workflow=run.get("workflowName"),
        status=run.get("status"),
        conclusion=run.get("conclusion"),
        url=run.get("url"),
    )


def collect(login: str, repos: list[str], *, max_workers: int = 6) -> list[RepoStatus]:
    results = run_batch(repos, lambda repo: latest_status(login, repo), max_workers=max_workers)
    rows: list[RepoStatus] = []
    for result in results:
        if result.ok and result.value is not None:
            rows.append(result.value)
        else:
            rows.append(
                RepoStatus(
                    repo=result.repo,
                    workflow=None,
                    status="error",
                    conclusion=result.error,
                    url=None,
                )
            )
    return rows


def render_table(rows: list[RepoStatus]) -> str:
    lines = ["| Repo | Workflow | Status | Conclusion |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| {row.repo} | {row.workflow or '—'} | {row.status or 'no runs'} | "
            f"{row.conclusion or row.bucket} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report latest CI run status per repo")
    parser.add_argument(
        "--login", default=None, help="GitHub login (default: current gh auth user)"
    )
    parser.add_argument(
        "--repo", action="append", default=None, help="Limit to this repo (repeatable)"
    )
    parser.add_argument(
        "--filter",
        choices=["all", "success", "failed", "pending", "no-ci", "error"],
        default="all",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    args = parser.parse_args()

    require_auth()
    login = args.login or current_login()

    if args.repo:
        repos = args.repo
    else:
        repos = [r.name for r in list_personal_repos(login, exclude_prefixes=EXCLUDE_PREFIXES)]

    rows = collect(login, repos)
    if args.filter != "all":
        rows = [r for r in rows if r.bucket == args.filter]

    if args.json:
        print(json.dumps([asdict(r) | {"bucket": r.bucket} for r in rows], indent=2))
    else:
        print(render_table(rows))
        failed = sum(1 for r in rows if r.bucket == "failed")
        if failed:
            print(f"\n{failed} repo(s) with a failing latest run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
