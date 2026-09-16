---
title: How to Install the Spec Kitty Claude Code Plugin
description: How to install Spec Kitty as a native Claude Code plugin that surfaces canonical mission commands and built-in agent profiles.
doc_status: active
updated: '2026-06-20'
audience: docs/context/audience/external/project-owner.md
type: how-to
---
# How to Install the Spec Kitty Claude Code Plugin

Spec Kitty ships as a native Claude Code plugin that surfaces all canonical
mission commands (`/spec-kitty.specify`, `/spec-kitty.plan`, etc.) and built-in
agent profiles directly inside Claude Code.

## Prerequisites

- Claude Code CLI v2.0.12 or later (`claude --version` to check).
- One of the following for runtime execution:
  - `spec-kitty` on PATH (fastest), or
  - `uv` installed (the wrapper falls back to `uvx spec-kitty-cli==<version>`).

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

**"wrapper: uvx not found" error**

The runtime wrapper falls back to `uvx` when `spec-kitty` is not on PATH.
Install `uv` to enable the fallback:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or install `spec-kitty` directly to skip the fallback altogether:

```bash
pip install spec-kitty-cli
```

**Windows: argument forwarding with quoted strings**

The Windows CMD wrapper (`bin/spec-kitty-wrapper.cmd`) uses `%*` for argument
forwarding, which may mishandle complex quoted arguments. If you encounter
quoting issues on Windows, invoke `spec-kitty` directly instead of going through
the wrapper.

---

## How the runtime wrapper works

When Claude Code executes a Spec Kitty skill, it calls
`bin/spec-kitty-wrapper` (bash) or `bin/spec-kitty-wrapper.cmd` (Windows).
The wrapper:

1. Checks if `spec-kitty` is on PATH and `spec-kitty --version` succeeds →
   delegates directly.
2. Falls back to `uvx spec-kitty-cli==<version>` if `uvx` is available.
3. Exits with an error message if neither is found.

The version string is substituted at build time by `spec-kitty plugin build`.
