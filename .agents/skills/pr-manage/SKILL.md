---
name: pr-manage
description: List, review, approve, merge, or close pull requests on delfianto's repos, with special support for sweeping Renovate's open PRs across many repos at once. Use for "what PRs are open", "merge the renovate PRs", "clean up dependabot/renovate noise", "review this PR".
---

# pr-manage

## Single-repo / single-PR work: prefer the GitHub MCP server

If the `github` MCP server is connected (see `.agents/mcp/`), use its tools for anything scoped
to one repo or one PR — it's interactive and avoids shelling out:

- `list_pull_requests` / `search_pull_requests` — listing/filtering.
- `pull_request_read` — diff, comments, status checks, reviews for one PR.
- `pull_request_review_write` — approve/request-changes/comment.
- `update_pull_request` — retarget, edit title/body, etc.
- `merge_pull_request` — **gated, see below.**

Equivalent `gh` fallback:

```bash
gh pr list --repo delfianto/<repo> [--state open|closed|merged|all]
gh pr view <number> --repo delfianto/<repo> [--comments]
gh pr diff <number> --repo delfianto/<repo>
gh pr review <number> --repo delfianto/<repo> --approve|--request-changes|--comment [-b "..."]
gh pr merge <number> --repo delfianto/<repo> --squash|--merge|--rebase [--delete-branch]
gh pr close <number> --repo delfianto/<repo>
```

**Merging and closing are state-changing actions on a shared system — always confirm the
specific PR(s) with the user before running `gh pr merge`/`gh pr close` (or the MCP equivalents,
`merge_pull_request` and `update_pull_request` with `state: closed`), even in a batch. Nothing in
this skill auto-merges.**

## Cross-repo Renovate sweep: use the script

Renovate opens PRs across many repos with the bot author `app/renovate`. To see all of them at
once instead of checking repo by repo:

```bash
python3 .agents/skills/pr-manage/scripts/renovate_prs.py [--repo NAME ...] [--update-type major|minor|patch|unclassified|all] [--json]
```

- No `--repo` → sweeps every repo in the same universe as `INVENTORY.md`.
- `update_type` classification is **best-effort**: it reads Renovate's own `major`/`minor`/
  `patch` labels if the repo's `renovate.json` adds them (many don't by default — check
  `renovate` skill if you want that enabled repo-wide). PRs without those labels come
  back `unclassified`; don't assume `unclassified` means "safe" or "unsafe," it means "unlabeled."
- `checks` is a rollup: `passing` only if every check succeeded, `failing` if any failed,
  `pending` otherwise, `no checks` if none are configured.

## Deciding what to do with Renovate PRs

A reasonable default triage (confirm with the user before acting, especially for `major`):

1. `patch`/`minor` with `checks: passing` and `mergeable: MERGEABLE` → safe to merge in most
   cases; still list them for the user rather than merging silently.
2. `major` → always call out separately; these can carry breaking changes. Read the PR body
   (Renovate includes release notes/changelogs) before recommending merge.
3. `checks: failing` → don't merge. Pull the failure via `ci-diagnose` (Renovate PR branches are
   just another branch/run) before deciding whether it's a real incompatibility or a flaky test.
4. Stale/superseded PRs (Renovate replaces its own PRs when a newer version lands) — closing
   old ones is safe once you've confirmed a newer PR for the same dependency exists.

## Batch operations

There's no batch-merge script by design — merging is exactly the kind of action that should stay
one confirmed `gh pr merge` call per PR, even when doing ten of them in a row. Loop over the
list from `renovate_prs.py`, confirm scope with the user once ("merge all passing patch/minor
Renovate PRs?"), then issue the calls.
