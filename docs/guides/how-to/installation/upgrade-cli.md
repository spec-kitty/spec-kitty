---
title: Upgrade the Spec Kitty CLI
description: Upgrade the Spec Kitty CLI to 3.2, verify the installed binary, and know when project migrations are still required.
doc_status: active
updated: '2026-06-03T00:00:00Z'
related:
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/guides/how-to/installation/upgrade-project.md
- docs/guides/how-to/installation/fork-packaging-hooks.md
audience: docs/context/audience/external/project-owner.md
kind: How-To
---
# Upgrade the Spec Kitty CLI

Upgrade the `spec-kitty` binary to a newer release. This page covers the CLI itself only; for upgrading an existing project's `.kittify/` scaffold to match, see [Upgrade a project](upgrade-project.md).

> Spec Kitty distinguishes **CLI upgrades** (installing a new `spec-kitty-cli` wheel) from **project upgrades** (running migrations inside a project). They are separate steps.

> **Packagers / forks:** If you publish Spec Kitty under a different distribution name or private index, do not overlay core sources — register entry-point hooks instead. See [Fork packaging hooks](fork-packaging-hooks.md).

## Quick reference

| Install method | Upgrade command |
|---|---|
| pipx | `pipx upgrade spec-kitty-cli` |
| uv tool | `uv tool upgrade spec-kitty-cli` |
| pip (in venv) | `pip install --upgrade spec-kitty-cli` |

Let the CLI tell you which one applies:

```bash
spec-kitty upgrade --cli
```

This prints the right upgrade command for your detected install method without touching any project state.

Guidance and preview intent is resolved before hidden agent preference
operations. Hidden `--agent-check`, `--agent-choice`, and `--agent-latest`
operations remain standalone; combining them with `--cli`, `--project --json`,
`--dry-run`, or `--plan-json` is rejected before preference state can change.
`--plan-json` and `--cli` are mutually exclusive.

## pipx

```bash
pipx upgrade spec-kitty-cli
```

To force a reinstall (handy after a corrupted upgrade):

```bash
pipx install --force spec-kitty-cli
```

To pin a specific version:

```bash
pipx install --force spec-kitty-cli==3.2.0
```

## uv tool

```bash
uv tool upgrade spec-kitty-cli
```

Or reinstall pinned:

```bash
uv tool install --force spec-kitty-cli==3.2.0
```

## pip in a venv

Activate the venv first, then:

```bash
pip install --upgrade spec-kitty-cli
```

Or pin a version:

```bash
pip install --upgrade 'spec-kitty-cli==3.2.0'
```

## Verify the upgrade

```bash
spec-kitty --version
# spec-kitty-cli version 3.2.x
```

If `--version` still reports the old number after an upgrade, your shell PATH is picking up a different install. Run `which spec-kitty` (or `where.exe spec-kitty` on Windows) and remove or correct the stale entry.

## What happens after a CLI upgrade

The CLI does not automatically modify any of your projects. When you next run a project command (e.g. `spec-kitty next`, `spec-kitty implement`), spec-kitty checks whether the project schema matches the new CLI:

- **Compatible** → command runs normally.
- **Project needs migration** → command exits with code 4 and tells you to run `spec-kitty upgrade` in the project root. See [Upgrade a project](upgrade-project.md).
- **Project too new for this CLI** → command exits with code 5. You upgraded down, not up; reinstall the newer CLI.

## Throttled upgrade nag

When a newer CLI version is available on PyPI, spec-kitty prints a single banner before normal output. It is throttled to once per 24 hours. Disable per invocation with `--no-nag`, per session with `SPEC_KITTY_NO_NAG=1`, or change the cadence with `SPEC_KITTY_NAG_THROTTLE_SECONDS=<seconds>`.

## Troubleshooting

**`pipx upgrade` says "already at latest" but PyPI has a newer version** — Your pipx cache is stale. Run `pipx install --force spec-kitty-cli`.

**`uv tool upgrade` fails with "tool not installed"** — You installed via pipx, not uv. Use the matching upgrade command for your original install method.

**`spec-kitty --version` reports the old version after upgrade** — `which spec-kitty` will reveal a competing install in another bin directory. Remove the stale one or reorder PATH.

**Upgrade succeeded but a command now exits 4 or 5** — That is the lazy-gate protecting your project; see [Upgrade a project](upgrade-project.md) for the next step.

## Next steps

- [Upgrade an existing project](upgrade-project.md)
- [Upgrade lifecycle reference](../../../api/upgrade-lifecycle.md)
- [Install and upgrade overview](install-and-upgrade.md)
- [Fork packaging hooks](fork-packaging-hooks.md) (renamed / private-index distributors)
