---
title: Set Up a Claude Code Cloud Session
description: Prepare a Claude Code cloud session so the Spec Kitty CLI, the test package and CodeGraph are ready before you run a Mission or an Op.
doc_status: active
updated: '2026-10-06'
audience: docs/context/audience/internal/maintainer.md
type: how-to
---
# Set Up a Claude Code Cloud Session

This page is for maintainers and contributors who run Spec Kitty Missions or
Ops in a Claude Code cloud session. When you finish, the session has the
`spec-kitty` CLI installed from your checkout, the test dependencies synced, and
a CodeGraph index ready to query.

Setup has two layers:

1. An **environment setup script**. It lives in the cloud environment settings,
   outside the repository, and runs when the container is built.
2. A **repository script**, `scripts/dev/cloud-session-setup.sh`. You run it
   once per session from the repository root.

## Step 1: Add the environment setup script

1. Open the environment menu in the session title bar.
2. Choose **Edit**, then **Setup script**.
3. Paste this script and save:

```bash
#!/bin/bash
set -euo pipefail
npm install -g @colbymchenry/codegraph@1.6.2
codegraph install --yes --target claude --location global || true
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
```

The script installs CodeGraph, registers it with Claude Code, and installs `uv`
if it is missing. New sessions pick up the change.

The `codegraph install` line has not been tested end to end, so it ends in
`|| true`: a failure there does not stop the container build. If the CodeGraph
tools are missing later, see [Troubleshooting](#troubleshooting).

## Step 2: Run the repository script in each session

From the repository root:

```bash
bash scripts/dev/cloud-session-setup.sh
```

The script does nothing unless `CLAUDE_CODE_REMOTE=true`, so it is safe to run
on a local machine. In a cloud session it:

- runs `uv sync --frozen --all-extras`, which installs the test extras and
  `pytest-xdist`;
- installs `build`;
- runs `uv pip install -e .`, so the `spec-kitty` CLI comes from your checkout.
  Tests that start `spec-kitty` as a subprocess need this;
- writes `PWHEADLESS=1` and `CODEGRAPH_TELEMETRY=0` to `CLAUDE_ENV_FILE`, when
  that file exists;
- adds `.codegraph/` to `.git/info/exclude`. An untracked index would make the
  working tree dirty, and a dirty tree trips the `WRITE_CHECKOUT_DIRTY` and
  dirty-worktree guards;
- starts `codegraph init` in the background when `codegraph` is on `PATH` and no
  index exists yet. This takes about 2 minutes and about 440 MB. The log is at
  `/tmp/codegraph-init.log`. The CodeGraph MCP server picks up the index as soon
  as it is written; you do not need to restart.

When everything is already in place, the script finishes in about 7 seconds.

### Why this is not a committed SessionStart hook

Spec Kitty writes its own hooks into `.claude/settings.json`. If that file were
tracked with a setup hook in it, every checkout would become dirty. Running the
script by hand keeps the tree clean.

If the repository is already cloned when the environment setup script runs, you
can append this line to that script instead:

```bash
cd <repo> && bash scripts/dev/cloud-session-setup.sh || true
```

Do this only if the clone exists at that point; otherwise keep running the
script by hand.

## Step 3: Check the result

```bash
.venv/bin/spec-kitty --version   # CLI installed from the checkout
make test-fast                   # test package and pytest-xdist work
codegraph status                 # index state
tail /tmp/codegraph-init.log     # progress of a background index build
```

## Troubleshooting

- **CodeGraph tools are missing in a new session.** Run
  `codegraph install --print-config claude` and add the printed configuration
  by hand.
- **Imports fail for a package that is declared and pinned.** The virtual
  environment is stale. Run `uv sync --frozen --all-extras` again.
- **The environment setup script fails.** Fix it in the environment settings
  (Step 1). New sessions use the fixed script.

## See also

- [Contributing to Spec Kitty](../contributing.md)
- [Local overrides for cross-package development](local-overrides.md)
- [How-to index](index.md)
