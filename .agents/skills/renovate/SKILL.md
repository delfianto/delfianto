---
name: renovate
description: View, validate, and edit a repo's Renovate JSON config (renovate.json / .github/renovate.json). Use when the user asks to add/change Renovate rules, set up labels or automerge, or check why Renovate is behaving oddly in a repo.
---

# renovate

## Validate before and after editing

```bash
python3 .agents/skills/renovate/scripts/check_renovate_config.py [path] [--repo owner/name]
```

- No args, run from inside a checked-out repo → checks `renovate.json`,
  `.github/renovate.json`, or `.renovaterc.json` (first match).
- `--repo owner/name` → fetches the config straight from GitHub via `gh api` contents, no clone
  needed. Useful for a quick health check across several repos without checking each one out.
- Catches: invalid JSON, **duplicate keys** (silently last-wins in plain `json.load`, which this
  script specifically guards against since it's an easy hand-edit mistake), unrecognized
  top-level keys (typo detector, not a full schema check), and `packageRules` entries with no
  `match*` selector (a rule with no selector matches *everything*, which is rarely intended).
- **Scope limit**: this is a lightweight linter, not the real Renovate schema validator, and it
  only understands plain JSON — not JSON5 with comments. For an authoritative check, the
  official tool is `npx --yes renovate-config-validator` (requires network + npm); reach for
  that if the user wants a definitive answer and this script's checks aren't enough.

## Editing

Fetch, edit, validate, then commit/PR — don't hand-wave field names, use the checker above to
catch obvious mistakes before pushing:

```bash
gh api repos/delfianto/<repo>/contents/renovate.json --jq '.content' | base64 -d > renovate.json
# edit renovate.json
python3 .agents/skills/renovate/scripts/check_renovate_config.py renovate.json
gh api repos/delfianto/<repo>/contents/renovate.json --jq '.sha'   # needed for the update call
gh api -X PUT repos/delfianto/<repo>/contents/renovate.json \
  -f message="chore(renovate): update config" \
  -f content="$(base64 -w0 renovate.json)" \
  -f sha="<sha from above>"
```

Prefer doing this in a real clone + branch + PR when the change is more than a one-line tweak —
pushing straight to the default branch via the contents API is fine for trivial fixes, not for
anything that changes update behavior meaningfully (e.g. enabling automerge).

## Common asks and where they live in the config

| Ask | Field |
| --- | --- |
| Add labels to Renovate PRs (needed for `pr-manage`'s update-type classification) | `packageRules[].labels` or top-level `labels` |
| Group all patch/minor updates into one PR | `packageRules` with `matchUpdateTypes: ["patch","minor"]` + `groupName` |
| Auto-merge safe updates | `automerge: true` scoped inside a `packageRules` entry, not top-level, unless the user really wants everything automerged |
| Change schedule/timezone | `schedule`, `timezone` |
| Ignore a dependency entirely | `ignoreDeps` |
| Limit concurrent PRs | `prConcurrentLimit`, `prHourlyLimit` |

## MCP alternative

The GitHub MCP server's `get_file_contents` (read) and `create_or_update_file` (write, handles
the base64/SHA bookkeeping itself) cover the same ground as the `gh api` + `base64` dance above —
prefer those if connected, they're less error-prone than the manual round-trip.
