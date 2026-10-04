#!/bin/bash
# SessionStart hook for Claude Code cloud sessions (no-op locally).
# Prepares the dev environment so tests, linters and the spec-kitty CLI work,
# and builds the CodeGraph index in the background when codegraph is installed
# (install it in the cloud environment's setup script; see CLAUDE.md).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Python dev environment, pinned to uv.lock (idempotent; cached after first run).
uv sync --frozen --all-extras
# Wheel-building packaging tests need the PEP 517 frontend.
uv pip install --quiet build
# The spec-kitty CLI from this checkout (subprocess-driven tests shell out to it).
uv pip install --quiet -e .

echo 'export PWHEADLESS=1' >> "$CLAUDE_ENV_FILE"
echo 'export CODEGRAPH_TELEMETRY=0' >> "$CLAUDE_ENV_FILE"

# Keep the CodeGraph index out of `git status`: a dirty tree trips spec-kitty's
# WRITE_CHECKOUT_DIRTY / merge dirty-worktree guards.
exclude="$(git rev-parse --git-path info/exclude)"
grep -qx '.codegraph/' "$exclude" 2>/dev/null || echo '.codegraph/' >> "$exclude"

# Build the CodeGraph index in the background (~2 min, ~440 MB) so session
# start is not blocked; the MCP server picks up the index live.
if command -v codegraph >/dev/null 2>&1 && [ ! -d .codegraph ]; then
  nohup codegraph init >/tmp/codegraph-init.log 2>&1 &
fi
