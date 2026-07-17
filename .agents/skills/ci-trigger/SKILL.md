---
name: ci-trigger
description: Manually trigger a GitHub Actions workflow run (workflow_dispatch) on a repo, optionally on a specific branch/ref with inputs. Use when the user asks to "kick off CI", "trigger a build", "re-run the workflow", "run the release workflow manually", etc.
---

# ci-trigger

Simple enough to not need a bundled script — use the GitHub MCP server's `actions_run_trigger` if
connected, otherwise `gh` directly.

**`actions_run_trigger` mutates the remote (kicks off a real CI run) — treat it like any other
gated action in this skill: confirm the workflow/ref/inputs with the user first, same as the
`gh workflow run` path below.**

## Steps

1. **Find the workflow** (if not named by the user):

   ```bash
   gh workflow list --repo delfianto/<repo>
   ```

   Note the workflow file name or numeric ID.

2. **Trigger it**:

   ```bash
   gh workflow run <workflow-file-or-id> --repo delfianto/<repo> [--ref <branch>] [-f key=value ...]
   ```

   - `--ref` defaults to the repo's default branch if omitted.
   - `-f key=value` sets `workflow_dispatch` inputs; repeat per input. Check the workflow's
     `on.workflow_dispatch.inputs` first (`gh workflow view <name> --repo owner/repo --yaml`) so
     you pass valid keys, not guessed ones.

3. **Find the run that was just created** (the trigger command doesn't return a run ID):

   ```bash
   gh run list --repo delfianto/<repo> --workflow <workflow-file-or-id> --limit 1
   ```

4. **Report back** the run URL, and optionally watch it:

   ```bash
   gh run watch <run-id> --repo delfianto/<repo>
   ```

   Only watch (blocking) if the user is waiting on the result; otherwise just hand back the URL
   and let `ci-status` pick it up later.

## Common failure: no workflow_dispatch trigger

If `gh workflow run` errors with something like "workflow does not have a workflow_dispatch
trigger", the workflow YAML doesn't declare one. Don't try to force it — tell the user, and if
they want it enabled, add:

```yaml
on:
  workflow_dispatch:
```

to the workflow file (alongside whatever other triggers it already has), commit, then retry.

## MCP alternative

If the `github` MCP server is connected, prefer `actions_run_trigger` for step 2 and
`actions_list` for step 3 (finding the resulting run) over shelling out — same effect, no
subprocess.
