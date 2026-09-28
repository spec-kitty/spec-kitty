---
work_package_id: WP03
title: Truthful mission numbering on consolidate (#4900)
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Silent-loss fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/mission_number.py
- tests/consolidation/test_mission_number_truthful_4900.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/consolidation/drivers.py
- src/specify_cli/consolidation/ordering.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/baseline.py
- src/specify_cli/consolidation/mission_number.py
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/consolidation/test_mission_number_truthful_4900.py
- tests/consolidation/test_ordering_bake_seam.py
- tests/architectural/test_no_dead_symbols.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Truthful mission numbering on consolidate (#4900)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`. Read CLAUDE.md "Consolidation & Preflight Patterns" and the `primary`/`merge` terminology footgun before touching this code.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4900: `spec-kitty consolidate` prints `Assigned mission_number=N` (from `ordering.py:~765`, **before** the mission→target squash), writes N into the **mission branch** `meta.json`, but the `meta.json` merge driver treats `mission_number` as target-authoritative (`drivers.py` `_TARGET_AUTHORITATIVE_META_FIELDS` ~:103-115, applied at ~:295-297 whenever the key is merely *present* in `ours`, even when `null`) — so the target's `null` wins and every mission ends up `null` / numbered 1.

Done means (FR-005–FR-007, contract `contracts/failure-surface.md`):
- FR-007: `merge-driver-meta` with ours (target) `mission_number: null` and theirs (mission) `1` → `1`; ours `3`, theirs `1` → `3`.
- FR-005: consolidating mission A then mission B into a fresh target records `1` and `2` in `kitty-specs/<m>/meta.json` **on the target branch**, matching the printed lines; a target with missions numbered up to 7 (one hand-numbered) gives the next mission `8`.
- FR-006: if the number read back from the target after consolidation ≠ the announced number, the command prints `Error: …` and exits 1, and no "Assigned" line claims a number that isn't recorded.
- `consolidate --resume` after a failed read-back re-verifies; it never exits 0 with `null` on the target.

## Context & Constraints

- Plan design decision **D2** (read it fully, including "rejected alternatives"); research **R2**; data-model "Mission number".
- **Design (plan D2, recorded — not optional)**: implement the driver fix (T014, FR-007 in its own right), the **unconditional** target-tree write through the MERGE_BOOKKEEPING commit (T015, plan D2(c) — the guarantee that does not depend on squash ordering or on whether git invokes the driver at all: a merge driver only fires when both sides changed `meta.json` since the merge base), and the read-back (T016). The existing pre-squash mission-branch bake may stay (resume compatibility) but is no longer what the announcement relies on. An earlier draft made T015 conditional; the post-tasks squad flagged the contradiction with D2 and the plan wins.
- Do NOT use `_bake_mission_number_on_primary_tree` (`ordering.py:~365`) — it is the coord-topology fallback, writes the repository root checkout's *current* branch with a raw `git add`/`commit`, no compare-and-swap.
- Read-back must go through `baseline._read_committed_meta_json` (`baseline.py:223`, `git show <target>:<meta_rel>` + `kernel.meta_decode`) — a new raw JSON read fails `tests/architectural/test_inline_meta_read_gate.py`.
- The driver runs as a subprocess (`spec-kitty merge-driver-meta`): tests need a fresh editable install (`uv run --frozen pip install -e .` in your lane is NOT needed if `uv sync` made it editable — verify `which spec-kitty` inside the test env resolves to the lane's venv) and the venv `bin/` on `PATH`; otherwise you get stale-install false reds (CLAUDE.md baseline-red gotcha #3).
- ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (gate, then mutate, with rollback) — read it.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. `spec-kitty implement WP03`.

## Subtasks & Detailed Guidance

### Subtask T012 – Campsite + one leaf definition of "assigned"

- Owned re-pins: `tests/consolidation/test_ordering_bake_seam.py:~57-62` pins `(0, True)` → re-pin `(0, False)` with a comment citing #4900 / data-model "≥1"; `tests/architectural/test_no_dead_symbols.py:~1382-1385` pins `_is_assigned_mission_number`'s body hash → refresh the hash with a rationale comment (the function now delegates). Run `test_no_dead_symbols.py` in T018.

- Two definitions disagree: `ordering.py:257` `_is_assigned_mission_number` (accepts 0 and negatives) and `cli/commands/agent/mission_check_prerequisites.py:176` (requires ≥1, which the data model states).
- Create `src/specify_cli/consolidation/mission_number.py` (leaf, stdlib only): `is_assigned_mission_number(value: object) -> bool` → `isinstance(value, int) and not isinstance(value, bool) and value >= 1`. Both old functions delegate (keep the private names as thin aliases or replace call sites — smallest diff). Add unit tests (0, -1, True, None, "3", 3). Commit separately as a behaviour-preserving-where-possible step and note that 0/negative now count as unassigned (a correction, pinned by test).

### Subtask T013 – Red-first repros (`tests/consolidation/test_mission_number_truthful_4900.py`)

Mark `@pytest.mark.regression`; confirm FAIL before fixing; paste failures into the Activity Log. Reuse helpers from `tests/consolidation/test_merge_time_number_assignment.py`, `test_merge_drivers.py`, `test_ordering_bake_seam.py`.

1. Driver unit (FR-007): invoke the driver function directly (find the entry used by `merge-driver-meta` in `drivers.py`) and via subprocess once. Only (null, 1) → 1 is RED today; (3, 1) → 3 and (missing key, 1) → 1 already pass and are **controls** (label them so).
2. Sequential consolidates (FR-005): scratch repo, two missions (lanes topology, like this mission), `spec-kitty consolidate --mission A` then `--mission B` via CLI; assert target-branch `meta.json` values 1 and 2 (read with `git show <target>:kitty-specs/<m>/meta.json`), and the stdout lines match. **You must show this test RED on unmodified code before fixing** (the issue's evidence: both print `Assigned mission_number=1`, `meta.json` stays null). If it is green on unmodified code, your fixture does not reproduce #4900's topology — fix the fixture (e.g. make both sides touch `meta.json` since the merge base, as real consolidation does), don't proceed.
3. Hand-numbered target (FR-005): target already has a mission with `mission_number: 7` committed → next consolidation records 8.
4. Resume (D2e): simulate a read-back failure (see T017's seam) on the first run, then `consolidate --resume` → must re-verify and either record correctly or exit non-zero; never exit 0 with null.

### Subtask T014 – Driver: unassigned target number is unset

- In `reconcile_meta_payloads` (~:295-297): for `mission_number` specifically, take `ours[key]` only if `is_assigned_mission_number(ours[key])`; otherwise keep `theirs`' value. Leave the other target-authoritative keys unchanged (research: only `mission_number` is minted null; widening is out of scope). Update the docstring.

### Subtask T015 – Target-tree write (unconditional, plan D2(c))

- Follow `_assign_planning_only_mission_number_if_needed` (`ordering.py:~774-793`): write the number into the **target-tree** `kitty-specs/<m>/meta.json`, set `run.mission_number_meta_path` (`executor.py:~1537`) so `_phase_commit_and_assert` commits it through `commit_merge_bookkeeping(destination_ref_override=target)` (~:1820-1880), and ensure `_phase_porcelain_invariant` (~:1770) whitelists it. Add `tests/architectural/test_trio_seam_only.py` and the terminus/reconciliation tests you can find touching `mission_number_meta_path` to your gate run.

### Subtask T016 – Read back, announce after verification, baked-flag semantics

- **Files**: `baseline.py`, `executor.py`, `ordering.py`.
- **Steps**:
  1. In `baseline.py` add `assert_mission_number_on_target(repo_root, target_branch, mission_slug, expected: int) -> None` next to `assert_baseline_merge_commit_on_target` (~:256), reading via `_read_committed_meta_json`; raise the same error type that sibling raises (`BaselineMergeCommitError` or a sibling subclass), with message "mission_number on <target> is <recorded>, expected <expected>" plus the remedy (NFR-003): "run `spec-kitty consolidate --mission <m> --resume` to re-verify, or inspect with `git show <target>:kitty-specs/<m>/meta.json`". Tests assert the remedy text.
  2. Thread the assigned number: `_bake_mission_number_into_mission_branch`'s return value is discarded at `executor.py:~776`; store it on `_MergeRunState`.
  3. Call the new assert right after the baseline assert (`executor.py:~1896`), with the same error handling (`Error:` line + `typer.Exit(1)`).
  4. Move the `console.print("[green]Assigned[/green] mission_number=…")` (`ordering.py:~765`) to after the read-back succeeds (print from executor, or return the number and print there). Keep the logger line at debug/info where it is if useful, worded "writing" not "assigned".
  5. `_mark_mission_number_baked` must be called only after verification. On `--resume` with `mission_number_baked` false, recompute/re-read the expected number from the mission-branch `meta.json` and verify.
  6. The `_surface_unbaked_mission_number` coord-fallback warn paths (`ordering.py:~397-420`) stay unchanged (they announce no number).

### Subtask T017 – Fault-injected mismatch (FR-006)

- The merge driver runs as a **separate process** (`lanes/consolidation.py:85`: `spec-kitty merge-driver-meta %O %A %B`), so monkeypatching `drivers` in the test process has no effect — never patch `drivers` for FR-006 or resume. Inject in-process under `CliRunner` at the read/write seam instead: patch `baseline._read_committed_meta_json` to return a payload with a mismatched `mission_number` (or patch the target-tree writer to write `expected+1`); assert exit 1, `Error:` names expected vs recorded, and no "Assigned mission_number=" line in stdout. Pair with the T013-2 happy path (same fixture builder).

### Subtask T018 – Convert and gate

```bash
uv run --frozen pytest tests/consolidation/test_mission_number_truthful_4900.py tests/consolidation/test_merge_time_number_assignment.py tests/consolidation/test_merge_drivers.py tests/consolidation/test_ordering_bake_seam.py tests/consolidation/test_issue_4474_topology_aware_bake.py -q
uv run --frozen pytest $(grep -rl "mission_number" tests/consolidation tests/specify_cli --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_trio_seam_only.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check <changed>
uv run --frozen mypy --strict <changed src files>
make test-fast
```

Remove regression markers after green. If a terminus/integration test outside these goes red, classify with the baseline-red gotcha (run it on the merge-base) before touching it — #5044 has 22 known pre-existing integration reds.

## Risks & Mitigations

- **Terminus gate attribution**: any new commit on the target must be the MERGE_BOOKKEEPING class; the reconciliation content axis FAILs unattributable paths. Prefer the driver-only path.
- **Resume**: test it explicitly.
- **Complexity**: `executor.py` functions are large; add logic via small helpers, keep ≤15.

## Review Guidance

- Printed number == target-branch number in every test; mismatch → exit 1 with no false line.
- One `is_assigned_mission_number` definition.
- Read-back uses the sanctioned meta read seam.
- The decision-rule outcome for T015 is recorded.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
