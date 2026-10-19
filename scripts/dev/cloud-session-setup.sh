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

# Wire Gradle to a Java 25 toolchain for the acceptance-jvm (Cucumber) suite, which
# `build.gradle` pins to `languageVersion = of(25)`. The JDK itself is installed at
# environment-provisioning time -- see acceptance-jvm/README.md > "Cloud sessions". Here
# we only POINT Gradle at a Java 25 that is already present, and put the pinned Gradle
# (acceptance-jvm/tools/pins.json, checksum-verified, the same one CI installs) first on
# PATH: the image's own Gradle 8.14.3 cannot run on Java 25 ("Unsupported class file
# major version 69"), the pinned 8.14.5 can. A session without a Java 25 still runs every
# Python check and the per-PR scenario contract, which need no JDK.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  jdk25=""
  for home in "${JAVA_HOME:-}" /usr/lib/jvm/*25* /opt/*jdk*25* /opt/java/*25*; do
    [ -n "$home" ] && [ -x "$home/bin/java" ] || continue
    if "$home/bin/java" -version 2>&1 | grep -q 'version "25'; then
      jdk25="$home"
      break
    fi
  done
  if [ -n "$jdk25" ]; then
    lines=("export JAVA_HOME=$jdk25")
    gradle_version=$(python3 -c 'import json,sys; print(next(t["version"] for t in json.load(open(sys.argv[1]))["tools"] if t["name"] == "gradle"))' acceptance-jvm/tools/pins.json)
    tools_dir="${XDG_CACHE_HOME:-$HOME/.cache}/spec-kitty/acceptance-jvm-tools"
    gradle_bin="$tools_dir/gradle-$gradle_version/bin"
    if [ ! -x "$gradle_bin/gradle" ]; then
      uv run --frozen --no-sync python contracts/tools/install_tools.py \
        --pins acceptance-jvm/tools/pins.json --dest "$tools_dir" --only gradle \
        || echo "note: the pinned Gradle $gradle_version could not be installed; acceptance-jvm needs it on Java 25."
    fi
    if [ -x "$gradle_bin/gradle" ]; then
      lines+=("export PATH=\"$gradle_bin:\$PATH\"")
    fi
    for line in "${lines[@]}"; do
      grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null || echo "$line" >> "$CLAUDE_ENV_FILE"
    done
  else
    echo "note: no Java 25 found; the acceptance-jvm (Cucumber) suite needs temurin 25." \
         "Add it to the environment setup script (acceptance-jvm/README.md > Cloud sessions)." \
         "Python checks and the per-PR scenario contract do not need it."
  fi
fi
