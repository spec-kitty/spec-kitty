---
work_package_id: WP01
title: One authority for the pack root and the containment verdict
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
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - One atomic refactor
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/drg/org_pack_loader.py
- src/charter/offering/assets/repository.py
- src/charter/offering/assets/__init__.py
- src/charter/drg.py
- src/charter/activation/drg_activation.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_profile_health_render.py
- tests/charter_offering/drg/test_org_body_path_escapes.py
- tests/charter_offering/assets/test_org_asset_path_escapes.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py
- tests/architectural/test_charter_facades_reexport_offering.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One authority for the pack root and the containment verdict

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(`python-pedro`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile show python-pedro` and follow it from
there.

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for the `review_ref` field before starting. If review feedback
exists, it is your TODO list and must be addressed before this package is complete. Record what you
changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

An org DRG fragment already knows the effective pack root it was loaded from; after this package it
**carries** that root, and the two offering containment predicates are fragment-only functions that
read it. No second lookup, no serialized-surface drift, and a loud typed refusal when the root is
not there.

This is one atomic refactor (review finding F1 on the earlier two-package split): the offering
signature change and the doctor/activation changes must land together, or `doctor charter-packs`
is broken between them.

Done when:

- `OrgDRGFragment` exposed by `load_org_pack` reports the same effective root (`subdir` applied)
  that the loader received, through a typed accessor.
- `OrgDRGFragment.model_dump()`, `model_dump_json()` and `model_json_schema()` are byte-identical
  to before the change (the carried root is not serialized).
- `find_body_path_escapes(fragment)` and `find_asset_path_escapes(fragment)` each take one argument
  and report exactly the escapes they reported before, in the same order, with the same messages.
- A fragment rebuilt from a dump has no root: reading it raises `OrgPackRootUnavailableError`
  naming the pack, never judges containment against a default path.
- `charter.drg` re-exports the two predicates and the new error, with live callers.
- One `_collect_org_layer_data` run and one `_render_org_layer_section` run each read the pack
  registry exactly **once** (three before this mission), inside `load_org_drg`.
- `charter.activation.drg_activation` no longer defines or exports `find_org_body_path_escapes`,
  `find_org_asset_path_escapes` or `_org_pack_roots_by_name`.
- `doctor charter-packs` produces the same findings, messages, JSON keys and exit codes as before,
  and the activation-seam gate passes with its baseline file unchanged.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6731 (follow-up to #6418). Mission:
  `kitty-specs/org-drg-fragment-pack-root-01M66YJG/` — read `spec.md` and `plan.md` first.
- **Current code**: `src/charter/offering/drg/org_pack_loader.py` defines `OrgDRGFragment` (pydantic
  `BaseModel`, `extra="forbid"`) and `find_body_path_escapes(fragment, pack_root)`.
  `src/charter/offering/assets/repository.py` defines `find_asset_path_escapes(pack, pack_root)`.
  `src/charter/offering/drg/org_pack_loader.py`'s `load_org_pack(pack_name, pack_root, layer_index)`
  already receives the effective root and writes `str(pack_root)` into `source_ref`.
- **Charter**: single canonical authority (one pack→root fact); offering layer must not import
  `charter` or `specify_cli` (see the module docstring's hierarchy). `charter.offering.assets`
  already imports `charter.offering.drg.org_pack_config`, so importing the fragment type from
  `charter.offering.drg.org_pack_loader` is the sanctioned sibling direction — resolved decision
  DM `01M66YN5CCFXQF4DBWDSVNSJBG` (read
  `kitty-specs/org-drg-fragment-pack-root-01M66YJG/decisions/`).
- **Do not** touch `packs/built-in/` or `packs/internal/` (fetched trees). Do not change pack
  loading, merge, or validation semantics. Do not add the root to the serialized model.
- **Do not** edit `charter_activation_boundary_baseline.yaml`. Both doctor files keep importing
  `load_org_drg` from `charter.activation.drg_activation`, so their baseline rows stay accurate; no
  row is added or drained. If the gate disagrees, the import change is wrong — fix the import, not
  the baseline.
- Keep the two `except Exception` channels and their exact message prefixes
  (`org-layer body_path check failed:`, `org-layer asset path check failed:`), and the human half's
  `not checked` rendering.

## Branch Strategy

- **Strategy**: this mission uses `single_branch` topology; planning artifacts and implementation
  commit on `kitty/mission-org-drg-fragment-pack-root-01M66YJG`, and completed changes merge back
  into that branch.
- **Planning base branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG`
- **Merge target branch**: `kitty/mission-org-drg-fragment-pack-root-01M66YJG`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them by
> hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red tests: the carried root and the fragment-only body predicate

- **Purpose**: Prove the two missing behaviours before writing them (ATDD-first, DIRECTIVE_034).
- **Steps**:
  1. In `tests/charter_offering/drg/test_org_body_path_escapes.py`, call
     `find_body_path_escapes(load_org_pack("acme", pack_root, 1))` with **one** argument. Every
     existing escape/containment case keeps its assertions; this alone must fail today
     (`TypeError`: the predicate needs `pack_root`).
  2. Add a test that `load_org_pack("acme", pack_root, 1).pack_root` equals the effective root, and
     a subdir case proving it is the effective root and not the checkout (reuse the registry +
     `subdir` fixture shape already in the module).
  3. Add a test that `fragment.model_dump()` has no `pack_root` key and that
     `OrgDRGFragment.model_json_schema()["properties"]` has no `pack_root` — this is the
     serialized-surface ratchet (NFR-003). Pair it with a positive control: `pack_name` **is** in
     the dump, so the probe can see a field when one is there.
  4. Add a test that `model_copy()` keeps the root, and that
     `OrgDRGFragment.model_validate(fragment.model_dump())` then `.pack_root` raises
     `OrgPackRootUnavailableError` (match the pack name and a readable message).
  5. Rewrite the module docstring: the wrapper is gone; the fragment carries the root. Keep the
     historical "#6418" framing of what is being refused.
- **Files**: `tests/charter_offering/drg/test_org_body_path_escapes.py`
- **Parallel?**: Yes (independent of T002).
- **Notes**: Keep the existing subdir/symlink/shadowing scenarios — they are the effective-root
  contract. Only the call shape (and the registry-aware test names, which no longer describe a
  registry read) changes.

### Subtask T002 – Red tests: the fragment-only asset predicate

- **Purpose**: Same red-first proof for the asset side.
- **Steps**:
  1. In `tests/charter_offering/assets/test_org_asset_path_escapes.py`, call
     `find_asset_path_escapes(load_org_pack("acme", pack_root, 1))` with **one** argument; keep
     every existing assertion (message text, code, ordering, NUL byte, symlinked `assets/`,
     shadowed ids, built-in items never judged).
  2. Add the FR-007 case for the asset predicate: a fragment rebuilt from `model_dump()` raises
     `OrgPackRootUnavailableError` rather than resolving against anything.
  3. Update the module docstring the same way as T001.
- **Files**: `tests/charter_offering/assets/test_org_asset_path_escapes.py`
- **Parallel?**: Yes.
- **Notes**: The `_make_pack` helper writes a fragment with no nodes; use `load_org_pack` to build
  the fragment so the test exercises the real loader (do not hand-construct a fragment and stamp a
  root privately in the test — that would test the test).

### Subtask T003 – Fragment root carriage and the body predicate

- **Purpose**: Implement FR-001, FR-002, FR-003 and FR-007 for the node half.
- **Steps**:
  1. Add `OrgPackRootUnavailableError(RuntimeError)` in `org_pack_loader.py`. Constructor takes the
     pack name; message names the pack and says the fragment carries no effective pack root because
     it was not produced by `load_org_pack` (a dump/reload or a hand-built instance). Add it to
     `__all__`.
  2. Add `_pack_root: Path | None = PrivateAttr(default=None)` to `OrgDRGFragment` (import
     `PrivateAttr` from pydantic) and a `pack_root` property that returns it or raises the typed
     error. Document: not serialized, survives `model_copy`, set by `load_org_pack`.
  3. In `load_org_pack`, stamp `fragment._pack_root = pack_root` at the single success return (after
     the discovered-node append), with a one-line comment saying why the root rides here.
  4. Change `find_body_path_escapes` to `find_body_path_escapes(fragment: OrgDRGFragment)` and read
     `fragment.pack_root`. Keep every containment rule and the "no target is opened or read"
     guarantee; update the docstring's *pack_root must be…* paragraph to describe the carried root
     and the typed refusal.
- **Files**: `src/charter/offering/drg/org_pack_loader.py`
- **Parallel?**: No.
- **Notes**: One stamp point. If you find yourself threading `pack_root` through a second helper,
  stop — that is the second authority this mission removes. Do not add a default of
  `Path(".")` or any fallback.

### Subtask T004 – The asset predicate takes the fragment

- **Purpose**: Same collapse for the asset half.
- **Steps**:
  1. In `charter/offering/assets/repository.py`, import `OrgDRGFragment` from
     `charter.offering.drg.org_pack_loader` and change
     `find_asset_path_escapes(fragment: OrgDRGFragment)`, reading `fragment.pack_name` and
     `fragment.pack_root`.
  2. Update the docstring's *pack_root must be the pack's effective root* paragraph; keep the
     anchor rule (`org_dirs=[<root>/assets]`), the org-provenance filter, the
     silenced-load-warnings behaviour, and the `assets/`-symlink rule untouched.
  3. Confirm the module still imports cleanly (no cycle): `python -c "import charter.offering.assets, charter.offering.drg.org_pack_loader"`.
- **Files**: `src/charter/offering/assets/repository.py` (and `__init__.py` only if an export list
  needs updating — the names do not change)
- **Parallel?**: No.
- **Notes**: Do not move the asset logic into the drg module; the asset repository stays the anchor
  authority.

### Subtask T005 – `charter.drg` facade re-exports

- **Purpose**: Give the runtime one offering door to both predicates (FR-003/FR-005 groundwork).
- **Steps**:
  1. In `src/charter/drg.py`, import and `__all__`-export `find_body_path_escapes`,
     `find_asset_path_escapes` and `OrgPackRootUnavailableError`, with a short comment saying they
     are the containment predicates the doctor's two halves call.
  2. Check `tests/architectural/test_no_dead_symbols.py` expectations: each new public name needs a
     live non-test caller from `src/`. T009/T010 wire the doctor call sites, and the
     `charter.activation` wrappers still call the predicates until T008 deletes them, so run the
     gate after T012 rather than adding a fake caller. The `charter.drg` facade also needs rows in
     `tests/architectural/test_charter_facades_reexport_offering.py`'s `_FACADE_TABLE`
     (the inverse-containment gate requires an identity contract for every advertised
     offering-origin symbol) — do it in this WP and record it as an out-of-map edit.
- **Files**: `src/charter/drg.py`
- **Parallel?**: No.
- **Notes**: Keep the file's existing ordering conventions; it is a pure re-export module.

### Subtask T006 – Verification

- **Purpose**: Prove the package on its own.
- **Steps**:
  1. `uv run --frozen pytest tests/charter_offering/drg/test_org_body_path_escapes.py tests/charter_offering/assets/test_org_asset_path_escapes.py -q`
  2. `uv run --frozen pytest tests/charter/test_org_drg_loader.py tests/charter_offering -q` (regression around the fragment model)
  3. `uv run --frozen ruff check src/charter/offering/drg/org_pack_loader.py src/charter/offering/assets/repository.py src/charter/drg.py tests/charter_offering/drg/test_org_body_path_escapes.py tests/charter_offering/assets/test_org_asset_path_escapes.py` and `uv run --frozen ruff format --check` on the same files
  4. `uv run --frozen mypy src/charter/offering/drg/org_pack_loader.py src/charter/offering/assets/repository.py src/charter/drg.py` (match the repo's configured invocation; a passing test runner is not a substitute)
  5. Record the results with `spec-kitty agent tasks add-history WP01 --note "..."`.
- **Files**: none (verification only)
- **Parallel?**: No.
- **Notes**: Do not run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

### Subtask T007 – Red counting test: one registry read per doctor run

- **Purpose**: Pin the acceptance criterion itself (FR-006 / NFR-001 / SC-001), red before the fix.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`, add a test that
     monkeypatches `charter.activation.drg_activation.load_pack_registry` with a counting wrapper
     (delegate to the real function), runs `_collect_org_layer_data(tmp_repo_with_org_pack)`, and
     asserts `len(calls) == 1`.
  2. Add the same count assertion for `_render_org_layer_section` (use the module's `_render`).
  3. Add a positive control in the same test: assert the real registry read happened (`calls`
     non-empty and `result["configured_packs"]` names the pack), so a broken probe cannot pass by
     counting zero calls.
  4. Run it: it must fail with 3 reads before T008–T010.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`
- **Parallel?**: No.
- **Notes**: Count reads, not time. Do not weaken the assertion to `<= 2`.

### Subtask T008 – Delete the wrappers and the re-read

- **Purpose**: FR-004. Remove the second authority and its home.
- **Steps**:
  1. Delete `find_org_body_path_escapes`, `find_org_asset_path_escapes` and
     `_org_pack_roots_by_name` from `src/charter/activation/drg_activation.py`.
  2. Drop them from `__all__`, and drop the imports that become unused (`Sequence`,
     `AssetPathEscape`, `BodyPathEscape`, `find_asset_path_escapes`, `find_body_path_escapes` —
     verify each; `load_org_drg` still needs `load_pack_registry`).
  3. Update the module docstring's "Provides:" list so it describes what the module actually
     provides now.
- **Files**: `src/charter/activation/drg_activation.py`
- **Parallel?**: No.
- **Notes**: `load_org_drg` itself is unchanged — it already reads the registry once and stamps the
  fragments.

### Subtask T009 – JSON half onto the facade

- **Purpose**: FR-005 for `_collect_org_layer_data`.
- **Steps**:
  1. In `_record_body_path_escapes` and `_record_asset_path_escapes`
     (`src/specify_cli/cli/commands/_charter_pack_collect.py`), import the predicate from
     `charter.drg` instead of `charter.activation.drg_activation`.
  2. Aggregate per fragment in fragment order:
     `escapes = [escape for fragment in fragments for escape in find_body_path_escapes(fragment)]`
     (and the asset equivalent), inside the existing `try`.
  3. Drop the `repo_root` parameter only if it becomes unused, and then update the two call sites
     in `_collect_org_layer_data`.
- **Files**: `src/specify_cli/cli/commands/_charter_pack_collect.py`
- **Parallel?**: Yes (independent of T010).
- **Notes**: Finding order must stay fragment order — the JSON arrays are compared by tests.

### Subtask T010 – Human half onto the facade

- **Purpose**: FR-005 for `_render_org_layer_section`'s two helpers.
- **Steps**:
  1. In `_render_org_body_path_escapes` and `_render_org_asset_path_escapes`
     (`src/specify_cli/cli/commands/_profile_health_render.py`), import from `charter.drg` and
     aggregate the same way.
  2. Keep the "not checked" branch and its exception text verbatim.
- **Files**: `src/specify_cli/cli/commands/_profile_health_render.py`
- **Parallel?**: Yes.
- **Notes**: The two halves must stay parallel in shape; a reviewer will diff them against each
  other.

### Subtask T011 – Re-point the doctor tests and assert the absence

- **Purpose**: The pinned refusals must keep pinning the *live* seam.
- **Steps**:
  1. Re-point the four `monkeypatch.setattr(drg_activation, "find_org_…_escapes", _boom)` targets
     at the `charter.drg` predicate names, so the "a check that could not RUN is reported" tests
     still inject a crash into the path the doctor actually calls.
  2. Add a test asserting `charter.activation.drg_activation` has no `find_org_body_path_escapes`,
     `find_org_asset_path_escapes` or `_org_pack_roots_by_name` attribute, with `load_org_drg` as
     the positive control (the probe can see a symbol that is there).
  3. Keep every existing assertion in the module unchanged: RC matrix, message text, JSON shape,
     truncation tails, `fine-logo` not named, etc.
- **Files**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py`
- **Parallel?**: No.
- **Notes**: A monkeypatch of a deleted symbol silently "passes" because setattr on a module
  creates the attribute — that is why (2) matters.

### Subtask T012 – Verification

- **Purpose**: Prove the whole deliverable, including the architectural ratchets.
- **Steps**:
  1. `uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py tests/charter_offering/drg/test_org_body_path_escapes.py tests/charter_offering/assets/test_org_asset_path_escapes.py tests/charter_offering/drg/test_org_pack_node_inference.py -q`
  2. `uv run --frozen pytest tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_no_dead_symbols.py -q`
  3. `uv run --frozen pytest tests/charter -q` (activation module regression; keep it scoped)
  4. `uv run --frozen ruff check` and `ruff format --check` on every touched file;
     `uv run --frozen python -m mypy` on the touched `src` files. Record any error that also
     reproduces on pristine `main` rather than fixing it here.
  5. Run `spec-kitty doctor charter-packs` end to end on a fixture repo to eyeball the human
     output once; record the result.
  6. Record results with `spec-kitty agent tasks add-history WP01 --note "..."`.
- **Files**: none (verification only)
- **Parallel?**: No.
- **Notes**: Do not run a full heavy suite. `cancelled` CI runs are not failures.

## Test Strategy

- Red first: T001/T002 fail before T003/T004 and pass after.
- The refusal cases keep their existing fixtures, so the positive control (a contained path is not a
  finding) lives on the same fixture as the escape.
- T007 is the acceptance proof for the doctor half (a count, not a shape): three registry reads
  before, one after. T011.2's absence test needs its `load_org_drg` positive control, or it would
  pass on an empty module.
- Add no test that only mirrors an implementation detail; each new test pins a stated requirement
  (carried root, absence from the serialized surface, copy survives, dump/reload refuses, one
  registry read).

## Risks & Mitigations

- **Silent default root** → forbidden; the typed error is the contract and is tested through the
  dump/reload path.
- **Serialized-surface drift** → the dump/schema test pins the key sets, with `pack_name` as the
  positive control.
- **Import cycle** between `charter.offering.assets` and `charter.offering.drg.org_pack_loader` →
  the loader imports no asset module; import both in one command as the check.

## Review Guidance

- Confirm there is exactly one place that stamps the root, and that no predicate accepts a root
  parameter any more.
- Confirm the docstrings still describe the judgement rules accurately (authored nodes only,
  org-provenance assets only, nothing opened, `assets/` symlink rule).
- Confirm no `Path(".")`/`None` fallback anywhere on the containment path.
- Confirm the module graph imports cleanly and the changed tests fail on the pre-change tree.
- Confirm the registry is read once and only inside `load_org_drg`
  (`grep -n load_pack_registry -r src/`).
- Confirm the two doctor halves are still parallel and share the predicate, so JSON and human output
  cannot disagree, and that no test assertion was weakened (only monkeypatch targets move).
- Confirm `charter_activation_boundary_baseline.yaml` and `charter/activation/api.py` are untouched.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
