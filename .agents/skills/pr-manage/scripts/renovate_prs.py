from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
AGENTS_DIR = _THIS.parents[3]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from batch import RepoResult, run_batch
from ghrepo import GhError, current_login, list_personal_repos, list_pull_requests, require_auth

EXCLUDE_PREFIXES = ("saas",)
RENOVATE_AUTHOR = "app/renovate"
UPDATE_TYPES = {"major", "minor", "patch"}


@dataclass(frozen=True)
class RenovatePr:
    repo: str
    number: int
    title: str
    update_type: str
    mergeable: str
    checks: str
    url: str


def classify_update_type(labels: list[dict[str, Any]]) -> str:
    names = {label.get("name", "").lower() for label in labels}
    for kind in UPDATE_TYPES:
        if kind in names:
            return kind
    return "unclassified"


def summarize_checks(pr: dict[str, Any]) -> str:
    rollup = pr.get("statusCheckRollup") or []
    if not rollup:
        return "no checks"
    states = [c.get("conclusion") or c.get("state") or "unknown" for c in rollup]
    if all(s in {"SUCCESS", "success"} for s in states):
        return "passing"
    if any(s in {"FAILURE", "failure", "ERROR", "error"} for s in states):
        return "failing"
    return "pending"


REDUCED_FIELDS = "number,title,url,labels,mergeable"


def fetch_repo_prs(login: str, repo: str) -> list[RenovatePr]:
    try:
        prs = list_pull_requests(login, repo, author=RENOVATE_AUTHOR, state="open")
    except GhError as exc:
        print(f"warning: {repo}: falling back to reduced fields ({exc})", file=sys.stderr)
        prs = list_pull_requests(
            login, repo, author=RENOVATE_AUTHOR, state="open", fields=REDUCED_FIELDS
        )
    return [
        RenovatePr(
            repo=repo,
            number=pr["number"],
            title=pr["title"],
            update_type=classify_update_type(pr.get("labels", [])),
            mergeable=str(pr.get("mergeable", "UNKNOWN")),
            checks=summarize_checks(pr) if "statusCheckRollup" in pr else "unknown",
            url=pr["url"],
        )
        for pr in prs
    ]


def collect(login: str, repos: list[str], *, max_workers: int = 6) -> list[RenovatePr]:
    def report(result: RepoResult[list[RenovatePr]]) -> None:
        if not result.ok:
            print(f"warning: {result.repo}: {result.error}", file=sys.stderr)

    results = run_batch(
        repos, lambda repo: fetch_repo_prs(login, repo), max_workers=max_workers, on_result=report
    )
    prs: list[RenovatePr] = []
    for result in results:
        if result.ok and result.value:
            prs.extend(result.value)
    return prs


def main() -> int:
    parser = argparse.ArgumentParser(description="List open Renovate PRs across repos")
    parser.add_argument(
        "--login", default=None, help="GitHub login (default: current gh auth user)"
    )
    parser.add_argument(
        "--repo", action="append", default=None, help="Limit to this repo (repeatable)"
    )
    parser.add_argument(
        "--update-type", choices=[*UPDATE_TYPES, "unclassified", "all"], default="all"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    require_auth()
    login = args.login or current_login()

    if args.repo:
        repos = args.repo
    else:
        repos = [r.name for r in list_personal_repos(login, exclude_prefixes=EXCLUDE_PREFIXES)]

    prs = collect(login, repos)
    if args.update_type != "all":
        prs = [p for p in prs if p.update_type == args.update_type]

    if args.json:
        print(json.dumps([asdict(p) for p in prs], indent=2))
        return 0

    if not prs:
        print("No open Renovate PRs found.")
        return 0

    print("| Repo | PR | Type | Checks | Mergeable | Title |")
    print("| --- | --- | --- | --- | --- | --- |")
    for pr in prs:
        print(
            f"| {pr.repo} | #{pr.number} | {pr.update_type} | {pr.checks} | "
            f"{pr.mergeable} | {pr.title} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
