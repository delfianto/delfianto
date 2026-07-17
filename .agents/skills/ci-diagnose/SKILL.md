---
name: ci-diagnose
description: Fetch a failed GitHub Actions run's logs and surface the relevant error excerpt so the agent can explain why it failed. Use after ci-status reports a failure, or when the user asks "why did CI fail on <repo>", "diagnose the failing build", etc.
---

# ci-diagnose

Fetches the failed-step log for a run and trims it down to the parts worth reading — full CI
logs are typically thousands of lines of setup/cache noise. **The script does extraction only;
diagnosing the root cause from the excerpt is your job, not the script's.**

## Running it

```bash
python3 .agents/skills/ci-diagnose/scripts/ci_diagnose.py --repo NAME [--run-id ID] [--max-lines N]
```

- No `--run-id` → finds the most recent run with a failing conclusion
  (`failure`/`timed_out`/`action_required`/`startup_failure`) and uses that.
- Prints:
  1. Which run/workflow it pulled from (with URL).
  2. Heuristic **hints** (e.g. "Rust compiler error", "Python missing package") — these are
     pattern matches on the log text, not a verdict. Treat them as a pointer to look closer, not
     a conclusion to repeat verbatim.
  3. A trimmed **log excerpt**: lines matching error-ish patterns plus a few lines of
     surrounding context, deduplicated and capped (`--max-lines`, default 200). If nothing
     matches, it falls back to the tail of the log.

## How to use this skill

1. Run the script for the repo in question.
2. Read the excerpt yourself and form the actual diagnosis — name the specific failing
   assertion/compiler error/lint rule, not just the hint category.
3. If the excerpt doesn't contain enough to explain the failure (e.g. the error is buried
   outside the matched windows), re-run with a higher `--max-lines`, or fall back to
   `gh run view <id> --repo owner/repo --log-failed` directly for the full log.
4. Report the diagnosis to the user in terms of what to fix, not just what broke — e.g. "rustfmt
   would reformat `src/image/convert.rs`; run `cargo fmt` and push" beats "the format check
   failed".

## Notes

- Needs `gh` authenticated; logs for very old runs may have expired on GitHub's side, in which
  case the script prints a message and exits non-zero — don't retry blindly, tell the user.
- This intentionally does not call any LLM/AI service itself — it's a deterministic fetch+trim
  step so the same run always produces the same excerpt, and the actual reasoning is left to
  you.

## MCP alternative

For a single run, the `github` MCP server's `actions_get` (run details) and `get_job_logs` (raw
job logs) cover the same ground interactively. The script still earns its keep for the
excerpt-trimming — `get_job_logs` returns the same firehose `gh run view --log-failed` does, so
route it through `extract_excerpt` (or eyeball it the same way) rather than dumping the whole log
into context.
