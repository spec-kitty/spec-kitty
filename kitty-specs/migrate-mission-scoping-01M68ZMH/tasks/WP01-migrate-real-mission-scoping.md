---
work_package_id: WP01
title: Real --mission scoping for the three corpus-walking migrate commands
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6347-migrate-mission-scoping
merge_target_branch: issue-6347-migrate-mission-scoping
branch_strategy: Planning artifacts for this mission were generated on issue-6347-migrate-mission-scoping. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6347-migrate-mission-scoping unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Feature
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/migration/test_migrate_mission_scoping.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/migrate_cmd.py
- src/specify_cli/cli/commands/migrate/backfill_provenance.py
- src/specify_cli/cli/commands/migrate/charter_encoding.py
- src/specify_cli/dossier/rebaseline.py
- tests/cli/test_mission_agnostic_flag.py
- tests/migration/test_migrate_mission_scoping.py
- docs/changelog/CHANGELOG.md
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6347'
---

# Work Package Prompt: WP01 – Real `--mission` scoping for the three corpus-walking `migrate` commands

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

Give `spec-kitty migrate backfill-provenance`, `migrate charter-encoding` and
`migrate rebaseline-dossier-hashes` a **real, working `--mission`** (issue
#6347, the follow-up #5294 / PR #6345 deferred), without touching the
corpus-wide default and without un-scoping the two commands that have no
Mission concept.

Done means all of:

- Each of the three commands accepts `--mission <handle>` where `<handle>` is a
  `mission_id` (ULID), an 8-char `mid8`, or a slug, resolved through
  `specify_cli.cli.selector_resolution.resolve_mission_handle`.
- A scoped run touches **only** that Mission's files; every other Mission's
  fixture file is byte-identical afterwards (SC-001).
- `charter-encoding --mission` leaves `.kittify/charter/` byte-identical, creates
  no `.bak` sibling there, and reports the exclusion in **both** the human
  summary and the `--json` payload (SC-002).
- Omitting `--mission` reproduces today's corpus-wide behaviour exactly, and
  `rewrite-opposed-by` / `repin-hooks` still reject `--mission` with the
  unchanged message (SC-003).
- An unknown or ambiguous handle exits non-zero with the resolver's diagnostic
  and mutates nothing (FR-008).
- A second scoped run reports no changes (NFR-002).

## Context & Constraints

- Issue: #6347 (P2, milestone "4.0.0 release scope"). Predecessor: #5294, fixed
  in PR #6345, which made five `migrate` subcommands **reject** `--mission`
  rather than silently ignore it. Its changelog entry explicitly deferred real
  per-Mission scoping for the corpus-walking commands to a follow-up — this is it.
- Operator triage disposition on the issue (2026-10-19) settled the one open
  design question: `charter-encoding --mission` skips the global charter store
  with an explicit diagnostic; it must not mutate it, and must not fail the
  valid Mission-scoped operation merely because a global store exists.
- Mission spec: `kitty-specs/migrate-mission-scoping-01M68ZMH/spec.md`.
  Plan (design + rejected alternatives): `kitty-specs/migrate-mission-scoping-01M68ZMH/plan.md`.
  Discovery decisions D-01..D-05: `kitty-specs/migrate-mission-scoping-01M68ZMH/research.md`.
- Charter constraints that bind this WP: single canonical authority (reuse
  `resolve_mission_handle`, do not write a second parser); locality of change
  (edit only the command module, its three backends, the two test modules and
  the docs the change touches); tests as scaffold (assert the operator-visible
  contract, never implementation detail); no gate may be skipped, xfailed or
  relaxed (`C-004`).
- Do not add a dependency. Do not change `selector_resolution.py`.
- `tests/architectural/test_mission_resolver_walker_gate.py` allowlists
  `cli/commands/migrate/charter_encoding.py` and
  `cli/commands/migrate/backfill_provenance.py` as sanctioned whole-corpus
  walkers; keep their `kitty-specs` enumeration inside those modules so the
  allowlist entry stays honest.

## Branch Strategy

- **Strategy**: Mission planning artifacts were generated on `issue-6347-migrate-mission-scoping`; this WP's completed changes merge back into `issue-6347-migrate-mission-scoping`.
- **Planning base branch**: `issue-6347-migrate-mission-scoping`
- **Merge target branch**: `issue-6347-migrate-mission-scoping`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red CLI-surface tests in `tests/cli/test_mission_agnostic_flag.py`

- **Purpose**: Pin the two ends of the new CLI surface before touching it: the
  reject set shrinks to exactly the two commands with no Mission concept, and
  the three scoped commands declare a **visible** `--mission` that reaches the
  callback.
- **Steps**:
  1. Narrow `_REJECT_SET` to `("migrate", "rewrite-opposed-by")` and
     `("migrate", "repin-hooks")`; the existing parametrized reject tests then
     cover exactly the commands that must still refuse the flag.
  2. Add a `_MISSION_SCOPED_SET` tuple for the three scoped command paths and a
     test that each one is **not** a `CorpusWideCommand` and exposes `--mission`
     in `--help` (NFR-003), plus a test that `--mission` on each still exits 2
     only because the handle is unknown (`"not mission-scoped"` must not appear;
     the resolver's unknown-handle diagnostic must).
  3. Keep the tree-wide `test_every_leaf_command_accepts_mission` green by
     deriving its reject assertion from the narrowed `_REJECT_SET`.
- **Files**: `tests/cli/test_mission_agnostic_flag.py`.
- **Parallel?**: No — author first, together with T002, and watch it fail.
- **Notes**: Run from an empty tmp dir (`_invoke` already chdirs) so an
  un-rejected run can never touch the real repo.

### Subtask T002 – Red scoping-contract tests in `tests/migration/test_migrate_mission_scoping.py`

- **Purpose**: The feature's actual contract: isolation, handle forms,
  fail-closed resolution, unchanged defaults, idempotency, and the exclusion
  diagnostic. These must fail on the current tree (where all three exit 2).
- **Steps**:
  1. Build a reusable two-Mission fixture: `kitty-specs/<a>/` and
     `kitty-specs/<b>/`, each with (a) an `acceptance-matrix.json` carrying one
     non-pending negative invariant without `provenance_origin`, (b) a
     `charter/charter.md` with a non-UTF-8 byte, and (c) a
     `.kittify/dossiers/<slug>/snapshot-latest.json` recorded with a non-canonical
     hash for a small but indexable source tree. Add a project-level
     `.kittify/charter/charter.md` non-UTF-8 file for the global-store case.
     Resolve each Mission through a real `meta.json` with a `mission_id` so
     mission_id / mid8 / slug all resolve (`spec-kitty specify`-shaped meta is
     enough; assert resolution works rather than assuming it).
  2. `test_scoped_run_touches_only_the_target_mission[...]` — one test per
     command: run with `--mission <slug-of-a>`; assert the a-file changed and
     the b-file is byte-identical.
  3. `test_handle_forms_select_the_same_mission[...]` — mission_id, mid8 and
     slug scope identically (`--dry-run --json` is enough for equivalence).
  4. `test_unknown_handle_fails_closed[...]` — exit non-zero, no file in either
     Mission mutated, and the output names the unknown handle.
  5. `test_omitted_mission_keeps_the_corpus_wide_default[...]` — without
     `--mission`, both Missions are processed (the ratchet for FR-006).
  6. `test_dry_run_writes_nothing[...]` and
     `test_second_scoped_run_is_a_noop[...]` (NFR-002).
  7. `test_charter_encoding_mission_reports_global_store_exclusion` — assert the
     global charter file is byte-identical, has no `.bak` sibling, the JSON
     payload carries the exclusion flag, and the human output says so.
- **Files**: `tests/migration/test_migrate_mission_scoping.py` (new).
- **Parallel?**: No — author with T001.
- **Notes**: Model the rebaseline snapshot fixture on the existing helpers in
  `tests/dossier/test_rebaseline.py` (`Indexer` + `compute_snapshot`, then a
  bare-hex digest written back) rather than inventing a new snapshot shape.
  `rebaseline-dossier-hashes` resolves the project root with
  `locate_project_root()`, so chdir into the fixture project for that command.

### Subtask T003 – CLI: real `--mission`, one resolver call, no reject class

- **Purpose**: Turn the flag from "parsed then refused" into "resolved then
  applied", once, in the one place that owns argv.
- **Steps**:
  1. Add a module-level helper:
     `_scoped_mission_slug(mission: str | None, repo_root: Path, *, json_output: bool) -> str | None`
     returning `None` when `mission is None`, else
     `resolve_mission_handle(mission, repo_root, json_mode=json_output).mission_slug`
     (import lazily, like `backfill-merge-commit` does).
  2. On `backfill_provenance`, `charter_encoding` and `rebaseline_dossier_hashes`:
     remove `cls=CorpusWideCommand` and add
     `mission: Annotated[str | None, typer.Option(_MISSION_FLAG, help=_MISSION_HELP, metavar=_MISSION_METAVAR)] = None`
     — the visible option, so `--help` advertises it (NFR-003).
  3. Thread the resolved slug into each backend call (T004..T006).
  4. Update each command's docstring: what `--mission` narrows for that command,
     the accepted handle forms, the corpus-wide default, and any exit-code
     change. Add a `--mission` usage example to each.
- **Files**: `src/specify_cli/cli/commands/migrate_cmd.py`.
- **Parallel?**: No — T004..T006 depend on this parameter shape.
- **Notes**: For `charter-encoding` and `backfill-provenance` the resolver root
  is `project_root.resolve()` (the same `--project-root` the walk uses), not
  `locate_project_root()`; for `rebaseline-dossier-hashes` it is the existing
  `repo_root = locate_project_root()`. Leave `CorpusWideCommand` itself and
  `rewrite-opposed-by` / `repin-hooks` untouched.

### Subtask T004 – `backfill_provenance.py`: scoped matrix discovery

- **Purpose**: Narrow the mission loop to one Mission without losing the
  coordination-aware read.
- **Steps**:
  1. `_collect_matrix_paths(repo_root: Path, mission_slug: str | None = None)`:
     iterate only `specs_dir / mission_slug` when scoped (and return `[]` when it
     is not a directory); keep the existing
     `placement_seam(repo_root, mission_dir.name).read_dir(MissionArtifactKind.ACCEPTANCE_MATRIX)`
     call and its fallback for every candidate.
  2. `run_backfill_provenance_migration(repo_root, *, dry_run=False, mission_slug=None)`
     passes it through and records the scope on `BackfillSummary`
     (`mission_slug: str | None = None`).
- **Files**: `src/specify_cli/cli/commands/migrate/backfill_provenance.py`.
- **Parallel?**: Yes — disjoint from T005/T006.
- **Notes**: Update the module docstring's "walks every on-disk acceptance
  matrix" sentence to state the scoped form; do not change the transaction,
  the stamping logic, or the AM-4 no-archive posture.

### Subtask T005 – `charter_encoding.py`: scoped charter discovery + exclusion diagnostic

- **Purpose**: Scope to one Mission's charter content and make the deliberate
  omission of the global store observable instead of silent.
- **Steps**:
  1. `_collect_charter_files(project_root: Path, mission_slug: str | None = None)`:
     when scoped, scan only `kitty-specs/<mission_slug>/charter/*.{yaml,md,txt}`
     and skip the `.kittify/charter/` glob entirely.
  2. `_ScanSummary` gains `mission_slug: str | None = None` and
     `global_store_excluded: bool = False`.
  3. `run_charter_encoding_migration(..., mission_slug: str | None = None)` sets
     both on the summary (exclusion is True whenever a scope was supplied — the
     store is excluded whether or not it exists), and keeps the existing
     exit-code rule over the **scoped** files only.
  4. `_emit_json_summary` adds `"mission": summary.mission_slug` and
     `"global_store_excluded": summary.global_store_excluded`;
     `_emit_human_summary` prints a line naming the exclusion and the path that
     was left alone (e.g. `.kittify/charter/ (excluded by --mission; unchanged)`).
- **Files**: `src/specify_cli/cli/commands/migrate/charter_encoding.py`.
- **Parallel?**: Yes.
- **Notes**: Do not add a prompt on the scoped path; the exclusion is reported,
  never asked about. Keep the JSON payload's existing keys and `sort_keys=True`.

### Subtask T006 – `dossier/rebaseline.py`: scoped recorded-snapshot discovery

- **Purpose**: Scope the backlog sweep to one Mission without turning discovery
  into a read of every snapshot in the corpus.
- **Steps**:
  1. Add
     `_snapshot_belongs_to_mission(snapshot_path: Path, mission_slug: str) -> bool`
     matching **path-derived identity**: the dossier directory name
     (`snapshot_path.parent.name`) or the owning source directory
     (`_resolve_feature_dir(snapshot_path).name`, guarded against a too-shallow
     path). Document why the recorded `mission_slug` field is not consulted
     (reading every candidate would violate the scoped-read guarantee).
  2. `iter_recorded_snapshot_files(root: Path, *, mission_slug: str | None = None)`
     applies it to the existing glob; `rebaseline_recorded_snapshots(root, *, dry_run=False, mission_slug=None)`
     passes it through.
- **Files**: `src/specify_cli/dossier/rebaseline.py`.
- **Parallel?**: Yes.
- **Notes**: `_resolve_feature_dir` is `parents[3]` — an IndexError is possible
  for a hand-built shallow path; handle it as "no source dir signal" rather than
  letting it escape. Do not change `rebaseline_snapshot_file`.

### Subtask T007 – Report the scope, and update the docs the change touches

- **Purpose**: A scoped run must be visible in its own output, and the
  user-facing docs/changelog must describe it.
- **Steps**:
  1. `backfill-provenance`: add `"mission": summary.mission_slug` to the JSON
     payload and a `Scope` line to the human summary.
  2. `rebaseline-dossier-hashes`: add `"mission"` to the JSON payload and name
     the scope in the human summary line.
  3. `docs/changelog/CHANGELOG.md`: an `[Unreleased]` entry — bold impact-first
     lead with `(#6347)`, then before/after, under 1,200 characters. Say
     explicitly that the two non-Mission commands still reject the flag.
  4. `docs/api/cli-commands.md`: regenerate only the section(s) this diff
     changes, then verify with
     `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0).
- **Files**: `src/specify_cli/cli/commands/migrate_cmd.py`,
  `docs/changelog/CHANGELOG.md`, `docs/api/cli-commands.md`.
- **Parallel?**: No — after T003..T006.
- **Notes**: The brief warns that the installed CLI's global asset cache is
  shared with other agents and a **full** reference rebuild can be
  non-deterministic; a partial, verifiable regeneration beats a churny full one.
  If a full rebuild is unavoidable and the result looks non-deterministic, say
  so in the PR's `## Deferred` section instead of committing churn.

## Test Strategy

- Red first: T001/T002 authored before the implementation, and run once to
  confirm they fail for the right reason (the current exit-2 reject).
- Targeted, not full-sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`):

```
uv run pytest tests/migration/test_migrate_mission_scoping.py -q
uv run pytest tests/cli/test_mission_agnostic_flag.py -q
uv run pytest tests/dossier/test_rebaseline.py -q
uv run pytest tests/migration/test_backfill_provenance.py tests/migration/test_verdict_provenance_backfill.py -q
uv run pytest tests/migrate/test_charter_encoding_migration.py -q
uv run pytest tests/architectural/test_mission_resolver_walker_gate.py -q
uv run ruff check <changed files>
uv run mypy <changed files>
```

- Fixtures: `tmp_path` projects; no network; no reliance on machine paths.
- Add tests only where they guard the contract above — no tautological or
  wiring-only assertions, no line-pinned ratchets (DIRECTIVE_041).

## Risks & Mitigations

- **Declared-but-ignored flag** (the exact defect #5294 closed): the T002
  isolation tests fail if the walk stays corpus-wide.
- **Over-narrowed `backfill-provenance`** missing coordination-homed matrices:
  T004 keeps the `placement_seam` read.
- **`charter-encoding` failing a valid scoped run** over a pre-existing global
  store: exit code is computed from scoped files only; T002 asserts the store
  is untouched and the run exits 0.
- **`rebaseline` reading the corpus to filter**: path-derived identity only.
- **Docs churn** from a full CLI-reference rebuild: regenerate the changed
  section, verify with the freshness check, and defer with a reason if the
  rebuild is non-deterministic.

## Review Guidance

- Confirm each of the three commands genuinely narrows at its discovery seam
  (not a post-hoc filter of a full corpus walk), and that `--mission` is
  resolved exactly once through `resolve_mission_handle`.
- Confirm `charter-encoding --mission` cannot reach `.kittify/charter/`, and
  that the exclusion appears in both renderings.
- Confirm the reject set is now exactly `rewrite-opposed-by` and `repin-hooks`,
  that `--help` advertises `--mission` only on the three scoped commands, and
  that no test was skipped, xfailed or relaxed (`C-004`).
- Confirm the unscoped paths are behaviourally untouched (diff the discovery
  functions: the `None` branch must be the previous code path).
- Confirm no pointer/handle parsing was added to a backend (`C-002`).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
