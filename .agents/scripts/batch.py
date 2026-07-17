from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class RepoResult(Generic[T]):
    repo: str
    ok: bool
    value: T | None = None
    error: str | None = None
    seconds: float = 0.0


def run_batch(
    repos: Sequence[str],
    fn: Callable[[str], T],
    *,
    max_workers: int = 6,
    on_result: Callable[[RepoResult[T]], None] | None = None,
) -> list[RepoResult[T]]:
    """Run fn(repo) for every repo in repos.

    One repo raising never aborts the rest of the batch — its failure is
    captured in that repo's RepoResult.error instead of propagating. Runs
    with bounded concurrency (these are I/O-bound gh CLI/API calls), but the
    returned list is always in the same order as `repos`, regardless of
    completion order. `on_result` fires once per repo as it finishes, in
    completion order, for streaming progress output.
    """
    results: dict[str, RepoResult[T]] = {}

    def call(repo: str) -> RepoResult[T]:
        start = time.monotonic()
        try:
            value = fn(repo)
            return RepoResult(repo=repo, ok=True, value=value, seconds=time.monotonic() - start)
        except Exception as exc:
            return RepoResult(
                repo=repo,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                seconds=time.monotonic() - start,
            )

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = {pool.submit(call, repo): repo for repo in repos}
        for future in as_completed(futures):
            result = future.result()
            results[result.repo] = result
            if on_result:
                on_result(result)

    return [results[repo] for repo in repos]


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Retry fn() with exponential backoff (base_delay, 2x, 4x, ...)."""
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2**attempt))
    assert last_exc is not None
    raise last_exc


def print_summary(results: Sequence[RepoResult[Any]], *, label: str = "repos") -> None:
    ok = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.ok]
    print(f"\n{ok}/{len(results)} {label} succeeded")
    if failed:
        print(f"{len(failed)} failed:")
        for r in failed:
            print(f"  - {r.repo}: {r.error}")


def _cli_check_file() -> int:
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ghrepo import current_login, list_personal_repos, path_exists_in_repo, require_auth

    parser = argparse.ArgumentParser(
        description="Check whether a file exists at HEAD across the repo collection"
    )
    parser.add_argument("path", help="Repo-relative file path, e.g. .github/dependabot.yml")
    parser.add_argument(
        "--login", default=None, help="GitHub login (default: current gh auth user)"
    )
    parser.add_argument(
        "--repo", action="append", default=None, help="Limit to this repo (repeatable)"
    )
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    require_auth()
    login = args.login or current_login()
    repos = args.repo or [r.name for r in list_personal_repos(login, exclude_prefixes=("saas",))]

    def check(repo: str) -> bool:
        return path_exists_in_repo(login, repo, args.path)

    def report(result: RepoResult[bool]) -> None:
        if not result.ok:
            print(f"{result.repo}: ERROR ({result.error})")
        else:
            print(f"{result.repo}: {'present' if result.value else 'absent'}")

    results = run_batch(repos, check, max_workers=args.workers, on_result=report)
    present = sorted(r.repo for r in results if r.ok and r.value)
    print_summary(results)
    if present:
        print(f"\npresent in {len(present)}: {', '.join(present)}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(_cli_check_file())
