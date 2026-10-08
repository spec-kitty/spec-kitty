---
title: Upgrade an existing Spec Kitty project
description: Upgrade an existing project to the Spec Kitty 3.2 schema after installing the current CLI, with validation and recovery steps.
doc_status: active
updated: '2026-06-12'
type: how-to
related:
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/guides/how-to/installation/uninstall.md
- docs/guides/how-to/installation/upgrade-cli.md
audience: docs/context/audience/external/project-owner.md
---
# Upgrade an existing Spec Kitty project

After upgrading the CLI, existing projects may need a one-time migration to match the new schema. This page walks through the project upgrade flow.

> For upgrading the `spec-kitty` binary itself, see [Upgrade the CLI](upgrade-cli.md).

## When do I need this?

Run a project upgrade when:

- You just upgraded the CLI (`pipx upgrade spec-kitty-cli` or equivalent).
- A spec-kitty command exits with code **4** and says `This project needs Spec Kitty project migrations`.
- You opened an older project on a newer CLI for the first time.

If migrations are current, upgrade can still repair missing managed surfaces or
provision missing activation metadata. A second successful run is a no-op only
after those owners are current too.

## The upgrade flow

From the project root:

```bash
cd /path/to/your/project
spec-kitty upgrade
```

You will see a summary of pending migrations and be asked to confirm. To preview without applying anything:

```bash
spec-kitty upgrade --dry-run
```

To apply without prompting (useful in CI):

```bash
spec-kitty upgrade --yes
```

For machine-readable output:

```bash
spec-kitty upgrade --dry-run --json
```

That command preserves the legacy compatibility schema. For the complete,
preview-only owner plan use:

```bash
spec-kitty upgrade --plan-json
```

The full plan reports roots, exact physical effects, preserved dispositions,
diagnostics, apply-only temporary artifacts, and commit policy. It cannot be
replayed or used as consent. `--yes` and `--force` never make a preview write.

## What `spec-kitty upgrade` does

The project upgrade runs **config-aware migrations** that bring your `.kittify/` scaffold and agent surfaces in sync with the installed CLI. Specifically, it:

1. Reads `.kittify/config.yaml` to learn which agents you have configured.
2. Walks pending migrations in version order.
3. **Updates agent command directories** for configured agents only (`.claude/commands/`, `.agents/skills/spec-kitty.<command>/`, `.amazonq/prompts/`, etc.). Agents you removed stay removed — migrations never recreate them.
4. **Refreshes templates and skill packages** under those agent directories from the CLI's bundled source templates.
5. **Bumps `.kittify/metadata.yaml`** to record the new schema version.
6. **Leaves your data alone**: `kitty-specs/`, `architecture/`, and any other content you authored is not touched.

Migrations are idempotent — running `spec-kitty upgrade` twice on the same project is safe.

## Common follow-ups

After a successful project upgrade:

```bash
spec-kitty agent config sync   # Reconcile filesystem with config.yaml
spec-kitty doctor              # Health check
```

`agent config sync` is useful if you removed or added agents and want spec-kitty to ensure the filesystem matches your `config.yaml`. `doctor` surfaces any post-upgrade warnings.

## Reviewing the changes

Project upgrades modify tracked files (agent command directories, `metadata.yaml`, sometimes templates). Review before committing:

```bash
git status
git diff
```

`spec-kitty upgrade` commits the files it changed itself when `auto_commit` is enabled (the default), and only those files; your own uncommitted work is left alone. If it reports that its changes were left uncommitted (auto-commit disabled, a hook rejected the commit, or files held for manual review), commit when you are satisfied by staging the listed files by name:

```bash
git add -- .kittify/metadata.yaml <other files git status lists>
git commit -m "chore: upgrade Spec Kitty project to <version>"
```

Or use `spec-kitty safe-commit <those files> -m "chore: upgrade Spec Kitty project to <version>"`.

> Files under `kitty-specs/` are version-controlled and contain your mission history. Migrations should not touch them; if `git diff` shows changes there, stop and investigate.

## Exit codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0    | Success / nothing to do | Continue working. |
| 2    | Usage error (e.g. `--cli` with `--project`) | Fix command-line flags. |
| 4    | Project needs migration | Run `spec-kitty upgrade` (this command). |
| 5    | Project too new for CLI | Upgrade the CLI first (`pipx upgrade spec-kitty-cli`). |
| 6    | Project metadata corrupt | Check `.kittify/metadata.yaml` exists and is valid YAML. |

For legacy `--dry-run --json`, a target refusal has semantic exit code 2 in the
document but process code 0; the too-new-project exception remains process code
5. `--plan-json` reports its process code directly in `process_exit_code`.

## Troubleshooting

**`spec-kitty upgrade` errored after applying some migrations** — Migrations commit progress to `.kittify/metadata.yaml` after each step. Fix the underlying error (often a permissions or PATH issue) and re-run `spec-kitty upgrade`; it will pick up where it left off.

**My agent command directories changed but I want the old templates** — Run `git diff .claude/` (or the relevant agent path) to inspect. If you maintained local customizations on top of generated files, restore them and consider opening an issue so the upstream templates can incorporate the change.

**`spec-kitty upgrade` says my project schema is too new** — The installed CLI is older than the schema in `.kittify/metadata.yaml`. Upgrade the CLI: `pipx upgrade spec-kitty-cli`.

**I want to skip a specific migration** — Migrations are non-optional; they exist because the runtime depends on the new layout. Investigate the root cause instead.

## Rollback

A failed upgrade can be rolled back with git, since `.kittify/`, `.claude/`, and other agent directories are version-controlled:

```bash
git restore .kittify/ .claude/ .agents/skills/
```

Then reinstall the previous CLI version:

```bash
pipx install --force spec-kitty-cli==<previous-version>
```

See [Uninstall](uninstall.md) for the full rollback procedure.

## Next steps

- [Upgrade the CLI](upgrade-cli.md)
- [Upgrade lifecycle reference](../../../api/upgrade-lifecycle.md)
- [Init lifecycle reference](../../../api/init-lifecycle.md)
- [Install and upgrade overview](install-and-upgrade.md)
