# Sidecar PR draft: spec-kitty/spec-kitty-open-packs (OD-2, WP24 T115)

Drafted by WP24 of mission charter-pack-cutover-01M491G6. NOT opened, NOT pushed.
The orchestrator opens it after the #3732 mission PR merges.

- Target repository: https://github.com/spec-kitty/spec-kitty-open-packs
- Read at: `309954be07e84e71b6cb83100f32a1535c85b1e5` (default branch HEAD, 2026-07-25), shallow clone.
- Finding: at that commit the repository ships **no pack yet** (`packs/` holds only `README.md`;
  no `pack.yaml`, no `org-charter.yaml`). So there is no descriptor field or `doctrine_pack_id`
  to change today; the PR fixes the guides, templates and the repository's own Spec Kitty
  project state, and sets the rules for the first packs.

---

## PR title

docs: follow the Spec Kitty charter pack cutover (charter commands, charter_packs config, presets)

## PR description

Spec Kitty 4.0.0rc6 renames "doctrine packs" to **Charter Packs** and removes the old names
with no aliases (spec-kitty/spec-kitty#3732, ADR 2026-10-06-1):

- The `spec-kitty doctrine` command group is gone. `doctrine pack validate|assemble`,
  `doctrine fetch` and the rest now live under `spec-kitty charter` (an old spelling exits 2
  as an unknown command).
- `spec-kitty doctor doctrine` is now `spec-kitty doctor charter-packs`.
- Consumers configure packs under `charter_packs.org.packs[]` in `.kittify/config.yaml`; the
  `doctrine.org.*` keys are no longer read (`spec-kitty upgrade` rewrites them once).
- `pack.yaml` must not carry `accompanies_doctrine_pack` (rejected with `RETIRED_PACK_FIELD`).
- `org-charter.yaml` activation entries use `charter_pack_id` instead of `doctrine_pack_id`
  (rejected with `RETIRED_PACK_FIELD`), and new files declare `schema_version: 2`.
- A pack can now ship **activation presets** as `presets/<name>.yaml`; consumers apply them
  with `spec-kitty charter activate --pack <pack> --preset <name>`.

This repository's guides, PR template and CI snippets still teach the old commands and keys,
so a contributor following them hits unknown-command errors. This PR updates every living
page. Research notes and ADRs under `docs/research/` and `docs/architecture/adr/` are left
as dated records.

Runbook: https://github.com/spec-kitty/spec-kitty/blob/main/docs/migrations/charter-pack-cutover.md

Checklist:
- [ ] Every command in `docs/guides/`, `README.md`, `packs/README.md` and
      `.github/PULL_REQUEST_TEMPLATE.md` runs under spec-kitty 4.0.0rc6.
- [ ] `spec-kitty upgrade` run once in this repository with 4.0.0rc6; the result committed.

---

## Changes, file by file

### `.github/PULL_REQUEST_TEMPLATE.md`

```diff
-- [ ] `spec-kitty doctrine pack validate ./<pack>` passes with exit code 0
+- [ ] `spec-kitty charter pack validate ./<pack>` passes with exit code 0
```

### `docs/guides/validate-a-pack.md` (lines 20, 31, 67)

```diff
-spec-kitty doctrine pack validate ./my-pack
+spec-kitty charter pack validate ./my-pack
-spec-kitty doctrine pack validate ./my-pack --json
+spec-kitty charter pack validate ./my-pack --json
-      spec-kitty doctrine pack validate "$pack" --json
+      spec-kitty charter pack validate "$pack" --json
```

Add one row to the findings table: `presets/<name>.yaml` malformed or naming an unknown id → **Error**;
`accompanies_doctrine_pack` in `pack.yaml` → **Error** (`RETIRED_PACK_FIELD`).

### `docs/guides/publish-a-pack.md` (line 53)

```diff
-spec-kitty doctrine pack assemble ./out ./packs/core-engineering ./packs/domain-driven-design
+spec-kitty charter pack assemble ./out ./packs/core-engineering ./packs/domain-driven-design
```

### `docs/guides/author-a-doctrine-pack.md`

Keep the file name (published URL). Text changes:

```diff
-> **Do not hand-write `pack-manifest.yaml`.** It is written by tooling (`doctrine fetch` for
-> non-git sources, `doctrine pack assemble`). Manual edits surface as an advisory in
-> `pack validate`.
+> **Do not hand-write `pack-manifest.yaml`.** It is written by tooling (`charter fetch` for
+> non-git sources, `charter pack assemble`). Manual edits surface as an advisory in
+> `charter pack validate`.
```

Layout tree: add `├── presets/                    # optional: <name>.yaml activation presets`.

Section 5 example:

```diff
 # org-charter.yaml
-schema_version: "1"
+schema_version: 2
 org_name: ACME Corporation
```

Add a short "Ship activation presets (optional)" section:

```yaml
# presets/team-default.yaml — name must equal the file stem
name: team-default
description: The ACME baseline.
mission_type_activations: [software-dev]
activated_directives: [acme-001-secret-handling]
# absent key = unrestricted; [] = none of that kind; activated_kinds is an optional kind gate
```

and the rule: never add `accompanies_doctrine_pack` to `pack.yaml`; in `org-charter.yaml`
`activations` entries use `charter_pack_id`.

### `docs/guides/use-a-doctrine-pack.md` (lines 22-56)

```diff
-A consumer enables the org layer by adding a `doctrine.org` block to
+A consumer enables the org layer by adding a `charter_packs.org` block to
 `.kittify/config.yaml`, listing each pack and pinning a version:

 # .kittify/config.yaml
-doctrine:
+charter_packs:
   org:
     packs:
       - name: domain-driven-design
-| `name` | yes | Unique pack name (used by `--pack`, shown in `doctor doctrine`). |
+| `name` | yes | Unique pack name (used by `--pack`, shown in `doctor charter-packs`). |
-spec-kitty doctrine fetch                 # fetch all configured packs
-spec-kitty doctrine fetch --pack domain-driven-design   # one pack
-spec-kitty doctrine fetch --dry-run       # preview without contacting any remote
+spec-kitty charter fetch                 # fetch all configured packs
+spec-kitty charter fetch --pack domain-driven-design   # one pack
+spec-kitty charter fetch --dry-run       # preview without contacting any remote
-spec-kitty doctor doctrine
+spec-kitty doctor charter-packs
```

Add a step: "Apply a preset the pack ships: `spec-kitty charter pack list`, then
`spec-kitty charter activate --pack domain-driven-design --preset <name>`."
(`charter fetch --pack` and `--dry-run` verified against `spec-kitty charter fetch --help` on the mission lane.)

### `docs/guides/compose-packs.md` (lines 28, 42, 72)

```diff
-- **org** — the packs you configure under `doctrine.org.packs` (including open packs from
+- **org** — the packs you configure under `charter_packs.org.packs` (including open packs from
-List several packs under `doctrine.org.packs`. Each contributes its artifacts additively;
+List several packs under `charter_packs.org.packs`. Each contributes its artifacts additively;
-  colliding org-pack IDs surface as advisories in `charter lint` / `doctor doctrine`.
+  colliding org-pack IDs surface as advisories in `charter lint` / `doctor charter-packs`.
```

### `README.md` and `packs/README.md`

Add `presets/  # optional activation presets (<name>.yaml)` to both layout trees.

### `docs/architecture/docsite-design.md` (lines 43, 111)

```diff
-| Validation status | `spec-kitty doctrine pack validate --json` | generated |
+| Validation status | `spec-kitty charter pack validate --json` | generated |
-... Shell out to `spec-kitty doctrine pack validate --json` now; ...
+... Shell out to `spec-kitty charter pack validate --json` now; ...
```

### Left unchanged (dated records)

`docs/research/*.md` and `docs/architecture/adr/2026-07-18-2-*.md` mention
`spec-kitty doctrine pack validate`; they are dated research and ADRs. Optionally add one line
under each title: "Command names predate the charter pack cutover (spec-kitty#3732)."

### Repository's own Spec Kitty state

This repository is itself a Spec Kitty project. Its `.kittify/skills-manifest.json` lists
`ad-hoc-profile-load` and six `spk-doctrine-*` skills, and the generated command skills under
`.agents/skills/spec-kitty.{implement,review,tasks-packages}/SKILL.md` say
`/ad-hoc-profile-load`. Run once with spec-kitty 4.0.0rc6 and commit the result:

```bash
spec-kitty upgrade --dry-run
spec-kitty upgrade
grep -rln "ad-hoc-profile-load" .kittify .agents   # replace any leftover with /spk-charter-profile-load
```

`.kittify/config.yaml` at the read commit carries no `doctrine` keys, so no config rewrite is expected.

### Rules for the first packs (none exist yet)

- `pack.yaml`: no `accompanies_doctrine_pack`.
- `org-charter.yaml`: `schema_version: 2`; `activations[*]` use `charter_pack_id`.
- Flat layout only: `<pack>/<kind>/`; a nested `<pack>/doctrine/<kind>/<layer>/` tree is not read.
- Optional `presets/<name>.yaml`, validated by `spec-kitty charter pack validate`.

---

Mission PR body hand-off line: "Sidecar PR drafted in the WP24 Activity Log; the orchestrator opens it after merge."
