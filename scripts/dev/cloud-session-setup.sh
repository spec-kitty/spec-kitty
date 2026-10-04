#!/bin/bash
# Repo-level setup for a Claude Code cloud session (no-op anywhere else).
#
# Run it once at the start of a cloud session, from the repository root:
#
#   bash scripts/dev/cloud-session-setup.sh
#
# It prepares the dev environment so tests, linters and the spec-kitty CLI
# work, and builds the CodeGraph index in the background when codegraph is
# installed (install it in the cloud environment's setup script).
#
# This is a plain script, not a tracked `.claude/settings.json` SessionStart
# hook: spec-kitty writes its own hooks into that file, so tracking it would
# leave every checkout dirty.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# Python dev environment, pinned to uv.lock (idempotent; cached after first run).
uv sync --frozen --all-extras
# Wheel-building packaging tests need the PEP 517 frontend.
uv pip install --quiet build
# The spec-kitty CLI from this checkout (subprocess-driven tests shell out to it).
uv pip install --quiet -e .

# Persist the session env vars when the harness offers an env file.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  for line in 'export PWHEADLESS=1' 'export CODEGRAPH_TELEMETRY=0'; do
    grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null || echo "$line" >> "$CLAUDE_ENV_FILE"
  done
fi

# Keep the CodeGraph index out of `git status`: a dirty tree trips spec-kitty's
# WRITE_CHECKOUT_DIRTY / merge dirty-worktree guards.
exclude="$(git rev-parse --git-path info/exclude)"
mkdir -p "$(dirname "$exclude")"
grep -qxF '.codegraph/' "$exclude" 2>/dev/null || echo '.codegraph/' >> "$exclude"

# Build the CodeGraph index in the background (~2 min, ~440 MB) so the session
# is not blocked; the MCP server picks up the index live.
if command -v codegraph >/dev/null 2>&1 && [ ! -d .codegraph ]; then
  nohup codegraph init >/tmp/codegraph-init.log 2>&1 &
fi
