---
name: tags
description: List, create, or delete git tags on a repo, both locally and on origin/GitHub. Use when the user asks to "list tags", "delete tag vX.Y.Z", "tag this commit", or is cleaning up stray/bad tags.
---

# tags

Simple enough to not need a bundled script. Prefer the GitHub MCP server's `list_tags`/`get_tag`
if connected for the remote-side read; `gh`/`git` fallbacks below. There is no MCP tool for
creating or deleting tags (as of the `context,repos,issues,pull_requests,actions` toolset this
project enables) — those go through `git`/`gh` regardless.

## List

```bash
gh api repos/delfianto/<repo>/tags --paginate --jq '.[].name'
# or, in a local checkout:
git tag --sort=-creatordate
```

`gh release list --repo delfianto/<repo>` is usually more useful than raw tags when the question
is "what's been released", since it also shows draft/prerelease state — check whether the user
means tags specifically or releases before picking one.

## Create

Prefer doing this as part of the `release` skill's flow (which also bumps the version file and
creates the GitHub release in the right order) rather than tagging in isolation, **unless** the
user explicitly just wants a bare tag with no release/version-bump attached.

Bare tag only:

```bash
git tag -a <tag> -m "<tag>"        # annotated tag, in a local checkout
git push origin <tag>
```

## Delete

**Deleting a tag is a shared-system, effectively-irreversible action once pushed** (anyone who
already fetched it keeps their local copy; if a GitHub release points at it, that release's
asset/ref association breaks). Always confirm the exact tag name and repo with the user before
deleting anything — never delete tags to "clean up" without being asked for that specific tag.

```bash
git push --delete origin <tag>     # remove from GitHub
git tag -d <tag>                   # remove locally, if you have a checkout
```

If a GitHub release is attached to the tag, decide with the user whether the release should go
too (`gh release delete <tag> --repo delfianto/<repo> [--yes]`) — deleting the tag alone leaves a
release pointing at a dangling ref, which is usually not what's wanted.

## Notes

- Tag naming conventions vary by project type — see the `release` skill's table (Obsidian
  plugins use bare `X.Y.Z`, everything else here uses `vX.Y.Z`). Match whatever the repo already
  uses rather than assuming.
- Listing via `gh api .../tags` doesn't tell you if a tag has an associated GitHub release;
  cross-reference with `gh release list` if that matters for the task at hand.
