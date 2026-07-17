from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
AGENTS_DIR = _THIS.parents[3]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from ghrepo import current_login, get_run_log_failed, list_workflow_runs, require_auth

FAILED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}

ERROR_PATTERN = re.compile(
    r"error|failed|failure|exception|traceback|panic|cannot|denied|"
    r"timeout|timed out|fatal|enoent|eacces|no space left|not found",
    re.IGNORECASE,
)

HINTS: list[tuple[str, str]] = [
    (r"Traceback \(most recent call last\)", "Python exception/traceback"),
    (r"error\[E\d+\]", "Rust compiler error"),
    (r"npm ERR!", "npm/Node error"),
    (r"Cannot find module|Module not found", "Missing dependency/module"),
    (r"permission denied", "Permission/filesystem access issue"),
    (r"no space left on device", "Disk full on the runner"),
    (r"rate limit", "GitHub/API rate limiting"),
    (r"OOMKilled|Killed$", "Likely out-of-memory kill"),
    (r"context deadline exceeded|timed out", "Timeout"),
    (r"401 Unauthorized|403 Forbidden", "Auth/token/secret problem"),
    (r"error: failed to (select|download)", "Cargo dependency resolution"),
    (r"ModuleNotFoundError|ImportError", "Python missing package"),
]


def find_latest_failed_run(login: str, repo: str, limit: int = 20) -> dict[str, Any] | None:
    for run in list_workflow_runs(login, repo, limit=limit):
        if run.get("status") == "completed" and run.get("conclusion") in FAILED_CONCLUSIONS:
            return run
    return None


def extract_excerpt(
    log: str, *, context_before: int = 3, context_after: int = 6, max_lines: int = 200
) -> str:
    lines = log.splitlines()
    if not lines:
        return ""

    hit_indexes = [i for i, line in enumerate(lines) if ERROR_PATTERN.search(line)]
    if not hit_indexes:
        return "\n".join(lines[-max_lines:])

    ranges: list[tuple[int, int]] = []
    for i in hit_indexes:
        start = max(0, i - context_before)
        end = min(len(lines), i + context_after + 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))

    out_lines: list[str] = []
    for start, end in ranges:
        if out_lines:
            out_lines.append("...")
        out_lines.extend(lines[start:end])
        if len(out_lines) >= max_lines:
            break
    return "\n".join(out_lines[:max_lines])


def find_hints(text: str) -> list[str]:
    return [
        description for pattern, description in HINTS if re.search(pattern, text, re.IGNORECASE)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and trim failed-run logs for diagnosis")
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--login", default=None, help="GitHub login (default: current gh auth user)"
    )
    parser.add_argument(
        "--run-id", default=None, help="Specific run ID; default: latest failed run"
    )
    parser.add_argument("--max-lines", type=int, default=200)
    args = parser.parse_args()

    require_auth()
    login = args.login or current_login()

    run_id: str | None = args.run_id
    run_meta: dict[str, Any] | None = None
    if run_id is None:
        run_meta = find_latest_failed_run(login, args.repo)
        if run_meta is None:
            print(f"No failed runs found for {login}/{args.repo} in the recent history.")
            return 0
        run_id = str(run_meta["databaseId"])

    log = get_run_log_failed(login, args.repo, run_id)
    if not log.strip():
        print(
            f"gh returned no failed-step log for run {run_id} "
            "(it may not have failed, or logs expired)."
        )
        return 1

    excerpt = extract_excerpt(log, max_lines=args.max_lines)
    hints = find_hints(log)

    if run_meta:
        print(f"Run: {run_meta.get('workflowName')} — {run_meta.get('url')}")
    print(f"Run ID: {run_id}")
    if hints:
        print("Heuristic hints (not a diagnosis — verify against the excerpt below):")
        for hint in hints:
            print(f"  - {hint}")
    print("\n--- Log excerpt ---\n")
    print(excerpt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
