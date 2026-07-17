---
name: release
description: Cut a version release (bump version, tag, push, create a GitHub release with the right assets) for a Rust crate, a Python package, an Obsidian plugin, or a browser extension. Use when the user asks to "cut a release", "ship vX.Y.Z", "bump the version and release", "publish this plugin update".
---

# release

Detects the project type from the repo checkout and follows that ecosystem's release
convention. This is deliberately **dry-run by default** — releasing involves a git push and a
public GitHub release, both hard to cleanly undo, so nothing touches disk or the network until
`--execute` is passed.

## Running it

```bash
python3 .agents/skills/release/scripts/release.py <path-to-repo-checkout> <major|minor|patch|X.Y.Z> [--execute] [--no-push] [--allow-dirty]
```

1. Run **without** `--execute` first. It prints: detected project type, current → new version,
   the tag it'll create, every file it will edit, the build command (if any), and the exact
   `git`/`gh` commands it will run — nothing is written yet.
2. **Show that plan to the user and get explicit confirmation** before re-running with
   `--execute`. This is a shared-system, hard-to-reverse action (pushed tag + public release);
   don't skip the confirmation step just because the dry run looked fine.
3. Re-run with `--execute` to actually do it. Requires a clean working tree unless
   `--allow-dirty` is passed.
4. `--no-push` commits and tags locally but stops there (no `git push`, no `gh release create`)
   — useful if the user wants to inspect the commit before it goes anywhere.

## Project-type conventions it follows

| Type | Detected by | Version lives in | Tag format | Build | Release assets |
| --- | --- | --- | --- | --- | --- |
| Rust | `Cargo.toml` | `[package].version` | `vX.Y.Z` | — (no `cargo publish`; see below) | none |
| Python | `pyproject.toml` | `[project].version` or `[tool.poetry].version` | `vX.Y.Z` | — (no PyPI upload; see below) | none |
| Obsidian plugin | `manifest.json` with `minAppVersion` | `manifest.json`, plus `versions.json` if present, plus `package.json` if present | **bare `X.Y.Z`, no `v` prefix** — this is an Obsidian community-plugin requirement, not a style choice | `npm run build` | `main.js`, `manifest.json` (required), `styles.css` (if the build produced one) |
| Browser extension | `manifest.json` with `manifest_version` | `manifest.json`, plus `package.json` if present | `vX.Y.Z` | `npm run build` | a zip of the build output dir (`dist/`, `build/`, or `extension/` — whichever has a `manifest.json`) |

If none of these match (no `Cargo.toml`/`pyproject.toml`/`manifest.json` with the right shape),
the script refuses rather than guessing — e.g. a repo like `docker-conf` that's just loose
scripts with no packaging manifest, or a full-stack app without a top-level `pyproject.toml`,
has no defined release convention here. Ask the user how they want to handle it instead of
inventing one.

## What this script deliberately does NOT do

- **No `cargo publish` / no PyPI upload.** Those need registry credentials this tooling has no
  business assuming exist or are wanted. It creates the git tag and GitHub release only; if the
  user wants the crate/package published to a registry too, that's a separate, explicit step
  they should confirm and run themselves (or ask for and you do it as its own action).
- **No changelog generation beyond `gh release --generate-notes`** (GitHub's own PR/commit-based
  notes). If the user wants hand-written release notes, write them to a file and swap in
  `gh release create ... --notes-file <path>` manually instead of relying on the script's
  `--generate-notes` call.
- **Dynamic/computed versions aren't supported** — if `pyproject.toml` sources its version from
  git tags or a Python module (`dynamic = ["version"]`), the script errors out; bump it by
  whatever mechanism that project actually uses instead.

## Non-semver bump

Pass an explicit `X.Y.Z` instead of `major`/`minor`/`patch` for anything that doesn't fit a
simple increment (pre-releases, resets, etc.) — the script accepts a literal version directly.
