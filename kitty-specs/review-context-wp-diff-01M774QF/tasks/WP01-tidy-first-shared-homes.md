---
work_package_id: WP01
title: 'Tidy-first: shared homes for the window-opener rule and owned-file matching'
dependencies: []
requirement_refs:
- FR-003
- C-005
- C-007
planning_base_branch: feat/7578-review-context
merge_target_branch: feat/7578-review-context
branch_strategy: Planning artifacts for this mission were generated on feat/7578-review-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7578-review-context unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- src/specify_cli/status/wp_window_selector.py
- src/specify_cli/ownership/matching.py
- tests/status/test_wp_window_selector.py
- tests/specify_cli/ownership/test_matching.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/wp_window_selector.py
- src/specify_cli/consolidation/wp_attribution.py
- src/specify_cli/consolidation/wp_evidence.py
- src/specify_cli/ownership/matching.py
- src/specify_cli/ownership/__init__.py
- tests/status/test_wp_window_selector.py
- tests/specify_cli/ownership/test_matching.py
- src/specify_cli/status/__init__.py
role: implementer
tags: []
tracker_refs: []
---

# WP01: Tidy-first: shared homes for the window-opener rule and owned-file matching

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude --mission review-context-wp-diff-01M774QF
```

## Objective

Move two pieces of pure logic to homes that `src/runtime` and `specify_cli/review` may import, without changing behaviour:

1. The FR-021 window-opener selector, from `consolidation/wp_attribution.py` to a NEW `status/wp_window_selector.py`.
2. The owned-file matcher (`owned_patterns`, `matches_owned`), from `consolidation/wp_evidence.py` to a NEW `ownership/matching.py`.

Both old import paths keep working through re-exports. This is a pure move (Standing Order #2, tidy-first). No caller, verdict or existing test changes.

## Context

- **Why.** Mission #7578 gives every review prompt the work package's own review range. Its base is the FR-021 window open, the same rule consolidation uses (FR-003). The rule must have exactly one definition (C-005). The review side (WP03's `specify_cli/review/wp_range.py`, rendered from `src/runtime/next/prompt_builder.py`) cannot import `consolidation`: `src/runtime -> specify_cli` is a frozen ledger (`_RUNTIME_ALLOWED_SPECIFY_CLI`, `tests/architectural/test_layer_rules.py:178-203`, cap 22) that allows `status` and `ownership`-style subpackages but not `consolidation` (C-007). Moving the rule down into `status/` keeps one definition and keeps the ledger at 22.
- **Why a sibling module.** `status/wp_window.py` is the git-free codec. Its module docstring promises "no git, no I/O and no `specify_cli` imports". The selector needs `StatusEvent` and `is_migration_actor` from `status/models.py`, so it goes into a sibling, `status/wp_window_selector.py` (post-plan squad finding P9). `wp_window.py` is not edited.
- **Why the matcher moves.** WP03's range resolver classifies changed paths as owned or out-of-map. It must use the same matcher as the `IMPLEMENTATION_MISSING` evidence axis, so review and the evidence gate agree (squad finding P2). The matcher is pure (`fnmatch` plus a prefix rule).
- **Facade gate (SR-2).** `tests/architectural/test_status_module_boundary.py` forbids any module outside `specify_cli.status` from importing a `specify_cli.status.*` submodule directly, including `from specify_cli.status.wp_window_selector import ...` and `from specify_cli.status.lane_head import ...`. `consolidation/wp_attribution.py` (this WP) and `review/wp_range.py` (WP03) therefore import the moved names through the `specify_cli.status` facade. `src/specify_cli/status/__init__.py` is in this WP's `owned_files` for exactly that. Do not work around SR-2 with an exemption entry or a lazy submodule import.
- **Who depends on this.** WP03 (range resolver) depends on WP01 and imports the selector names and `read_lane_head` from the `specify_cli.status` facade. WP05 and WP07 (renderer and render sites) use WP03.
- **Decision.** Ruling Q5 (`decisions/`), research R4, plan IC-01.
- **Pure, no git.** `window_open_of` takes injected `on_lane` / `is_ancestor` predicates and performs no git read. That stays true after the move.

**C-010 (per work package): the lane's first commit is a failing test.** Write T004's two new test files first and commit them alone (`test(WP01): red — shared homes for the window rule and owned-file matcher`). They fail on import (`specify_cli.status.wp_window_selector` and `specify_cli.ownership.matching` do not exist yet, and the facade has no `read_lane_head`), for that reason and no other. The moves (T001-T003) follow in later commits and turn them green. Every pre-existing test stays unedited.

Read before starting: `plan.md` (IC-01), `research.md` (R4 and the post-plan squad table, P2/P9/P10), `research/code-grounding.md` sections 3 and 4.

### Subtask T001: Move the FR-021 selector block into `status/wp_window_selector.py`

**Purpose**: give the window-opener rule a home in `specify_cli.status`, verbatim.

**Steps**:

1. Re-read the current file and confirm the ranges before moving anything. On base `73a18543` they are:
   - `src/specify_cli/consolidation/wp_attribution.py:261-263`: `is_migration_event`.
   - `:715-725`: the section comment and `_REWORK_FROM_LANES`, `_PLANNED`.
   - `:728-762`: `WindowGapReason`, `WindowOpen`, `WindowGap`.
   - `:765-795`: `GapEntry`. **It stays in consolidation.** It sits in the middle of the block, so cut around it.
   - `:797-933`: `OpenerSelection`, `_window_value`, `_branch_missing_detail`, `_cycle_start_index`, `_candidates`, `_skip_leading_branch_missing`, `window_opener_events`, `_topological_first`, `_bind`, `window_open_of`.
   - `:64`: `_ENTERED_IMPLEMENTATION_LANES: frozenset[str] = WINDOW_OPENING_LANES`, together with its comment block at 58-63.

   If the line numbers have drifted, locate the block by symbol name. The symbol list is what binds, not the numbers.
2. Create `src/specify_cli/status/wp_window_selector.py`:
   - A module docstring. Say it is the one FR-021 window-opener selector (contract R-1 to R-5, ADR `2026-11-08-2`). Say it was moved from `consolidation/wp_attribution.py` by Mission `review-context-wp-diff-01M774QF` so that `runtime` and `review` can share it. Say it is pure: no git, no I/O, and it takes events in log order plus caller-bound predicates.
   - Intra-package imports only:
     - `from .models import StatusEvent, is_migration_actor`;
     - `from .wp_window import WINDOW_OPENING_LANES, WP_WINDOW_KEY, ParsedWpWindow, RecordedGapReason, parse_wp_window`;
     - stdlib `Callable`, `Sequence`, `dataclass`, `StrEnum`.
   - Move these verbatim: `is_migration_event`, `_REWORK_FROM_LANES`, `_PLANNED`, `WindowGapReason`, `WindowOpen`, `WindowGap`, `OpenerSelection`, `_window_value`, `_branch_missing_detail`, `_cycle_start_index`, `_candidates`, `_skip_leading_branch_missing`, `window_opener_events`, `_topological_first`, `_bind`, `window_open_of`.
   - Define `_ENTERED_IMPLEMENTATION_LANES: frozenset[str] = WINDOW_OPENING_LANES` in the new module. It derives from the codec's constant, so it is not a second definition.
   - Keep the docstrings and the comments, including the `follow_imports = "skip"` annotated-local comment in `_branch_missing_detail`. Under `follow_imports` the type inside `status` may now resolve precisely. If mypy then flags the annotation as redundant, drop the annotation with a one-line reason in the commit message. Do not add `# type: ignore`.
   - In `window_open_of`'s docstring, "raises `GitProbeError` through this function" describes the caller's predicate. Keep the sentence, but do not import `GitProbeError`, because `status` must not import `consolidation`. You may reword it to "a git failure raised by a predicate propagates", with no change in meaning.
   - Add an `__all__` with the public names: `OpenerSelection`, `WindowGap`, `WindowGapReason`, `WindowOpen`, `is_migration_event`, `window_open_of`, `window_opener_events`.
3. Delete the moved definitions from `wp_attribution.py`. Keep `_ENTERED_IMPLEMENTATION_LANES` there as well. `_entered_implementation` (line ~285) still uses it, and it is the same codec-derived alias. Keep `stamp_of`, `GapEntry` and everything else.
4. **Do not edit** `status/wp_window.py`. Its docstring invariant ("no `specify_cli` imports") must stay true.
5. Check the new module's imports against the cold-import gate. `specify_cli.status` is already a forbidden root for the protected cold-import roots, and the new module is reached only through the `status` facade or `wp_attribution`, so no protected root newly pulls it in. Run the gate in T005 to confirm.

**Files**: NEW `src/specify_cli/status/wp_window_selector.py` (~230 lines). `src/specify_cli/consolidation/wp_attribution.py` (about 200 lines removed).

**Validation**: `python -c "import specify_cli.status.wp_window_selector"` succeeds. `git diff --color-moved=zebra` shows the block as moved, not rewritten. `grep -n "def window_open_of\|def window_opener_events\|class WindowGap\b" -r src/` lists exactly one definition of each, in `status/wp_window_selector.py`.

### Subtask T002: Re-export the moved names so every import site keeps working

**Purpose**: behaviour-preserving. No caller and no existing test changes.

**Steps**:

1. **Facade first (SR-2; see Context).** In `src/specify_cli/status/__init__.py`, beside the existing `from .wp_window import (...)` block (~line 427), add:

   ```python
   from .wp_window_selector import (
       OpenerSelection,
       WindowGap,
       WindowGapReason,
       WindowOpen,
       is_migration_event,
       window_open_of,
       window_opener_events,
   )
   ```

   Add the names to `__all__` in the same region as `WP_WINDOW_KEY` / `ParsedWpWindow`, with a one-line comment that names this Mission (the file's existing convention).

   In the same file, extend the existing `from .lane_head import (LANE_HEAD_KEY,)` block (~line 421) with the redundant-alias form `read_lane_head as read_lane_head`, under a one-line comment naming this Mission (`#7578`: WP03's review range reads the live write-branch head through the facade, SR-2). Do **not** add `read_lane_head` to `__all__`: the alias form is the facade's re-export marker for ruff, and `__all__` stays the list of names this package advertises. WP03 imports it as `from specify_cli.status import read_lane_head`. `LaneHeadReading` is not needed by WP03 (it reads `.sha` and `.applicable` attributes only), so do not add it.
2. In `consolidation/wp_attribution.py`, import the moved names through the facade by extending the existing `from specify_cli.status import (...)` block: `OpenerSelection`, `WindowGap`, `WindowGapReason`, `WindowOpen`, `is_migration_event`, `window_open_of`, `window_opener_events`.
   - `is_migration_event` is still used inside `wp_attribution` (lines ~285, ~342, ~685). `GapEntry.from_gap` uses `WindowGap`.
   - Drop imports that are now unused (`parse_wp_window`, `ParsedWpWindow`, `WP_WINDOW_KEY`, `RecordedGapReason`, `is_migration_actor`, maybe `Callable`, `StrEnum`) only if ruff reports them unused. Check each one, because `wp_attribution` may still use some of them elsewhere.
3. Keep `wp_attribution.__all__` exactly as it is today. It already lists `is_migration_event`, `WindowGap`, `WindowGapReason`, `WindowOpen`, `window_open_of`, and those names now resolve through the import. `OpenerSelection` and `window_opener_events` are not in `__all__` today. They stay importable as module attributes (`tests/consolidation/test_window_opener.py:18-26` imports them), so do not add them to `__all__`: that would be a surface change. If ruff `F401` flags a re-export-only import, use the redundant-alias form `name as name`, which the repo already uses in `consolidation/reconciliation.py:79-82`. Do not add `# noqa`.
4. Confirm that every existing import site resolves unchanged, without editing any of them:
   - `consolidation/approved_bound.py:42` (`is_migration_event`);
   - `consolidation/canceled_attestation.py:46` (`is_migration_event`);
   - `consolidation/write_branch_bound.py:49` (`WindowGap`, `WindowOpen`, `window_open_of`);
   - `consolidation/reconciliation_bound.py:29` (`WindowGap`, `WindowOpen`);
   - `consolidation/window_gap_report.py:19` (`WindowGapReason`);
   - `tests/consolidation/test_window_opener.py:18-26` (`OpenerSelection`, `window_opener_events`, ...);
   - `tests/consolidation/test_window_gap_report.py:16`.

   Run `grep -rn "wp_attribution import" src tests --include=*.py` and check each hit.
5. Identity matters. `isinstance` checks and `match` statements on `WindowOpen` / `WindowGap` in `write_branch_bound.py` and `reconciliation_bound.py` must see the same class objects. Because these are re-exports, `wp_attribution.WindowGap is specify_cli.status.wp_window_selector.WindowGap`.
6. Monkeypatch sites. `grep -rn "setattr.*wp_attribution\|wp_attribution, \"" tests` finds any test that patches a moved private helper on `wp_attribution`, for example `_bind`. A patch on the old module no longer reaches the moved function. If any such test exists, **stop and report it** rather than editing the test: the "no test edits" rule binds, and the orchestrator decides.

**Files**: `src/specify_cli/consolidation/wp_attribution.py` (import block). `src/specify_cli/status/__init__.py` (facade: the selector names, plus the `read_lane_head` alias).

**Validation**: `pytest tests/consolidation/test_window_opener.py tests/consolidation/test_write_branch_bound.py tests/consolidation/test_window_gap_report.py -q` is green with no test edits. `pytest tests/architectural/test_status_module_boundary.py -q` is green. `python -c "from specify_cli.status import read_lane_head; from specify_cli.status.lane_head import read_lane_head as r; assert read_lane_head is r"` succeeds.

### Subtask T003: Move `owned_patterns` / `matches_owned` into `ownership/matching.py`

**Purpose**: one owned-file matcher, importable from `review` and `runtime` without `consolidation`.

**Steps**:

1. Confirm the range: `src/specify_cli/consolidation/wp_evidence.py:133-150` on the base (`owned_patterns`, then `matches_owned`).
2. Create `src/specify_cli/ownership/matching.py`:
   - A docstring. Say it is the owned-file matcher shared by the evidence axis, `move-task` and the review range. Say it mirrors `policy.commit_guard._matches_any_glob`, which remains a separate, pre-existing authority for commit scoping that this module does not replace. Keep the existing `matches_owned` docstring text.
   - Stdlib-only imports: `fnmatch`, `collections.abc.Iterable`, `Sequence`. **No `specify_cli` imports.** The module must stay a leaf.
   - Move both functions verbatim, with `__all__ = ["matches_owned", "owned_patterns"]`.
3. In `wp_evidence.py`, delete the two definitions and add `from specify_cli.ownership.matching import matches_owned as matches_owned, owned_patterns as owned_patterns` (redundant-alias form). Keep both names in `wp_evidence.__all__` (lines ~1016 and ~1018). Remove `import fnmatch` only if nothing else in the module uses it.
4. `ownership/__init__.py`: **prefer leaving it unchanged.** Callers import `specify_cli.ownership.matching` directly.
   - Importing the submodule still runs `ownership/__init__`, which eagerly imports `inference`, `validation`, `workspace_strategy` and others, some of which import `specify_cli.status`. Check that `wp_evidence -> specify_cli.ownership` creates no import cycle: `python -c "import specify_cli.consolidation.wp_evidence"` and `python -c "import specify_cli.ownership.matching"` in fresh interpreters.
   - Add the two names to `ownership/__init__.py` and its `__all__` only if a later WP needs the package-level name. WP03 can import from `ownership.matching`, so the default is no change. If you do change it, note it in the PR. CLAUDE.md's `__init__.py` version-bump rule targets the package root `specify_cli/__init__.py`. If in doubt, leave `ownership/__init__.py` unchanged.
5. Leave the `move-task` call sites unchanged: `cli/commands/agent/tasks_move_task.py:985` (`wp_evidence.owned_patterns`) and `:993` (`wp_evidence.matches_owned`) keep working through the re-export. The identity tests `tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py:275` and `tests/consolidation/test_single_branch_evidence_axis.py:224-243` must stay green unedited.

**Files**: NEW `src/specify_cli/ownership/matching.py` (~40 lines). `src/specify_cli/consolidation/wp_evidence.py` (about 18 lines removed, 1 import added). `src/specify_cli/ownership/__init__.py` (expected: unchanged).

**Validation**: `wp_evidence.matches_owned is specify_cli.ownership.matching.matches_owned`. `pytest tests/consolidation/test_single_branch_evidence_axis.py tests/consolidation/test_wp_evidence.py -q` is green.

### Subtask T004: New tests

**Purpose**: pin the new homes and the re-export identity, so a later "fix" cannot fork the rule into two definitions.

**Steps**:

1. `tests/status/test_wp_window_selector.py` (NEW, ~120 lines, marker `fast`/`unit` per `tests/status/` conventions; check `tests/status/conftest.py`):
   - **Facade alias.** `specify_cli.status.read_lane_head is specify_cli.status.lane_head.read_lane_head`, and `"read_lane_head" not in specify_cli.status.__all__` (the alias is a re-export for WP03, not an advertised name).
   - **Identity.** For each name in (`window_open_of`, `window_opener_events`, `OpenerSelection`, `WindowOpen`, `WindowGap`, `WindowGapReason`, `is_migration_event`), assert `getattr(wp_attribution, name) is getattr(wp_window_selector, name)`. Assert the same for the facade, `getattr(specify_cli.status, name) is getattr(wp_window_selector, name)`. The test file itself may import the submodule, because SR-2 scans `src/` only. Confirm that against the gate's file list.
   - **Single definition.** Assert `wp_window_selector.window_open_of.__module__ == "specify_cli.status.wp_window_selector"`.
   - **FR-021 rework smoke.** Build `StatusEvent`s in log order with `policy_metadata["wp_window"]` from `status.wp_window.encode_open` (`tests/consolidation/test_window_opener.py` has helpers to copy the shape from, not import). Use the cycle planned -> claimed(open A) -> in_progress -> for_review -> planned (review rejection) -> claimed(open B), where A is an ancestor of B. Assert `window_open_of(...)` returns `WindowOpen(A)`, because a rejection keeps the window. Add a rewind case: in_progress -> planned, then claimed(open B), returns `WindowOpen(B)`.
   - **Gap smoke.** An opener with no `wp_window` gives `WindowGap(NOT_RECORDED)`. A leading `lane_branch_missing` opener is skipped (`window_opener_events(..., cycle=True).skipped_branch_missing == 1`). A migration-actor event is ignored.
   - Use stub predicates `on_lane=lambda sha: True` and `is_ancestor` backed by a dict. No git.
2. `tests/specify_cli/ownership/test_matching.py` (NEW, ~60 lines), parametrised:
   - `fnmatch`: `("src/m1/x.py", ("src/m1/*",)) -> True`.
   - Prefix rule: `("src/m1/deep/x.py", ("src/m1/**",)) -> True`, `("src/m1/deep/x.py", ("src/m1/*",)) -> True`, `("src/m2/x.py", ("src/m1/**",)) -> False`, `("src/m10/x.py", ("src/m1/**",)) -> False` (the prefix needs the `/` boundary).
   - Normalisation: a path `"./src/m1/x.py"` and a path `"src\\m1\\x.py"` match `("src/m1/**",)`.
   - `owned_patterns(["./src/m1/**", "  ", "a\\b/*"]) == ("src/m1/**", "a/b/*")`.
   - An empty pattern tuple never matches.
   - Identity: `wp_evidence.matches_owned is matching.matches_owned` and `wp_evidence.owned_patterns is matching.owned_patterns`.

**Files**: the two new test files, together ~180 lines.

**Validation**: both files pass. Each identity assertion fails if you temporarily inline a copy of the function (a mental check: do not commit the copy).

### Subtask T005: Verification (targeted; never `make test-full` and never the whole `tests/architectural/`)

**Steps** (record the commands and pass/fail counts for the PR's *Tests run* section):

1. `make test-fast`.
2. Consolidation suites that exercise the moved code:

   ```bash
   uv run --frozen pytest -q \
     tests/consolidation/test_window_opener.py \
     tests/consolidation/test_wp_attribution.py \
     tests/consolidation/test_wp_window_round_trip.py \
     tests/consolidation/test_window_gap_report.py \
     tests/consolidation/test_window_gap_report_entry_points.py \
     tests/consolidation/test_window_predicates.py \
     tests/consolidation/test_write_branch_bound.py \
     tests/consolidation/test_lane_approval_windows.py \
     tests/consolidation/test_approved_bound.py \
     tests/consolidation/test_approved_bound_residuals.py \
     tests/consolidation/test_wp_evidence.py \
     tests/consolidation/test_single_branch_evidence_axis.py \
     tests/consolidation/test_lane_evidence_axis.py \
     tests/consolidation/test_evidence_ownership_unresolved.py \
     tests/consolidation/test_refusal_precedence_matrix_windows.py
   ```

   Then the full owning directory once, `uv run --frozen pytest -q tests/consolidation/`, because `wp_attribution` feeds the whole reconciliation family.
3. `uv run --frozen pytest -q tests/status/ tests/specify_cli/ownership/`.
4. Move-task identity: `uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py` (out-of-matrix, so run it explicitly).
5. Architectural gates, these specific files only:

   ```bash
   uv run --frozen pytest -q \
     tests/architectural/test_layer_rules.py \
     tests/architectural/test_no_dead_symbols.py \
     tests/architectural/test_cold_import_status_boundary.py \
     tests/architectural/test_status_module_boundary.py
   ```

   `test_status_module_boundary.py` is added because of the SR-2 facade import. `test_no_dead_symbols.py` needs every new public name to have a `src/` caller: `wp_attribution` imports the selector names, and `wp_evidence` imports the matcher names, so all of them have one.
6. Lint, format and types on the changed files:

   ```bash
   uv run --frozen ruff check <changed files>
   uv run --frozen ruff format --check --force-exclude <changed files>
   uv run --frozen mypy --strict src/specify_cli/status/wp_window_selector.py src/specify_cli/ownership/matching.py src/specify_cli/consolidation/wp_attribution.py src/specify_cli/consolidation/wp_evidence.py src/specify_cli/status/__init__.py
   ```

7. Classify any red with the CLAUDE.md baseline-red procedure before you treat it as yours.

## Definition of Done

- [ ] T001: `status/wp_window_selector.py` holds the only definition of the FR-021 selector and `is_migration_event`. `status/wp_window.py` is unchanged. `GapEntry` remains in `wp_attribution`.
- [ ] T002: every pre-existing import of the moved names (src and tests) resolves unchanged. The names are on the `specify_cli.status` facade, and `read_lane_head` is re-exported there as an alias (not in `__all__`) for WP03. `wp_attribution.__all__` is unchanged. SR-2 is green with no new exemption.
- [ ] T003: `ownership/matching.py` holds the only definition of `owned_patterns` / `matches_owned`. `wp_evidence` re-exports them and keeps its `__all__`. `move-task` call sites are unchanged.
- [ ] T004: both new test files exist and pass, including the identity and FR-021 rework assertions. They were the lane's first commit, red on import (C-010, per work package).
- [ ] T005: every command above was run, with counts recorded. NFR-006: ruff, ruff format (`--force-exclude`) and `mypy --strict` are clean on the changed files, with no new `# noqa` or `# type: ignore`, and every function has complexity ≤ 15.
- [ ] No existing test file was edited.
- [ ] Tracer files (`tracer-*.md`) are not edited from the lane: anything worth recording (for example a mypy annotation dropped in T001) goes in the completion note, and the orchestrator records it.
- [ ] Each subtask is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done` (event-sourced; no ticked checkboxes as evidence).

## Risks

- **SR-2 facade gate.** The selector must reach `wp_attribution` (and later `review/wp_range.py`) through `specify_cli.status`, so `status/__init__.py` is edited here (it is owned by this WP). Do not exempt the import or hide it in a function-scoped import, because SR-2 catches lazy imports too.
- **Import cycles.** `status/__init__` imports many modules eagerly. The new module imports only `.models` and `.wp_window`, which are both already loaded by the facade, so the risk is low. `wp_evidence -> ownership` pulls in `ownership/__init__`'s eager imports. Mitigation: fresh-interpreter import checks (T003 step 4) and the cold-import gate.
- **Monkeypatch drift.** A test that patches a moved private helper on `wp_attribution` would silently stop patching. Mitigation: the grep in T002 step 6. Escalate, do not edit.
- **Hidden behaviour change.** Re-typing, reordering or "tidying" during the move would break the pure-move promise. Mitigation: move verbatim, and review with `git diff --color-moved`.
- **mypy precision change.** Inside `status`, `ParsedWpWindow` may no longer read as `Any`. Mitigation: fix the annotation properly; do not suppress.
- **Residual (unchanged by this WP).** Parallel or parked claims give an over-wide window (strict xfail `test_parallel_claims_window_is_not_over_wide`, #5721).

## Reviewer Guidance

- Review with `git diff --color-moved=zebra --color-moved-ws=allow-indentation-change`. Apart from imports, docstring headers, `__all__` and the facade lines, the source change must show up as moved blocks. Question any line that is not a moved block.
- Confirm the first lane commit holds only the two new test files and was red on import (C-010).
- Confirm there is no behaviour change. Every pre-existing test passes unedited, and the only test files the diff touches are the two new ones.
- Confirm there is one definition of each moved name (grep for `def window_open_of`, `class WindowGap`, `def matches_owned`) and that the identity tests pin it.
- Confirm `status/wp_window.py` is untouched and still imports nothing from `specify_cli`. Confirm `ownership/matching.py` imports nothing from `specify_cli`.
- Confirm `wp_attribution.__all__` and `wp_evidence.__all__` are unchanged.
- Confirm SR-2 and `test_layer_rules.py` are green with no new allowlist or exemption entries. Confirm the facade diff is limited to the selector import block, its `__all__` lines and the `read_lane_head as read_lane_head` alias.
- Confirm the *Tests run* section lists the exact commands and counts from T005.
