# AGENTS.md

This repo is `delfianto`'s GitHub profile repo, repurposed as a **meta-repo for managing his
personal GitHub repositories** — an inventory of them plus a set of harness-agnostic agent
skills for day-to-day repo maintenance (CI, PRs, Renovate, releases, tags). This file is the
entry point for any coding agent working here; `CLAUDE.md` is a symlink to it.

## What's here

```
INVENTORY.md              categorized table of personal repos (generated, see below)
AGENTS.md                 this file
CLAUDE.md                 -> AGENTS.md (symlink)
.claude/
  settings.json            permissions so routine ops don't prompt every time
  skills/                  -> ../.agents/skills (symlink)
.agents/
  pyproject.toml           ruff + basedpyright config for everything under .agents/
  scripts/ghrepo.py         shared stdlib helpers (gh CLI wrapper, repo listing, project-type detection)
  scripts/batch.py          shared batch-execution harness for any "do X across every repo" script
  mcp/github-mcp-server.sh  GitHub MCP server launcher, token from `gh auth token`
  skills/<name>/SKILL.md    one directory per skill, harness-agnostic
.mcp.json                  Claude Code project MCP config
opencode.json              OpenCode project config (mcp section)
.antigravitycli/mcp_config.json   Antigravity project-local MCP config (see caveat below)
```

## Repo inventory

`INVENTORY.md` lists every personal, non-fork, non-archived, non-`saas*` repo owned by
`delfianto`, grouped into category tables (Obsidian Plugins, Browser Extensions, Linux Utils,
Docker & Self-Hosting, AI & Agents, Misc). It's generated, not hand-maintained:

```bash
python3 .agents/skills/inventory/scripts/build_inventory.py
```

Category assignments live in `.agents/skills/inventory/categories.json`; new repos get a
best-effort auto-guess appended there on first run — see the `inventory` skill for details.

## Skills

Every skill is a self-contained directory with a `SKILL.md` (YAML frontmatter + instructions)
and, where the logic is non-trivial enough to warrant it, a Python script under `scripts/`. They
are written to be readable and actionable by **any** agent with shell access — Claude Code,
OpenCode, Antigravity, or a human — not just Claude Code specifically. Nothing in a `SKILL.md`
assumes a specific harness's tool-calling conventions.

| Skill | Does |
| --- | --- |
| `inventory` | Regenerate `INVENTORY.md` |
| `ci-status` | Latest CI run status per repo, one or many, filterable to failed/pending/no-ci |
| `ci-diagnose` | Fetch + trim a failed run's log to the part worth reading |
| `ci-trigger` | Manually kick off a `workflow_dispatch` run |
| `pr-manage` | List/review/merge/close PRs; cross-repo sweep of open Renovate PRs |
| `renovate` | Validate and edit a repo's `renovate.json` |
| `release` | Detect project type (Rust/Python/Obsidian plugin/browser extension) and cut a release |
| `tags` | List/create/delete git tags, local and remote |

### Design principles behind the skills

- **MCP first, script second, raw `gh` third.** Where the `github` MCP server (see below) has a
  tool that does the job for a single repo/PR/run, the skill says so by name — no hand-waving
  "use the MCP server for this." A bundled Python script only exists where the task is a
  **multi-repo sweep** (`inventory`, `ci-status`, `pr-manage`'s Renovate sweep) or needs
  **deterministic, reusable logic** that shouldn't be re-derived by hand each time (log
  excerpting in `ci-diagnose`, project-type detection and version-file patching in `release`,
  JSON linting in `renovate`). Simple one-shot actions (`ci-trigger`, `tags`) are
  instructions only.
- **Destructive/shared-state actions are never scripted as one-shot batch operations.** Merging
  PRs, deleting tags, force-pushing, creating releases — a script could technically loop over
  these, but none of them do. Every skill that touches one of these explicitly says to confirm
  with the user before each call. `release.py` goes further and defaults to a dry run; nothing
  writes to disk or the network without `--execute`.
- **Python scripts are stdlib-only** and live either at `.agents/scripts/` (shared: `ghrepo.py`,
  `batch.py`) or under a skill's own `scripts/`. They shell out to `gh` (already required,
  already authenticated) rather than reimplementing GitHub's API/auth/pagination by hand. All of
  them pass `ruff check`, `ruff format --check`, and `basedpyright` under `.agents/pyproject.toml`
  — run those three from `.agents/` before considering a script change done:

  ```bash
  cd .agents && ruff check . && ruff format --check . && basedpyright .
  ```
- **Any "for each repo, do X" loop goes through `.agents/scripts/batch.py`'s `run_batch`, not a
  hand-rolled `for` loop.** This isn't a style preference — every hand-rolled version of this
  loop written during this repo's early history had a real bug: zsh not word-splitting an
  unquoted `for r in $repos` (silently ran once with the whole list as one repo name), a `jq
  '.name'` on a 404 response returning the literal string `"null"` which is truthy in bash (every
  repo false-positived as "has the file"), `status` colliding with a zsh builtin variable, and one
  repo's permission error crashing an entire 31-repo sweep. `run_batch` fixes all of these at
  once: it isolates failures per-repo (one repo raising never aborts the rest — captured in that
  repo's `RepoResult.error` instead), runs with bounded concurrency instead of one-repo-at-a-time,
  and returns results in a stable order regardless of completion order. `inventory`, `ci-status`,
  and `pr-manage`'s Renovate sweep all use it; a new script that loops over repos should too.
  `batch.py` also has a small standalone CLI for one-off checks that would otherwise become a
  throwaway shell loop, e.g. `python3 .agents/scripts/batch.py .github/dependabot.yml` to see
  which repos still have a given file.

## MCP servers

`.agents/mcp/github-mcp-server.sh` wraps `ghcr.io/github/github-mcp-server` (Docker) with the
token pulled fresh from `gh auth token` at launch — no token is ever written into a config file
in this repo. If `gh` isn't authenticated, the wrapper exits 1 immediately instead of starting
the server, by design (`gh auth token` failing is the "unauthed" signal).

It's wired into three harnesses' project-scoped config, all pointing at the same script:

- **Claude Code** — `.mcp.json`, trusted via `enabledMcpjsonServers` in `.claude/settings.json`
  (no manual "trust this server?" prompt needed).
- **OpenCode** — `opencode.json`, `mcp.github` (`type: local`).
- **Antigravity** — `.antigravitycli/mcp_config.json`. **Caveat:** as of writing, Antigravity CLI
  has a known bug ([google-antigravity/antigravity-cli#60](https://github.com/google-antigravity/antigravity-cli/issues/60))
  where project-local `mcp_config.json` is discovered but not actually loaded — only the
  HOME-level `~/.gemini/config/mcp_config.json` spawns servers. The project-local file here is
  correct and forward-compatible once that's fixed; until then, merge the same `"github"` entry
  (same command/args, just point `args` at this repo's absolute path instead of a relative one)
  into your global Antigravity config yourself if you want it available there today. Not done
  automatically — that file is outside this repo and shared across every other project you use
  Antigravity in.

The enabled toolset is `context,repos,issues,pull_requests,actions` (set via `GITHUB_TOOLSETS` in
the wrapper) — enough for everything the skills above need, deliberately not the full tool
surface (no `code_security`, `discussions`, etc).

Tool names actually exposed by this toolset (verified by querying the running server, not
guessed): `actions_get`, `actions_list`, `actions_run_trigger`, `get_file_contents`,
`create_or_update_file`, `list_pull_requests`, `pull_request_read`, `pull_request_review_write`,
`merge_pull_request`, `update_pull_request`, `list_tags`, `get_tag`, `search_repositories`, and
others — see individual `SKILL.md` files for which tool applies where.

## Permissions (`.claude/settings.json`)

Allow-listed without a prompt: read-only `gh`/`git` commands (`list`/`view`/`diff`/`status`/`log`
etc.), `git add`/`commit`/`tag -a` (local, reversible), this repo's own Python scripts under
`.agents/`, `ruff`/`basedpyright`/`npm run build`, and the read-only `github` MCP tools listed in
the file.

Deliberately **not** allow-listed (stays a per-action confirmation, even though it's an expected
use of these skills): `git push` (including `--delete`), `git tag -d`, `gh pr merge`/`close`,
`gh release create`/`delete`, `gh workflow run`, any `docker` command, and the corresponding MCP
write tools (`merge_pull_request`, `actions_run_trigger`, etc — anything not on the explicit
allow list). This mirrors the "confirm before destructive/shared-state actions" rule baked into
the skill docs themselves; the settings file just saves the confirmation prompt for everything
that *isn't* one of those.

One known imprecision: `Bash(gh api *)` is allow-listed broadly (mostly used for reads across
these skills), but `gh api`'s write forms (`-X PUT`/`-X DELETE`) match the same prefix and aren't
distinguishable by Claude Code's prefix-wildcard permission syntax. The one write path that
exists today (`renovate`'s contents-API update) is narrow and documented; be aware of this
gap rather than assuming every `gh api` call is a safe read.

## Adding a new skill

1. `.agents/skills/<name>/SKILL.md` with `name`/`description` frontmatter — description should
   state concretely when to use it (trigger phrases help).
2. Only add a `scripts/` script if the logic is genuinely multi-step/stateful/multi-repo; a
   single `gh`/`git` command doesn't need one.
3. If it needs the shared helpers, `sys.path.insert(0, str(Path(__file__).resolve().parents[3] /
   "scripts"))` then `from ghrepo import ...` (see any existing skill script for the exact
   pattern — the `parents[3]` index is fixed because every skill script lives at
   `.agents/skills/<name>/scripts/<script>.py`).
4. Run `ruff check . && ruff format --check . && basedpyright .` from `.agents/` before calling
   it done.
5. No symlinking needed — `.claude/skills` already points at `.agents/skills` as a whole
   directory.
