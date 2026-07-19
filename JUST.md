# Justfile rules — Rust binary projects

**Order of law:** RULES → BASELINE → LAYERS → EXCEPTIONS. Never reverse that.

| | |
| --- | --- |
| Template | `justfile-rust` → copy into each binary repo as `justfile` |
| Project root | `/srv/project/personal/` |
| In scope | Personal **Rust executable binary** crates |
| Out of scope | Pure libraries (`plex-rs`, future lib-only) |

---

## 1. Rules (non-negotiable)

### R1 — Baseline is sacred and maximal

Every binary repo ships the **full** baseline recipe set from `justfile-rust`.  
No subset. No alternate names for the same job.

If a recipe is useful to nearly every binary crate, it belongs in the baseline
template — not as a one-off special.

### R2 — Knobs, not forks

Per-repo differences the baseline understands are **variables**, not forked bodies.

| Knob | Meaning |
| --- | --- |
| `bins` | Space-separated cargo binary **names** (not paths). One or many. |
| `primary` | Which bin `run` invokes. Must be one of `bins`. Single-bin: same as `bins`. |
| `bin_dir` | Default install dir: `~/.local/bin` |
| `sys_dir` | System install dir: `/usr/local/bin` |
| `links` | L1 symlink pairs (`link:target` …). Empty = L1 off. |
| `test_unit` | Shell command for safe unit gate (`just test`). Default: `cargo test`. |
| `test_integration` | Shell command for live/integration suite. Empty = no suite. |

`build` / `install` / `uninstall` always loop `{{bins}}` (build also upx-packs each).  
**Multi-bin is a baseline knob**, not a recipe layer:

```just
bins    := "nvprime nvprime-sys"
primary := "nvprime"
```

All bins install to the **same** directory (local or system). No split layouts.

### R3 — Build is native release + upx (flags for debug only)

- `just build` = `RUSTFLAGS=-C target-cpu=native` + `cargo build --release` **then** upx every bin in `bins`.
- `just build --debug` = `cargo build` (debug profile, **no** upx).
- `install` **always** depends on default `build` (native release + upx).
- upx missing on the release path → **hard fail**.
- Already packed → skip that binary (`upx -t`), then pack with `--best --lzma`.
- Native is **scoped to the `build` recipe** (not a global `export RUSTFLAGS`).
- Do **not** add `compress`, `build-tiny`, `build-native`, or `build-debug` recipes.

### R4 — Install layout is fixed

```text
just install            → ~/.local/bin/<each bin>     (no sudo)
just install --system   → /usr/local/bin/<each bin>   (sudo)
just uninstall [--system]
```

Only known flag: `--system`. Anything else → error.

`install` installs **binaries only** (+ L1 links if configured).  
It never installs systemd units or dbus policy (that is L2).

### R5 — One recipe name, flags select mode

Prefer **one recipe + flags** over a family of near-duplicate recipe names.

#### `build` (unified)

| Invocation | Meaning |
| --- | --- |
| `just build` | Native-CPU release + upx every bin in `bins` |
| `just build --debug` | `cargo build` (debug; no upx) |

Do **not** add `build-debug` or `build-native` recipes.

#### `test` (unified)

| Invocation | Meaning |
| --- | --- |
| `just test` | Safe unit gate only (`test_unit`) |
| `just test --verbose` | Same, with `--nocapture` |
| `just test --integration` | Integration/live suite only (`test_integration`) |
| `just test --run-all` | Unit then integration |
| `just test --run-all --verbose` | Both, with `--nocapture` |

- `--integration` and `--run-all` are mutually exclusive.
- If `test_integration` is empty, `--integration` / `--run-all` **error**.
- Do **not** add `test-verbose`, `test-integration`, or `test-all` recipes.

#### `format` (unified)

| Invocation | Meaning |
| --- | --- |
| `just format` | Same as `--apply` |
| `just format --apply` | `cargo fmt --all` (write) |
| `just format --check-only` | `cargo fmt --all -- --check` (CI) |

Do **not** add `fmt` or `fmt-check` recipes.

#### `full-gate` (unified local CI)

```text
just full-gate  →  format --check-only + lint + test
```

Do **not** add a `check` recipe. That name is retired.

#### Other fixed names

| Recipe | Always means |
| --- | --- |
| `default` | `just --list` |
| `build` | flags: default = native release + upx; `--debug` = debug profile, no upx |
| `run` | `cargo run --release --bin <primary> -- <args>` (dev path; no upx) |
| `lint` | clippy `--all-targets --all-features -- -D warnings` |
| `install` / `uninstall` | binary path above (+ L1 links); install depends on `build` |
| `clean` | `cargo clean` |

Never redefine `full-gate`, `lint`, `install`, or default `test` to mean something else.  
Need a different job → **new name** (`test-signal`, `setup`, `ci`, …).

**Forbidden:** global `export RUSTFLAGS := "-C target-cpu=native"` (taints
`full-gate` / `test` / `lint`). Native is only inside the default `build` recipe.

**Forbidden recipe names (retired):**  
`fmt` · `fmt-check` · `check` · `test-verbose` · `test-integration` · `test-all` ·
`test-live` · `compress` · `build-tiny` · `build-native` · `build-debug` ·
`install-system` · `uninstall-system` · `install-service` · `remove-service`

### R6 — Layers only append

File order after copy:

```text
1. knobs
2. BASELINE          (identical bodies)
3. L2 block          (only if systemd/dbus)
4. EXCEPTIONS        (repo-unique, last)
```

L1 is a **knob** (`links`) wired into baseline install/uninstall — no extra recipes.  
L2 adds recipes; it does not replace `install`.

### R7 — Interpolation style

Tight `{{bins}}` / `{{bin_dir}}` / `{{primary}}` / `{{links}}` / `{{test_unit}}` / …  
Do not let `just --fmt` re-space interpolations.

### R8 — CI contract

Binary CI (`ci-rust` → `.github/workflows/ci.yml`), **four steps**:

| Step | Command | Notes |
| --- | --- | --- |
| format | `just format --check-only` | not `fmt-check` / `fmt` |
| lint | `just lint` | clippy all-targets/all-features `-D warnings` |
| build | `cargo build --all-targets` | **not** `just build` (native+upx; needs upx; not all-targets) |
| test | `just test` | safe unit only — **never** `--integration` / `--run-all` / `--verbose` in default CI |

Local one-shot: `just full-gate` (= format --check-only + lint + test).  
`full-gate` does **not** replace the CI `cargo build --all-targets` step.  
Libraries without a justfile stay on raw cargo.

### R9 — Decision tree (when adding a recipe)

```text
Useful to nearly every binary crate?
  YES → put it in justfile-rust BASELINE and roll out
  NO  ↓

Is it another mode of test / format / install?
  YES → add a flag on the existing recipe (or a knob), not a new recipe name
  NO  ↓

Symlinks for extra install names?
  YES → L1 (`links` knob)
  NO  ↓

Systemd unit / D-Bus / service lifecycle?
  YES → L2 (`setup` / `teardown` / `restart` / `logs` / …)
  NO  ↓

Only “more than one cargo bin”?
  YES → set `bins` + `primary` (baseline knobs)
  NO  ↓

EXCEPTION — append at bottom with a why-comment; never shadow baseline names
```

---

## 2. Baseline

Source of truth: **`justfile-rust`**. Bodies must stay identical across repos.

### Knobs every repo sets

```just
bins              := "foo"           # or "foo bar"
primary           := "foo"           # run target; one of bins
links             := ""              # or "alias:foo other:foo"
test_unit         := "cargo test"    # override only if bare cargo test is unsafe
test_integration  := ""              # or the live/integration command
```

### Full baseline recipe set

`default` · `build` (flags) · `run` ·  
`test` (flags) · `format` (flags) · `lint` · `full-gate` ·  
`install` · `uninstall` ·  
`clean`

### Multi-bin (baseline capability)

```just
bins    := "nvprime nvprime-sys"
primary := "nvprime"
links   := ""
```

No extra recipes. Loops already handle multiple names.

### Integration suites (still baseline — knobs only)

```just
# stash-mcp
test_unit        := "cargo test"
test_integration := "cargo test integration"

# llama.rs (exclude live_* from the safe gate)
test_unit        := "cargo test --lib --test cli --test api -- --test-threads=1"
test_integration := "cargo test --test live_server"
```

Then:

```bash
just test
just test --verbose
just test --integration
just test --run-all
just test --run-all --verbose
```

---

## 3. Layers

Only two product layers. Everything else is an exception.

### L1 — Symlinks (multicall / rename compat)

**When:** install must create extra names pointing at one binary.  
**Projects:** zentools, frontmatter-mcp.

**Knob:**

```just
# form: "link_name:target_bin" space-separated; empty = off
links := "zen-epp:zentools zen-smu:zentools zen-mem:zentools"
# frontmatter-mcp:
# links := "frontmatter-mcp:frontmatter"
```

**Behavior (built into baseline install/uninstall):**

- After installing bins: `ln -sf target link` for each pair.
- Uninstall removes those link names too.
- Target must be a real binary name (usually one of `bins`), never the whole `bins` string.

### L2 — Systemd unit + D-Bus

**When:** repo ships unit files and/or dbus policy.  
**Projects:** nvprime (`system/`), compose-utils (`systemd/`).

**Hard rule:** `install` / `uninstall` = binaries (+ L1) only.  
System integration uses **different names** so it never collides with baseline install.

**Forbidden L2 names** (do not use, ever):

`install-system` · `uninstall-system` · `install-service` · `remove-service` ·
`install-systemd` · any other `install-*` / `uninstall-*` for units

**Fixed L2 recipe names:**

| Recipe | Job |
| --- | --- |
| `setup` | `just install --system`, install unit (+ dbus), daemon-reload, enable --now |
| `teardown` | stop/disable, remove unit/dbus, daemon-reload, `just uninstall --system` |
| `restart` | systemctl restart + status |
| `logs` | journalctl -f |
| `logs-recent` | last N lines |
| `status` | systemctl status |
| `test-dbus` | optional busctl ping |

Template bodies live commented in `justfile-rust` (L2 section). Uncomment and
set `unit_src` / `dbus_src` / `unit_dst` / `dbus_dst` / `unit_name`.

**Unit `ExecStart` must match `just install --system`** (`sys_dir`, usually
`/usr/local/bin/...`).

**compose-utils:** wrapping `./systemd/install.sh` is fine as the **body**, but
the recipe names stay `setup` / `teardown`.

**nvprime:** either enable full L2 (`setup` …), or ship **no** system recipes.  
Orphan ops helpers without a `setup` path are not a layer — delete them.

---

## 4. Exceptions (last, rare)

Only when the project is not plain build (release+upx) → install, and knobs are not enough.

| Class | Allowed | Forbidden |
| --- | --- | --- |
| Extra live suites beyond `test_integration` | `test-signal`, `test-download`, … | Re-adding `test-all` / `test-live` |
| Containers / coverage | `test-linux`, `coverage*`, `ci`, … (wsmr) | Renaming baseline `full-gate` / `lint` |
| App-specific process helpers | `serve`, `serve-stdio` (pika) | Replacing `run` |

Every exception block:

```just
# ===========================================================================
# EXCEPTIONS — <repo>: <one-line why>
# ===========================================================================
```

---

## 5. Per-repo mapping

| Repo | Knobs | Layers | Exceptions |
| --- | --- | --- | --- |
| tei-proxy | `tei-proxy` | — | — |
| dotlinker | `dot-rs` | — | — |
| vicuna | `vicuna` | — | — |
| media-forge | `media-forge` | — | drop global `RUSTFLAGS` (native is default `build`) |
| stash-mcp | + `test_integration` | — | — |
| frontmatter-mcp | `frontmatter` + L1 links | **L1** | — |
| zentools | `zentools` + L1 links | **L1** | — |
| compose-utils | `composectl` | **L2** `setup`/`teardown` | — |
| nvprime | multi-bin + primary | **L2** or none | no orphan daemon helpers |
| llama.rs | custom `test_unit` + `test_integration` | — | optional `test-signal` / `test-download` / `test-ollama` |
| pika | `pika` | — | `serve` / `serve-stdio` |
| wsmr | `wsmr` | — | container / coverage / `ci` (use `full-gate` not `check`) |
| plex-rs | — | — | **out of scope** (library) |

---

## 6. Standing ops preferences

- **Always push to `main`** (no PRs). If `origin/main` moved: `git fetch` →
  `git rebase origin/main` (Cargo.lock conflicts: take our side, then
  `cargo build` to reconcile) → push.
- Branch-protection required `ci` check: owner bypass is expected.
- After push: `gh run list --branch main --limit 1` then
  `gh run watch <id> --exit-status`.
- `just lint` alone does **not** run rustfmt — use `just format --apply` before
  push, or `just full-gate`.

---

## 7. Rollout checklist (per binary repo)

```bash
cd /srv/project/personal/<repo>
# 1. Replace justfile from justfile-rust
# 2. Set bins, primary, links, test_unit, test_integration
# 3. Uncomment L2 (setup/teardown/…) only if unit/dbus exist; wire paths
# 4. Append EXCEPTIONS only if justified
# 5. Update CI: format --check-only (not fmt-check); drop check if present
just --list
just full-gate
git add justfile .github/workflows/ci.yml
git commit -m "Align justfile to flagged test/format baseline"
git push origin main
```

Meta-repo (this one): commit `justfile-rust` + `JUST.md` + `ci-rust` first; then roll children.

---

## 8. Related files in this meta-repo

| File | Role |
| --- | --- |
| `justfile-rust` | Canonical template |
| `JUST.md` | This policy |
| `ci-rust` | Canonical GitHub Actions workflow for binary repos |
| `install-system-bins.sh` | Batch `just install --system` across binary repos |

---

## 9. Locked one-screen summary

1. **Rules → baseline → layers → exceptions.**  
2. **`build` = native release + upx; `build --debug` for debug.** No `compress` / `build-tiny` / `build-native` / `build-debug`.  
3. **`bins` + `primary` are the multi-bin mechanism.**  
4. **`test` / `format` take flags; no `test-*` / `fmt*` twin recipes.**  
5. **`full-gate` replaces `check`.**  
6. **L1 = `links`. L2 = systemd/dbus (`setup` / `teardown` / ops).**  
7. **`install` never touches units.** No `install-system` / `install-service`.  
8. **Integration = `test_integration` knob + `just test --integration|--run-all`.**  
9. **Exceptions explain themselves** and never shadow baseline names.  
10. **Template:** `delfianto/justfile-rust`. Repos copy, set knobs, enable layers, then exceptions.
