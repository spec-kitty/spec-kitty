---
title: Set Up a Claude Code Cloud Session
description: Prepare a Claude Code cloud session so the Spec Kitty CLI, the test package and CodeGraph are ready before you run a Mission or an Op.
doc_status: active
kind: How-To
updated: '2026-11-14T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
---
# Set Up a Claude Code Cloud Session

This page is for maintainers and contributors who run Spec Kitty Missions or
Ops in a Claude Code cloud session. When you finish, the session has the
`spec-kitty` CLI installed from your checkout, the test dependencies synced, and
the pinned packs in place, and a CodeGraph index ready to query.

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

### Optional: resolve Maven Central through a mirror

Use this when the environment also builds the Java repositories
(`spec-kitty-charter`, `spec-kitty-events`) with Gradle. Maven Central
rate-limits by address (HTTP 429), and the sessions of one environment share an
address, so Gradle builds stall or cache false 404s. Google's mirror serves the
same artifacts. Append this to the environment setup script:

```bash
mkdir -p ~/.gradle/init.d
cat > ~/.gradle/init.d/central-mirror.gradle <<'EOF'
def mirror = 'https://maven-central.storage-download.googleapis.com/maven2/'
def centralHosts = ['repo.maven.apache.org', 'repo1.maven.org']
def useMirror = { RepositoryHandler repos ->
    repos.withType(MavenArtifactRepository).configureEach { r ->
        if (r.url?.host in centralHosts) { r.url = mirror }
    }
    if (repos.findByName('CentralMirror') == null) {
        def m = repos.maven { url = mirror; name = 'CentralMirror' }
        repos.remove(m)
        repos.addFirst(m)
    }
}
beforeSettings { settings ->
    useMirror(settings.pluginManagement.repositories)
    settings.pluginManagement.repositories.gradlePluginPortal()
}
settingsEvaluated { settings ->
    useMirror(settings.pluginManagement.repositories)
    if (!settings.dependencyResolutionManagement.repositories.isEmpty()) {
        useMirror(settings.dependencyResolutionManagement.repositories)
    }
}
allprojects {
    afterEvaluate {
        if (!buildscript.repositories.isEmpty()) { useMirror(buildscript.repositories) }
        if (!repositories.isEmpty()) { useMirror(repositories) }
    }
}
EOF
```

- Allow `maven-central.storage-download.googleapis.com` in the environment's
  network settings.
- The init script lives in `~/.gradle/init.d/`, outside every repository, so it
  changes no tracked file. The builds' strict SHA-256 dependency verification
  still checks every artifact.
- The mirror goes first in every repository list. Rewriting Central's URL alone
  is not enough: `gradlePluginPortal()` redirects Central artifacts to
  `repo.maven.apache.org` on its own server.
- Declaring a plugin repository drops the implicit plugin portal, so the script
  adds it back.
- Put it in the environment setup script, not in a session. A session that
  writes this script itself can be refused by its permission classifier; the
  environment script is the sanctioned place.

The same procedure is in `spec-kitty-charter`'s
`docs/development/cloud-session-setup.md`. Verified on 2026-11-14: the charter
`:kernel:compileJava` build resolved through the mirror with no 429.

### Optional: install the CLI when core is not attached

A session that works on another repository (`spec-kitty-charter`,
`spec-kitty-events`, `spec-kitty-open-packs`) has no core checkout to install
the CLI from. Append this to the environment setup script so those sessions get
the CLI from current `main`:

```bash
export PATH="$HOME/.local/bin:$PATH"
SK_SRC=./spec-kitty
if [ ! -d spec-kitty ]; then
  SK_SRC=/opt/spec-kitty
  if [ -d "$SK_SRC/.git" ]; then
    git -C "$SK_SRC" pull --ff-only -q || true
  else
    git clone -q https://github.com/spec-kitty/spec-kitty "$SK_SRC" || echo "note: clone failed"
  fi
  (cd "$SK_SRC" && make sync-packs >/dev/null 2>&1) || echo "note: packs sync failed"
fi
if [ -d "$SK_SRC" ]; then
  uv tool install --force --editable "$SK_SRC" >/dev/null 2>&1 || echo "note: CLI install failed"
fi
```

- The editable install from `/opt/spec-kitty` tracks that checkout, so the
  session has the CLI from `main` as of container build.
- A running session that needs a newer CLI runs
  `git -C /opt/spec-kitty pull --ff-only`. A permission classifier can refuse
  that pull in an auto-mode session; then the session keeps the build-time CLI
  until a fresh container is built.
- A session must not install the CLI itself (for example `uv tool install`
  from a fresh clone): a permission classifier refuses that as code from an
  external source. The environment setup script is the place for it.

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
- syncs the pinned packs, as `make sync-packs` does, so `packs/built-in` and
  `packs/internal` are in place before any `spec-kitty` command runs. Without
  them a command fails with `BuiltInPackMissing` or reports a charter context
  error. It first checks the placed trees offline and fetches only when one is
  missing or stale. A failed fetch stops the script;
- fetches the pinned service extras, as `make sync-services ARGS=--extras-only`
  (part of `make dev-setup`) does. The contract and conformance tests read them
  and fail without them. The CLI does not need them, so a failure here prints a
  note and the script goes on;
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

When everything is already in place, the script finishes in a few seconds
(about 3 seconds measured, with the pack check and the cached service extras).

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
uv run --frozen python scripts/sync_packs.py --check   # packs in place: "built-in: ok", "internal: ok"
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
- [How-to index](README.md)
