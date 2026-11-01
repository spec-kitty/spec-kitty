---
title: How to Install the Spec Kitty Claude Code Plugin
description: How to install Spec Kitty as a native Claude Code plugin that surfaces canonical mission commands and built-in agent profiles.
doc_status: active
updated: '2026-10-31'
audience: docs/context/audience/external/project-owner.md
type: how-to
---
# How to Install the Spec Kitty Claude Code Plugin

Spec Kitty ships as a native Claude Code plugin that surfaces all canonical
mission commands (`/spec-kitty.specify`, `/spec-kitty.plan`, etc.) and built-in
agent profiles directly inside Claude Code.

## Prerequisites

- Claude Code CLI v2.0.12 or later (`claude --version` to check).
- `spec-kitty` on PATH: the bundled skills invoke the `spec-kitty` console
  script directly, so install the CLI before you use the plugin
  (`uv tool install spec-kitty-cli`, `pipx install spec-kitty-cli` or
  `pip install spec-kitty-cli`).

---

## Install the bundle

```bash
# From the spec-kitty repository root, build the bundle:
spec-kitty plugin build --target claude-code

# Use the bundle for a single session:
claude --plugin-dir dist/spec-kitty-plugins/claude-code "<your prompt>"

# Or install persistently:
claude plugin install dist/spec-kitty-plugins/claude-code
```

The bundle contains command skills under `skills/`, agent profiles under
`agents/`, `hooks/hooks.json` and the manifest at
`.claude-plugin/plugin.json`. It deliberately ships **no** top-level `bin/`:
Claude.ai and Cowork refuse to install a plugin that has one, and no bundled
skill needs it.

For build system details, see [CONTRIBUTING.md](../../../development/contributing.md).

> **Marketplace install is not available yet.** `dist/` is a build output and is
> not committed, so `claude plugin marketplace add spec-kitty/spec-kitty` cannot
> resolve the bundle until the catalog points at a hosted location. Use the
> build-and-install path above.

---

## Troubleshooting

**Plugin agents not appearing in `/agents`**

1. Verify the install: `claude plugin list` — the plugin should appear as `spec-kitty`.
2. If it does not appear, try reinstalling:
   ```bash
   claude plugin uninstall spec-kitty
   claude plugin install dist/spec-kitty-plugins/claude-code
   ```

**A skill fails with "spec-kitty: command not found"**

The skills call the `spec-kitty` console script; the plugin does not bundle a
runtime. Install the CLI and confirm `spec-kitty --version` works in the same
shell Claude Code uses.
