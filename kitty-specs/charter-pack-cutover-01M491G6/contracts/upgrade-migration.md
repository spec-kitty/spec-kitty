# Upgrade migration contract: charter-pack-cutover-01M491G6 (FR-012)

## Identity and ordering

- One migration module `m_4_0_0rc6_charter_pack_cutover.py`, `migration_id = "charter_pack_cutover"`, `target_version = "4.0.0rc6"` (the current version; no version bump), `runs_first = True`.
- `MigrationRegistry.get_applicable` places `runs_first` migrations before every other selected migration; `get_all()` keeps version order.
- Re-selection: the runner selects the cutover migration whenever its **structural** predicate is true (legacy project root `.kittify/doctrine/` present, legacy config keys present, or an activation entry carrying `doctrine_pack_id`), even when `metadata.yaml` already records it as applied. A pulled teammate checkout or a merge that brings legacy state back is therefore migrated again, never wedged behind the FR-011 gate. The structural predicate excludes the `[]`, stale-list, kind-gate and installed-skill checks.
- `runs_on_worktrees = False` (worktrees are skipped by the runner, #5457).

## `detect(project_path) -> bool`

True when any item of the FR-012 inventory is present: legacy keys in `config.yaml` / `charter.yaml` / `governance.yaml` / `answers.yaml` / tracker block; `.kittify/doctrine/` exists; a path reference carries the old prefix; an activation entry carries `doctrine_pack_id`; while the migration is not yet recorded as applied: an `activated_*` key matches a snapshot or is `[]`, or `activated_kinds` matches the snapshot 8-kind list or `[directives, tactics]` (after the first application these reset predicates are never consulted again); a removed skill is installed. Shares the cheap legacy predicate with the CLI-root gate; the expensive checks run only in `detect()`.

## `apply(project_path, dry_run) -> MigrationResult`

Order inside `apply` (each step idempotent):

1. Preflight: if `.kittify/doctrine/` and `.kittify/charter-packs/` share a path with different content → `success=False`, `errors` lists the paths, nothing written.
2. Move `.kittify/doctrine/**` → `.kittify/charter-packs/**` (plain move; locked file → refuse naming the path).
3. Rewrite path references: synthesis manifest, provenance sidecars, `.kittify/skills-manifest.json` `source_ref`, `.gitignore` rules.
4. Rewrite config keys (legacy single-pack form gets an explicit pack name ≠ `default`).
5. Rewrite `doctrine_pack_id` → `charter_pack_id` in project activation entries.
6. Reset stale lists, stale kind gates and per-artifact `[]` to absent (resolved activation store and the other file if it also carries keys). Runs only on the first application (recorded); a structural re-selection never resets a deliberate post-cutover `activated_<kind>: []`.
7. Remove installed removed skills (manifested, or unmanifested and hash-equal to a released copy); keep edited copies.
8. Record results.

`MigrationResult` fields used: `changes_made` (one line per item: moved / rewritten / reset), `warnings` (kept-for-review lists, `minimal`-equal lists, edited skill copies, each reset `[]` with the file and key to restore), `manual_review_required = bool(warnings)`, `preserved_paths` (edited skill copies). `spec-kitty upgrade` prints these as the upgrade summary. `dry_run=True` reports the same lines and writes nothing.

## `spec-kitty upgrade --json`: `migration_reports.charter_pack_cutover`

`changes_made[0]` carries the report as JSON; the CLI decodes it into `migration_reports["charter_pack_cutover"]`. Keys, each an ordered list of strings (one line per item):

| Key | Content |
|---|---|
| `moved` | paths moved from `.kittify/doctrine/` to `.kittify/charter-packs/` |
| `rewritten` | config keys and path references rewritten (file and key) |
| `reset` | stale lists, stale kind gates and `[]` reset to absent (file and key) |
| `kept_for_review` | customised or near-miss lists and unconvertible entries kept |
| `matches_minimal` | lists equal to the released `minimal` preset, kept |
| `skills_removed` | installed copies of removed skills deleted |
| `skills_kept` | edited copies kept |
| `errors` | refusals (collision paths, locked files) |

## Neutralised migrations

`m_3_2_0rc35_default_charter_pack`, `m_3_2_x_normalize_activation_absence`, `m_2_1_2_fix_glossary_context_skill`: `detect()` returns False (recorded as skipped); bodies removed; ids unchanged.

## Guarantees (tested on every NFR-001 fixture)

- after ⊇ golden before, with the per-fixture expected relation of spec NFR-001 (`ALL_BUILTIN` kinds expanded against the built-in inventory at comparison time).
- A second `spec-kitty upgrade` changes 0 bytes; `detect()` is False.
- A pre-rc35 project reaches the cutover version in one `spec-kitty upgrade` with 0 errors.
