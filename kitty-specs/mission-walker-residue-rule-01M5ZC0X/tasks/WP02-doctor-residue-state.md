---
work_package_id: WP02
title: 'Doctor walkers: residue state and mission-type skip'
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-002
- C-004
planning_base_branch: issue-5875-mission-walker-is-mission-dir
merge_target_branch: issue-5875-mission-walker-is-mission-dir
branch_strategy: Planning artifacts for this mission were generated on issue-5875-mission-walker-is-mission-dir. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5875-mission-walker-is-mission-dir unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Doctor
history:
- at: '2026-10-27T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/identity_audit.py
- src/specify_cli/cli/commands/_identity_audit.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_mission_type_audit.py
- tests/doctor/test_identity_audit.py
- tests/specify_cli/cli/commands/test_identity_audit.py
- tests/specify_cli/cli/commands/test_doctor_mission_type.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Doctor walkers: residue state and mission-type skip

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

`doctor identity` classifies every `kitty-specs/` directory child that `is_selectable_mission_dir` (WP01) rejects as a new **`residue`** state. That state gets its own count, path section, JSON value, `--fail-on` value and one remedy. Residue does not appear in the duplicate-prefix or ambiguous-selector reports. `doctor mission-type` skips residue. These are operator decisions D3/D4 in `../research.md` §4. The contract is in `../contracts/doctor-identity-residue.md` and the table in `../data-model.md`.

## Context & Constraints

- Read `../spec.md` (FR-003..FR-006, NFR-002, C-002..C-004), `../plan.md` ("doctor identity residue state", "Remedy text") and `../data-model.md`.
- `classify_mission` keeps its contract (C-004). It is also used by `src/specify_cli/audit/identity_adapter.py`. `residue` is set only by the walk.
- The three walkers are allowlisted raw corpus walks (`tests/architectural/test_mission_resolver_walker_gate.py`). Keep them raw walks in these files.
- `doctor identity` is a read-only reporter, so it probes with `tracked_mission_paths`: a broken index raises, the same posture as the audit engine. `doctor mission-type` may use either. Prefer `probe_tracked_mission_paths` there, since its job is mission types, not git health. Both probe lazily, at most once per walk, and only when a child lacks an identity.
- Import `is_selectable_mission_dir` from `specify_cli.context.mission_resolver`. A function-local import is fine if a module-level one creates a cycle. Run `python -c "import specify_cli.status"` to check.
- No new command or migration. Complexity ≤ 15. No new suppressions. ruff, `ruff format --check --force-exclude` and mypy must be clean on touched files.

## Branch Strategy

Planning branch `issue-5875-mission-walker-is-mission-dir`, final merge target the same branch. The topology is `single_branch`: work in the repository root checkout, where WP01 has already landed. Commit on that branch. Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push.

## Subtasks & Detailed Guidance

### Subtask T006 – Tidy-first walk helper (its OWN commit, behaviour-preserving)

Extract the duplicated walk in `audit_repo`, `find_duplicate_prefixes` (`status/identity_audit.py`) and `audit_mission_types` (`cli/commands/_mission_type_audit.py`) into one helper in `status/identity_audit.py`, for example `iter_kitty_specs_children(repo_root) -> list[Path]`. It returns the sorted directory children, uses `safe_is_dir` on `kitty-specs/` and on each entry, returns `[]` on an `OSError` while listing, and skips unstattable entries. Exact current semantics, including `#3194`. If it is cross-module, expose it the way this package exposes things (check `status/__init__.py` and the dead-symbol gate `tests/architectural/test_no_dead_symbols*.py`: a public symbol with exactly one consumer may need care). Run the existing tests unchanged: `uv run --frozen pytest tests/doctor tests/specify_cli/cli/commands/test_identity_audit.py tests/specify_cli/cli/commands/test_doctor_mission_type.py tests/audit -q`. **Commit this alone**: `refactor(doctor): share one kitty-specs walk across the identity and mission-type audits (#5875)`.

### Subtask T010 – Red-first tests (write before T007–T009)

In the owned test files, add git-repo fixtures covering: a committed Mission, a spec.md-only folder (untracked, and tracked), an untracked id-less `meta.json`, a tracked id-less `meta.json` (stays `orphan`/`legacy`), and a lock-only folder. Assert:
- `audit_repo` gives `residue` for the rejected ones and unchanged states for Missions. `summarize(...)["counts"]["residue"]` is correct, and `"residue_paths"` lists them.
- Residue sharing a 3-digit prefix with a Mission does not appear in `find_duplicate_prefixes`, and residue does not appear in `find_ambiguous_selectors`.
- CLI `doctor identity --json`: `summary.residue`, a row with `state: "residue"`, and `residue_remedy` present only when residue exists. `--fail-on residue` exits 1. Human output shows the residue section and the remedy text. `--mission <residue-slug>` reports `residue`.
- `doctor mission-type` (`audit_mission_types` and the CLI): residue is absent, and a spec.md-only folder is never `typeless`.
- NFR-001/NFR-002: no git probe when every child has an identity (monkeypatch the probe to raise).
Confirm they FAIL before T007–T009 and log it.

### Subtask T007 – `residue` state

- `IdentityStateLabel` gains `"residue"`. Update the module docstring: the four Mission states plus `residue` for non-Missions. NFR-002's "no subprocesses" becomes "at most one batch git ls-files".
- `audit_repo`: for each child from the T006 helper, `residue` when the predicate rejects it (`IdentityState(path, slug, None, None, "residue", error=None)`), else `classify_mission(entry)`.
- `summarize`: zero-fill `residue`, add `residue_paths`.
- `find_duplicate_prefixes` and `find_ambiguous_selectors`: exclude residue.

### Subtask T008 – Renderer and CLI

`cli/commands/_identity_audit.py`:
- The summary table iterates the 5 states (`residue` styled `[yellow]`).
- `_print_identity_path_sections` gains a "Residue folders (not Missions; Mission selection does not list them):" section, then prints the remedy once. Keep each helper ≤ 15 CC (extract a helper if needed).
- One module constant `RESIDUE_REMEDY` holds the text from `../plan.md` "Remedy text", word for word. It is separate from `RESIDUE_NOTICE`, which you must NOT edit.
- JSON: `summary` carries `residue`. Add a top-level `"residue_remedy"` only when a residue row exists.
- `_scope_to_mission` fallback path (a placement-seam dir not in the walk): apply the same predicate so that `--mission <residue>` reports `residue`.
`cli/commands/doctor.py` `identity` command: `--fail-on` help and the docstring list `residue` with a one-line meaning.

### Subtask T009 – `doctor mission-type` skips residue

`audit_mission_types`: skip children the predicate rejects (lazy probe). Update its docstring: it audits exactly what Mission selection lists, and residue is reported by `doctor identity`.

## Test Strategy

Red first (T010). Then: `uv run --frozen pytest tests/doctor tests/status tests/audit tests/specify_cli/cli/commands/test_identity_audit.py tests/specify_cli/cli/commands/test_doctor_mission_type.py tests/architectural/test_mission_resolver_walker_gate.py -q`, the dead-symbol gate if you added a public symbol, and `make test-fast`. Record commands and counts in the Activity Log.

## Risks & Mitigations

- JSON consumers: the change is additive only. `audit/identity_adapter.py` is unaffected (it uses `classify_mission`). Run `tests/audit`.
- An import cycle: use a function-local import.

## Review Guidance

Reviewer: confirm T006 is its own behaviour-preserving commit, that `classify_mission` is unchanged, that the remedy text matches the plan exactly, that `RESIDUE_NOTICE` is untouched, that collisions exclude residue, that the probe is lazy and runs once, and that complexity is ≤ 15.

## Activity Log

- 2026-10-27T19:20:00Z – system – Prompt created.
- 2026-10-27T21:30:00Z – claude (python-pedro, implementer) – T006–T010 done.
  - T006 (`bcbfec63`, behaviour-preserving, own commit): `iter_kitty_specs_children(repo_root)` in `status/identity_audit.py`, shared by `audit_repo`, `find_duplicate_prefixes` and `audit_mission_types`. Existing tests unchanged and green: `pytest tests/doctor tests/specify_cli/cli/commands/test_identity_audit.py tests/specify_cli/cli/commands/test_doctor_mission_type.py tests/audit tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_no_dead_symbols.py -n 4 --dist loadfile` → 433 passed, 3 skipped. One nuance: `audit_mission_types` now returns `[]` before resolving the roster when the walk yields no directory (it used to resolve it for an existing-but-empty `kitty-specs/`); the result is identical.
  - T010 red-first: 24 new tests across the three owned test files; before T007–T009, 21 failed and 3 passed (the two NFR-001 no-git guards and the no-residue-no-remedy render, which pass vacuously on the old code by design).
  - T007–T009 (`f8ff78e2`): `residue` state; `classify_walk_entry` + `ReporterTrackedPaths` (lazy, once-per-walk memo of the unhardened `tracked_mission_paths`, so a broken index raises); `summarize` zero-fills `residue` and adds `residue_paths`; collisions exclude residue; renderer section + `RESIDUE_REMEDY` (verbatim from plan.md, checked by string comparison); `residue_remedy` JSON key only with residue; `--fail-on` help/docstring; `_scope_to_mission` fallback applies the rule; `doctor mission-type` skips residue via `LazyTrackedMissionPaths`. `classify_mission` and `RESIDUE_NOTICE` untouched.
  - Design note: `ReporterTrackedPaths` is not a subclass of `LazyTrackedMissionPaths`, because narrow-file mypy (`specify_cli.*` follow_imports=skip) sees the base as `Any` and refuses the subclass. Laziness instead comes from `_needs_git`: with an empty tracked set the public predicate accepts exactly a child whose meta.json carries a mission_id, so the memo is read only for an id-less meta.json.
  - Tests: owned files → 117 passed, 2 skipped. `pytest tests/doctor tests/status tests/audit tests/specify_cli/cli/commands/test_identity_audit.py tests/specify_cli/cli/commands/test_doctor_mission_type.py tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_no_dead_symbols.py -q -n 4 --dist loadfile` → 2057 passed, 9 skipped. `make test-fast` → 2476 passed, 6 skipped. Wider callers (`tests/cli_gate/test_doctor_modes.py`, meta fail-closed census/degradation, `test_doctor_cli_surface_golden.py`, `test_meta_read_permission_denied_regression.py`, `tests/integration/test_colliding_mission_flow.py`, `test_json_contract_enumeration.py`, `test_timing_coverage_invariant.py`, `tests/consolidation/test_mid8_embedded_preflight.py`, `tests/core/test_mission_create_protected_single_branch.py`, `tests/specify_cli/migration/test_mission_state_identity.py`, `test_cutover_doctor.py`, `tests/context`) → 467 passed after the golden update. ruff, `ruff format --check --force-exclude`, C901 and mypy clean on touched files (the one mypy error in `doctor.py:1266` is pre-existing, at line 1264 on the base).
  - Out-of-map edit: `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` — the `doctor identity --help` snapshot pins the docstring and `--fail-on` help this WP was told to change; updated to the new text.
- 2026-10-27T23:40:00Z – claude (python-pedro, implementer) – Review cycle 1 fix (`293bfe3e`).
  - Blocker: the audit engine consumed the residue-aware walk and lost `IDENTITY_MISSING` / `DUPLICATE_PREFIX` / `AMBIGUOUS_SELECTOR` for spec.md-only folders. `audit_repo` / `find_duplicate_prefixes` now take keyword-only `residue_aware: bool = False` (pre-#5875 contract by default); only `_identity_audit.run_identity_audit` opts in (`_scope_to_mission`'s fallback already uses `classify_walk_entry`). Other `src/` callers: only `audit/engine.py` (left on the default, with a comment saying why). `find_ambiguous_selectors` keeps its residue skip, a no-op for the engine because its states never carry `residue`.
  - Red-first: `tests/audit/test_engine_keeps_its_mission_rule.py` (2 tests: committed `001-spec-tracked` beside `001-mission`, and a non-git `002-spec-only`; exact findings taken from the base source `673e5664` run in a scratch copy) → 2 failed on HEAD `1cc3441b`, 2 passed after the fix. The reviewer repro's engine output is byte-identical between base and the fixed tree (diffed).
  - Nits: (1) out-of-map, `tests/architectural/test_mission_resolver_walker_gate.py`: removed the stale `_mission_type_audit.py` allowlist entry (gate passes without it). (2) `test_residue_remedy_is_the_planned_text` compares the full text. (4) `classify_walk_entry` reads meta.json once in the identity-bearing case (`_needs_git` removed). (5) the three new `# type: ignore` in `test_summarize_counts_and_lists_residue` replaced by `isinstance` asserts. Out-of-map comment-only edit in `src/specify_cli/audit/engine.py` (FR-008 note at the `audit_repo` call).
  - Owned-test stubs of `audit_repo` / `find_duplicate_prefixes` now accept `**_kw`.
  - Tests: `pytest tests/audit tests/doctor tests/status tests/cli_gate/test_doctor_modes.py tests/specify_cli/cli/commands/test_identity_audit.py tests/specify_cli/cli/commands/test_doctor_mission_type.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_no_dead_symbols.py -q -n 4 --dist loadfile` → 2139 passed, 9 skipped, 3 failed (the positional-only stubs), then `tests/specify_cli/cli/commands/test_identity_audit.py` → 43 passed after the stub fix. `make test-fast` → 2476 passed, 6 skipped. ruff, `ruff format --check --force-exclude`, mypy clean on touched files.
