---
title: Migrating Shared Doctrine to the Org Layer
description: Move shared governance artifacts out of project-local `.kittify/doctrine/` and into a proper org doctrine pack, including how to deal with deprecated constitution-era paths.
doc_status: superseded
updated: '2026-10-08'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migrating Shared Doctrine to the Org Layer

> **Superseded; kept as a historical record.** The charter-pack cutover (#3732) replaced the layout
> and commands this page describes, and Spec Kitty no longer reads them. The current path is
> [Charter pack cutover](charter-pack-cutover.md).

This guide is for projects that previously shared governance content by copying it into
each project's `.kittify/doctrine/` folder (directly, via a bootstrap script, or by
copy-paste), or that still rely on deprecated constitution-era paths. The org doctrine
layer gives you a cleaner way to express the same intent.

> **The project layer still works.** The org layer is **additive**, not a replacement.
> You do not have to migrate. This guide is for teams who want to.

For background on the model, see [Understanding the Org Doctrine
Layer](../architecture/org-doctrine-layer.md). For pack authoring details, see
[How to create an org doctrine pack](../guides/how-to/governance/create-an-org-doctrine-pack.md).

---

## Who this guide is for

You should read this guide if **either** of the following applies:

1. You maintain shared governance artifacts in `.kittify/doctrine/` across multiple
   projects (typically duplicated via a bootstrap script or copy-paste) and you want a
   single source of truth that is fetched, not copied.
2. You are still on deprecated constitution-era paths
   (`.kittify/memory/constitution.md`, `.kittify/constitution/*.yaml`) and need to know
   what replaces them.

If your `.kittify/doctrine/` content is genuinely project-specific (exceptions, local
overrides, project-only directives), **do not migrate**. That is exactly what the
project layer is for.

---

## What changes

### Before

```
project-A/.kittify/doctrine/      # shared content, copied
project-B/.kittify/doctrine/      # shared content, copied (drifts over time)
project-C/.kittify/doctrine/      # shared content, copied
```

Each project carries its own snapshot of "shared" governance. Updates require touching
every project. Drift is invisible until something breaks.

### After

```
~/.kittify/org/acme/              # one snapshot, fetched from git
project-A/.kittify/doctrine/      # project-only exceptions (or empty)
project-B/.kittify/doctrine/      # project-only exceptions (or empty)
project-C/.kittify/doctrine/      # project-only exceptions (or empty)
```

A single org snapshot serves all projects. Each project carries only its genuine
exceptions. Updates are a single PR against the pack repository plus a `doctrine fetch`
on each developer machine.

### Resolution order

| Layer | When considered | Wins on collision against... |
|-------|-----------------|------------------------------|
| Project (`.kittify/doctrine/`) | Always (if non-empty) | Org and built-in |
| Org (configured packs) | When `doctrine.org` is set in config | Built-in |
| Built-in (bundled with CLI) | Always | — |

Project still wins. Your project-only exceptions continue to override anything the org
layer ships.

---

## Option 1: Migrate from `.kittify/doctrine/` shared overlay

### Step 1: Extract shared artifacts into a new pack

Create a new directory outside any specific project. This is the **authoring location**
for your pack:

```bash
mkdir ~/work/acme-doctrine
cd ~/work/acme-doctrine
```

Identify which artifacts in your project-local `.kittify/doctrine/` are actually shared
across projects (the ones you have been copying). Move those to the new pack, preserving
their subdirectory layout:

```bash
# Example: extract shared directives and tactics
cp -r project-A/.kittify/doctrine/directive/  ~/work/acme-doctrine/directives/
cp -r project-A/.kittify/doctrine/tactic/     ~/work/acme-doctrine/tactics/
```

Leave behind anything that is project-specific (exceptions, local overrides). Those
stay in each project's `.kittify/doctrine/`.

### Step 2: Validate the new pack

Run `pack validate` to catch schema issues before you publish:

```bash
uv run spec-kitty doctrine pack validate ~/work/acme-doctrine
```

Fix any errors reported. Advisories about ID collisions with built-in artifacts mean
the pack will override built-in defaults — usually a sign you should rename to a
namespaced ID like `acme-001-...`.

### Step 3: Publish the pack

Choose a transport. Git is recommended:

```bash
cd ~/work/acme-doctrine
git init
git add .
git commit -m "Initial extract from shared project overlay"
git remote add origin git@example.com:acme/doctrine.git
git push -u origin main
git tag v1.0.0
git push origin v1.0.0
```

For HTTPS bundle or API options, see
[How to create an org doctrine pack — Step 7](../guides/how-to/governance/create-an-org-doctrine-pack.md#step-7-publish-the-pack).

### Step 4: Configure the consumer projects

In each project's `.kittify/config.yaml`, add the `doctrine.org` block:

```yaml
doctrine:
  org:
    packs:
      - name: acme
        local_path: "~/.kittify/org/acme/"
        source_type: git
        url: "git@example.com:acme/doctrine.git"
        ref: "v1.0.0"
```

Run fetch on each developer machine:

```bash
uv run spec-kitty doctrine fetch
```

### Step 5: Remove the duplicates from project overlays

For each consumer project, remove the now-redundant artifacts from
`.kittify/doctrine/`:

```bash
cd project-A
# Remove only the artifacts that moved to the org pack.
# KEEP anything that is a project-specific exception.
rm .kittify/doctrine/directive/acme-001-secret-handling.directive.yaml
# ... etc
git add -A
git commit -m "Migrate shared doctrine to org pack"
```

### Step 6: Verify

```bash
uv run spec-kitty doctor doctrine
uv run spec-kitty charter context --action implement --json
```

Resolved artifacts that previously appeared with `source: project` should now appear
with `source: org`. Genuine project exceptions still show `source: project`.

---

## Option 2: Migrate from constitution-era paths

Earlier spec-kitty releases used a `constitution` concept. These paths are no longer
loaded by the runtime:

| Deprecated path | Replacement |
|-----------------|-------------|
| `.kittify/memory/constitution.md` | Move policy content into `.kittify/charter/charter.md` (the project charter). Delete the constitution file. |
| `.kittify/constitution/*.yaml` | Migrate to charter content or to a doctrine pack (built-in, org, or project — whichever matches the rule's audience). |

If the YAML rules under `.kittify/constitution/` are project-specific, move them under
`.kittify/doctrine/` (project layer). If they are shared across teams, follow Option 1
above and put them in an org pack.

The project charter (`.kittify/charter/charter.md`) remains the human-edited governance
centre of every project. External documents are referenced from the charter rather than
loaded directly. See [How to set up project governance](../guides/how-to/governance/setup-governance.md)
for the canonical charter workflow.

---

## Before vs. after

| Scenario | Before | After |
|----------|--------|-------|
| Shared `.kittify/doctrine/` across multiple projects | Same files copied into each project | One pack at `~/.kittify/org/<name>/`, referenced from each `.kittify/config.yaml` |
| `.kittify/memory/constitution.md` | Loaded by older spec-kitty | Not loaded; content moves into `charter.md` |
| `.kittify/constitution/*.yaml` | Loaded by older spec-kitty | Not loaded; content moves into a doctrine pack |
| Project-specific exception | Project doctrine overlay | Project doctrine overlay (unchanged) |
| Built-in defaults | Built-in layer | Built-in layer (unchanged) |

---

## Verification checklist

After migrating, confirm:

- [ ] `uv run spec-kitty doctor doctrine` reports the org snapshot is present and the
      artifact counts look right.
- [ ] `uv run spec-kitty charter context --action implement --json` shows the migrated
      artifacts with `"source": "org"` (not `"source": "project"`).
- [ ] `uv run spec-kitty doctrine pack validate <pack-path>` exits 0 on the published
      pack.
- [ ] Existing project tests still pass (the resolved governance set should be
      equivalent).
- [ ] Any deprecated `constitution.md` / `constitution/*.yaml` files have been removed
      and their content migrated to `charter.md` or to an appropriate doctrine layer.

---

## Rollback

The org layer is purely additive. If anything goes wrong:

1. **Put the artifacts back.** Restore the files you removed from
   `.kittify/doctrine/` — they continue to work as before.
2. **Remove the config.** Delete the `doctrine.org` block from
   `.kittify/config.yaml`. Resolution will silently fall back to built-in + project.
3. **Leave the snapshot directory in place** (or delete it) — its presence or absence
   has no effect once the config block is gone.

Rolling back does not require any data migration. Your project layer was never
touched (beyond the deletions you performed in Step 5, which you can revert with
`git revert`).

---

## See also

- [Understanding the Org Doctrine Layer](../architecture/org-doctrine-layer.md)
- [How to create an org doctrine pack](../guides/how-to/governance/create-an-org-doctrine-pack.md)
- [How to set up project governance](../guides/how-to/governance/setup-governance.md)
