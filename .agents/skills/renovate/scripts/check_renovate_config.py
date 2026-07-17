from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

_THIS = Path(__file__).resolve()
AGENTS_DIR = _THIS.parents[3]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from ghrepo import GhError, gh_json

KNOWN_TOP_LEVEL_KEYS = {
    "$schema",
    "extends",
    "enabled",
    "schedule",
    "timezone",
    "labels",
    "assignees",
    "reviewers",
    "packageRules",
    "rangeStrategy",
    "rebaseWhen",
    "prConcurrentLimit",
    "prHourlyLimit",
    "commitMessagePrefix",
    "semanticCommits",
    "dependencyDashboard",
    "lockFileMaintenance",
    "vulnerabilityAlerts",
    "ignoreDeps",
    "ignorePaths",
    "postUpdateOptions",
    "platformAutomerge",
    "automerge",
    "automergeType",
    "major",
    "minor",
    "patch",
    "pin",
    "digest",
    "branchPrefix",
    "baseBranches",
    "gitAuthor",
    "configMigration",
    "customManagers",
    "hostRules",
    "registryUrls",
}

MATCH_SELECTOR_KEYS = (
    "matchPackageNames",
    "matchPackagePatterns",
    "matchManagers",
    "matchDepTypes",
    "matchFileNames",
    "matchUpdateTypes",
    "matchCurrentVersion",
    "matchDatasources",
)

CONFIG_CANDIDATES = ("renovate.json", ".github/renovate.json", ".renovaterc.json")


class DuplicateKeyError(ValueError):
    pass


def _no_dupes_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKeyError(f"duplicate key: {key!r}")
        seen[key] = value
    return seen


def check(text: str) -> list[str]:
    problems: list[str] = []
    try:
        data = json.loads(text, object_pairs_hook=_no_dupes_hook)
    except DuplicateKeyError as exc:
        return [str(exc)]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["top level must be a JSON object"]

    if "$schema" not in data:
        problems.append(
            'missing "$schema" (recommended: https://docs.renovatebot.com/renovate-schema.json)'
        )

    unknown = sorted(set(data.keys()) - KNOWN_TOP_LEVEL_KEYS)
    if unknown:
        problems.append(f"unrecognized top-level key(s), check for typos: {', '.join(unknown)}")

    package_rules = data.get("packageRules")
    if isinstance(package_rules, list):
        for i, rule in enumerate(package_rules):
            if isinstance(rule, dict) and not any(key in rule for key in MATCH_SELECTOR_KEYS):
                problems.append(
                    f"packageRules[{i}] has no match* selector — it will apply to everything"
                )

    return problems


def load_local(path: Path | None) -> tuple[str, str] | None:
    candidates = [path] if path else [Path(c) for c in CONFIG_CANDIDATES]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(), str(candidate)
    return None


def load_remote(login: str, repo: str) -> tuple[str, str] | None:
    for candidate in CONFIG_CANDIDATES:
        try:
            data = gh_json("api", f"repos/{login}/{repo}/contents/{candidate}")
        except GhError:
            continue
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, f"{login}/{repo}:{candidate}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a Renovate JSON config for common mistakes")
    parser.add_argument("path", type=Path, nargs="?", default=None, help="Local config path")
    parser.add_argument("--repo", default=None, help="owner/repo to fetch the config from instead")
    args = parser.parse_args()

    if args.repo:
        login, _, repo = args.repo.partition("/")
        loaded = load_remote(login, repo)
    else:
        loaded = load_local(args.path)

    if loaded is None:
        print("no renovate config found (tried: " + ", ".join(CONFIG_CANDIDATES) + ")")
        return 1

    text, label = loaded
    problems = check(text)
    if not problems:
        print(f"{label}: OK")
        return 0

    print(f"{label}: {len(problems)} issue(s)")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
