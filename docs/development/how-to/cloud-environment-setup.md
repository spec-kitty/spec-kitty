---
title: Set Up a Claude Code Cloud Environment for Spec Kitty
description: Configure the cloud environment that Claude Code cloud sessions run in for Spec Kitty work, covering network hosts, variables, the setup script, validation and the GitHub side.
doc_status: active
kind: How-To
updated: '2026-11-20T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
related:
- development/how-to/cloud-session-setup
- development/multi-session-orchestration
- development/how-to/run-a-multi-session-orchestration
---
# Set Up a Claude Code Cloud Environment for Spec Kitty

This page is for maintainers who run Spec Kitty work in Claude Code cloud
sessions. A cloud **environment** is the saved setup that every session started
in it shares: its network rules, its environment variables and a setup script
that runs when a container is built. When you finish, a new session in the
environment has:

- Java 25 for the service repositories;
- Gradle resolving Maven Central through a mirror;
- the core checkout warmed up;
- the `spec-kitty` CLI installed from source;
- a summary of all of the above at the top of the setup log.

The per-session steps (the repository script, the CodeGraph index) are on
[Set up a Claude Code cloud session](cloud-session-setup.md). This page covers
the layer underneath them.

## Before you start

- A claude.ai account with Claude Code cloud sessions.
- The repositories you work on: core (`spec-kitty/spec-kitty`) and, as needed,
  `spec-kitty-events`, `spec-kitty-charter`, `spec-kitty-open-packs` and
  `doc-kitty`.

## Step 1: Set the network access

In the environment's settings, choose **limited** network access, and allow
both **package managers** and **MCP servers**. The package-manager switch opens
the common registries (PyPI, npm and others) without listing them. The
MCP-server switch opens the hosts of the MCP servers a session has configured.

Then add these allowed hosts. Hosts must be exact names: wildcards such as
`*.example.com` are not accepted, so a host family is listed one name at a
time.

| Purpose | Hosts |
|---------|-------|
| JDK download (Temurin release on GitHub) | `api.adoptium.net`, `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com` |
| Gradle distribution and plugins | `services.gradle.org`, `downloads.gradle.org`, `plugins.gradle.org`, `plugins-artifacts.gradle.org` |
| Maven Central and its mirror | `repo.maven.apache.org`, `repo1.maven.org`, `maven-central.storage-download.googleapis.com` |
| Spec Kitty docsite | `docs.spec-kitty.ai`, `spec-kitty.github.io` |
| SonarCloud reports (`scripts/ci/sonarcloud_branch_review.sh`) | `sonarcloud.io` |
| GitHub Actions logs and artifacts | `productionresultssa0.blob.core.windows.net` to `productionresultssa4.blob.core.windows.net`, plus `productionresultssa18`, `productionresultssa31` and `productionresultssa32` on the same domain |
| Sigstore trust root for `gh attestation verify` (service pin provenance) | `tuf-repo-cdn.sigstore.dev`, `tuf-repo.github.com` |
| Your own domains, if any | as needed |

Notes:

- GitHub serves Actions logs and artifacts from numbered storage shards. A new
  shard number shows up as a refused host the first time a session reads a log
  stored there. Add that exact name when it happens.
- The proxy refuses any host that is not on the list. A research session that
  needs other sites either gets those hosts added or marks each external claim
  as verified or unverified.

## Step 2: Set the environment variables

Under **Environment variables**, set:

```
CODEGRAPH_TELEMETRY=0
JAVA_HOME=/usr/lib/jvm/temurin-25
PWHEADLESS=1
SPEC_KITTY_NO_NAG=1
SPEC_KITTY_NO_UPGRADE_CHECK=1
```

- `CODEGRAPH_TELEMETRY=0` turns off CodeGraph usage reporting.
- `JAVA_HOME` points at the JDK the setup script installs (Step 3).
- `PWHEADLESS=1` runs Playwright tests headless.
- `SPEC_KITTY_NO_NAG=1` hides the "newer version on PyPI" banner. The CLI comes
  from a source checkout, so the banner does not apply.
- `SPEC_KITTY_NO_UPGRADE_CHECK=1` skips the PyPI version check and its network
  call.

Variables are stored in plain text and shown to anyone who can edit the
environment. Never put a key or token in one. A credential for a host goes in
the environment's **network secrets**: the proxy adds it to requests to that
host. For example, a read token for `npm.pkg.github.com` lets sessions install
GitHub Packages.

The variables to avoid, and what `SPEC_KITTY_NON_INTERACTIVE` does, are listed
on [Set up a Claude Code cloud session](cloud-session-setup.md#optional-environment-variables).

## Step 3: Add the setup script

Under **Setup script**, paste the script below. It runs as root each time a
container is built for a new session. It runs after the session's repositories
are cloned and before Claude starts, from the directory that holds the
checkouts (so core is at `./spec-kitty`).

```bash
#!/bin/bash
set -euo pipefail
START_DIR="$PWD"
npm install -g @colbymchenry/codegraph@1.6.2
codegraph install --yes --target claude --location global || true
command -v uv >/dev/null || curl -LsSf --retry 5 --retry-all-errors https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Java 25: the Temurin release spec-kitty-events pins (scripts/ensure_jdk25.sh); bump together.
JDK_DIR=/usr/lib/jvm/temurin-25
JDK_TAR=OpenJDK25U-jdk_x64_linux_hotspot_25.0.5_8.tar.gz
JDK_SHA=68982529869257d0ee6b824ec5aa270ff8b118bb438670da0b97ebdab178d7fb
if [ ! -x "$JDK_DIR/bin/java" ]; then
  tmp=$(mktemp -d)
  curl -fsSL --retry 5 --retry-all-errors --retry-delay 3 -o "$tmp/jdk.tar.gz" \
    "https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.5%2B8/$JDK_TAR"
  echo "$JDK_SHA  $tmp/jdk.tar.gz" | sha256sum -c -
  mkdir -p "$JDK_DIR" && tar -xzf "$tmp/jdk.tar.gz" -C "$JDK_DIR" --strip-components=1
  rm -rf "$tmp"
fi
# Make it the default java, so tools that use PATH (not JAVA_HOME) get 25 too.
for b in java javac jar; do ln -sf "$JDK_DIR/bin/$b" /usr/local/bin/$b; done
java -version

# Maven Central mirror (avoids HTTP 429)
mkdir -p ~/.gradle/init.d
cat > ~/.gradle/init.d/central-mirror.gradle <<'EOF'
// Resolve Maven Central through Google's mirror (same artifacts) to avoid Central's per-address HTTP 429.
// The build's strict SHA-256 dependency verification still checks every artifact.
// Plugin resolution keeps the build's own repository order (e.g. gradlePluginPortal first): only Central
// URLs there are rewritten, so plugin-marker POMs come from where the verification metadata expects.
def mirror = 'https://maven-central.storage-download.googleapis.com/maven2/'
def centralHosts = ['repo.maven.apache.org', 'repo1.maven.org']
def rewrite = { RepositoryHandler repos ->
    repos.withType(MavenArtifactRepository).configureEach { r ->
        if (r.url?.host in centralHosts) { r.url = mirror }
    }
}
def useMirror = { RepositoryHandler repos ->
    rewrite(repos)
    if (repos.findByName('CentralMirror') == null) {
        def m = repos.maven { url = mirror; name = 'CentralMirror' }
        repos.remove(m)
        repos.addFirst(m)
    }
}
settingsEvaluated { settings ->
    rewrite(settings.pluginManagement.repositories)
    if (!settings.dependencyResolutionManagement.repositories.isEmpty()) {
        useMirror(settings.dependencyResolutionManagement.repositories)
    }
}
allprojects {
    afterEvaluate {
        if (!buildscript.repositories.isEmpty()) { rewrite(buildscript.repositories) }
        if (!repositories.isEmpty()) { useMirror(repositories) }
    }
}
EOF

# Core checkout attached: sync deps, packs (per checkout) and pinned service assets. Non-fatal.
cd "$START_DIR"
if [ -f spec-kitty/Makefile ]; then
  (cd spec-kitty && uv sync --frozen --all-extras && make sync-packs && make sync-services) \
    || echo "note: spec-kitty checkout warm-up failed (non-fatal)"
fi

# Spec Kitty CLI (editable): from the attached core checkout, else a clone of core main in /opt.
SK_SRC="$START_DIR/spec-kitty"
if [ ! -f "$SK_SRC/pyproject.toml" ]; then
  SK_SRC=/opt/spec-kitty
  if [ -d "$SK_SRC/.git" ]; then
    git -C "$SK_SRC" pull --ff-only -q || true
  else
    git clone -q --depth 1 https://github.com/spec-kitty/spec-kitty "$SK_SRC" || echo "note: spec-kitty clone failed"
  fi
  (cd "$SK_SRC" && uv sync --frozen --all-extras && make sync-packs) || echo "note: /opt spec-kitty warm-up failed"
fi
if [ -f "$SK_SRC/pyproject.toml" ]; then
  uv tool install --force --editable "$SK_SRC" || echo "note: spec-kitty CLI install failed"
fi

# Environment summary (informational; never fails setup).
echo "=== environment summary ==="
{
  echo "java:       $(java -version 2>&1 | grep -m1 version)"
  echo "node/pnpm:  $(node -v 2>/dev/null) / $(pnpm -v 2>/dev/null)"
  echo "uv/python:  $(uv --version 2>/dev/null) / $(python3 --version 2>/dev/null)"
  echo "codegraph:  $(codegraph --version 2>/dev/null || echo n/a)"
  echo "spec-kitty: $(spec-kitty --version 2>/dev/null || echo 'not installed')"
  for r in spec-kitty spec-kitty-events spec-kitty-charter spec-kitty-open-packs doc-kitty; do
    [ -d "$START_DIR/$r/.git" ] && echo "repo $r: $(git -C "$START_DIR/$r" rev-parse --abbrev-ref HEAD) @ $(git -C "$START_DIR/$r" log -1 --format='%h %cs')"
  done
} || true
echo "==========================="
```

### What each part does

**Tools.** The first lines install CodeGraph at a pinned version, register it
with Claude Code (`|| true`: a failure there must not stop the build), and
install `uv` if the image lacks it. `START_DIR` remembers the checkout
directory, because later steps change directory.

**Pinned Temurin JDK 25.** The service repositories build with Java 25. The
script downloads the exact Temurin release that `spec-kitty-events` pins in its
`scripts/ensure_jdk25.sh`, so change the two together.

- `sha256sum -c` checks the archive against the pinned digest. Under
  `set -euo pipefail` a mismatch stops the build, so a changed or truncated
  download is never installed.
- The `if [ ! -x ... ]` guard skips the download when the JDK is already there.
- The `ln -sf` loop links `java`, `javac` and `jar` into `/usr/local/bin`.
  `JAVA_HOME` (Step 2) covers Gradle, but some tools find Java on `PATH` only,
  and the image may carry an older default Java.

**Gradle Maven-Central mirror.** Maven Central rate-limits by address
(HTTP 429). All sessions in an environment share an address, so parallel
Gradle builds stall or cache false 404s. The init script in
`~/.gradle/init.d/` sends Central requests to Google's mirror, which serves the
same artifacts. It lives outside every repository, so no tracked file changes,
and the builds' strict SHA-256 dependency verification still checks every
artifact.

- **Dependency repositories** (`dependencyResolutionManagement`, and each
  project's `repositories`) get both treatments, through `useMirror`. Central
  URLs are rewritten, and a `CentralMirror` repository goes first.
- **Plugin repositories** (`pluginManagement`, and each project's
  `buildscript`) get the URL rewrite only, through `rewrite`. Their order stays
  as the build declares it, normally `gradlePluginPortal()` first. The build's
  dependency-verification metadata records where each plugin-marker POM came
  from. Putting the mirror in front of the portal would fetch those POMs from
  elsewhere and fail verification.

**Core warm-up.** When core is attached, the script runs three steps in the
checkout:

- `uv sync --frozen --all-extras` installs the dev and test extras.
- `make sync-packs` fetches the pinned `packs/built-in` and `packs/internal`
  trees. Without them a command fails with `BuiltInPackMissing`.
- `make sync-services` fetches the pinned service assets.

The step is non-fatal: a failure prints a note and the build goes on, so a
broken pin does not lock you out of the session that fixes it.

**Editable CLI install.** `uv tool install --force --editable` installs
`spec-kitty` from the attached core checkout, so the CLI follows your branch.
A session that works on another repository has no core checkout. For it the
script keeps a clone of core `main` in `/opt/spec-kitty`, pulled on each
build, synced, and installed the same way. Install the CLI here, not from a
session: a session's permission classifier can refuse installing code from an
external source.

**Summary block.** The setup script's output is not kept anywhere a session can
read later. The summary prints the tool versions and, for each repository
present, its branch and last commit. A failure inside it (`|| true`) never
fails setup.

## Step 4: Check a change with a fresh session

The setup script runs only when a container is built fresh. Saving a change
does not rerun it in sessions that already exist. To check a change:

1. Start a new session in the environment, with core attached.
2. Give it a short read-only brief: report `java -version`, `which java`,
   `spec-kitty --version`, `ls ~/.gradle/init.d`, the variables from Step 2, and
   `uv run --frozen python scripts/sync_packs.py --check` in core. Tell it to
   change nothing and to stop after reporting.
3. Compare the report with what the script should produce. Archive the session
   when you are done.

## Step 5: Connect GitHub

- **Connector.** Connect your GitHub account to claude.ai. Sessions reach
  GitHub through the GitHub MCP tools; `gh` in a cloud session is limited to
  search.
- **Claude GitHub App.** Install the app on each repository a session reads or
  writes, or ask an owner of the repository's organization to install it.
  Without it, a clone or push to that repository is refused.
- **Repositories on the session.** A session works only on the repositories
  attached to it. Name the repository a session writes to when you start it.
  An `add_repo` call from inside a session can be refused for a repository the
  brief did not name; see
  [Repository access is per session](../multi-session-orchestration.md#repository-access-is-per-session).

## Known limits

- **One edit call carries at most 4,096 bytes**, unless it changes only the
  setup script or only the variables. When an edit to the environment through
  the session tools is refused for size, send the script, the variables and the
  hosts in separate calls.
- **The setup script runs only on a fresh container.** Use Step 4 to check a
  change.
- **Setup output is not kept.** Make the summary block print what you need to
  know.
- **Hosts are exact names.** No wildcards, IP addresses or internal-only names.
- **No secrets in variables or the script.** Both are plain text; use network
  secrets.
- **`gh` is limited to search** in a cloud session. Use the GitHub MCP tools
  for issues, pull requests and comments.
- **`gh attestation verify` needs the Sigstore hosts** from Step 1. Without
  them it cannot load the trust root, and the service pin provenance check
  fails.

## See also

- [Set up a Claude Code cloud session](cloud-session-setup.md): the per-session repository script.
- [Multi-session orchestration](../multi-session-orchestration.md): the sessions that share this environment.
- [How to sync and bump the built-in and internal packs](sync-packs.md)
- [How-to index](README.md)
