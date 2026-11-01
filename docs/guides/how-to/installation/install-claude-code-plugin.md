---
title: How to Install the Spec Kitty Claude Code Plugin
description: How to install Spec Kitty as a native Claude Code plugin that surfaces canonical mission commands and built-in agent profiles.
doc_status: active
updated: '2026-06-20T00:00:00Z'
audience: docs/context/audience/external/project-owner.md
kind: How-To
---
# How to Install the Spec Kitty Claude Code Plugin

Spec Kitty ships as a native Claude Code plugin that surfaces all canonical
mission commands (`/spec-kitty.specify`, `/spec-kitty.plan`, etc.) and built-in
agent profiles directly inside Claude Code.

## Prerequisites

- Claude Code CLI v2.0.12 or later (`claude --version` to check).
- One of the following for runtime execution:
  - a `spec-kitty` on PATH from the same release series as the bundle (fastest), or
  - `uv` installed, so the wrapper can run the pinned version with `uvx --from`.

If you have neither, install the CLI:

```bash
uv tool install spec-kitty-cli
# or
pipx install spec-kitty-cli
```

---

## Option 1: Marketplace install (recommended)

```bash
# Add the Spec Kitty plugin from the git-based marketplace:
claude plugin marketplace add https://github.com/spec-kitty/spec-kitty

# Verify the plugin is listed:
claude plugin list
```

The marketplace entry points Claude Code at `dist/spec-kitty-plugins/claude-code/`
inside the repository, which contains the pre-built bundle.

---

## Option 2: Dev install (contributors and local builds)

```bash
# From the spec-kitty repository root, build the bundle:
spec-kitty plugin build --target claude-code

# Use the bundle for a single session:
claude --plugin-dir dist/spec-kitty-plugins/claude-code "<your prompt>"

# Or install persistently:
claude plugin install dist/spec-kitty-plugins/claude-code
```

For build system details, see [CONTRIBUTING.md](../../../development/contributing.md).

---

## Troubleshooting

**Plugin agents not appearing in `/agents`**

1. Verify the install: `claude plugin list` — the plugin should appear as `spec-kitty`.
2. If it does not appear, try reinstalling:
   ```bash
   claude plugin uninstall spec-kitty
   claude plugin install dist/spec-kitty-plugins/claude-code
   ```

**"No usable spec-kitty found" error**

The runtime wrapper could not find a CLI it may run. The message names the
release series the bundle was built for. Either install that series:

```bash
uv tool install spec-kitty-cli
# or
pipx install spec-kitty-cli
```

or install `uv` so the wrapper can run the pinned version on demand:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**A `spec-kitty` from another series is ignored**

Delegation to a PATH CLI is gated on `spec-kitty --version` naming the bundle's
release series. A shim, wrapper or alias that installs a `spec-kitty` but prints
no version on `--version` is treated as unusable and the pinned version runs
instead, so a broken shim never silently becomes the plugin's runtime. Run
`spec-kitty --version` yourself if the plugin seems to ignore your install.

**Windows: argument forwarding with quoted strings**

The Windows CMD wrapper (`bin/spec-kitty-wrapper.cmd`) uses `%*` for argument
forwarding, which may mishandle complex quoted arguments. If you encounter
quoting issues on Windows, invoke `spec-kitty` directly instead of going through
the wrapper.

---

## How the runtime wrapper works

When Claude Code executes a Spec Kitty skill, it calls
`bin/spec-kitty-wrapper` (bash) or `bin/spec-kitty-wrapper.cmd` (Windows).
The wrapper resolves a runtime in this order:

1. **A `spec-kitty` on PATH inside the bundle's release series.** The wrapper
   reads `spec-kitty --version` and delegates only when its `<major>.<minor>`
   matches the version the bundle was built from. A CLI from another series is
   ignored rather than run against commands and skills it does not match; an
   unreachable or unreadable one falls through the same way.
2. **The pinned version through `uvx`.**
   `uvx --from "spec-kitty-cli==<version>" spec-kitty …` names both the
   distribution and the executable it ships. (The plain form
   `uvx spec-kitty-cli==<version>` cannot work: `uvx` runs an executable named
   after the distribution, and this distribution ships `spec-kitty`.)
3. **The bundle's series through `uvx`.** If the exact version is not published
   (a bundle built from a pre-release or a local build), the wrapper retries with
   `spec-kitty-cli>=<version>,<<next minor>`, so the newest published release of
   the same series runs.
4. **Exit 1** with a remedy naming `uv tool install` / `pipx install`.

The version string is substituted at build time by `spec-kitty plugin build`.
`uvx` resolves and caches the package on first use, so the fallback needs network
access once per version.
