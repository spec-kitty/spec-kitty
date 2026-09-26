---
work_package_id: WP08
title: Runtime-parity bans, parity residue and next-no-unknown-state scan
dependencies: []
requirement_refs:
- FR-013
- FR-016
- NFR-002
- NFR-005
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ratchet-baseline-census-gate-remediation-01M3EW3Z
base_commit: 7712d71d33a53c09e8f7c857c97da1f9eb229a6f
created_at: '2026-09-26T15:58:20.160500+00:00'
subtasks:
- T043
- T044
- T045
- T046
- T047
- T048
phase: Phase 4 - Parity remediation
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-26T17:00:00Z'
  actor: planner-priti
  action: Folded post-tasks squad findings
agent_profile: python-pedro
authoritative_surface: tests/next/test_internal_runtime_parity.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/next/test_internal_runtime_parity.py
- tests/contract/test_next_no_unknown_state.py
- tests/missions/test_surface_resolution_equivalence.py
- tests/architectural/test_execution_context_parity.py
- tests/review/test_transition_gate_parity.py
- tests/architectural/test_docs_cli_reference_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Runtime-parity bans, parity residue and next-no-unknown-state scan

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action doctrine: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Make the runtime-parity bans non-vacuous (FR-013), fix the same vacuous scan in `tests/contract/test_next_no_unknown_state.py:40`, and remove the stale parity residue named in the #2631 grounding from kept suites (FR-016).

Done means all of the following hold:

1. **Rich/typer ban**. `tests/next/test_internal_runtime_parity.py::test_no_rich_or_typer_imports_in_internal_package` scans the **live** package `src/runtime/next/_internal_runtime` (16 `.py` files on the planning base). It uses a pure AST helper `_rich_typer_import_offenders(root)` that walks `ast.Import`/`ast.ImportFrom`, so it catches `import os, typer`, which the line-prefix match misses. It asserts a floor of `root.is_dir()` and `>= 16` files inspected. The helper **fails** on a missing or empty target.
2. **Rich/typer tests**:
   - `test_rich_typer_ban_inspects_live_runtime_package` went RED first, because the base scan inspects 0 files: `src/specify_cli/next` does not exist;
   - `test_rich_typer_ban_fails_on_missing_or_empty_target` passes;
   - `test_rich_typer_ban_flags_planted_import` passes.
3. **Retired tests**. These are retired, each with a recorded NFR-006 reason:
   - `test_no_spec_kitty_runtime_imports_in_internal_package`, whose survivor is `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package`;
   - the two surface-shape pins `test_public_surface_matches_contract` and `test_submodule_surface_matches_contract`.

   The golden test's module docstring is relabelled as a characterization golden.
4. **`test_next_no_unknown_state.py`**. `test_placeholder_is_absent_from_runtime_source` scans the live `src/runtime/next` tree (31 `.py` files on the planning base) with an `is_dir()` + `>= 31` floor and a planted-placeholder test. On base it inspects 0 files, because it globs `src/specify_cli/next`.
5. **FR-016 residue removed**:
   - `test_surface_resolution_equivalence.py`: the stale RED/GREEN narrative, the dead strict-xfail machinery (`_apply_xfail` and the always-`None` `xfail_reason` column), and the drained-WP06 comment block. A new `test_equivalence_detects_planted_divergence` proves the matrix can fail.
   - `test_execution_context_parity.py`: the xfail→WP docstring map and the stale xfail comment block (0 `pytest.mark.xfail` remain), and the name-only `missing_seams` arm.
   - `test_transition_gate_parity.py`: `test_wp09_hook_landmine_disposition_is_documented_accurately`, a test of its own docstring.
   - `test_docs_cli_reference_parity.py`: `test_retired_check_residual_option_is_absent`, a retired-name tombstone costing about 72 s.
6. SC-005 for this WP's bans holds: **0 bans pass when their scan target is empty or missing.**

## Context & Constraints

- **Mission artefacts**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/`. Read:
  - `spec.md`: FR-013, FR-016, US3-AS1, SC-005, NFR-002, NFR-006;
  - `plan.md` rev 2: the WP08 row. `test_next_no_unknown_state` is folded into this WP per `research/postplan-priti.md` Q4, which supersedes the plan's "Follow-ups" bullet;
  - `research.md` §F1 and §F4;
  - `research/grounding-2631_2972.md`;
  - `research/postplan-debbie.md` [INFO]: the planning-base rich/typer scan inspects 0 files; the live `_internal_runtime` has 16 files; the only rich import under `runtime/next` is `runtime_bridge_retrospective.py:158`.
- **Charter**: `.kittify/charter/charter.md`. The rules that apply are:
  - SO #4, red-first. The converted ban gives the genuine RED, and FR-016's deletions ride on it;
  - SO #5, gate non-vacuity: a concrete floor plus self-mutation through the **real** scan function;
  - DIRECTIVE_041, test-remediation discipline: delete the assertion, not the test, when a test encodes a hole;
  - the #2620 catalog format for verdicts. WP12 owns the catalog; you record the evidence here.
- **Governance applied while authoring this prompt**: profile `planner-priti`; `charter context --action tasks`, specifically:
  - DIRECTIVE_041/043 (gate discipline, non-vacuity);
  - DIRECTIVE_044 (no duplicate bans: `test_shared_package_boundary.py` already owns the `spec_kitty_runtime` ban);
  - USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY;
  - RECONCILE_CHANGE_SCOPE_TENSIONS (campsite only on touched files).
- **Scope of the rich/typer ban stays `_internal_runtime` only.** `src/runtime/next/runtime_bridge_retrospective.py:158` legitimately imports `rich.prompt`, so widening to `src/runtime/next` would red on a sanctioned import.
- **C-005**: no `src/` edits. If the retargeted `test_next_no_unknown_state` scan finds a real placeholder in `src/runtime/next`, stop and report it as a finding. Do not fix `src/`. The planning-base grep finds 0 occurrences of `[QUERY - no result provided]` under `src/` and `packs/`.
- **Format-exclude rule**: all six owned files are listed in `[tool.ruff.format].exclude`:
  - `tests/next/test_internal_runtime_parity.py` (pyproject L1809)
  - `tests/contract/test_next_no_unknown_state.py` (L1286)
  - `tests/missions/test_surface_resolution_equivalence.py` (L1798)
  - `tests/architectural/test_execution_context_parity.py` (L977)
  - `tests/review/test_transition_gate_parity.py` (L1899)
  - `tests/architectural/test_docs_cli_reference_parity.py` (L970)

  Do **not** run `ruff format` on them and do **not** edit `pyproject.toml` (WP13 owns those lines). Write new code tidily and `ruff check`-clean. If an edit leaves one of them format-clean, `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` goes red. Stop and escalate; never edit pyproject here.
- **Out of scope**:
  - `tests/cross_branch/test_parity.py` (WP12 verdict row only);
  - `TestNoLegacyQueryPlaceholderInTemplates.test_placeholder_is_absent_from_command_templates`. It scans `src/specify_cli/missions` (15 template `.md` files on base, so it is **not** empty), while the canonical templates now live in `packs/built-in/missions/`. Record this scope drift in the tracer as a follow-up candidate. Do not widen it here.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implementers commit in their lane worktree (`spec-kitty implement WP08`). Never push, never merge.

## Subtasks & Detailed Guidance

### Subtask T043 – RED first: floor tests for both vacuous scans

- **Purpose**: Land the acceptance tests that fail for the intended reason, "the ban inspected 0 files", not an `ImportError`, before changing either scan target (C-001, #5068).
- **Steps**:
  1. In `tests/next/test_internal_runtime_parity.py`:
     - Hoist the **current** scan target into a module constant `_RUNTIME_PACKAGE` with its value **unchanged**. That value is `<repo>/src/specify_cli/next/_internal_runtime` (the path at L95-101 and L120-126).
     - Add the pure helper `_rich_typer_import_offenders(root: Path) -> tuple[int, list[str]]`, returning `(files_inspected, offenders)`. It raises `AssertionError` (or returns a sentinel the tests assert on) when `root` is not a directory or holds 0 `.py` files. It walks `ast.Import` names and `ast.ImportFrom.module` for a top-level segment in `{"rich", "typer"}`, so it catches `import os, typer`, `from rich.console import X` and `import rich.prompt`.
     - Add three tests:
       - `test_rich_typer_ban_inspects_live_runtime_package` asserts `files_inspected >= 16` for `_RUNTIME_PACKAGE`;
       - `test_rich_typer_ban_fails_on_missing_or_empty_target(tmp_path, kind)`, **parametrized** over `kind in ("missing", "empty")` (2 node IDs), where both fail;
       - `test_rich_typer_ban_flags_planted_import(tmp_path)` writes `mod.py` containing `import os, typer` and a second file with `from rich.console import Console`, and asserts both offenders are named.
  2. In `tests/contract/test_next_no_unknown_state.py`:
     - Hoist the current target at L40 into `_RUNTIME_SOURCE_ROOT` with its value unchanged (`src/specify_cli/next`).
     - Extract `_placeholder_offenders(root) -> tuple[int, list[tuple[Path, int]]]`, which fails on a missing or empty target.
     - Add `test_runtime_placeholder_scan_inspects_live_source` asserting `files_inspected >= 31`, as a **module-level** function (not inside `TestNoLegacyQueryPlaceholderInTemplates`). T046's planted test is module-level too.
  3. Run both floor tests on the lane base. They fail with "0 files inspected" (or "missing target"). **That is the RED.** The missing, empty and planted tests pass already, because they exercise the helper on `tmp_path`.
  4. Commit this alone ("test(WP08): RED ..."). Record the verbatim RED output:
     ```bash
     spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z \
       --category design-decisions --actor claude --entry "WP08 red-first: ..."
     ```
- **Files**: `tests/next/test_internal_runtime_parity.py`, `tests/contract/test_next_no_unknown_state.py`.
- **Notes**: Keep each helper ≤ 15 complexity. Do not reformat either file; match the existing style.

### Subtask T044 – Convert the rich/typer ban onto the live runtime package

- **Purpose**: Make the ban measure the property it claims (FR-013, US3-AS1).
- **Steps**:
  1. Retarget `_RUNTIME_PACKAGE` to `Path(__file__).resolve().parents[2] / "src" / "runtime" / "next" / "_internal_runtime"`. Confirm `parents[2]` is the repo root from `tests/next/`.
  2. Rewrite `test_no_rich_or_typer_imports_in_internal_package` (L118-139) to call `_rich_typer_import_offenders(_RUNTIME_PACKAGE)`, assert the floor and assert `offenders == []`. Delete the line-prefix loop. Keep the test name: it is the ban.
  3. **Load-bearing proof** (NFR-002 (b), a one-off recorded in the tracer rather than committed): monkeypatch the helper's forbidden-root set to `set()`. The planted test turns green-for-the-wrong-reason and fails its "offender named" assertion. Conversely, planting `import typer` into a **tmp copy** of the live package reds the live ban.
  4. Run `pytest tests/next/test_internal_runtime_parity.py -q`. The T043 floor test is now green, with 16 files inspected.
- **Files**: `tests/next/test_internal_runtime_parity.py`.

### Subtask T045 – Retire the duplicate ban and the surface-shape pins; relabel the golden

- **Purpose**: Remove parity tests that duplicate an owning gate or pin positive shape (DIRECTIVE_044, #2631 verdicts). Record NFR-006 evidence for each.
- **Steps**:
  1. Delete `test_no_spec_kitty_runtime_imports_in_internal_package` (L89-115). It also scans the deleted `src/specify_cli/next`, so it has never been able to fail.
     - **Survivor**: `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package` (L58-59). Its `_PRODUCTION_ROOTS` (L19) includes `src/runtime`, and it carries a planted self-test in `_assert_live_negative_import_guard` (L42-55).
     - Run the survivor and record its node ID and result.
  2. Delete `test_public_surface_matches_contract` (L142-158) and `test_submodule_surface_matches_contract` (L161-169). These are positive-shape pins, and the second pins the private `engine._read_snapshot`.
     - **NFR-006 reason**: `__all__`/`hasattr` equality pins shape. The behaviour is covered by `test_internalized_runtime_matches_upstream_snapshot`, which replays through `start_mission_run`/`next_step`/`provide_decision_answer` via `tests/fixtures/runtime_parity/_capture_baselines.py`.
     - **Mutation proof** (recorded, not committed): in a scratch copy of the tree, do a **behaviour-preserving rename** of `engine._read_snapshot` (`src/runtime/next/_internal_runtime/engine.py:130`) **and all three internal call sites** (`engine.py:280`, `:541`, `:814`). Only `test_submodule_surface_matches_contract` reds, while the golden stays green. That demonstrates it pinned shape, not behaviour. Do **not** use `monkeypatch.delattr` / `del engine._read_snapshot`: the internal callers then raise, and all 4 golden nodes ERROR (Pedro probe). Note that `tests/runtime/test_bridge_parity.py:294` and `:969` also import `_read_snapshot` (WP11's scope), so the scratch rename reds those too; that is expected and unrelated to this retirement.
  3. Rewrite the module docstring (L1-12). The file holds a **characterization golden** of the internalized runtime, captured from upstream `spec_kitty_runtime` 0.4.x, plus the rich/typer layer ban. Drop "WP01 acceptance gate" and "independence is the entire point of WP01".
  4. Record all three retirements in one tracer entry. Give per test: verdict (retire), discriminator (duplicate ban / positive shape), survivor or reason, and the mutation result. WP12 lifts these into the FR-018 catalog.
- **Files**: `tests/next/test_internal_runtime_parity.py`.
- **Validation**: `pytest tests/next/test_internal_runtime_parity.py tests/architectural/test_shared_package_boundary.py -q`.

### Subtask T046 – Fix the vacuous runtime-source scan in `test_next_no_unknown_state.py`

- **Purpose**: This is the same defect class as FR-013. `rglob` over the missing `src/specify_cli/next` yields 0 files, so `test_placeholder_is_absent_from_runtime_source` can never fail (SC-005).
- **Steps**:
  1. Retarget `_RUNTIME_SOURCE_ROOT` to `_REPO_ROOT / "src" / "runtime" / "next"`. That is 31 `.py` files on base, including `_internal_runtime/`. The placeholder emitter family (`runtime_bridge.py`, `decision.py`, `prompt_builder.py`) lives there.
  2. Rewrite `test_placeholder_is_absent_from_runtime_source` (L39-53) to use `_placeholder_offenders(_RUNTIME_SOURCE_ROOT)` with the floor. Keep its name and its offender message.
  3. Add `test_runtime_placeholder_scan_flags_planted_placeholder(tmp_path)`. It writes a `.py` file containing the `_PLACEHOLDER` literal and asserts the helper names `(path, line)`. Add a clean file as the negative control.
  4. Leave the other test classes unchanged. Inside `TestNoLegacyQueryPlaceholderInTemplates`, only `test_placeholder_is_absent_from_runtime_source` changes; its sibling `test_placeholder_is_absent_from_command_templates` stays untouched. `TestRuntimeBridgeBlockedReasonIsConcrete` already reads the real `src/runtime/next/runtime_bridge.py`.
  5. Record the scope-drift observation on `TestNoLegacyQueryPlaceholderInTemplates` (see Context) in the tracer as a follow-up candidate.
- **Files**: `tests/contract/test_next_no_unknown_state.py`.
- **Validation**: `pytest tests/contract/test_next_no_unknown_state.py -q`. All green, and the T043 floor test is green with 31 files.

### Subtask T047 – FR-016 residue: `test_surface_resolution_equivalence.py`

- **Purpose**: Remove dead strict-xfail machinery and stale narrative, and prove the kept matrix can still fail.
- **Steps**:
  1. Delete `_apply_xfail` (L578-597) and parametrize `test_entry_points_agree_per_cell` (L600) directly over the matrix. Extract its body into `_check_cell(topology, slug, mid8, entry_points)`, which step 6 reuses. Keep the ids by building `pytest.param(topology, slug, mid8, id=test_id)` inline, so node IDs stay identical: compare `--collect-only -q` before and after, and record the diff (expected empty).
  2. Drop the `xfail_reason` column from `_MATRIX` (L488-575). All 14 rows carry `None` on base, and the type becomes `list[tuple[str, str, str, str]]`. Delete the explanatory comment for that column (L488-490).
  3. Delete the stale RED/GREEN cell table and the strict-xfail narrative in the module docstring (L8, L36-108; re-locate by content). Keep a short statement of what the matrix proves.
  4. Delete the drained "WP06 documented out-of-scope divergence reasons (the T026 allowlist)" and "WP05 … drains the last three RED" comment block (L436-486). Nothing remains RED.
  5. **Keep** `_assert_equivalent`, `_observe`, `_entry_points` and the matrix.
  6. Add `test_equivalence_detects_planted_divergence(tmp_path, monkeypatch)`:
     - build a coord-topology cell with the module's own `_build_topology`;
     - monkeypatch one leg of `_entry_points` so that for this cell it returns the **primary** feature dir while the others return the coordination dir, by wrapping `_entry_points` and replacing one closure;
     - drive the comparison through a helper `_check_cell(topology, slug, mid8, entry_points)` that you **extract** from `test_entry_points_agree_per_cell` in step 1 and that both tests call. Assert `pytest.raises(AssertionError)` around `_check_cell`. Never copy the loop into the planted test.

     This is a planted-violation control through the **real** comparison. It is green on base, because it strengthens the suite; the WP's genuine RED comes from T043.
- **Files**: `tests/missions/test_surface_resolution_equivalence.py` (format-excluded; do not reformat).
- **Validation**: `pytest tests/missions/test_surface_resolution_equivalence.py -q`. Same node IDs plus 1 new, all green.

### Subtask T048 – FR-016 residue in the other three suites, then validate

- **Purpose**: Remove self-referential, name-only and tombstone tests from kept suites. Each removal gets an NFR-006 record.
- **Steps**:
  1. `tests/architectural/test_execution_context_parity.py`:
     - Delete the module-docstring "xfail → convergence-WP map (IC-08 / T003)" section and the xfail narrative around it (about L105-160). Keep the "Live parity coverage" description, updated so it does not say "non-xfail".
     - Delete the stale ATDD-first xfail comment block (about L1392-1416). 0 `pytest.mark.xfail` remain on base.
     - Remove the scattered "xfail removed" breadcrumb comments only where they sit in blocks you already edit.
     - In `test_no_feature_dir_anchored_status_event_reads` (L2160-2209), delete the `missing_seams` arm (L2195-2200). **Disposition: retire (redundant within the test)**. It is not a lone name pin: the kept ban already reds when a seam is renamed or deleted, because the exempt seams (`_resolve_events_path`, `_canonical_events_dir`) contain the fallback reads and are exempted by name, so a renamed seam's reads surface as forbidden hits (Pedro probe: with the arm removed, renaming both seams still reds via `gate.py:218` and `agent_retrospect.py:264`). Keep the negative ban, meaning the forbidden-read hits and the "seam no longer calls `resolve_status_surface`" check.
     - **NFR-006 mutation**: record that, with the arm removed, renaming both exempt seams in a scratch copy still reds the kept ban (naming `gate.py:218` and `agent_retrospect.py:264`), and that re-introducing a `feature_dir`-anchored `read_events()` also reds it. If your probe disagrees, keep the arm and record why.
  2. `tests/review/test_transition_gate_parity.py`: delete `test_wp09_hook_landmine_disposition_is_documented_accurately` (L280-304).
     - **Reason**: it asserts on this module's own docstring and on a marker's absence, which is the self-referential docstring test named in the grounding.
     - Confirm the module docstring no longer claims a pending xfail (L28-29 already says "no `xfail` marker"), so removing the guard loses no invariant.
  3. `tests/architectural/test_docs_cli_reference_parity.py`: delete `test_retired_check_residual_option_is_absent` (L205-213).
     - **Reason**: a retired-name tombstone (`--check-residual`) costing about 72 s.
     - **Survivor**: `test_visible_paths_match_reference` (L154) and `test_deprecated_paths_classified` (L181) keep help/reference parity.
     - Record the `--durations` delta in the PR.
     - **Survivor proof** (one-off, recorded in the tracer): re-add `--check-residual` as a **visible** option in a scratch copy and confirm a named survivor (e.g. `test_visible_paths_match_reference`) reds. If no survivor reds, keep the tombstone and record why.
  4. Append one tracer entry listing every FR-016 removal with its reason or survivor and mutation evidence.
  5. Run the full validation below.
- **Files**: `tests/architectural/test_execution_context_parity.py`, `tests/review/test_transition_gate_parity.py`, `tests/architectural/test_docs_cli_reference_parity.py` (all format-excluded; do not reformat).

## Test Strategy

Tests are required. Record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run* section.

```bash
.venv/bin/python -m pytest tests/next/ tests/contract/test_next_no_unknown_state.py \
  tests/missions/test_surface_resolution_equivalence.py tests/architectural/test_execution_context_parity.py \
  tests/review/test_transition_gate_parity.py tests/architectural/test_docs_cli_reference_parity.py \
  tests/architectural/test_shared_package_boundary.py tests/architectural/test_ruff_format_exclude_ratchet.py -q --durations=10
make test-fast
.venv/bin/ruff check tests/next/test_internal_runtime_parity.py tests/contract/test_next_no_unknown_state.py \
  tests/missions/test_surface_resolution_equivalence.py tests/architectural/test_execution_context_parity.py \
  tests/review/test_transition_gate_parity.py tests/architectural/test_docs_cli_reference_parity.py
.venv/bin/mypy tests/next/test_internal_runtime_parity.py tests/contract/test_next_no_unknown_state.py \
  tests/missions/test_surface_resolution_equivalence.py tests/architectural/test_execution_context_parity.py \
  tests/review/test_transition_gate_parity.py tests/architectural/test_docs_cli_reference_parity.py
```

- **mypy bar**: NFR-005 covers all six changed files, but the base is not clean (e.g. `tests/next/test_internal_runtime_parity.py` has 6 pre-existing `type-arg` errors around L72-73). Run the same mypy command on the planning base, record both counts, and require **0 new errors** at head. Fixing the pre-existing ones is allowed as campsite work in blocks you already edit, never by suppression.

- Collect-only node-ID diffs:
  - `test_surface_resolution_equivalence.py`: identical plus 1 new;
  - `test_internal_runtime_parity.py` (8 nodes on base): minus 3 retired, plus 4 new (`inspects_live_runtime_package`, `fails_on_missing_or_empty_target[missing]`, `[empty]`, `flags_planted_import`) = 9;
  - `test_next_no_unknown_state.py`: plus 2.

  Put these in the PR.
- Complexity: C901 ≤ 15. Add zero new suppressions.
- **Pre-existing failure rule**: `tests/next/` is broad. Classify any red that is also red on the planning base (CLAUDE.md "baseline-red gotcha"). If it is pre-existing and untracked, file a GitHub issue before continuing and note it here. Never retry-to-green.
- **Campsite (FR-020)**: clean #2972 Sonar findings (S5778/S5779/S8997 class) only in these six files and only where you already edit. Record before/after pairs. Zero is acceptable.

## Risks & Mitigations

- **Floors break on a legitimate future file deletion under `src/runtime/next`** (e.g. #2633 delegate deletions). The floors are the planning-base counts (16 and 31) per NFR-002. A shrink is a deliberate one-line edit that the failure message explains; do not pre-emptively lower them.
- **Excluded file becomes format-clean** after deletions: check with `ruff format --check <file>` (it should still report "Would reformat"). If a file becomes clean, stop and escalate; never edit pyproject here.
- **Parametrize ids drift in the equivalence matrix**: keep the `ids` source identical, and diff `--collect-only`.
- **Hidden rich import added to `_internal_runtime` by a parallel lane**: the converted ban is designed to red on exactly that. Treat it as a real finding.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md` [HIGH] NFR-002, [MEDIUM] FR-012/FR-013 floor, [HIGH] NFR-006):

1. **Red for the intended reason.** The T043 commit precedes T044/T046. Its recorded failure says "0 files inspected" or "missing target" for both floor tests. It is not an `ImportError` or `NameError`.
2. **Real scan path.** The planted-import and planted-placeholder tests call the **same** helper the production ban calls (`_rich_typer_import_offenders`, `_placeholder_offenders`). They do not use a reimplemented matcher.
3. **Concrete floors.** `>= 16` and `>= 31`, never `>= 1` or `assert files`. A missing or empty target fails.
4. **AST, not line prefix.** Reviewer spot-check: `import os, typer` in a tmp package is flagged.
5. **Retirements carry evidence.** Each retired test has either a named surviving node ID (spec_kitty_runtime → `test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package`; `--check-residual` → the reference-parity tests) or a cited reason plus a mutation showing it could not fail or pinned only shape. There are 0 retirements without one (NFR-006).
6. **Scope discipline.** The rich/typer ban is still scoped to `_internal_runtime`, so `runtime_bridge_retrospective.py:158` is not flagged. In `TestNoLegacyQueryPlaceholderInTemplates` only `test_placeholder_is_absent_from_runtime_source` changed; `test_placeholder_is_absent_from_command_templates` is untouched, and its drift is recorded as a follow-up.
7. **Planted divergence** reds `_assert_equivalent` through the extracted `_check_cell`, the same helper the matrix test calls.
8. There is no `pyproject.toml` or `src/` diff. `ruff check` is clean and mypy shows 0 new errors on all six changed files (base and head counts recorded).
9. The `_read_snapshot` mutation proof used a behaviour-preserving rename (not `delattr`); the `missing_seams` retirement cites the redundancy probe.

**Reviewer RED reproduction** (mechanical; run in the lane worktree; `<lane-base>` is the lane's base commit, e.g. `git merge-base HEAD claude/spec-kitty-remediation-wfje22`):

```bash
RED=$(git log --reverse --format=%H <lane-base>..HEAD | head -1)
git stash -u; git checkout "$RED"
.venv/bin/python -m pytest tests/next/test_internal_runtime_parity.py::test_rich_typer_ban_inspects_live_runtime_package tests/contract/test_next_no_unknown_state.py::test_runtime_placeholder_scan_inspects_live_source -q
git checkout -; git stash pop
```

It must fail with "0 files inspected" or "missing target" for both floor tests. An `ImportError`, `NameError` or collection error is not a valid RED.

**Issue matrix**: #2631 is seeded `in-mission` against WP08, but WP08 fixes only part of it (WP09–WP12 own the rest, and the oracle retirement is deferred to #5116). Leave the row `in-mission`; WP13 T073 finalizes it.

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-013, FR-016, NFR-002 (floors + planted violations), NFR-005, NFR-006 (every retirement names a survivor or a mutation), C-001, C-005; contributes to SC-005.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-26T17:07:42Z – claude – shell_pid=416 – Blocked on move-task for_review: lane-branch kitty-specs guard flags tasks/WP02-*.md and tasks/WP05-*.md, inherited via lane-setup merges 816dd9e8/87d0e94a (not WP08 commits; d61d05ba/e034ecf9 touch only tests/). Implementation complete and committed; T043-T048 marked done. Orchestrator decision needed: canonical cleanup (git restore --source claude/spec-kitty-remediation-wfje22 -- kitty-specs/ + commit) or --force.
