---
work_package_id: WP01
title: Shared pre-accept exemption in the cut-over predicate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-005
- SC-001
- SC-002
- SC-003
planning_base_branch: fix/cutover-guard-pre-accept-exemption
merge_target_branch: fix/cutover-guard-pre-accept-exemption
branch_strategy: Planning artifacts for this mission were generated on fix/cutover-guard-pre-accept-exemption. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cutover-guard-pre-accept-exemption unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cutover-guard-pre-accept-exemption-01M49DF4
base_commit: 073fd471727275899275f060fc403c7a64661ace
created_at: '2026-10-06T21:47:34.281086+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core fix
history:
- at: '2026-10-06T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/specify_cli/cli/commands/test_cutover_guard_pre_accept.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/status/cutover_eligibility.py
- src/specify_cli/migration/backfill_runtime_state.py
- tests/status/test_cutover_eligibility.py
- tests/specify_cli/migration/test_dogfood_corpus_backfilled.py
- tests/specify_cli/cli/commands/test_cutover_guard_pre_accept.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared pre-accept exemption in the cut-over predicate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission cutover-guard-pre-accept-exemption-01M49DF4`). If present, every feedback item is your TODO list.

---

## Objective

Fix P0 #5835 and #5300. Today a Mission driven only by canonical commands fails the cut-over predicate as soon as its first WP is claimed. The event log carries runtime evidence, and the `status_phase` stamp is written only at accept or consolidate (by design, #2917). Add **one** fail-closed *pre-accept exemption* in `src/specify_cli/status/cutover_eligibility.py` and consume it from **both** verdict paths:

- `is_cut_over` — used by the CI guard (`src/specify_cli/cli/commands/cutover_guard.py::evaluate_touched_missions`).
- `eligible_runtime_missions` — used by `assert_birth_invariant_holds`, which the dogfood corpus test (#5300) calls. **It never calls `is_cut_over`**: it checks `status_phase` directly at `cutover_eligibility.py:~325`.

Read first: `kitty-specs/cutover-guard-pre-accept-exemption-01M49DF4/spec.md` (FR-001…FR-006, C-001…C-005), `plan.md` (IC-01), `data-model.md`, `research.md`.

## Hard constraints

- **Do NOT write `status_phase` anywhere** (C-001/C-002). No birth stamp. `migration/runtime_state_cutover.py` is untouched.
- **No parallel definitions** (C-003). Legacy detection is a new method on the existing `LegacyWPRuntime` dataclass and reads through the existing `read_legacy_runtime`. Terminal evidence uses the same `meta.json` fields `migrate backfill-wp-status` uses.
- **Fail closed** (FR-005). An exception, a missing or malformed `meta.json`, a malformed `status_phase`, or an absent `mission_id` must never produce PASS.
- Complexity ≤ 15 per function; ruff, `ruff format --check --force-exclude` and mypy clean on the touched files. No new `noqa` / `type: ignore`, except that the existing local-import `# noqa: PLC0415` pattern may be reused, with its rationale comment.
- Terminology: "Mission", never "feature", in new identifiers, docstrings and messages.
- **Tests: targeted files only.** Never run `make test-full`, the whole `tests/architectural/`, or e2e/perf suites.

## Branch Strategy

- Planning base and final merge target: `fix/cutover-guard-pre-accept-exemption`. The PR later goes to upstream `main`.
- Your execution worktree is allocated per computed lane from `lanes.json`. Prepare it **only** with `spec-kitty agent action implement WP01 --agent claude --mission cutover-guard-pre-accept-exemption-01M49DF4`, and work in the path it returns. Never reconstruct worktree paths.

## Subtasks

### T001 — Red-first #5835 repro through the guard's entry point

**Purpose**: prove the P0 through the pre-existing entry point before any fix (ADR `2026-07-17-1`, DIRECTIVE_034/041).

**File**: `tests/specify_cli/cli/commands/test_cutover_guard_pre_accept.py` (new).

**Steps**:
1. Build a fixture Mission under `tmp_path/kitty-specs/<slug>/`:
   - `meta.json` with `mission_id` (any valid ULID-like string), `mission_slug`, and **no** `status_phase`, `accepted_at`, `merged_at` or `mission_number` (or `mission_number: null`).
   - `tasks/WP01-x.md` whose frontmatter is the **real WP template frontmatter**, empty values included (`agent: ""`, `assignee: ""`, `shell_pid: ""`). Copy those keys from `packs/built-in/missions/software-dev/templates/task-prompt-template.md` by reading the file at test time, or inline them verbatim with a comment naming the source. That pins the fact that empty template values do not count as legacy runtime.
   - `tasks.md` with a WP01 section and **checked** subtask reference rows (checkboxes are authoring and must not block the exemption).
   - `status.events.jsonl` holding a bootstrap `planned` event plus a `planned -> claimed` event whose `policy_metadata` carries `{"agent": "claude", "shell_pid": 1234}`. Reuse the event-construction helpers already used in `tests/status/test_cutover_eligibility.py` (`_genesis_to_planned`, and the claim test at `:65`) rather than hand-rolling JSON. Write through `specify_cli.status.store.append_event`.
2. Call `evaluate_touched_missions` (read its signature at `cutover_guard.py:169`) for that slug and assert `verdict.passed is True`. Also assert the per-Mission `CutOverVerdict` reasons contain the pre-accept note.
3. Mark the test `@pytest.mark.regression` and pin the issue (`# issue #5835`; use `p0_repro(issue=5835)` if that marker helper exists — check `tests/conftest.py` / `grep -rn "def p0_repro" tests`).
4. **Run it on the unmodified code and confirm it is RED** with `status_phase not flipped despite event-log runtime evidence`. Record the command and the failing output in your Activity Log / commit message body.

### T002 — Red-first #5300 repro through `assert_birth_invariant_holds`

**File**: `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` (existing; add a test next to the synthetic-corpus test around `:300-325`).

**Steps**:
1. Build a synthetic corpus in `tmp_path`: one exempt-shaped Mission (the T001 shape; factor a shared builder only if it stays inside your owned files, otherwise duplicate the small builder) plus one stamped, fully-cut-over Mission, so the corpus is non-empty for the `assert missions` check. Note that a stamped Mission must also pass `verify_backfill` and have a non-empty runtime snapshot. Look at how the existing synthetic test builds its healthy Mission and reuse that.
2. Assert `assert_birth_invariant_holds(corpus)` does **not** raise. On the base it raises `eligible missions not cut over: [...]`, so it is RED first. Mark it `regression` and pin #5300.
3. If building a fully healthy stamped Mission is disproportionate, assert instead that `eligible_runtime_missions(corpus)` excludes the exempt Mission and includes an unstamped *accepted* twin. Document the choice in the test docstring.

### T003 — `LegacyWPRuntime.has_frontmatter_runtime()`

**File**: `src/specify_cli/migration/backfill_runtime_state.py` (dataclass at `:192-232`).

**Steps**:
1. Add a method next to `has_claim_state`:
   ```python
   def has_frontmatter_runtime(self) -> bool:
       """True when the WP FILE carries runtime state (claim, assignee, tracker refs, completed review).

       Narrower than :meth:`has_evictable_state`: ``subtasks`` come from ``tasks.md``
       reference rows, which every natively-born Mission authors, so they are not
       evidence of un-migrated legacy runtime (#5835).
       """
       return bool(
           self.has_claim_state()
           or self.assignee is not None
           or self.tracker_refs
           or (self.review is not None and self.review.complete)
       )
   ```
2. Leave `has_evictable_state` unchanged. It drives backfill seeding.
3. Unit-test it in `tests/status/test_cutover_eligibility.py` (owned), or wherever the existing `LegacyWPRuntime` tests live if that file is yours. Otherwise keep the tests in your owned eligibility test file. Construct `LegacyWPRuntime` directly. Cover:
   - all empty → False;
   - subtasks only → False;
   - `agent` → True;
   - `assignee` → True;
   - `tracker_refs` → True;
   - completed review → True;
   - incomplete review → False.

### T004 — `pre_accept_exemption(mission_dir) -> str | None`

**File**: `src/specify_cli/status/cutover_eligibility.py`.

**Contract** (see `data-model.md`): return the note string `PRE_ACCEPT_EXEMPT_NOTE` (a module constant, for example `"pre-accept: status_phase stamp deferred to accept/consolidate"`) only when **all** of the following hold. Otherwise return `None`.
1. `meta.json` exists and parses to a mapping. **Do not use `_read_meta` alone for this**: it returns `{}` on malformed input, which would look like "no terminal evidence". Call `load_meta(..., on_malformed=...)` in its raising or sentinel mode; read `load_meta`'s signature to see what it offers. Keep `encoding="utf-8-sig"` (the BOM fix, #1440).
2. `status_phase` is absent/null, or a well-formed integer `< 1`. **A present but non-integer value is malformed**, so return `None`. Note that the existing `status_phase()` returns `None` for both absent and malformed values, so you need the raw value to tell them apart.
3. No terminal evidence: `accepted_at` and `merged_at` are absent or empty after `str().strip()`, and `mission_number` is absent or `None`. **`0` counts as evidence.**
4. `read_legacy_runtime(mission_dir)` succeeds and no WP reports `has_frontmatter_runtime()`. **Any exception** (`LegacyRuntimeReadError`, `OSError`, `UnicodeDecodeError`, `ValueError`, …) returns `None`. Catch `Exception` with a `# noqa: BLE001` and a comment that fail-closed is the contract, mirroring the existing `verify_backfill` catch in `is_cut_over`.

Split the four checks into small private helpers (`_terminal_evidence(meta)`, `_raw_phase_state(meta)`, `_carries_frontmatter_runtime(mission_dir)`) so every function stays ≤ 15. Import `read_legacy_runtime` locally with the same circular-import rationale comment as the existing `verify_backfill` import.

The helper must also be able to tell the caller *why* it declined, so `is_cut_over` can emit a reason-specific FAIL (FR-007). Recommended shape: return a small frozen dataclass or a `(note | None, block_reason | None)` pair. Define the block-reason strings as module constants, because WP02 reuses them for the remedy text:
- `REASON_TERMINAL_UNSTAMPED` — e.g. "accepted/merged but status_phase not stamped"
- `REASON_LEGACY_FRONTMATTER` — e.g. "WP frontmatter carries legacy runtime to migrate"
- `REASON_PHASE_MALFORMED`
- `REASON_META_UNREADABLE`
- `REASON_LEGACY_UNDECIDABLE`

Keep `"status_phase not flipped despite event-log runtime evidence"` as the prefix of the terminal and legacy reasons, so existing assertions and greps still match. Check `grep -rn "status_phase not flipped" tests src` and keep every hit green.

### T005 — Wire into `is_cut_over` and `eligible_runtime_missions`

1. In `is_cut_over` (`:234`), replace the `phase < 1` block (`:271-277`):
   - malformed phase → FAIL with `REASON_PHASE_MALFORMED`. Today it reads as `< 1`; keep it a FAIL, just name it.
   - phase absent or `< 1` → consult the exemption. If exempt: `CutOverVerdict(cut_over=True, reasons=(PRE_ACCEPT_EXEMPT_NOTE,))`. Otherwise FAIL with the block reason.
   - phase ≥ 1 → unchanged strict path (snapshot plus `verify_backfill`).
   - Update the class and function docstrings: a PASS may now carry one explanatory reason. **Check every consumer** of `CutOverVerdict.reasons` (`grep -rn "\.reasons" src/specify_cli | grep -i cut`) for logic that treats non-empty reasons as failure, and report any you find. `cutover_guard.py` belongs to WP02, so if it breaks, note it rather than editing it — unless a one-line fix is required to keep tests green, in which case record a rationale.
2. In `eligible_runtime_missions` (`:199`), skip Missions for which the exemption holds, and update the docstring. `assert_birth_invariant_holds` then inherits it. Do **not** change `assert_birth_invariant_holds`'s strictness for stamped Missions.
3. Keep the module docstring accurate. It describes both consumers sharing one predicate; amend it to say they share the exemption.

### T006 — Verdict matrix + repro conversion

**File**: `tests/status/test_cutover_eligibility.py`.

1. Write a parametrized matrix over `is_cut_over`, one fixture builder, one varied attribute per cell (NFR-001: only the first exempt cells change verdict):

| Cell | Expect |
|---|---|
| no event-log evidence | PASS, no reasons |
| evidence, no stamp, pre-accept, template frontmatter | PASS + note |
| same + checked subtasks in tasks.md | PASS + note |
| + `accepted_at` | FAIL terminal |
| + `merged_at` | FAIL terminal |
| + `mission_number: 0` | FAIL terminal |
| + `agent: claude` in WP frontmatter | FAIL legacy |
| + `assignee: x` | FAIL legacy |
| + `tracker_refs: [X-1]` | FAIL legacy |
| `status_phase: "abc"` | FAIL malformed |
| `status_phase: "0"` pre-accept | PASS + note |
| meta.json is invalid JSON (with a mission_id-free fallback) | FAIL (absent mission_id or meta unreadable — assert not cut over) |
| WP file unreadable/unparsable frontmatter | FAIL undecidable |
| absent mission_id | FAIL (unchanged) |

2. A stamped, verified Mission stays PASS. Reuse an existing passing fixture if the file has one; if building it is heavy, cover it in T002's corpus instead and say so.
3. **Repro conversion**: the T001/T002 repros pin a defect that is now fixed. Per ADR `2026-07-17-1`, convert them into ordinary focused tests: drop `@pytest.mark.regression` / `p0_repro` and keep the issue reference in the docstring. They must not stay marked `regression`.
4. Corpus no-drift check (not committed): run a throwaway loop over `kitty-specs/*` calling `is_cut_over` and confirm the baseline **576 PASS / 5 FAIL (absent mission_id)**, give or take the Missions added since. Report the counts.

## Test commands (targeted only)

```bash
.venv/bin/python -m pytest tests/status/test_cutover_eligibility.py tests/specify_cli/cli/commands/test_cutover_guard_pre_accept.py tests/specify_cli/cli/commands/test_cutover_guard.py tests/specify_cli/migration/test_dogfood_corpus_backfilled.py tests/specify_cli/cli/test_accept_birth_cutover.py tests/specify_cli/upgrade/test_runtime_state_backfill_migration.py -q
.venv/bin/python -m pytest tests/status -q -m "fast or unit"
uv run --frozen ruff check src/specify_cli/status/cutover_eligibility.py src/specify_cli/migration/backfill_runtime_state.py <your test files>
uv run --frozen ruff format --check --force-exclude <same files>
uv run --frozen mypy src/specify_cli/status/cutover_eligibility.py src/specify_cli/migration/backfill_runtime_state.py
```

Use `.venv/bin/python`, never a bare `uv run pytest`, which re-syncs the venv.

## Definition of Done

- T001/T002 were RED on the unmodified code (evidence recorded) and are GREEN now, converted to focused tests.
- Every matrix cell passes. Existing cut-over, guard and accept tests are green.
- ruff, format and mypy are clean on touched files. Complexity ≤ 15.
- No `status_phase` writer added (`git diff` shows no new write).
- Subtasks marked with `spec-kitty agent tasks mark-status T001 ... --status done --mission cutover-guard-pre-accept-exemption-01M49DF4`.
- Commit in the lane worktree with a conventional message (`fix(status): ...`) that cites #5835 and #5300. End the commit message with the session attribution trailers given to you by the orchestrator.

## Risks / reviewer guidance

- **Over-broad exemption**: verify every strict cell has a same-fixture positive control (non-vacuity).
- **Hidden consumer** treating non-empty `reasons` as failure (T005.1).
- **BOM / malformed meta**: the exemption must not regress #1440's BOM tolerance, and must not pass on a malformed meta.
- **Activity Log**: append notes below.

## Activity Log

