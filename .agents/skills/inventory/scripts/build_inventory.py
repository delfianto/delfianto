from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[4]
AGENTS_DIR = _THIS.parents[3]
SKILL_DIR = _THIS.parents[1]

sys.path.insert(0, str(AGENTS_DIR / "scripts"))
from batch import run_batch
from ghrepo import RepoInfo, current_login, has_ci, list_personal_repos, require_auth

CATEGORIES_FILE = SKILL_DIR / "categories.json"
EXCLUDE_PREFIXES = ("saas",)

KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Obsidian Plugins", ("obsidian",)),
    ("Browser Extensions", ("browser extension", "extention", "clanker-")),
    (
        "AI & Agents",
        ("llama", "llm", "mcp", "ollama", "stable diffusion", "roleplay", "clanker"),
    ),
    ("Docker & Self-Hosting", ("docker", "compose", "self-host", "selfhost")),
]


def guess_category(repo: RepoInfo) -> str:
    haystack = f"{repo.name} {repo.description}".lower()
    for category, keywords in KEYWORD_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category
    if repo.language in {"Rust", "Shell", "QML", "Dockerfile"}:
        return "Linux Utils"
    return "Misc"


def load_categories() -> tuple[list[str], dict[str, str]]:
    if not CATEGORIES_FILE.exists():
        return [], {}
    data = json.loads(CATEGORIES_FILE.read_text())
    return list(data.get("order", [])), dict(data.get("assignments", {}))


def save_categories(order: list[str], assignments: dict[str, str]) -> None:
    payload = {"order": order, "assignments": dict(sorted(assignments.items()))}
    CATEGORIES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def fetch_ci_map(login: str, repos: list[RepoInfo], *, max_workers: int = 6) -> dict[str, bool]:
    names = [r.name for r in repos]
    results = run_batch(names, lambda name: has_ci(login, name), max_workers=max_workers)
    return {r.repo: bool(r.value) for r in results if r.ok}


def render(
    login: str,
    order: list[str],
    grouped: dict[str, list[RepoInfo]],
    ci_map: dict[str, bool],
) -> str:
    lines = [
        "# Repository Inventory",
        "",
        f"Personal, non-fork, non-archived repositories owned by "
        f"[`{login}`](https://github.com/{login}), excluding anything prefixed "
        f"`{', '.join(p + '*' for p in EXCLUDE_PREFIXES)}`.",
        "",
        "Regenerate this file with the `inventory` skill (`.agents/skills/inventory`) "
        "rather than editing it by hand.",
        "",
        f"_Last generated: {date.today().isoformat()}_",
        "",
    ]
    for category in order:
        repos_in_category = grouped.get(category)
        if not repos_in_category:
            continue
        lines.append(f"## {category}")
        lines.append("")
        lines.append("| Name | Language | Has CI | Description |")
        lines.append("| --- | --- | --- | --- |")
        for repo in sorted(repos_in_category, key=lambda r: r.name.lower()):
            ci = "Yes" if ci_map.get(repo.name, False) else "No"
            row = f"| [`{repo.name}`]({repo.url}) | {repo.language} | {ci} | {repo.description} |"
            lines.append(row)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build(login: str, output: Path) -> list[str]:
    require_auth()
    repos = list_personal_repos(login, exclude_prefixes=EXCLUDE_PREFIXES)
    order, assignments = load_categories()

    newly_guessed: list[str] = []
    grouped: dict[str, list[RepoInfo]] = {}
    for repo in repos:
        category = assignments.get(repo.name)
        if category is None:
            category = guess_category(repo)
            assignments[repo.name] = category
            newly_guessed.append(f"{repo.name} -> {category}")
        grouped.setdefault(category, []).append(repo)

    for category in grouped:
        if category not in order:
            order.append(category)

    save_categories(order, assignments)
    ci_map = fetch_ci_map(login, repos)
    output.write_text(render(login, order, grouped, ci_map))
    return newly_guessed


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate INVENTORY.md")
    parser.add_argument(
        "--login", default=None, help="GitHub login (default: current gh auth user)"
    )
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "INVENTORY.md")
    args = parser.parse_args()

    login = args.login or current_login()
    guesses = build(login, args.output)
    print(f"Wrote {args.output}")
    if guesses:
        print(f"New repos auto-categorized (review {CATEGORIES_FILE}):")
        for guess in guesses:
            print(f"  - {guess}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
