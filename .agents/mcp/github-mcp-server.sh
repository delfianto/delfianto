#!/usr/bin/env bash
set -euo pipefail

if ! token=$(gh auth token 2>/dev/null); then
  echo "github-mcp-server: gh is not authenticated (run \`gh auth login\`)" >&2
  exit 1
fi

exec docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN="$token" \
  -e GITHUB_TOOLSETS="context,repos,issues,pull_requests,actions" \
  ghcr.io/github/github-mcp-server
