---
name: inventory
description: Regenerate INVENTORY.md, the categorized table of delfianto's personal, non-fork, non-archived, non-saas* GitHub repositories. Use when the user asks to update/refresh the repo inventory, add a newly created repo to it, or re-check which repos have CI.
---

# inventory

Maintains `INVENTORY.md` at the repo root: personal repos owned by the account, grouped into
category tables (Obsidian Plugins, Browser Extensions, Linux Utils, Docker & Self-Hosting,
AI & Agents, Misc), alphabetical within each table, columns `Name | Language | Has CI | Description`.

## Requirements

- `gh` CLI, authenticated (`gh auth status`).
- Python 3.11+, standard library only.

## Running it

```bash
python3 .agents/skills/inventory/scripts/build_inventory.py
```

This:

1. Lists the account's source (non-fork), non-archived repos via `gh repo list --source`,
   excluding anything named `saas*`.
2. Looks up each repo's category in `.agents/skills/inventory/categories.json`. Repos not yet
   present get a best-effort guess (keyword/language heuristics) and are **appended** to
   `categories.json` so the guess is stable across runs.
3. Checks CI presence per repo via `GET /repos/{owner}/{repo}/actions/workflows`
   (`total_count > 0`).
4. Rewrites `INVENTORY.md`.

If the `github` MCP server is connected, `search_repositories` (e.g. `user:delfianto fork:false
archived:false`) and `actions_list` cover the same lookups interactively — fine for a one-off
"does repo X have CI" question. For the *inventory build itself*, prefer the script: it's what
keeps `categories.json` (the categorization judgment call) persisted and consistent between
runs, which ad hoc tool calls won't do.

## After running

- If stdout lists "New repos auto-categorized", **review those against user intent** before
  treating the output as final — the heuristics are approximate. Edit
  `.agents/skills/inventory/categories.json` by hand to correct a category, then re-run.
- Diff `INVENTORY.md` before presenting it as done; a repo silently moving categories is a sign
  the heuristics guessed wrong, not that the repo changed.

## Changing the category list or exclusions

- Add/rename/reorder categories by editing the `order` array in `categories.json`.
- The `saas*` exclusion prefix and the account login default live in
  `scripts/build_inventory.py` (`EXCLUDE_PREFIXES`, and `--login` which defaults to the
  currently authenticated `gh` user). Pass `--login <user>` to build an inventory for a
  different account, `--output <path>` to write elsewhere.
