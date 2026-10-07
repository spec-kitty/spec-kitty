---
title: spec-kitty upgrade lifecycle
description: Reference for the spec-kitty upgrade command lifecycle. Understand the project schema check, CLI migrations, and agent command synchronization.
doc_status: active
updated: '2026-06-09'
type: reference
related:
- docs/api/cli-commands.md
- docs/api/environment-variables.md
- docs/api/init-lifecycle.md
audience: end-users
---
# `spec-kitty upgrade` lifecycle

Reference description of what `spec-kitty upgrade` modifies, in what order, and how its options interact. For task-oriented walkthroughs see [Upgrade the CLI](../guides/how-to/installation/upgrade-cli.md) and [Upgrade a project](../guides/how-to/installation/upgrade-project.md).

## Two upgrade scopes

Spec Kitty has two distinct upgrade concepts:

| Scope | What it changes | How |
|---|---|---|
| **CLI** | The `spec-kitty-cli` Python package on PATH. | `pipx upgrade spec-kitty-cli`, `uv tool upgrade spec-kitty-cli`, or `pip install --upgrade spec-kitty-cli`. |
| **Project** | One project's `.kittify/` + agent surfaces, to match the schema the installed CLI expects. | `spec-kitty upgrade` inside the project root. |

The CLI never silently upgrades a project. Projects never silently upgrade the CLI.

## Synopsis

```text
spec-kitty upgrade [OPTIONS]
```

| Option | Description |
|---|---|
| `--cli` | Print CLI upgrade guidance only. Does not look for a project. Safe to run anywhere. |
| `--project` | Run project migrations only; suppress the CLI nag banner. Errors outside a project. |
| `--dry-run` | Show pending migrations without applying them. |
| `--yes` / `--force` | Non-interactive confirmation. Does **not** bypass schema-incompatibility blocks. |
| `--no-nag` | Suppress the upgrade-nag banner for this invocation only. |
| `--target <version>` | Migrate to a specific intermediate schema version (rare; debugging only). |
| `--json` | Emit a machine-readable plan / result. |
| `--plan-json` | Emit the complete preview-only owner plan. Never applies changes. |

`--cli` and `--project` together exit with code 2 (mutually exclusive).

## What gets modified

Project upgrade walks pending migrations in version order. For each migration, it may:

1. **Read `.kittify/config.yaml`** to learn which agents are configured. Migrations are *config-aware* and only touch directories for agents you have enabled.
2. **Refresh agent command directories** for configured agents (`.claude/commands/`, `.agents/skills/spec-kitty.*/`, `.amazonq/prompts/`, etc.) from the CLI's bundled source templates.
3. **Update `.kittify/` scaffold files** — `memory/`, `command-skills-manifest.json`, and config schemas — to the new layout.
4. **Bump `.kittify/metadata.yaml`** to record the new schema version after each migration step.
5. **Leave user data alone** — `kitty-specs/`, `architecture/`, `docs/`, `src/`, and anything else you author is untouched.

Migrations are idempotent: re-running `spec-kitty upgrade` is a no-op when the schema is current.

After migration selection, one guarded finalizer orders activation provisioning,
managed-surface repair, and the generated-churn commit. When hosted drain is on, upgrade
only reports TeamSpace mission-state blockers (last, never committed); it never
repairs. The repair runs only via `spec-kitty doctor mission-state --fix`.
Owner preconditions are rechecked immediately before writes; a changed input
requires reassessment rather than replaying stale prepared bytes.

## What does **not** get modified

- Git state: no commits, no stages, no branches.
- `kitty-specs/`: every mission directory, spec, plan, task file, and status event log is preserved.
- Agent directories that are not in `config.yaml`: if you removed `.gemini/` and never added `gemini` back to config, the migration will not recreate it.
- User-authored content under `architecture/`, `docs/`, `src/`, etc.
- Environment variables, PATH, shell config.

## Lazy compatibility gate

When the project schema does not match the installed CLI, commands like `spec-kitty next` and `spec-kitty implement` are blocked until you upgrade.

| Schema state | Exit code | Remediation |
|---|---|---|
| Up to date | 0 | None. |
| Project older than CLI | 4 | `spec-kitty upgrade` |
| Project newer than CLI | 5 | Upgrade the CLI (`pipx upgrade spec-kitty-cli`). `--yes` does **not** bypass this. |
| Metadata corrupt | 6 | Check `.kittify/metadata.yaml` exists and is valid YAML. |

Commands that are always allowed regardless of schema:

```bash
spec-kitty --help
spec-kitty --version
spec-kitty upgrade --dry-run   # always allowed
spec-kitty upgrade --cli       # always allowed
```

After the project schema is compatible, inspect the current Mission's work
packages with:

```bash
spec-kitty agent tasks status --mission <mission>
```

## When is a project upgrade required?

After a CLI upgrade, a project upgrade is required **only when migrations have rolled** since the project's recorded schema. Many patch releases roll no migrations and require no project upgrade.

Check ahead of time with:

```bash
spec-kitty upgrade --dry-run --json | jq '.pending_migrations'
```

An empty list means no project upgrade is needed.

## Reviewing generated changes

Project upgrades modify version-controlled files. Inspect with git before committing:

```bash
git status
git diff .kittify/ .claude/ .agents/skills/ .gemini/
```

Typical changes:

- New or updated files under each configured agent directory (templates refreshed).
- `.kittify/metadata.yaml` schema bump.
- Occasionally `.kittify/config.yaml` schema migrations.

Commit the result:

```bash
git add .kittify/ .claude/ .agents/skills/
git commit -m "chore: upgrade Spec Kitty project to <version>"
```

## Upgrade nag

When a newer CLI is available on PyPI, spec-kitty prints a single banner before normal output:

```
Spec Kitty 3.2.1 is available; you have 3.2.0.
Upgrade with: pipx upgrade spec-kitty-cli
```

Behaviour:

- Throttled to once per 24 hours by default.
- Configurable via `SPEC_KITTY_NAG_THROTTLE_SECONDS=<seconds>` or `~/.config/spec-kitty/upgrade.yaml` → `nag.throttle_seconds`.
- Disable per invocation with `--no-nag`; per session with `SPEC_KITTY_NO_NAG=1`.
- Automatically suppressed in CI (`CI=1`) and when stdout is not a TTY.
- Suppressing the nag never bypasses the compatibility gate — incompatible projects still exit 4 or 5.

## JSON output

`--json` returns a structured plan / result.

```bash
spec-kitty upgrade --dry-run --json | jq .case
# "project_migration_needed"

spec-kitty upgrade --dry-run --json | jq -r '.upgrade_hint.command'
# pipx upgrade spec-kitty-cli

spec-kitty upgrade --dry-run --json | jq '.pending_migrations | length'
# 0
```

Schema is stable across patch releases.

`--plan-json` uses
`kitty-specs/upgrade-preview-mission-health-01M1V6E1/contracts/upgrade-plan.schema.json`.
It retains the full envelope for refusals and exposes `complete`, diagnostics,
effects, dispositions, execution artifacts, and commit policy. The report is
informational, not an apply token. Legacy `--json` shapes remain unchanged.

## Examples

```bash
# Show CLI upgrade hint, anywhere
spec-kitty upgrade --cli

# Preview project migrations
spec-kitty upgrade --dry-run

# Apply project migrations non-interactively (CI)
spec-kitty upgrade --yes

# Project-only upgrade, no nag, JSON for tooling
spec-kitty upgrade --project --no-nag --json
```

## See also

- [Upgrade the CLI](../guides/how-to/installation/upgrade-cli.md)
- [Upgrade a project](../guides/how-to/installation/upgrade-project.md)
- [Init lifecycle](init-lifecycle.md)
- [Environment variables](environment-variables.md)
- [CLI commands](cli-commands.md)
