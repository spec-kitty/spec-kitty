---
title: Set Up a Claude Code Cloud Session
description: Prepare a Claude Code cloud session so the Spec Kitty CLI, the test package and CodeGraph are ready before you run a Mission or an Op.
doc_status: active
updated: '2026-10-09'
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
if it is missing. New sessions pick up the change. If your environment clones the
repository before this script runs, you can also fold the per-session Step 2 work
in here — see
[Optional: run the repository script from the environment setup script](#optional-run-the-repository-script-from-the-environment-setup-script).

The `codegraph install` line has not been tested end to end, so it ends in
`|| true`: a failure there does not stop the container build. If the CodeGraph
tools are missing later, see [Troubleshooting](#troubleshooting).

### Optional: environment variables

In the same environment settings, under **Environment variables**, you can set:

```
PWHEADLESS=1
CODEGRAPH_TELEMETRY=0
SPEC_KITTY_NO_NAG=1
SPEC_KITTY_NO_UPGRADE_CHECK=1
```

- `PWHEADLESS=1` runs Playwright tests headless.
- `CODEGRAPH_TELEMETRY=0` turns off CodeGraph usage reporting.
- `SPEC_KITTY_NO_NAG=1` hides the "newer version on PyPI" banner. The CLI
  comes from your checkout, so the banner does not apply.
- `SPEC_KITTY_NO_UPGRADE_CHECK=1` skips the PyPI version check and its network
  call.

The repository script also sets the first two for each session. Setting them
here makes them hold even when nobody runs the script.

Do not set these:

- `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`: it bypasses a governance gate.
- `SPEC_KITTY_RUN_P0_REPRO` or `SPEC_KITTY_RUN_QUARANTINE`: they add test
  suites that are expected to fail.
- `SPEC_KITTY_ENABLE_SAAS_SYNC`: it is left over from the retired sync
  transport and does nothing.

#### What `SPEC_KITTY_NON_INTERACTIVE` does

This page does not recommend a value for `SPEC_KITTY_NON_INTERACTIVE`. It
controls whether spec-kitty may stop and wait for a person to answer a prompt,
such as a confirmation or an interview question. The CLI decides in this order
(`is_interactive()` in `src/specify_cli/core/env.py`):

1. `SPEC_KITTY_FORCE_INTERACTIVE` set to a true value: prompts are allowed.
2. `SPEC_KITTY_NON_INTERACTIVE` set to a true value: prompts are skipped.
3. Otherwise, prompts are allowed only when stdin is a terminal.

Setting `SPEC_KITTY_NON_INTERACTIVE=0` is the same as leaving it unset, so the
CLI falls through to the terminal check. Commands an agent runs in a cloud
session usually have no terminal on stdin, so prompts are skipped there either
way. Forcing prompts on with `SPEC_KITTY_FORCE_INTERACTIVE=1` in an agent
session can make a command wait forever, because nobody can type an answer.

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

### Optional: run the repository script from the environment setup script

If your cloud environment clones the repository *before* the environment setup
script runs, you can fold Step 2 into Step 1 and skip the per-session run. Append
this to the environment setup script (Step 1):

```bash
repo="${CLAUDE_PROJECT_DIR:-}"
if [ -n "$repo" ] && [ -d "$repo/.git" ]; then
  (cd "$repo" && bash scripts/dev/cloud-session-setup.sh) || true
fi
```

This is clone-order safe: when the checkout is not present yet (the common case,
where the environment setup script runs at container-build time, before the repo
lands), the guard makes it a no-op and you keep running the script by hand each
session. When the clone *is* present, it runs the repository script for you. The
trailing `|| true` keeps a failure from breaking the container build.

The repository script is itself idempotent and gated on `CLAUDE_CODE_REMOTE`, so
appending this line never does harm — the worst case is that it no-ops.

### Why this is not a committed SessionStart hook

Spec Kitty writes its own hooks into `.claude/settings.json`. If that file were
tracked with a setup hook in it, every checkout would become dirty. Running the
script by hand (or wiring it in as above) keeps the tree clean.

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
