---
title: 'Migration: Charter Pack Cutover'
description: 'Runbook for the charter pack cutover (#3732): run spec-kitty upgrade once, handle LEGACY_CHARTER_STATE and lanes in flight, update packs, and rewrite saved scripts.'
doc_status: active
type: how-to
audience: docs/context/audience/external/project-owner.md
updated: '2026-10-08'
related:
- docs/adr/4.x/2026-10-06-1-charter-offering-active-charter-and-activation-presets.md
- docs/context/charter.md
- docs/changelog/CHANGELOG.md
- docs/migrations/doctrine-local-overlay-to-org-layer.md
- docs/migrations/relocate-builtin-doctrine-packs.md
---
# Migration: Charter Pack Cutover

**Issue**: [#3732](https://github.com/spec-kitty/spec-kitty/issues/3732)
**Ships in**: spec-kitty-cli 4.0.0rc6
**Audience**: operators who run `spec-kitty` in a project, authors of org Charter Packs, and anyone with saved scripts or CI jobs that call `spec-kitty`.

## What changed

Spec Kitty now uses one name for each idea ([ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-charter-offering-active-charter-and-activation-presets.md)).
A **Charter Pack** is a bundle of charter components that a project can draw from; the packs plus the project's own layer form the **charter offering**.
An **activation preset** is a named set of activations that a pack ships, applied with `spec-kitty charter activate --preset <name>`.
The **active charter** is what your project has activated (`activated_<kind>` keys, `activated_kinds`, `mission_type_activations`).
The older "doctrine" names are removed, not deprecated: the `spec-kitty doctrine` command group, the `doctrine.*` and `organisation_packs` config keys, the `.kittify/doctrine/` directory, the `spk-doctrine-*` skills and their older `spec-kitty-*` twins.
There are no aliases. An old command fails as an unknown command (exit 2), and an old project layout stops every command until you run `spec-kitty upgrade` once.
The glossary entries are in [docs/context/charter.md](../context/charter.md); the full list of renamed names is in the [changelog](../changelog/CHANGELOG.md) and in [Saved scripts](#saved-scripts) below.

## Operators

### Upgrade a project

Run these from the repository root checkout, on the branch you integrate into:

```bash
spec-kitty upgrade --dry-run     # preview: every line starts with "Would ..."
spec-kitty upgrade               # apply
git status                       # review the moves and rewrites
git add -A && git commit -m "chore: spec-kitty charter pack cutover"
```

The cutover migration runs before every other pending migration, so the later migrations read the new layout.
It is a plain filesystem move plus key rewrites: uncommitted edits under `.kittify/doctrine/` are carried over to `.kittify/charter-packs/` as they are.
Commit the result so teammates and lanes receive it.
A second `spec-kitty upgrade` changes nothing.
If a teammate pulls an older branch that brings the old layout back, `spec-kitty upgrade` selects the cutover again and migrates it again.

### Read the upgrade summary

The summary groups every line of the cutover. `spec-kitty upgrade --json` carries the same lists under `migration_reports.charter_pack_cutover`.

| Report key | Summary prefix | What it means | What you do |
|---|---|---|---|
| `moved` | `Moved` | A file moved from `.kittify/doctrine/` to `.kittify/charter-packs/`. | Commit it. |
| `rewritten` | `Rewrote` | A config key or path reference was renamed (file and key named). | Commit it. |
| `reset` | `Reset` | An activation key was removed because it was a stale copy of an old default list, the old 8-kind gate, the old `minimal` kind gate, or an `[]` written by an earlier upgrade. The kind is now unrestricted (or limited to what your org packs require). | Check the restore hint (below) if you meant to keep it. |
| `kept_for_review` | `Kept for review` | A customized list, or an entry the migration could not convert, was left as it is. | Read the line and edit the file by hand if needed. |
| `matches_minimal` | `Matches preset minimal, kept` | A list equals the released `minimal` preset; it stays. | Nothing, or apply a preset (see [Choosing a starting point](#choosing-a-starting-point)). |
| `skills_removed` | `Removed skill` | An installed copy of a removed skill was deleted. | Nothing; the new skill is installed. |
| `skills_kept` | `Kept edited skill copy` | You edited an installed copy of a removed skill. It is kept, dropped from `.kittify/skills-manifest.json` and is now yours: later upgrades leave it alone. | Delete it when you no longer need it. |
| `errors` | error lines | The run refused (a path collision or a locked file). Nothing in the refused step was written. | Fix the named path and run `spec-kitty upgrade` again. |

### Keys that were reset

Reset lines are there because older releases wrote lists that silently hid every newer built-in artifact. After the reset the key is absent, which means "all built-ins of this kind are in force" (or, where an org pack requires artifacts, only those).

- **A deliberate `[]` was reset.** A per-kind `activated_<kind>: []` cannot be told apart from the empty lists an earlier upgrade wrote, so the cutover removes it and prints a hint naming the file and the key, for example: `To switch the kind off again, set activated_tactics: [] in .kittify/config.yaml.` Put the `[]` back if you meant it. The reset runs only on the first application, so a later `[]` you write stays.
- **The `minimal` kind gate is gone.** Projects that applied the old `minimal` preset carried `activated_kinds: [directives, tactics]`, which switched every other kind off. The new `minimal` preset has no kind gate, so the cutover removes it and says so. To gate kinds again, set `activated_kinds` yourself.
- **A list that matches an old default list** was reset; a list you customized was kept and reported for review.

### Refusals during the upgrade

- **Collision.** When `.kittify/doctrine/` and `.kittify/charter-packs/` both hold the same path with different content, the upgrade refuses and lists every colliding path. Nothing is written. Keep the copy you want under `.kittify/charter-packs/`, delete the other, and run `spec-kitty upgrade` again.
- **Locked file (Windows).** A file held open by an editor or another process stops the move and is named. Close it and run `spec-kitty upgrade` again; the run finishes the remaining moves.

### `LEGACY_CHARTER_STATE`: the project is not migrated yet

Every command refuses a project (or the checkout you are in) that still has the old layout, with exit 1:

```text
Error (LEGACY_CHARTER_STATE): This project uses the retired doctrine layout (<first finding>).
Run `spec-kitty upgrade` to migrate it.
See docs/migrations/charter-pack-cutover.md.
```

In a lane worktree the message adds: upgrade the repository root and merge the target into this lane (do not rebase).
These still run on an unmigrated project, so you can always reach the fix: `spec-kitty upgrade`, `spec-kitty init`, `--version`, `--help`, the git merge drivers (`spec-kitty merge-driver-*`) and the hook entry points (`spec-kitty live-work hook`, `session-start`, `session-stop`, `commit-guard-hook`).
The findings are: the `.kittify/doctrine/` directory, a `governance.yaml` with the old selection key, or one of the old keys in `.kittify/config.yaml` (`doctrine.org`, `organisation_packs`, `governance.doctrine`, `tracker.doctrine`).

### Config that the upgrade does not rewrite

- **`charter_packs.org.local_path` (single-pack form).** Only the named list form is read. Move the fields into one entry of `charter_packs.org.packs[]` with a `name` (not `default`, which is the preset name):

  ```yaml
  charter_packs:
    org:
      packs:
        - name: acme
          local_path: ../acme-charter-pack
  ```

  The old `doctrine.org` single-pack form is rewritten for you: the entry is named after the `local_path` directory (or `org`).
- **`organisation_packs` entries that are not local paths** are kept and reported for review. Declare them under `charter_packs.org.packs[]` with their source fields.
- **Org packs outside the project that use the nested layout** `<pack>/doctrine/<kind>/<layer>/` are no longer read; nor is a repository-root `doctrine/` directory used as the project layer. The upgrade cannot convert files it does not own. `spec-kitty doctor charter-packs` names each one; the pack maintainer moves the artifacts to the flat layout `<pack>/<kind>/`.
- **Agent prompts that still say `/ad-hoc-profile-load`.** Projects that took the 3.2.0rc35 profile hand-off migration have that text in `.kittify/missions/software-dev/command-templates/implement.md` and `review.md`, `.kittify/overrides/missions/software-dev/templates/task-prompt-template.md`, and `.agents/skills/spec-kitty.implement/SKILL.md` and `spec-kitty.review/SKILL.md`. The migration does not run twice, so replace the old skill name yourself:

  ```bash
  grep -rln "ad-hoc-profile-load" .kittify .agents
  # in each file: /ad-hoc-profile-load -> /spk-charter-profile-load
  ```

## Missions in flight

The upgrade skips lane and coordination worktrees. A lane created before the upgrade still carries the old layout, so commands run inside it refuse with `LEGACY_CHARTER_STATE`. Pick one of these:

1. **Upgrade, then merge into each lane.** Upgrade and commit in the repository root checkout (above). Then, in each lane worktree, **merge** the upgraded target branch:

   ```bash
   cd .worktrees/<mission-slug>-lane-<id>
   git merge <target-branch>
   ```

   **Do not rebase the lane.** A rebase rewrites the lane commits, so the lane no longer contains the commit recorded when its work package was approved, and `spec-kitty consolidate` refuses with `APPROVAL_STAMP_NOT_ON_LANE`. A merge keeps the approved commits.
2. **Finish first.** Consolidate the Mission with the release you started it on, then upgrade.

## Choosing a starting point

A preset replaces the activation keys it governs. It refuses to overwrite a key you customized unless you pass `--force`, and prints the per-key difference.

```bash
spec-kitty charter pack list                         # packs and the presets each ships
spec-kitty charter activate --preset default         # every built-in artifact, plus the built-in mission types
spec-kitty charter activate --preset minimal         # a small curated baseline
spec-kitty charter activate --preset minimal --force # overwrite customized keys
spec-kitty charter activate --pack acme --preset team-default   # a preset of an org pack
spec-kitty charter pack path built-in --preset minimal          # print the preset file
```

A fresh `spec-kitty init` already behaves like the `default` preset. The applied preset name is not stored: the result is ordinary activation keys you can edit.

## Pack authors

Update each org Charter Pack you maintain:

1. **`pack.yaml`**: delete `accompanies_doctrine_pack`. A pack that still has it is rejected with `RETIRED_PACK_FIELD`; presets now ship inside the pack.
2. **`org-charter.yaml`**: in every `activations` entry, rename `doctrine_pack_id` to `charter_pack_id` (the old field is rejected with `RETIRED_PACK_FIELD`, whatever the schema version), and set `schema_version: 2`. Version 1 files still load; `spec-kitty charter org init` writes version 2.
3. **Presets** (optional): add `presets/<name>.yaml`. The file name is the preset name (lowercase letters, digits and hyphens).

   ```yaml
   name: team-default
   description: The Acme baseline.
   mission_type_activations: [software-dev]
   activated_directives: [ACME-001]
   # activated_<kind> for directives, tactics, styleguides, toolguides, paradigms,
   # procedures, agent_profiles, mission_step_contracts, anti_patterns.
   # Absent key: unrestricted. []: none of that kind.
   # activated_kinds: optional kind gate; it must include every kind you list ids for.
   ```

   No context-scoped entries. Every id must resolve in the built-in pack, the org pack chain or the project layer. `spec-kitty charter org init` scaffolds `presets/starter.yaml`.
4. **Validate and regenerate**:

   ```bash
   spec-kitty charter pack validate ./my-pack      # also validates presets/
   spec-kitty charter org validate ./my-pack
   spec-kitty charter pack regenerate-graph        # built-in pack maintainers
   ```

5. **Flatten nested layouts**: move `<pack>/doctrine/<kind>/<layer>/` artifacts to `<pack>/<kind>/`.
6. **Replace retired command and skill names** in your procedures, READMEs and skills (see the tables below).

## Saved scripts

Every old spelling exits 2 as an unknown command. Replace it with the new one.

### Commands

| Old | New | Notes |
|---|---|---|
| `spec-kitty charter pack apply <name> [--force]` | `spec-kitty charter activate [--pack <pack>] --preset <name> [--force]` | `--pack` defaults to `built-in`. |
| `spec-kitty charter pack list` (preset rows) | `spec-kitty charter pack list [--json]` | One row per pack with its presets. |
| `spec-kitty charter pack path <preset>` | `spec-kitty charter pack path <pack> [--preset <preset>]` | |
| `spec-kitty charter pack consistency-check` | `spec-kitty charter consistency-check` | `--json` key `missing_from_doctrine` is now `missing_from_offering`. |
| `spec-kitty doctrine pack validate <dir>` | `spec-kitty charter pack validate <dir>` | |
| `spec-kitty doctrine pack assemble …` | `spec-kitty charter pack assemble …` | |
| `spec-kitty doctrine regenerate-graph [--check]` | `spec-kitty charter pack regenerate-graph [--check]` | |
| `spec-kitty doctrine asset list` / `asset path <id>` | `spec-kitty charter pack asset list` / `asset path <id>` | |
| `spec-kitty doctrine fetch` / `new` / `validate` / `org init` / `org validate` | `spec-kitty charter fetch` / `new` / `validate` / `org init` / `org validate` | |
| `spec-kitty doctrine mission-type list` | `spec-kitty charter mission-type list --include-inactive` | |
| `spec-kitty doctor doctrine [--json]` | `spec-kitty doctor charter-packs [--json]` | JSON keys unchanged. |
| `spec-kitty tracker bind --doctrine-mode <m>` | `spec-kitty tracker bind --ownership-mode <m>` | The `doctrine_mode` JSON key is gone; read `ownership_mode`. |
| `spec-kitty doctor tool-surfaces --kind doctrine-skill` | `spec-kitty doctor tool-surfaces --kind charter-skill` | Kind value `charter_skill`; surface ids contain `.charter_skill.`. |

`spec-kitty charter pack list --json` now prints `{"packs": [{"name", "tier", "root", "presets": [{"name", "description", "path"}]}]}`.

### Skills

| Old | New |
|---|---|
| `spk-doctrine-charter`, `spec-kitty-charter-doctrine`, `spec-kitty-constitution-doctrine` | `spk-charter-governance` |
| `spk-doctrine-glossary`, `spec-kitty-glossary-context` | `spk-charter-glossary` |
| `spk-doctrine-profile-load`, `ad-hoc-profile-load` | `spk-charter-profile-load` |
| `spk-doctrine-spdd-reasons`, `spec-kitty-spdd-reasons` | `spk-charter-spdd-reasons` |
| `spk-doctrine-bulk-edit`, `spec-kitty-bulk-edit-classification` | `spk-practice-bulk-edit` |
| `spk-doctrine-semantic-compression` | `spk-practice-semantic-compression` |
| `spk-doctrine-show-me` | `spk-practice-show-me` |

The upgrade removes the old copies from the project skill roots, and the global skill sync removes them from the user-global roots.

### Config keys and paths

| Old | New |
|---|---|
| `doctrine.org.packs[]`, `doctrine.org.{local_path,subdir,source_type,url,ref}`, `organisation_packs[]` | `charter_packs.org.packs[]` |
| `governance.doctrine.*` (`config.yaml`, `charter.yaml`); top-level `doctrine:` in `governance.yaml` | `governance.charter.*`; top-level `charter:` |
| `tracker.doctrine` | `tracker.ownership` |
| top-level `doctrine:` in `.kittify/charter/interview/answers.yaml` | `charter:` |
| `doctrine_pack_id` in `activations` entries | `charter_pack_id` |
| `.kittify/doctrine/` | `.kittify/charter-packs/` |
| `.kittify/doctrine/replaceable-builtins.yaml` | `.kittify/charter-packs/replaceable-builtins.yaml` |

### Error codes

| Old | New | Raised when |
|---|---|---|
| `CHARTER_PACK_CONFIG_INVALID` | `ACTIVE_CHARTER_CONFIG_INVALID` | The active charter config has an invalid shape (also a `governance.doctrine` key left in `charter.yaml`). |
| — | `LEGACY_CHARTER_STATE` | The project still has the old layout. |
| `DefaultCharterPackMissingError` | `DEFAULT_PRESET_MISSING` | The built-in `default` preset is missing during `init`, `charter generate` or upgrade provisioning. |
| — | `PACK_NOT_FOUND`, `PRESET_NOT_FOUND` | `charter activate --preset` or `charter pack path` names an unknown pack or preset. |
| — | `PRESET_ID_UNRESOLVED`, `PRESET_INVALID` | A preset names an id that resolves nowhere, or the preset file is malformed. |
| — | `PRESET_WOULD_OVERWRITE` | A preset would change a customized key and `--force` was not given. |
| — | `RESYNTHESIS_FAILED` | `charter activate --preset … --json` wrote the preset but the follow-up recompile failed; run `spec-kitty charter synthesize`. |
| generic "extra field" error | `RETIRED_PACK_FIELD` | A pack file still has `accompanies_doctrine_pack` or `doctrine_pack_id`. |

Text mode prints coded errors as `Error (<CODE>): <message>`; `--json` mode prints a JSON error object and exits 1.

### Python callers

If you import Spec Kitty internals, see the changelog's "Charter pack cutover" entries for renamed classes and modules (for example `CharterPackManager` → `ActiveCharterManager`, `DoctrineService` → `CharterOfferingService` / `ActiveCharterService`, `specify_cli.doctrine` → `charter.offering.packs`, `charter.activation` and `specify_cli.charter_packs`).
