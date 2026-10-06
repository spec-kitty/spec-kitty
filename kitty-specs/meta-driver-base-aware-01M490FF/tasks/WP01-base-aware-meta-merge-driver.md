---
work_package_id: WP01
title: Base-aware meta merge driver with pipeline opt-out
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
- FR-009
- FR-010
- FR-011
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: fix/meta-driver-base-aware
merge_target_branch: fix/meta-driver-base-aware
branch_strategy: Planning artifacts for this mission were generated on fix/meta-driver-base-aware. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/meta-driver-base-aware unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-meta-driver-base-aware-01M490FF
base_commit: 5e24579df12355eef9946d6b1fcd7d5377f9df41
created_at: '2026-10-06T20:33:09.981103+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Fix
history:
- at: '2026-10-06T20:28:26Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_meta_driver_base_aware_5460.py
- tests/consolidation/test_meta_driver_base_aware_5460_unit.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/drivers.py
- src/specify_cli/cli/commands/merge_driver.py
- src/specify_cli/lanes/consolidation.py
- tests/consolidation/test_meta_driver_base_aware_5460.py
- tests/consolidation/test_meta_driver_base_aware_5460_unit.py
- tests/consolidation/merge_driver_goldens/merge-driver-meta/**
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5460'
---

# Work Package Prompt: WP01 – Base-aware meta merge driver with pipeline opt-out

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission meta-driver-base-aware-01M490FF`). Address every feedback item before completing.

---

## Objectives & Success Criteria

- FR-001/FR-002: in an ordinary merge, a `meta.json` key changed (or deleted, or added) on only one side since the ancestor survives from that side; the #5460 discard (`discarded_at` added, `flattened: true`, `topology`/`coordination_branch` deleted) is kept while the teammate's `vcs`/`vcs_locked_at` are taken.
- FR-003/FR-004: a genuine both-sides conflict keeps today's precedence (target-authoritative keys from `ours`, every other key from `theirs`, the #4900 `mission_number` rule); equal changes collapse.
- FR-005: `acceptance_history` is always the deduplicated, time-ordered union.
- FR-006: an empty ancestor (absent file, whitespace-only file, or `{}`) selects today's two-way rule byte-for-byte; the five existing goldens show zero diff.
- FR-007: a malformed ancestor raises the named `MergeDriverError` carrying the `%O` path; nothing is written.
- FR-008: the red-first tests are RED on the planning base through the pre-existing entry points and GREEN at the final commit (C-004, SC-003).
- FR-009: three new golden cases + refreshed `base-absent` note + docstrings + CHANGELOG entry.
- FR-010: the flatten triple, the `merged_*` block and the acceptance stamp group each move as one unit.
- FR-011: the lane-merge pipeline's merges keep the two-way rule through an explicit opt-out; an ordinary merge does not.
- NFR-001/NFR-002: byte-stable serialisation; the merge suites pass unchanged. SC-001: the issue reproducer reports `kept`.

## Context & Constraints

- Spec: `kitty-specs/meta-driver-base-aware-01M490FF/spec.md`; plan IC-01…IC-04; `data-model.md` holds the per-unit rule table and invariants; `research.md` holds the dispositions of the post-spec review (read the "Decision" paragraphs before coding).
- Root cause: `src/specify_cli/consolidation/drivers.py` `reconcile_meta_payloads` (`result = dict(theirs)` then copies `_TARGET_AUTHORITATIVE_META_FIELDS` from `ours`) and `run_meta_driver` (`_ = base`) never read git's `%O`. Verified live on `origin/main` 0d4c7583e: the issue reproducer gives `trigger: lost` / `nodriver: conflict`.
- Existing seams to reuse unchanged: `_load_json_object` (missing/empty → `{}`, corrupt → `EventLogMergeError` naming the path), `_union_acceptance_history`, `_TARGET_AUTHORITATIVE_META_FIELDS`, `_META_JSON_KWARGS`, `is_assigned_mission_number`, `_resolve_merge_driver_paths` (already validates `%O`), `MergeDriverError`/`MergeDriverOutcome`.
- Do NOT reuse `_merge_field` (acceptance-matrix driver): it treats "removed" and "changed to `None`" identically; the meta driver must distinguish them (data-model invariant 2).
- Decisions already taken (do not reopen): target-authoritative keys win only on a genuine conflict in ordinary merges (`01M490FHTGTH51TAD3KNPVMG8H`); the pipeline keeps two-way (`01M493BC3KPSC4FT6XSC7ESNDN`). Out of scope: #5292, #4316, #4169, failing closed on conflicts, deep-merging nested values.
- Module boundary: `consolidation/drivers.py` must not import `typer` or `specify_cli.cli.*` (`TestMergeCliBoundary` scans it); read the environment in the CLI shell, not in the body.
- Ownership: stay within `owned_files`; the only edit in `lanes/consolidation.py` is one line in `_make_merge_env` (+ docstring). No change to `.gitattributes` writers, `init`, migrations, `git_probes` (meta is excluded from replay) or strategy selection.
- Charter: ATDD-first (C-011) — commit the red tests before the fix; no full/heavy suites locally (CI owns them); complexity ≤ 15 per function; new branches get tests in the same commit; ruff-format the touched files (never add to the `[tool.ruff.format].exclude` list).
- Captured #5460 blobs for the unit fixture: `/tmp/claude-1000/-home-user-Documents-code-test-qa/8fe7469d-3cea-4581-bf45-d7554f843b9c/scratchpad/ground-5460/` (`meta_8a2412913974.json` = ancestor, `meta_HEAD1.json` = discarding side, `meta_HEAD2.json` = teammate). If the scratch files are gone, re-derive them from the issue body: ancestor has `topology: "coord"`, `coordination_branch`, `flattened: false`, no `discarded_at`, no `vcs`; side A deletes `topology`/`coordination_branch`, sets `flattened: true`, adds `discarded_at`; side B adds `vcs: "git"` and `vcs_locked_at`.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/meta-driver-base-aware`
- **Merge target branch**: `fix/meta-driver-base-aware`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first `p0_repro` tests through the pre-existing entry points

- **Purpose**: pin #5460 so the fix is proven, and make the red impossible to get for the wrong reason (research "red for the right reason").
- **Steps**:
  1. Create `tests/consolidation/test_meta_driver_base_aware_5460.py` with `pytestmark = [pytest.mark.unit, pytest.mark.fast]` at module level for the file-level cases, and per-test `@pytest.mark.git_repo` + `@pytest.mark.non_sandbox` on the real-git cases (look at `tests/consolidation/test_event_log_merge_driver_integration.py` for the marker shape and the `.gitattributes` + `git config merge.<key>.driver` wiring). Mark the two red cases `@pytest.mark.p0_repro(issue=5460)` (registered in `pytest.ini`; the plugin `tests/_support/p0_repro.py` deselects them unless `SPEC_KITTY_RUN_P0_REPRO=1`).
  2. File-level red case: write `O`/`A`/`B` as sibling files under `tmp_path` from the captured blobs (ancestor, discarding side, teammate), call `run_meta_driver(str(O), str(A), str(B))` (today's signature — no new argument), then assert on the JSON written to `A`: `discarded_at` present, `flattened is True`, `"topology" not in merged`, `"coordination_branch" not in merged`, `vcs == "git"`, `vcs_locked_at` equals B's. On the pre-fix driver this fails on the first assertion (A is overwritten with B's keys).
  3. Real-git red case: `git init -b main` under `tmp_path`; write `kitty-specs/m/meta.json` = ancestor, `.gitattributes` with `kitty-specs/**/meta.json merge=spec-kitty-meta`, commit; create a recording wrapper script `tmp_path/driver.py` that appends a line to `tmp_path/driver.calls` and then `os.execv(sys.executable, [sys.executable, "-m", "specify_cli", "merge-driver-meta", *sys.argv[1:]])`; `git config merge.spec-kitty-meta.driver "<sys.executable> <wrapper> %O %A %B"` and `merge.spec-kitty-meta.name "test"`. Branch `discard`: write side A's record, commit; `main`: write side B's record, commit. Run `git merge --no-edit discard` on `main` with a clean env (`GIT_CONFIG_NOSYSTEM=1`, no inherited `SPEC_KITTY_META_MERGE_TWO_WAY`). Assert in this order: `returncode == 0`; `driver.calls` has exactly one line (driver invoked); then the content assertions of step 2 on `kitty-specs/m/meta.json`. Pre-fix: exit 0, one call, content assertion fails.
  4. Positive control (NOT `p0_repro`, green before and after): same two branches, but `git rebase main` on `discard` (sides swap; today's two-way already keeps the discard); assert exit 0, driver invoked once, `discarded_at` present.
  5. Squash-opt-out fixture (green only after T005 — mark it `p0_repro` too, it is part of the red commit): pick an ancestor/sides triple whose two-way and three-way results differ (e.g. ancestor `{"a":1,"b":1}`, ours `{"a":2,"b":1}`, theirs `{"a":1,"b":2}` → three-way `{"a":2,"b":2}`, two-way `{"a":1,"b":2}`); call `run_meta_driver` with and without the opt-out and assert the two results differ as computed. Implement the opt-out call via the shell: run `python -m specify_cli merge-driver-meta O A B` as a subprocess with `SPEC_KITTY_META_MERGE_TWO_WAY=1` in the env and compare.
  6. Run the file on the planning base with `SPEC_KITTY_RUN_P0_REPRO=1` and record the RED output lines in the Activity Log. Commit T001+T002 alone first (`test(5460): red-first reproduction of the base-blind meta merge`).
- **Files**: `tests/consolidation/test_meta_driver_base_aware_5460.py` (new, ~220 lines).
- **Validation**: red cases fail on the pre-fix driver with a content assertion (not a `TypeError`, not a non-zero git exit); rebase control green; markers registered (no collection error).

### Subtask T002 – Goldens

- **Purpose**: pin the new shapes at the byte level and keep the existing five provably untouched (FR-006, FR-009, review MAJOR-6).
- **Steps**:
  1. Read `tests/consolidation/merge_driver_goldens/_capture.py` and `test_merge_driver_goldens.py` to learn the case layout (`O`/`A`/`B`/`expected_A`/`case.json` with `absent`, `exit_code`, `note`, `stdout`, `stderr`) and how cases are discovered (`iter_cases()`).
  2. Add `merge-driver-meta/base-one-sided-delete/`: `O` = ancestor with `topology`, `coordination_branch`, `flattened: false`, `mission_slug`; `A` = flatten applied + `discarded_at` + `flattened: true`; `B` = ancestor + `vcs`/`vcs_locked_at`; `expected_A` = the correct merged record serialised with `indent=2, sort_keys=True, ensure_ascii=False` + trailing newline (hand-author it; verify with a quick in-Python `json.dumps`); `case.json` note: "one-sided deletion and addition survive; the pre-fix driver returned B plus nothing (discard lost)".
  3. Add `merge-driver-meta/base-both-changed-precedence/`: `O` = `{"mission_slug":"m","purpose_tldr":"a","status":"in_review","mission_number":5}`; `A` = `purpose_tldr: "b"`, `status: "accepted"`, `mission_number: null`; `B` = `purpose_tldr: "c"`, `status: "in_review"`→`"approved"`, `mission_number: 5`; `expected_A` = `purpose_tldr: "c"` (mission wins planning conflict), `status: "accepted"` (target wins), `mission_number: 5` (unassigned never replaces assigned). Note the pre-fix difference.
  4. Add `merge-driver-meta/base-empty-file/`: a zero-byte `O`; `A`/`B`/`expected_A` identical to `field-union` (proves the empty-file ancestor selects the two-way rule); note it.
  5. Edit `merge-driver-meta/base-absent/case.json` `note` to "base (%O) file absent -- an absent ancestor selects the two-way field merge". Do NOT run `_capture.py` over the existing five directories; `git diff --stat` on them must be empty at the end of the WP.
- **Files**: three new case directories (4 files each), one edited `case.json`.
- **Validation**: `pytest tests/consolidation/test_merge_driver_goldens.py -k meta` is red on the pre-fix driver for the three new cases and green after T003/T004; the existing five pass throughout.

### Subtask T003 – Base-aware reconciliation rule

- **Purpose**: the product fix for ordinary merges (FR-001–FR-005, FR-010, NFR-001).
- **Steps**:
  1. In `drivers.py`, add a module-level `_MISSING: Final = object()` sentinel (with a one-line comment: distinguishes absence from `null`).
  2. Add `_META_COUPLED_KEY_GROUPS: tuple[frozenset[str], ...]` = flatten triple `{"coordination_branch", "topology", "flattened"}`; merge block `{"merged_at", "merged_by", "merged_into", "merged_strategy", "merged_push", "merged_commit"}`; acceptance stamps = `frozenset(ACCEPTANCE_PROVENANCE_FIELDS) - {"vcs", "vcs_locked_at"}` (assert at import that the subtraction leaves the five `accept*`/`acceptance_mode` keys; if `ACCEPTANCE_PROVENANCE_FIELDS` contains others, list the five explicitly instead and add a test that they are a subset of the constant).
  3. Extract today's body of `reconcile_meta_payloads` verbatim into `_reconcile_meta_two_way(ours, theirs) -> dict` (behaviour-preserving; existing tests cover it).
  4. Change the signature to `reconcile_meta_payloads(ours, theirs, base: dict[str, Any] | None = None)`. If `not base` (None or `{}`): `return _reconcile_meta_two_way(ours, theirs)`. Otherwise run the three-way pass:
     - Build the unit list: each coupled group whose members intersect `base ∪ ours ∪ theirs` keys becomes one unit; every other key (except `acceptance_history`) is its own unit.
     - A unit's value on a side = tuple of `side.get(member, _MISSING)` in a fixed member order (sort members).
     - Resolve per `data-model.md`: `ours == theirs` → ours; `ours == base` → theirs; `theirs == base` → ours; else precedence: `ours` if the unit is target-authoritative (any member in `_TARGET_AUTHORITATIVE_META_FIELDS`), else `theirs`.
     - Write the winning side's members into `result` — a `_MISSING` member is omitted, a present member (even `None`) is written.
     - `mission_number` guard after resolution: if `result.get("mission_number")` is unassigned (`not is_assigned_mission_number`) and the other side's value is assigned, take the assigned value (covers one-sided changes, review MAJOR-4).
     - `acceptance_history`: `_union_acceptance_history(theirs.get(...), ours.get(...))`; set only if non-empty (same as today).
  5. Keep each function ≤ 15 complexity: split into `_meta_merge_units(keys)`, `_resolve_meta_unit(unit, base, ours, theirs)`, `_apply_mission_number_guard(result, ours, theirs)`.
  6. Update the `reconcile_meta_payloads` docstring: the two rules (ordinary merge: base-aware; empty base/opt-out: two-way), the precedence, the groups, the sentinel.
- **Files**: `src/specify_cli/consolidation/drivers.py`.
- **Validation**: T001 file-level case green; `tests/consolidation/test_squash_reconcilers_2709.py`, `test_mission_number_truthful_4900.py`, `test_merge_drivers.py -k meta`, `test_merge_driver_wrappers_2709.py` unchanged and green; the new goldens green.
- **Edge cases to unit-test in T001's file (add them now, `unit`/`fast`)**: deleted-vs-changed conflict on a planning key (theirs wins, absent if theirs deleted); `null` vs absent (`base {"x":1}`, `ours {"x":null}`, `theirs {}` → conflict → planning → absent); coupled group where one member conflicts and another is one-sided (whole group from one side); `acceptance_history` dropped on one side still unioned; `mission_number` base 5 / ours null / theirs 5 → 5; both sides add the same new key → once.

### Subtask T004 – `run_meta_driver` reads the ancestor

- **Purpose**: wire `%O` into the body and fail loud on a damaged ancestor (FR-006, FR-007).
- **Steps**:
  1. `def run_meta_driver(base_path: str, ours_path: str, theirs_path: str, *, two_way: bool = False) -> MergeDriverOutcome`. Replace `_ = base` with: `base_payload = {} if two_way else _load_json_object(base)`, inside the same `try` that wraps the side loads so a corrupt ancestor raises `MergeDriverError(str(exc))` from the named `EventLogMergeError` exactly like a corrupt side.
  2. Pass `base=base_payload` to `reconcile_meta_payloads`. Serialisation unchanged.
  3. `MERGE_DRIVER_BODIES["merge-driver-meta"]` keeps the 3-positional signature (the keyword default makes it compatible).
  4. Add to T001's file: `test_meta_driver_malformed_ancestor_fails_loud` (O = `{ not json`, A/B valid → `MergeDriverError` whose message contains the `O` path; `A` unchanged on disk) and `test_meta_driver_whitespace_ancestor_is_two_way` (O = `"\n  \n"` → equals two-way result).
- **Files**: `src/specify_cli/consolidation/drivers.py`, the test module.
- **Validation**: both new tests green; `test_merge_driver_meta_diagnosability.py` unchanged.

### Subtask T005 – Lane-merge pipeline opt-out

- **Purpose**: keep consolidation results byte-identical (FR-011, Decision `01M493BC3KPSC4FT6XSC7ESNDN`).
- **Steps**:
  1. In `drivers.py` add `META_DRIVER_TWO_WAY_ENV: Final = "SPEC_KITTY_META_MERGE_TWO_WAY"` with a docstring: set to `"1"` by the lane-merge pipeline's single environment authority because the mission→target squash records no ancestry (stale `%O` after a reopen); never set it for ordinary merges. Export it in `__all__` if the module declares one (charter `__all__` convention).
  2. In `src/specify_cli/cli/commands/merge_driver.py`, the `merge-driver-meta` command: `two_way = os.environ.get(META_DRIVER_TWO_WAY_ENV) == "1"` and call `run_meta_driver(base, ours, theirs, two_way=two_way)`. Update the module docstring's meta bullet.
  3. (Superseded by the scout addendum: set the variable only on the two `git merge --squash` subprocess envs in `lanes/consolidation.py`, never in `_make_merge_env`.) Originally: import the constant from `specify_cli.consolidation.drivers` (check `tests/architectural/test_layer_rules.py` allows `lanes → consolidation` imports; `lanes/consolidation.py` already imports from `specify_cli.consolidation`? grep first; if not allowed, define the constant in `lanes/consolidation.py` and import it in `drivers.py` is wrong-direction — in that case place the constant in a small shared module both may import, e.g. `specify_cli/consolidation/__init__.py` re-export).
  4. Check `tests/architectural/test_merge_pipeline_ratchets.py` (FR-008b: every pipeline subprocess routes env through `_make_merge_env`) still passes; check `lanes/auto_rebase.py` — if its git subprocesses do not use `_make_merge_env`, the lane rebase becomes base-aware, which is correct (real ancestor); note it in the Activity Log either way.
  5. Tests: a unit test that `_make_merge_env()[META_DRIVER_TWO_WAY_ENV] == "1"`; the T001 squash-opt-out fixture now passes; a shell test that the subprocess driver with the env set equals `run_meta_driver(..., two_way=True)`.
- **Files**: `drivers.py`, `cli/commands/merge_driver.py`, `lanes/consolidation.py`, the test module.
- **Validation**: `pytest tests/consolidation/test_merge_pipeline_ratchets.py tests/architectural/test_layer_rules.py -q` (targeted) green.

### Subtask T006 – Docstrings, CHANGELOG, prose gates

- **Purpose**: discoverability (FR-009, SC-004).
- **Steps**:
  1. `drivers.py` module docstring, meta bullet: "field merge, base-aware for ordinary merges (one-sided change/deletion wins; genuine conflict: acceptance/VCS/lifecycle keys target-authoritative, planning keys mission-authoritative; coupled groups move as a unit; `acceptance_history` unioned); the lane-merge pipeline opts into the two-way rule via `META_DRIVER_TWO_WAY_ENV`". Mirror in `cli/commands/merge_driver.py`.
  2. `docs/changelog/CHANGELOG.md` under `[Unreleased]` → `Fixed`, matching the existing entry style: bold impact-first lead with `(#5460)`, then before → after in plain language (a teammate's `git pull` no longer silently undoes `mission close --discard`; the `meta.json` merge driver now honours the merge base for ordinary merges; consolidation unchanged).
  3. Run `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q` and `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors=0; link WARNINGS fine).
- **Files**: `drivers.py`, `cli/commands/merge_driver.py`, `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink — edit the canonical file).
- **Validation**: gates green; markdownlint budget respected for the changelog file.

### Subtask T007 – Verification and closeout

- **Purpose**: honest green (SC-001–SC-003).
- **Steps**:
  1. In the fix commit, remove the `@pytest.mark.p0_repro(issue=5460)` markers (the tests become ordinary per-PR guards; keep `unit`/`fast`/`git_repo`/`non_sandbox`).
  2. Targeted runs: `tests/consolidation/test_meta_driver_base_aware_5460.py`, `test_merge_drivers.py`, `test_squash_reconcilers_2709.py`, `test_mission_number_truthful_4900.py`, `test_merge_driver_goldens.py -k meta`, `test_merge_driver_wrappers_2709.py`, `test_merge_driver_meta_diagnosability.py`, `test_merge_pipeline_ratchets.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_merge_cli_boundary*` (find the `TestMergeCliBoundary` file). No full suites.
  3. `ruff check` + `ruff format --check --force-exclude` on the touched files; `mypy src/specify_cli/consolidation/drivers.py src/specify_cli/cli/commands/merge_driver.py`.
  4. End-to-end: `RUN_ROOT=/tmp/sk-5460 python3 /home/user/Documents/code/test/qa/round18/repro_pull_reverts_discard.py <lane-venv or project venv spec-kitty> trigger` → expect `RESULTS {'trigger': 'kept'}` (use the venv whose editable install points at the lane worktree, or run `pip install -e <worktree>` into a scratch venv).
  5. `git diff --stat <planning base> -- tests/consolidation/merge_driver_goldens/merge-driver-meta/{base-absent/A,base-absent/B,base-absent/expected_A,field-union,identical-sides,malformed-json,path-injection}` must be empty.
  6. Append tracer entries (`spec-kitty agent tracer-append --mission meta-driver-base-aware-01M490FF --category approach|design-decisions|tooling-friction --actor <agent>`) for anything learned; record the RED and GREEN outputs in the Activity Log; `spec-kitty agent tasks mark-status T001 … T007 --status done --mission meta-driver-base-aware-01M490FF`.
- **Validation**: all of the above green; the lane holds at least two commits: the red test commit and the fix commit(s).

## Scout addendum (brownfield scout, 2026-10-06 — read before coding; it overrides earlier lines where they differ)

- **Opt-out scope (narrowed):** do NOT modify `_make_merge_env` (its exact value is pinned by `tests/architectural/test_merge_pipeline_ratchets.py:214-223`, not an owned file). Instead, in `src/specify_cli/lanes/consolidation.py` find the two `git merge --squash` subprocess calls (the real integration in `_merge_branch_into` and the dry-run preview that raises `_SquashMergeConflict`) and give each `env = _make_merge_env(); env[META_DRIVER_TWO_WAY_ENV] = "1"`. Nothing else in that file changes. Every other pipeline subprocess (auto-rebase, dependency merges, `--no-ff` lane→mission) stays base-aware — intended.
- **`drivers.py` facts:** `from typing import Any` at :78 — add `Final`. `_TARGET_AUTHORITATIVE_META_FIELDS` :111-122; `_load_json_object` :237-259; `_union_acceptance_history` :262-287; `reconcile_meta_payloads` :290-325 (body to extract :312-325); `run_meta_driver` :328-340 (`_ = base` :331; the `try/except (json.JSONDecodeError, EventLogMergeError)` :332-338 — load the ancestor INSIDE that try); `MERGE_DRIVER_BODIES` :1323-1333; `__all__` :1344-1348 with the comment at :1335-1343 (add `run_meta_driver` and `META_DRIVER_TWO_WAY_ENV`, update the comment). `ACCEPTANCE_PROVENANCE_FIELDS` is exactly `('accepted_at','accepted_by','accepted_from_commit','acceptance_mode','accept_commit','vcs','vcs_locked_at')`. Never call `json.loads` on a meta blob (`tests/architectural/test_inline_meta_read_gate.py`); use `_load_json_object`.
- **Shell:** `merge_driver.py` `_run` :62-76, `merge_driver_meta` :88-94 — keep its three positional parameters (called directly by `test_merge_driver_wrappers_2709.py:139,154`); read `os.environ` inside the function and call `run_meta_driver(base, ours, theirs, two_way=…)` directly (the registry's `Callable[[str, str, str], …]` cannot carry the keyword); `os` is not imported there yet.
- **Terminology ratchet:** `tests/architectural/test_no_legacy_terminology.py:328-333` bans the phrases "lane merge", "lane-merge", "merge the lanes", "merging lanes" in `src/` and `docs/` except baselined files; `drivers.py` and `merge_driver.py` are NOT baselined — write "consolidation pipeline" / "mission→target squash". No "feature".
- **Subprocesses in tests must run the worktree's code:** the editable install points at the main checkout's `src`. In the real-git wrapper and the opt-out shell test set `env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")` (pattern: `tests/consolidation/test_event_log_merge_driver_integration.py:39`; the golden capture does the same). Also set `GIT_CONFIG_NOSYSTEM=1` and local `user.email`/`user.name` (that file :81-107 shows the driver registration and `.gitattributes` wiring; no fixture needed).
- **Markers:** `unit`/`fast` mean "no subprocess": put `pytestmark = [pytest.mark.unit]` only on a pure-logic module, or split: module-level `pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]` for the git file and keep the pure `run_meta_driver` cases in a second file `tests/consolidation/test_meta_driver_base_aware_5460_unit.py` with `[unit, fast]` (add it to `create_intent`/`owned_files` — both are under this WP's ownership by pattern; record a one-line rationale in the Activity Log). `p0_repro(issue=5460)` tests are deselected silently without `SPEC_KITTY_RUN_P0_REPRO=1`.
- **Goldens:** `_capture.py` `iter_cases()` discovers directories automatically; `absent` is metadata only; a zero-byte `O` is copied byte-for-byte (`absent: []`); each new `case.json` needs `exit_code: 0`, `stdout: ""`, `stderr: ""`, `absent`, `note`. No per-command case-count pin. The in-process golden leg calls the registry body three-positionally (base-aware), the subprocess leg uses `PYTHONPATH=<repo>/src` with no opt-out env.
- **NFR-003:** in T007 time one `python -m specify_cli merge-driver-meta O A B` subprocess on a ~4 KiB record and note the wall time in the Activity Log (expect it to equal the pre-fix driver's, ~1.4 s dominated by CLI import).
- **Residuals to note in the Activity Log (not to fix):** `vcs`/`vcs_locked_at` are written as a pair by `set_vcs_lock` but merged as individual keys (coherent on a genuine conflict since both are target-authoritative); `merge_history` whole-value next to the `merged_*` group; `discarded_at` not coupled with the flatten triple (disjoint in #5460).

## Test Strategy

```bash
# red on the planning base, green at the end
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest tests/consolidation/test_meta_driver_base_aware_5460.py -q
# neighbours that must not move
.venv/bin/python -m pytest tests/consolidation/test_merge_drivers.py tests/consolidation/test_squash_reconcilers_2709.py \
  tests/consolidation/test_mission_number_truthful_4900.py tests/consolidation/test_merge_driver_wrappers_2709.py \
  tests/consolidation/test_merge_driver_meta_diagnosability.py tests/consolidation/test_merge_driver_goldens.py -q -k "meta or Meta"
.venv/bin/python -m pytest tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py tests/architectural/test_inline_meta_read_gate.py -q
.venv/bin/ruff check src/specify_cli/consolidation/drivers.py src/specify_cli/cli/commands/merge_driver.py src/specify_cli/lanes/consolidation.py tests/consolidation/test_meta_driver_base_aware_5460.py
.venv/bin/ruff format --check --force-exclude <same files>
.venv/bin/mypy src/specify_cli/consolidation/drivers.py src/specify_cli/cli/commands/merge_driver.py
```

## Risks & Mitigations

- `None`/absent conflation → explicit `_MISSING` sentinel, dedicated test.
- Half-flattened or half-merged records → coupled groups as single units, dedicated test.
- Green-washed goldens → never re-capture the existing five; hand-author the new three in the red commit.
- Red for the wrong reason → git exit 0 and the invocation marker are the first assertions; the driver path is `sys.executable -m specify_cli`.
- Layer rule on the constant import → check `test_layer_rules.py` before placing the constant.
- Complexity ≤ 15 → three small helpers instead of one loop.

## Review Guidance

- Verify the red commit precedes the fix commit on the lane and that the T001 red output in the Activity Log is a content assertion failure (not a TypeError / non-zero git exit).
- Verify `git diff` against the planning base shows no change under the five existing golden directories.
- Verify the opt-out is set only on the `git merge --squash` subprocess env (`_run_squash_merge`), never in `_make_merge_env`, and read only in the CLI shell; `drivers.py` imports neither `typer` nor `os.environ` for this.
- Run the issue reproducer once (`trigger` arm) and confirm `kept`.
- Confirm mypy + ruff clean, complexity ≤ 15, markers registered, the CHANGELOG entry reads impact-first.

## Activity Log

- 2026-10-06T20:28:26Z – system – Prompt created.
- 2026-10-06T21:15:00Z – python-pedro (sonnet) – Lane commits: 6c4cacc69 test(red-first), 5e7b0eab3 fix, 08a7db229 changelog. RED at 6c4cacc69 (`SPEC_KITTY_RUN_P0_REPRO=1`): real-git `test_ordinary_merge_keeps_a_discard_next_to_a_teammates_edit` — git exit 0 and one driver call passed, then `assert None == '2026-10-06T16:09:05.242367+00:00'` (discarded_at); unit `test_discard_survives_a_teammates_unrelated_edit` same; `test_one_sided_change_survives_from_the_ours_side` `{'a': 1, 'b': 2} == {'a': 2, 'b': 2}`; `test_one_sided_deletion_survives` `{'a': 1, 'b': 1, 'c': 3} == {'b': 1, 'c': 3}`; `test_null_and_absent_are_distinct_values` `{'x': 1} == {'x': None}`; `test_two_way_opt_out_selects_the_two_way_rule_in_the_shell` `{'a': 1, 'b': 2} == {'a': 2, 'b': 2}`; golden `base-one-sided-delete` "written A bytes drifted from golden" (both legs). Rebase control green. GREEN at 08a7db229: 24/24 new tests; neighbours 87 passed / 70 deselected; architectural gates 227 passed 1 skipped; docs-freshness errors=0; ruff/mypy clean; goldens: only base-absent/case.json + 3 new dirs changed; e2e reproducer `RESULTS {'trigger': 'kept'}` (wrapper named `spec-kitty` with PYTHONPATH=<worktree>/src). NFR-003: ~1.4 s per driver subprocess, identical pre-fix (CLI import cost; reconcile ~76 µs).
- 2026-10-06T21:15:00Z – orchestrator – Deviations accepted: opt-out set once in `_run_squash_merge` (covers integration + preview); shell uses `functools.partial(run_meta_driver, two_way=…)`; only `base-one-sided-delete` is red pre-fix (the other two goldens pin unchanged behaviour); the real-git red case merges `main` into `discard` (the pull shape). Second test module justified by the unit/fast = no-subprocess marker vocabulary.

