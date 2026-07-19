# Justfile Normalization Plan

Goal: unify `justfile`s across personal **Rust binary** projects onto one
canonical baseline (`justfile-rust` in this meta-repo), including upx on every
install path. Pure libraries (e.g. `plex-rs`) are out of scope.

Root of all projects: `/srv/project/personal/`  
Canonical template: `justfile-rust` (copy into each repo as `justfile`, set `bins`).

---

## Standing preferences

- **Always push to `main`** (no PRs). If `origin/main` moved: `git fetch` →
  `git rebase origin/main` (Cargo.lock conflicts: take our side, then
  `cargo build` to reconcile) → push.
- Branch-protection required `ci` check: owner bypass is expected
  (`remote: Bypassed rule violations`).
- After push: `gh run list --branch main --limit 1` then
  `gh run watch <id> --exit-status`.
- CI gates (typical): `cargo fmt --all --check`,
  `cargo clippy --all-targets --all-features -- -D warnings`,
  `cargo build --all-targets`, `cargo test`.
  `just lint` alone does **not** run rustfmt — always `cargo fmt` before push.

---

## Locked decisions

| decision | choice |
| --- | --- |
| Template | `justfile-rust` → copy to each binary repo as `justfile` |
| Filename | lowercase `justfile` (**Task A done**: compose-utils, llama.rs, media-forge) |
| Multi-bin | `bins := "a b c"` — compress/install/uninstall loop all of them |
| upx | **always** in base; `install` depends on `compress`; fail if upx missing |
| install | `~/.local/bin` default; `just install --system` → `/usr/local/bin` |
| `build` | always release |
| `check` | `fmt-check lint test` (mirrors CI) |
| `lint` | full clippy (`--all-targets --all-features -- -D warnings`) |
| Libraries | **skip** `plex-rs` (and any future pure-lib crate) |
| nvprime bins | always install **both** `nvprime` and `nvprime-sys` to the same dir |
| nvprime system | **option A**: delete `system/install.sh`; baseline is binaries-only. Keep `nvprime.service` + dbus conf in-tree for **manual** install later |
| compose-utils | baseline (`composectl` + upx) + keep `systemd/install.sh` as **extras** |
| wsmr | full baseline; rename any colliding old `check`/`lint` meanings; keep podman/coverage as extras |
| interpolation | tight `{{bins}}` / `{{bin_dir}}` — do not let `just --fmt` re-space |

---

## Task A — filename lowercase (DONE)

```text
compose-utils  Justfile → justfile  (pushed)
llama.rs       Justfile → justfile  (pushed)
media-forge    Justfile → justfile  (pushed)
```

---

## Canonical baseline

Source of truth: **`justfile-rust`**. Summary of house style:

| axis | decision |
| --- | --- |
| `bins` | space-separated binary **names** (never paths) |
| env | `env_var("HOME")` not `env("HOME")` |
| `build` | `cargo build --release` |
| `fmt` / `fmt-check` | standalone |
| `lint` | clippy all-targets/all-features, `-D warnings` |
| `check` | `fmt-check lint test` |
| `compress` | upx `--best --lzma`, skip if already packed (`upx -t`) |
| `install` | depends on `compress`; `--system` flag |
| `uninstall` | same dir logic as install |
| `clean` | `cargo clean` |

### Per-repo specials (append after baseline, never replace it)

| project | `bins` | specials to keep / add |
| --- | --- | --- |
| zentools | `zentools` | multicall symlinks `zen-epp` `zen-smu` `zen-mem` on install/uninstall |
| frontmatter-mcp | `frontmatter` | upx already in base; keep `frontmatter-mcp` symlink; optional `test-verbose` |
| stash-mcp | `stash-mcp` | `test-integration`, `test-all` |
| media-forge | `media-forge` | `export RUSTFLAGS := "-C target-cpu=native"`; `run +args` |
| vicuna | `vicuna` | optional `build-tiny` size report after compress |
| pika | `pika` | `serve`, `serve-stdio`, `ps`, `help`, test helpers |
| llama.rs | `llama` | bespoke `test` (no live); keep `test-live` / `test-signal` / `test-download` / `test-ollama` / `test-all` |
| nvprime | `nvprime nvprime-sys` | drop `system/install.sh`; optional `run` / daemon helpers that don't use the script; unit+dbus stay for manual use |
| wsmr | `wsmr` | baseline names win; keep `test-linux`, `build-linux`, `integration`, `coverage*`, `ci` as extras (rename old local `check`/`lint` if they conflict) |
| compose-utils | `composectl` | `install-systemd *args:` → `./systemd/install.sh {{args}}` (or similar) as **extra**, not replacing baseline `install` |
| tei-proxy | `tei-proxy` | include if still a shipped binary (same base) |
| dotlinker | *(confirm bin name)* | include if shipped as a binary |

### Out of scope

- **plex-rs** — library only
- non-Rust inventory repos

---

## Rollout status

| project | status | notes |
| --- | --- | --- |
| justfile-rust (meta) | ✅ present | not yet committed necessarily |
| filename Task A | ✅ | three renames pushed |
| zentools | 🔧 baseline-ish locally | `07d5a89` ahead of origin — align to template + push |
| frontmatter-mcp | 🔧 retrofit | add fmt pair; `check: fmt-check lint test`; upx already |
| stash-mcp | 🔧 retrofit | same as frontmatter |
| media-forge | 🔧 full adopt | install semantics change |
| vicuna | 🔧 full adopt | fix `bin` path → name |
| pika | 🔧 full adopt | `env_var`, `--system`, full lint |
| llama.rs | 🔧 full adopt | `build` debug→release |
| nvprime | 🔧 full adopt + **delete install.sh** | both bins; option A |
| wsmr | 🔧 full adopt | rename colliding recipes |
| compose-utils | 🔧 full adopt + keep install.sh extras | bin = `composectl` |
| tei-proxy / dotlinker | 🔧 if binary | confirm + adopt |
| plex-rs | ⏭ skip | library |

---

## Execution order

1. Commit `justfile-rust` (+ this plan) in **delfianto** if not already.
2. Per binary repo (one commit each), copy template → set `bins` → append specials → delete nvprime `system/install.sh` when touching nvprime:
   1. zentools (push pending commit / re-align)
   2. frontmatter-mcp
   3. stash-mcp
   4. pika
   5. vicuna
   6. media-forge
   7. llama.rs
   8. compose-utils
   9. nvprime (delete install.sh)
   10. wsmr
   11. tei-proxy / dotlinker if applicable
3. Push each to `main` and watch CI (prefer per-repo so failures are isolated).

### Per-repo checklist

```bash
cd /srv/project/personal/<repo>
# write justfile from justfile-rust; set bins; append specials
# nvprime only: git rm system/install.sh  (and drop just recipes that called it)
just --list
cargo fmt --all
cargo clippy --all-targets --all-features -- -D warnings
cargo test   # or repo-specific safe test recipe
git add -A && git commit -m "Adopt shared justfile baseline (+ specials)"
git fetch origin && git rebase origin/main   # if needed
git push origin main
gh run watch "$(gh run list --branch main --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```

---

## Context notes (prior work)

- frontmatter-mcp / stash-mcp already had near-baseline install + upx + AGY shim work; still need fmt-gated `check`.
- zentools local commit renames binary `zen`→`zentools` with multicall shortcuts; needs template align + push.
- llama.rs `test` must stay non-live; `check` uses that `test`.
- compose-utils binary name is **`composectl`** (package name `compose`).
