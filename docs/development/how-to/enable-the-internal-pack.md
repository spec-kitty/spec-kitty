---
title: How to enable the internal charter and skills
description: Register the internal org pack in your clone, project the four kitty-* maintainer skills into each tool, verify them, and work around two known defects.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/how-to/create-a-pack-skill.md
- docs/architecture/org-doctrine-layer.md
- docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md
---
# How to enable the internal charter and skills

`packs/internal/` holds the doctrine that governs how the core team works, plus four
shared maintainer skills: `kitty-land-pr`, `kitty-issue-triage`, `kitty-mission-from-issue`
and `kitty-report-debrief`. The pack never ships to consumers. This page gets it working in
your clone.

## Step 1: Register the pack

Add the pack to `.kittify/config.yaml` as an org pack:

```yaml
charter_packs:
  org:
    packs:
    - name: internal
      local_path: packs/internal
```

This is the canonical shape. This repository's own config already carries the entry.

The pack's `org-charter.yaml` sets `skill_namespace: kitty` and lists all four skills in
`required_skills`, so registering the pack puts them in force. You do not run
`spec-kitty charter activate skill` for them.

## Step 2: Project the skills

```bash
mkdir -p .claude   # only if `claude` is a configured tool and .claude/ is missing (#4275)
spec-kitty upgrade
```

The `SKILL.md` files are not on disk until `upgrade` writes them into each configured tool's
project skill root. See the root table in
[Create and activate a pack skill](create-a-pack-skill.md#step-3-activate-it).

## Step 3: Verify

Check that each tool's project skill root holds the four directories, for example:

```bash
ls .claude/skills .agents/skills | grep kitty-
```

You should see `kitty-land-pr`, `kitty-issue-triage`, `kitty-mission-from-issue` and
`kitty-report-debrief`, each with a `SKILL.md`. Do not rely on
`spec-kitty doctor skills` for this check (see below).

## Known defects

| Symptom | Cause | Workaround |
| --- | --- | --- |
| `upgrade` fails with "Owner effect conflict" on `.claude` | `claude` is configured and the clone has no `.claude/` directory (#4275) | `mkdir .claude`, then run `upgrade` again. Projects that do not configure `claude` are not affected. |
| `doctor skills` reports healthy but a `kitty-*` directory is missing | `doctor skills` does not notice a pack skill in force that was never projected, and `--fix` does not project it (#5801) | Check the directories yourself after `upgrade`, as in Step 3. |

## After pulling the change that untracked the command-skill ledger

`.kittify/command-skills-manifest.json` is a per-machine ledger and is no longer tracked. Pulling
the change that untracked it deletes your local copy, and `spec-kitty doctor skills --fix` then
refuses because it sees unmanaged files. Do this once:

```bash
rm -rf .agents/skills/spec-kitty.*
spec-kitty doctor skills --fix
spec-kitty upgrade
```

The first command removes the generated `spec-kitty.*` command-skill directories. The `fix`
rebuilds the ledger, and `upgrade` projects the `kitty-*` skills.

## See also

- [Internal pack README](../../../packs/internal/README.md): what the pack contains.
- [Create and activate a pack skill](create-a-pack-skill.md): author your own skill.
- [Understanding the Org Layer of the Charter Offering](../../architecture/org-doctrine-layer.md): how a project registers a pack.
