---
title: Set up Post-Edit Lint Hooks
description: Configure your AI agent harness to automatically run ruff and mypy after every code edit using spec-kitty lint.
doc_status: active
updated: '2026-09-28'
type: how-to
audience: docs/context/audience/external/project-owner.md
---
# Set up Post-Edit Lint Hooks

One of the most effective ways to reduce review cycles is to catch linting and type errors at the **cheapest point**: immediately after the AI agent makes a change.

Spec Kitty provides a universal wrapper command, `spec-kitty lint`, designed specifically for this purpose. When configured as a "post-edit hook," it feeds violations back to the agent in the same turn, allowing it to self-correct.

## 1. The Universal Wrapper

The `spec-kitty lint <file_path>` command:
- Runs `ruff check` (linting).
- Runs `mypy --strict` (type-checking).
- Summarizes errors in an agent-friendly format.
- Exits with `1` if errors are found, triggering the agent's auto-fix logic.

**Two invocation forms.** When you pass a path explicitly (`spec-kitty lint path/to/file.py`) it lints that file. When you omit the path (`spec-kitty lint --json`, the form wired into harness hooks below) it reads the edited file from the harness's JSON payload on **stdin** — Claude Code delivers `tool_input.file_path`, Cursor delivers `file_path`. A hook that fires without a Python file to lint (for example after a non-edit tool call) is a harmless no-op, never an error that blocks the agent.

## 2. Managed setup (recommended)

Rather than hand-editing harness config, let Spec Kitty manage the hooks for the agents in your `.kittify/config.yaml`:

```bash
spec-kitty agent config set lint_on_edit true
spec-kitty agent config sync --sync-hooks
```

This writes the Claude Code (`PostToolUse`) and Cursor (`afterFileEdit`) hook entries below for every configured agent, idempotently and without disturbing your other hooks/settings. Set `lint_on_edit false` and re-sync to remove them. Only agents listed in `config.yaml` are touched.

## 3. Configuration by Harness (manual)

### Claude Code
Claude Code supports `PostToolUse` hooks in `.claude/settings.json`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "spec-kitty lint --json"
          }
        ]
      }
    ]
  }
}
```

### Aider
Aider supports the `--lint-cmd` flag. You can set this in your `.aider.conf.yml` or pass it at startup.

```bash
aider --lint-cmd "spec-kitty lint"
```

### Cursor
Cursor (v1.7+) supports hooks in `.cursor/hooks.json`.

```json
{
  "version": 1,
  "hooks": {
    "afterFileEdit": [
      {
        "command": "spec-kitty lint --json"
      }
    ]
  }
}
```

### Windsurf
Windsurf has no programmatic post-edit hook, so `--sync-hooks` does not manage it. Configure it manually by adding a natural-language rule to your `.windsurfrules` file:

```markdown
# Linting Guardrail
After every file edit, you MUST run `spec-kitty lint <file_path>` and fix any reported errors immediately.
```

## Troubleshooting

### "`.claude/settings.json` is not valid UTF-8"

`spec-kitty agent config sync --sync-hooks` and `spec-kitty live-work install` decode `.claude/settings.json` before merging in the lint/session hooks. They only decode an encoding they can *prove*: plain UTF-8, or a byte-order mark (BOM) for UTF-8, UTF-16, or UTF-32. If the file was saved in a single-byte code page (for example, Windows ANSI/cp1252 — common when an editor auto-saves non-ASCII values such as `"OWNER": "José"` without a BOM), the command refuses rather than guessing:

- The file is left **byte-identical** — nothing is written.
- The command exits non-zero and names the file plus the fix: re-save it as UTF-8.

**Fix:** open `.claude/settings.json` in your editor and re-save it with UTF-8 encoding (no BOM required, though a UTF-8/UTF-16/UTF-32 BOM is also accepted), then re-run the sync/install command.

If the file *is* a provable non-UTF-8 encoding (BOM'd UTF-16 or UTF-32), the command decodes it, merges in the hook entries, and — before rewriting it as UTF-8 — makes a byte-exact backup sidecar next to the original, named `settings.json.<timestamp>`. Your original bytes are never lost even when the encoding changes.

## 4. Advanced Usage

### Auto-Fixing
You can instruct `spec-kitty lint` to attempt to fix errors automatically (via `ruff --fix`) by adding the `--fix` flag:

```bash
spec-kitty lint <file_path> --fix
```

### JSON Output
For tools that can parse structured feedback, use the `--json` flag to get a machine-readable error report:

```bash
spec-kitty lint <file_path> --json
```

## Why use hooks?

1. **Faster Merges:** Code arrives at the review gate already clean and type-safe.
2. **Lower Costs:** Fewer turns spent on trivial "unused import" or "missing type hint" fixes.
3. **Better Quality:** Enforces project standards (like `mypy --strict`) automatically.
