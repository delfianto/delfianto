---
name: ci-status
description: Check GitHub Actions CI status for one repo, a list of repos, or the whole personal repo collection — filterable to all/success/failed/pending/no-ci. Use when the user asks "is CI green", "which repos are failing", "check CI status", or similar across delfianto's repos.
---

# ci-status

Reports the **latest workflow run** status per repository.

## Preferred path: GitHub MCP server

If the `github` MCP server is connected (see `.agents/mcp/`), use its tools directly for a single
repo or a handful of repos — it's interactive and needs no setup:

- `actions_list` — list workflow runs for a repo; read `status`/`conclusion` off the most recent.
- `actions_get` — details on one specific run.

Reach for the script below instead when you need to sweep **many repos at once** — that's the
case it's built for, and it's what makes `--filter failed` a single command instead of N tool
calls.

## Script: many-repo sweep

```bash
python3 .agents/skills/ci-status/scripts/ci_status.py [--repo NAME ...] [--filter all|success|failed|pending|no-ci] [--json]
```

- No `--repo` given → sweeps every personal, non-fork, non-archived, non-`saas*` repo (same
  universe as `INVENTORY.md`).
- `--repo` is repeatable to scope to specific repos.
- `--filter failed` is the fast path for "what's broken right now".
- `--json` for programmatic use (each row: `repo, workflow, status, conclusion, url, bucket`).

`no-ci` means the repo has zero configured workflows (distinct from a workflow that hasn't run
yet, or `pending` which means the latest run is still in progress/queued).

## Interpreting results

- A `failed` bucket includes `failure`, `timed_out`, `action_required`, and `startup_failure`
  conclusions.
- This only looks at the **most recent** run per repo/default view — it does not aggregate
  history. If the user wants trend/flakiness data, that's out of scope for this skill; say so
  rather than fabricating it.
- For *why* a run failed, hand off to the `ci-diagnose` skill — this skill only reports status,
  not root cause.
