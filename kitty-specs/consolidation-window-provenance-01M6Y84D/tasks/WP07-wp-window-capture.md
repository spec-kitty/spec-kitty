---
work_package_id: WP07
title: LaneHeadReading and wp_window capture on opening transitions
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-002
- FR-003
- NFR-006
- C-002
- C-003
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T034
- T035
- T036
- T037
- T038
- T039
- T040
phase: Phase 2 - Record and unify inputs
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_wp_window_capture.py
- docs/changelog/unreleased/7403-wp-window-capture.internal.md
- tests/consolidation/characterization_support.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/lane_head.py
- tests/consolidation/characterization_support.py
- src/specify_cli/status/transition_pipeline.py
- src/specify_cli/status/__init__.py
- src/specify_cli/status/emit.py
- src/specify_cli/coordination/status_transition.py
- tests/status/test_wp_window_capture.py
- tests/status/test_lane_head.py
- tests/status/test_transition_pipeline.py
- docs/changelog/unreleased/7403-wp-window-capture.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – LaneHeadReading and wp_window capture on opening transitions

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP07 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Record the window-open SHA when a work package's window opens (US1, FR-002, FR-003):

1. On every **non-migration** transition of a **lane-mapped** work package into `claimed` or `in_progress`, the status event's `policy_metadata` gains `wp_window`:
   - `{"schema_version": 1, "open_sha": <sha>}` when the lane head was read (equal to `lane_head` on the same row, invariant WP-1);
   - `{"schema_version": 1, "gap": {"reason": "lane_branch_missing", "detail": ...}}` when the lane branch does not exist;
   - `{"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "git_error"|"probe_error", "detail": ...}}` for any other failed reading.
2. Not-applicable readings (planning lane, work package not in `lanes.json`, no `lanes.json`) write nothing. Migration actors (`migration:` prefix) never write it. Any other `to_lane` (incl. `blocked`) never writes it.
3. `lane_head` stays **byte-identical** for every existing event shape (WP-3); an event that does not qualify is byte-identical to today.
4. The move is never refused, delayed or retried because of the key (WP-4, NFR-006), and the reading is the **one** lane-head reading already taken (0 extra git reads per move).
5. The status pipeline stays git-free (C-002): the probe is injected by the two composition shells.
6. `WP_WINDOW_KEY` is re-exported from `specify_cli.status` like `LANE_HEAD_KEY` (SR-2). **No version bump** (operator ruling 2026-11-08, research R-14); one changelog fragment.
7. Zero verdict change: the characterization corpus (WP02) is unchanged.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md` — the JSON Schema and writer rules W-1..W-7 (**your contract**).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` sections 1 (`LaneHeadReading`, invariants) and 2 (writer table, WP-1..WP-5).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-06.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — US1 (acceptance 1-5), FR-002, FR-003, NFR-006, C-002, C-003.
- Code today:
  - `src/specify_cli/status/lane_head.py`: `LANE_HEAD_KEY`, `LaneHeadProbe` (returns `str | None`), `probe_lane_head` (never raises, C-1), `_resolve_lane_head`, `_branch_head`, `_write_branch_head` (`single_branch` minted write branch, S8).
  - `src/specify_cli/status/transition_pipeline.py`: `_stamped_policy_metadata(...)` (~line 180) — the one stamp site.
  - Shell injection sites: `src/specify_cli/status/emit.py` (~1006-1017, ~1113-1129: `lane_head_probe=probe_lane_head`) and `src/specify_cli/coordination/status_transition.py` (~1646-1655, ~2001-2026).
  - `src/specify_cli/status/__init__.py` (~413-417, ~527): the `LANE_HEAD_KEY` re-export pattern to copy.
  - `specify_cli.status.is_migration_actor` — pure migration-actor check.
- Gates that must stay green: `tests/architectural/test_status_module_boundary.py`, `tests/architectural/test_cold_import_status_boundary.py` (keep `LaneHeadReading` at `lane_head.py` top level with **no** import of `mission_runtime`, `specify_cli.lanes` or `specify_cli.core.git_ops` at module level — those stay function-local as today).
- Cross-cutting: C-009, C-013, C-014, NFR-004 (keep `_stamped_policy_metadata` <= 15 complexity: extract a `_wp_window_value(reading, request)` helper), NFR-005.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP07 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T034 – `LaneHeadReading` and `CaptureCause`

- **Steps**:
  1. In `status/lane_head.py` add `class CaptureCause(StrEnum)`: `LANE_BRANCH_MISSING = "lane_branch_missing"`, `GIT_ERROR = "git_error"`, `PROBE_ERROR = "probe_error"`.
  2. Add `@dataclass(frozen=True) class LaneHeadReading` with `sha: str | None`, `applicable: bool`, `cause: CaptureCause | None`, `detail: str = ""`, and classmethod constructors `of_sha(sha)`, `not_applicable()`, `failed(cause, detail)`. Enforce the invariant (exactly one of sha set / not applicable / cause set) in `__post_init__` (raise `ValueError` — this is a programming error, not a capture failure).
  3. Truncate `detail` to 500 characters (contract `maxLength`).
- **Files**: `src/specify_cli/status/lane_head.py`.

### Subtask T035 – Reading-returning probe, injected by both shells

- **Steps**:
  1. Add `class LaneHeadReader(Protocol)` returning `LaneHeadReading` and `def read_lane_head(*, repo_root, mission_slug, wp_id, owned=None) -> LaneHeadReading` that **never raises** (broad catch -> `failed(PROBE_ERROR, <exception class: message>)`, keeping the C-1 rationale comment).
  2. Refactor `_resolve_lane_head` into a reading-returning `_read_lane_head` that maps today's branches:
     - minted `single_branch` write branch exists -> `of_sha`; missing -> `failed(LANE_BRANCH_MISSING, "Mission branch <b> does not exist")` (keep the warning log);
     - `CorruptLanesError` -> `failed(PROBE_ERROR, "corrupt lanes.json")` (W-3 "any other failed reading"; record this choice in `traces/design-decisions.md`);
     - no manifest / WP not in a lane / planning lane -> `not_applicable()`;
     - `_branch_head` raises -> `failed(GIT_ERROR, str(exc))`;
     - lane branch absent -> `failed(LANE_BRANCH_MISSING, "refs/heads/<branch> not found")` (keep today's warning vs debug log split).
  3. Keep `probe_lane_head(...) -> str | None` as a **thin adapter**: `return read_lane_head(...).sha`. Every existing caller keeps working unchanged.
  4. In the shells, inject the reader instead of the sha probe at every site listed in Context. Keep the function-local import style (`# noqa: PLC0415` already justified there — do not add new suppressions; reuse the existing import line, changing the imported name).
- **Files**: `lane_head.py`, `status/emit.py`, `coordination/status_transition.py`, `transition_pipeline.py` (parameter type).

### Subtask T036 – Write `wp_window` in `_stamped_policy_metadata`

- **Steps**:
  1. Change the parameter to `lane_head_reader: LaneHeadReader | None` (rename consistently in `prepare_transition` and its callers).
  2. Take the reading **once**. `lane_head` logic is unchanged: written iff `reading.sha`.
  3. Add `_wp_window_value(request, reading) -> dict[str, Any] | None`: returns `None` unless all hold: `request.to_lane` in {`claimed`, `in_progress`} (compare with the `Lane` enum, after alias resolution), `not is_migration_actor(request.actor)`, `reading.applicable`. Then map: sha -> `{"schema_version": 1, "open_sha": sha}`; `LANE_BRANCH_MISSING` -> gap without cause; other causes -> `capture_failed` with `cause`.
  4. Merge: `{**(request_policy_metadata or {}), LANE_HEAD_KEY?: sha, WP_WINDOW_KEY?: value}` — only add keys that are set. If nothing is added, return `request_policy_metadata` **unchanged** (same object/None), as today.
  5. Never raise from this path (a malformed reading is a bug caught by T034's invariant at construction).
- **Files**: `src/specify_cli/status/transition_pipeline.py`.

### Subtask T037 – `WP_WINDOW_KEY` export and re-export

- **Steps**: `WP_WINDOW_KEY: Final = "wp_window"` in `lane_head.py` beside `LANE_HEAD_KEY`; re-export from `src/specify_cli/status/__init__.py` exactly as `LANE_HEAD_KEY` is (import block and `__all__`). **Do not** bump `pyproject.toml`'s version (operator ruling, R-14).
- **Then retire WP02's stand-in constant.** WP02's window-state injector in `tests/consolidation/characterization_support.py` declares a local `WP_WINDOW_KEY = "wp_window"` because the status export did not exist yet (WP02 T010 step 4 says the export arrives here). Replace that local constant with `from specify_cli.status import WP_WINDOW_KEY`, so the corpus injector and the writer share one key and cannot drift (single canonical authority). Change nothing else in that file. The golden file must stay byte-identical: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py` passes without the regeneration switch and `git diff --exit-code tests/consolidation/characterization/verdict_corpus.json` is clean. (This shared file is also what places WP07 in the same execution lane as the Phase 1 and Phase 3 work packages; see `traces/design-decisions.md`, 2026-11-08.)
- **Files**: `src/specify_cli/status/lane_head.py`, `src/specify_cli/status/__init__.py`, `tests/consolidation/characterization_support.py`.

### Subtask T038 – `tests/status/test_wp_window_capture.py`

- **Test names** (one per writer-table row, data-model section 2):
  - `test_claim_with_lane_branch_records_open_sha_equal_to_lane_head`
  - `test_in_progress_with_lane_branch_records_open_sha`
  - `test_missing_lane_branch_records_lane_branch_missing_gap_and_move_succeeds`
  - `test_git_error_records_capture_failed_with_git_error_cause`
  - `test_probe_exception_records_capture_failed_with_probe_error_cause`
  - `test_planning_lane_writes_no_wp_window`
  - `test_unassigned_wp_and_no_lanes_json_write_no_wp_window`
  - `test_migration_actor_never_writes_wp_window`
  - `test_blocked_and_other_lanes_never_write_wp_window`
  - `test_non_qualifying_event_is_byte_identical_to_today`
  - `test_move_task_claimed_before_implement_then_in_progress` (US1-5: `move-task --to claimed` before the lane branch exists writes the `lane_branch_missing` gap; the later `in_progress` after the lane branch exists writes `open_sha`)
  - `test_capture_adds_no_git_read` (count `_branch_head` / `run_command` invocations per move: same count as before the change, NFR-006)
  - `test_wp_window_value_matches_contract_schema` (validate every produced value against the contract's JSON Schema; use `jsonschema` if it is already a dependency, otherwise hand-check the shape rules)
- Use real-git fixtures where existing `tests/status/test_lane_head.py` does; inject fake readers for the failure rows (pure pipeline tests).
- **Files**: `tests/status/test_wp_window_capture.py`; adjust `tests/status/test_lane_head.py` / `tests/status/test_transition_pipeline.py` only where the probe parameter rename requires it (behaviour assertions unchanged).

### Subtask T039 – Status boundary and cold-import gates

- **Steps**: run `tests/architectural/test_status_module_boundary.py` and `tests/architectural/test_cold_import_status_boundary.py`; fix any violation by moving imports function-local, never by allowlisting.

### Subtask T040 – Changelog fragment [P]

- **Steps**: create `docs/changelog/unreleased/7403-wp-window-capture.internal.md` with one entry in the style of `docs/changelog/unreleased/README.md`, e.g.:
  `- **Status events record the work-package window-open SHA** (#7403). Every move of a lane work package into \`claimed\` or \`in_progress\` now records \`policy_metadata.wp_window\`: the lane head, or a typed gap (\`lane_branch_missing\`, \`capture_failed\`). The move is never refused.`
- Run `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.

## Test Strategy

ATDD: write `test_wp_window_capture.py` first (red), then implement. Unit tests for the pure pipeline with injected readers; real-git tests for the reader branches.

## Definition of Done

```bash
uv run --frozen pytest -q tests/status/test_wp_window_capture.py tests/status/test_lane_head.py tests/status/test_lane_head_single_branch.py tests/status/test_transition_pipeline.py
uv run --frozen pytest -q tests/status/ tests/coordination/
uv run --frozen pytest -q tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py tests/consolidation/test_reconciliation_intended_verdicts.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check src/specify_cli/status src/specify_cli/coordination/status_transition.py tests/status/test_wp_window_capture.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/status/lane_head.py src/specify_cli/status/transition_pipeline.py src/specify_cli/status/__init__.py src/specify_cli/status/emit.py src/specify_cli/coordination/status_transition.py tests/status/test_wp_window_capture.py
uv run --frozen mypy src/specify_cli/status/lane_head.py src/specify_cli/status/transition_pipeline.py
uv run --frozen python -m scripts.docs.check_changelog_style
make test-fast
```

- [ ] Corpus golden file unchanged (`git diff --exit-code tests/consolidation/characterization/verdict_corpus.json`); intended-verdict tests still all `xfailed`.
- [ ] `pyproject.toml` version untouched.
- [ ] No new `# noqa` / `# type: ignore`; `_stamped_policy_metadata` and the reader functions <= 15 complexity (`uv run --frozen ruff check --select C901 src/specify_cli/status`).
- [ ] **Tracer files**: dated entries in `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (corrupt-`lanes.json` mapping, probe rename) and `traces/tooling-friction.md` (friction). Format `- **[YYYY-MM-DD][implement WP07] <summary>.** <detail>`. No `kitty-specs/` in your checkout: `spec-kitty agent tasks add-history WP07 --note "..."`.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **`lane_head` regression**: `test_non_qualifying_event_is_byte_identical_to_today` and the unchanged `test_lane_head.py` assertions.
- **Cold-import violation**: keep heavy imports function-local.
- **Extra git read**: `test_capture_adds_no_git_read`.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: top** (status pipeline purity and soundness of the recorded value).
- Check W-1..W-6 one by one against the code and tests.
- Check the shells inject the reader at every site that injected `probe_lane_head` (grep both shells).
- If the key shape differs from the contract filed in spec-kitty/spec-kitty-events#229 (the `lane_branch_missing` reason postdates the filing), note it for WP21's follow-up comment draft; do not post on GitHub.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP07 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP07 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
