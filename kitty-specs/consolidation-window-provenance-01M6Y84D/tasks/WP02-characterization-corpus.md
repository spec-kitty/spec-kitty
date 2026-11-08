---
work_package_id: WP02
title: Characterization corpus with an in-process runner and window-state axis
dependencies: []
requirement_refs:
- FR-016
- NFR-001
- C-008
- SC-005
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent:
- tests/consolidation/characterization_support.py
- tests/consolidation/test_reconciliation_characterization.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/integration/single_branch_window_support.py
execution_mode: code_change
model: ''
owned_files:
- tests/consolidation/characterization_support.py
- tests/consolidation/test_reconciliation_characterization.py
- tests/consolidation/characterization/verdict_corpus.json
- tests/integration/single_branch_window_support.py
- tests/integration/test_single_branch_approval_windows.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Characterization corpus with an in-process runner and window-state axis

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
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Before any code moves out of `src/specify_cli/consolidation/reconciliation.py`, pin **today's actual verdict** for every scenario cell, so the split (Phase 3) has a byte-level witness (FR-016, NFR-001, C-008) and the behaviour changes (Phase 4) can show their diff is limited to named cells (NFR-002).

Done means:

1. `tests/consolidation/characterization_support.py` provides reusable scenario builders, a window-state injector and an **in-process** verdict runner for the three modes (forecast `consolidate --dry-run`, fresh run `consolidate`, resume `consolidate --resume`).
2. `tests/consolidation/characterization/verdict_corpus.json` records, per cell: verdict status (pass/refuse/fail), refusal code(s), divergence fields, exit code. Known-wrong verdicts are recorded **as they are today**.
3. `tests/consolidation/test_reconciliation_characterization.py` recomputes every cell and asserts byte equality with the golden file; a regeneration switch rewrites the golden file deterministically.
3a. `characterization_support.changed_cells(base_ref: str) -> list[str]` returns the sorted cell keys whose value differs between the golden file at `base_ref` (`git show <base_ref>:tests/consolidation/characterization/verdict_corpus.json`) and the working-tree golden file (added and removed keys count as changed). Every Phase 2, 3 and 4 work package uses it as its zero-diff or named-cells check, so it must not depend on uncommitted state alone (post-tasks squad R-01/R-03). It has its own unit test in the test module (a synthetic two-version golden in a scratch git repo: one changed key, one added key).
4. The exception and weaker-check cells (listed in T012) exist in the golden file and record a pass.
5. The `--dry-run` verdict on the post-approval-commit fixture is pinned (R-09), and the finding is written to the tracer.

You do **not** write the intended-verdict `xfail` tests (WP05) or the seeded mutations (WP06); you build what they reuse.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-02 (Purpose and Risks are your acceptance criteria), IC-17 (why the runner must be in process), "Routing hint".
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-09, R-13, R-18.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-016, NFR-001, NFR-002 (the named cells (a)-(h) you must make addressable), Edge Cases.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` section 2 (the `wp_window` shapes your injector writes) and `contracts/status-event-wp-window.md` (the JSON Schema).
- Existing builders to reuse (do not copy-paste them; import them):
  - `tests/terminus/post_approval_support.py` — `build_post_approval_mission(tmp_path, "lanes"|"coord")`, `add_post_approval_commit`, `strip_approval_stamps`, `rework_and_reapprove`, `lane_worktree`.
  - `tests/terminus/canceled_dependency_support.py` — `strip_lane_head_stamps` (model for your injector: it rewrites every copy of the event log and commits it where it lives).
  - `tests/terminus/approved_content_support.py` — `InterruptedConsolidate` (SIGKILL driver pattern).
  - `tests/terminus/rollback_harness.py` — `run_hard_killed`, `state_path`, `state_bookkeeping`, `ref_shas`.
  - `tests/terminus/conftest.py` — `CoordMission`, `run_terminus` (**subprocess**: do not use it for the verdict computation), `_cli_env`.
  - `tests/consolidation/test_reconciliation.py` fixtures, the mixed-lane and canceled-lane builders under `tests/terminus/` (`mixed_lane_support.py`, `canceled_dependency_support.py`).
- Residual counts come from the test files, never from prose (R-13): `tests/consolidation/test_canceled_line_attribution_6309.py`, `tests/consolidation/test_canceled_content_residuals.py`, `tests/consolidation/test_approved_bound_residuals.py`, `tests/integration/test_single_branch_approval_windows.py`.
- Cross-cutting: C-009, C-013, C-014, NFR-004, NFR-005 (no new allowlist entries), mypy-clean test helpers.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T007 – In-process corpus runner (forecast and fresh run)

- **Purpose**: A seeded mutation applied with `monkeypatch` in the test process must reach the verdict computation. A subprocess (`run_terminus`) cannot be reached, so the runner calls the CLI in process.
- **Steps**:
  1. Add `run_in_process(mission, args) -> CellResult` in `characterization_support.py`. Use Typer's `CliRunner` against the `specify_cli` Typer app (find the app object the `spec-kitty` entry point uses; `src/specify_cli/__init__.py` / `main`) or call the `consolidate` command function directly. `chdir` into `mission.repo` with `monkeypatch.chdir`, and apply the same HOME/XDG isolation `_cli_env(mission.home)` builds (set the variables with `monkeypatch.setenv`). Keep `SPEC_KITTY_NO_UPGRADE_CHECK=1`.
  2. `CellResult` captures: `exit_code`, combined output, and a parsed verdict. For `--dry-run --json`, parse the JSON payload. For the fresh run, parse refusal codes from the output (codes are upper-snake tokens such as `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING`; reuse the collapse helper in `tests/terminus/mixed_lane_support.py`).
  3. Divergence fields: when the gate fails, the verifier's `Divergence` fields are rendered in the output; capture the field names present (e.g. `canceled_content`, `canceled_reachable_via_dependency`, `approved_content_missing`), not free text.
  4. Add a control test proving the runner is in process: `monkeypatch` a function on the claim path (e.g. `build_approved_wp_set` in the module that looks it up, `specify_cli.consolidation.phase_claim`) to raise a sentinel; assert the sentinel surfaces in the cell result. Remove nothing afterwards: `monkeypatch` restores. (`phase_claim.py`, `phase_gate.py` and `forecast.py` bind reconciliation names by name; WP04's family helper patches those consumer bindings too, post-tasks squad pedro #1. Here you patch `phase_claim` directly because WP04 may not have landed yet.)
- **Files**: `tests/consolidation/characterization_support.py`, `tests/consolidation/test_reconciliation_characterization.py`.
- **Notes**: Per-test HOME isolation already exists in the root conftest (WP04 of an earlier Mission); do not touch `~/.spec-kitty`.

### Subtask T008 – Resume cells: SIGKILL after claim capture, then in-process resume

- **Purpose**: A resume cell must reach a real interrupted state; a hand-written `state.json` is forbidden (NFR-010), and an exception exit clears or re-baselines the record (#6770), which turns the resume into a fresh run.
- **Steps**:
  1. Write a driver (pattern: `approved_content_support._DRIVER`) that runs the real CLI in a child process and `os.kill(os.getpid(), signal.SIGKILL)` right **after** the claim anchors were saved (`phase_claim.py`, after `save_state` of `pre_interrupt_lane_tips` / `pre_mutation_coord_sha`) and **before** `_phase_merge_lanes` runs. Hook a function called between those two points; inspect `phase_claim.py` and `executor.py` to choose it, and document the choice in a docstring.
  2. After the kill: assert `state.json` exists (`rollback_harness.state_path`) and holds `pre_interrupt_lane_tips`; remove the stale global merge lock (`.kittify/runtime/merge/__global_merge__/lock`), as `InterruptedConsolidate.operator_clears_stale_locks` does.
  3. Run `consolidate --resume` **in process** with `run_in_process`.
  4. Expose this as `interrupt_after_claim(mission) -> None` so WP05 and WP18 reuse it.
- **Files**: `characterization_support.py`.
- **Notes**: Coordinate with WP18's design (same state). If a resume cell cannot be reached for a lane shape, record the cell as `"mode_not_applicable": "<reason>"`, never silently skip.
- **Resume cells exist only on the coordination topology** (post-tasks squad pedro #4). `pre_interrupt_lane_tips` is persisted only when the coordination checkpoint resolves (`phase_claim.py` `_resolve_pre_mutation_coord_sha`: `checkpoint is None -> return None`, nothing saved, ~line 338). So every resume cell builds its shape on the coordination topology (`build_post_approval_mission(tmp_path, "coord")` or the shape's coordination variant). Resume cells of shapes that cannot have a coordination checkpoint (LANES-only, `single_branch`, `planning_lane`) are recorded as `"mode_not_applicable": "no frozen tips without a coordination checkpoint (phase_claim.py _resolve_pre_mutation_coord_sha)"`. Do not try to reach them.

### Subtask T009 – Lane-shape scenario builders [P]

- **Purpose**: One builder per lane shape of IC-02.
- **Steps**: Provide `build_shape(tmp_path, shape) -> ShapeMission` for: `single_lane`, `two_wp_lane`, `mixed_lane_canceled_wp`, `fully_canceled_dependency`, `dependency_chain`, `planning_lane`, `single_branch`. `ShapeMission` is a small `typing.Protocol` (or a frozen dataclass wrapper) exposing what the runner needs: `repo: Path`, `home: Path`, `slug: str`, `target_branch: str`, `topology: str`. `CoordMission` (terminus) and the `single_branch` `Mission` both satisfy it; do not force one into the other's type. Compose existing builders; add history steps only where a shape needs them (e.g. the dependency chain: lane B depends on lane A, merges lane A's tip, then WP on lane B is approved).
- **Builders that do not exist yet** (post-tasks squad pedro #5); you own them:
  - `single_branch`: today the only builder lives inside the test module `tests/integration/test_single_branch_approval_windows.py` (`build_template`, `Mission`, `git`, `cli_env`, `_sk`, `_wp_file` and the `settle`/`move`/`emit`/`commit_file`/`claim`/`implement`/`submit`/`approve`/`send_back`/`build_and_approve`/`consolidate`/`tip` helpers, ~lines 93-320). **Promote** these into a new support module `tests/integration/single_branch_window_support.py` as a pure move: the test module keeps its pytest fixtures (`minted_template`, `checkout`, `mission`) and its tests, and imports the helpers from the support module. Its test names, bodies and results do not change (run it before and after; same pass count). `build_shape(..., "single_branch")` then calls the promoted builder with an explicit `tmp_path` instead of `tmp_path_factory`/`monkeypatch` fixtures (take a `monkeypatch` argument where `chdir`/env is needed).
  - `two_wp_lane`: two approved WPs on **one** lane with the lane worktree reused for the second WP. No builder exists (`post_approval_support.py` is two lanes with one WP each; the mixed-lane builders pair approved with canceled). Write it from `build_post_approval_mission` plus explicit history steps (WP01 claim/commit/approve, WP02 claim on the same lane/commit/approve). WP05 T024 and T029 depend on it.
  - `planning_lane`: a Mission whose only WP is a planning-lane WP (no code lane). No builder is pointed to; build it from the terminus `CoordMission` helpers with a `lanes.json` whose single lane is `lane-planning`.
- Approval-stamp axis: `present` (builder default), `missing` (`strip_approval_stamps`), `rewritten` (rewrite the lane so the stamp is not on it; reuse an existing helper if one exists in `tests/consolidation/test_approved_bound.py`, otherwise `git reset --hard` the lane to a new commit off the base).
- **Files**: `characterization_support.py`.

### Subtask T010 – Window-state injector [P]

- **Purpose**: Before Phase 2 no writer produces `wp_window`, so every window state must be set explicitly after the builder runs (IC-02: "never left to which builder wrote the events"). Before Phase 4 every window state must give today's verdict.
- **Steps**:
  1. `set_window_state(mission, wp_id, state)` with `state` in `recorded`, `not_recorded`, `capture_failed`, `lane_branch_missing`, `not_on_lane`.
  2. Model the file rewrite on `strip_lane_head_stamps`: walk every copy of `status.events.jsonl` in the repo (skip `.git`), rewrite, `git add` + commit where it lives.
  3. On the work package's opening events (non-migration, `to_lane` in `claimed`/`in_progress`): `recorded` -> `{"schema_version": 1, "open_sha": <lane_head of that event, or the lane base>}`; `capture_failed` -> `{"schema_version": 1, "gap": {"reason": "capture_failed", "cause": "git_error", "detail": "test"}}`; `lane_branch_missing` -> gap with that reason, no cause; `not_on_lane` -> `open_sha` of a commit not on the lane (create it with `git commit-tree`, then keep it reachable from a non-lane ref, `git update-ref refs/test/not-on-lane/<wp_id> <sha>`, so a `gc`/`prune` in a copied repo cannot turn "not on lane" into "unresolvable"; post-tasks squad pedro LOW); `not_recorded` -> remove the key.
  4. Use `WP_WINDOW_KEY = "wp_window"` as a local constant (the status export arrives in WP07).
- **Files**: `characterization_support.py`.

### Subtask T011 – Golden serialization, normalization and regeneration

- **Steps**:
  1. Cell key: `"{mode}|{shape}|stamp={stamp}|window={window}"` (plus a variant suffix for named cells). Sort keys; write JSON with `indent=2`, `sort_keys=True`, trailing newline.
  2. Normalize: replace every 40-hex SHA and every `tmp_path` fragment in captured text with stable labels (`<sha:lane-a-tip>` style, or a per-cell first-seen counter). Store codes and field names, not raw prose, except where a cell pins text (FR-023 all-gap cell, T012).
  3. Regeneration: `SPEC_KITTY_REGEN_VERDICT_CORPUS=1 uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py` rewrites the golden file; without the variable, a difference fails with a unified diff of the changed cells.
  4. Expose `assert_cells_match(cells)` and `regenerate_cells(names)` so Phase 4 work packages regenerate **only** their named cells.
- **Files**: `characterization_support.py`, the test module, the JSON.

### Subtask T012 – Generate `verdict_corpus.json`

- **Steps**:
  1. Enumerate cells: mode (forecast, fresh, resume) x shape (T009) x stamp (present, missing, rewritten) x window (T010). Combinations that do not apply are recorded with `"not_applicable": "<reason>"`. **Pruning rule** (post-tasks squad pedro #5; write it verbatim in the test module docstring and apply it in the enumerator, not by hand):
     - **P1 stamp short-circuit.** A `missing` or `rewritten` approval stamp refuses before any window logic (`check_lane`: stamp refusals first, WW-4). So for stamp in {`missing`, `rewritten`} the window axis collapses to one cell, `window=any`; the other four window values are not generated.
     - **P2 no lane window.** `planning_lane` and `single_branch` have no lane window: their generic window axis collapses to `window=any`. (The named `single_branch` (c) cell of step 2 is separate and keeps its window state.)
     - **P3 resume topology.** Resume cells exist only for shapes built on the coordination topology (T008 note); the rest are `mode_not_applicable`.
     - Nothing else is pruned. A pruned combination is not written to the golden file as a cell; the docstring states the rule so a reviewer can recompute the cell count.
  2. Add the named cells NFR-002 will flip, so they are addressable: (a) commit between two approvals incl. gap-then-recorded; (b) its refusal text; (c) rewound work package, **twice**: `fresh|two_wp_lane|...|rewound` (lanes, flipped by WP19) and `fresh|single_branch|stamp=present|window=recorded|rewound` plus its forecast twin (flipped by WP20; post-tasks squad R-07: the `single_branch` half of (c) needs its own golden witness, so `not_applicable` applies only to the generic `single_branch` window axis, never to this named cell); (d) read-error (record the current pass); (e)/(f)/(g) resume after a dependency-lane advance (coordination topology); (h) forecast with an excluded canceled WP.
  2a. Add the **mutation-target cells** WP06 needs (post-tasks squad pedro #2; WP06 owns no corpus file, so they must exist here). Each records today's verdict:
     - `fresh|single_lane|lane_commit_during_run`: a lane commit lands **during** the run, after the claim and before the gate (model: `_inject_then_merge` in `tests/integration/test_single_branch_approval_windows.py`, ~line 73, adapted to the in-process runner by wrapping the first lane-merge step). Target of WP06's `lane-tip-recheck` row.
     - `fresh|single_lane|dependency_ref`: a run with `--dependency-ref <ref>` naming a verified external dependency branch merged into the lane (model: the #6771 tests that pass `--dependency-ref`). Target of `external-dependency-refs`.
     - `resume|single_lane|approved_content_missing`: a lagging checkout whose staged deletions were committed, then `--resume` (model: `tests/terminus/test_resume_refuses_committed_staged_deletions.py`), so the gate reports `APPROVED_CONTENT_MISSING`. Coordination topology. Target of `verifier-presence-axis`.
     - `fresh|single_lane|unattributable_squash_path`: under the default squash strategy, a content path on the target that no approved lane authored (for example a commit added to the mission branch outside every lane before the gate), so `_unattributable_content_squash` reports it. Target of `verifier-squash-axis`.
     If one of these cannot be built in process, record why in the cell (`"mode_not_applicable": "<reason>"`) and tell the orchestrator before WP06 starts; never leave WP06 to invent it.
  3. Add the exception and weaker-check cells pinned as passing (IC-02): dependency chain (FR-007 exception); a gap WP covering a stray commit before a recorded WP (US3-4); an all-gap lane with a post-approval commit whose refusal **text** is pinned (FR-023); a skewed-clock rework; a leading branch-missing opener.
  4. Generate with the regeneration switch, then run without it twice: both runs green, zero diff.
- **Notes**: Keep the suite runtime bounded: share built missions across cells of the same shape where the cell does not mutate the repo (copy the `tmp_path` repo with `shutil.copytree` when a cell mutates).
- **Runtime budget** (post-tasks squad pedro #5): the full corpus test must finish in **at most 10 minutes serial** (`-n0`) and **at most 3 minutes** under `-n auto --dist loadfile` on the reference dev machine. Record both measured times and the generated cell count in the WP history. If the budget is exceeded after pruning, stop and ask the orchestrator; do not drop cells silently. Mark the module `pytest.mark.integration` and `pytest.mark.git_repo` so `make test-fast` (fast/unit tier) never runs it.

### Subtask T013 – Pin the `--dry-run` verdict on the post-approval fixture (R-09)

- **Steps**: Add a named cell `forecast|single_lane|post_approval_commit`. Record whether the forecast reports `LANE_MOVED_AFTER_APPROVAL`. Record the observed answer with `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP02" --entry "R-09: ..."` so WP21 can correct `CLAUDE.md` and the `2026-10-04-5` ADR.

## Test Strategy

Tests are the deliverable. The corpus test must be deterministic (two consecutive runs, zero diff) and must run under `pytest -n auto --dist loadfile` (no shared mutable state across files).

## Definition of Done

Run and record exact commands and pass/fail counts in the WP history:

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # second run: zero diff
uv run --frozen pytest -q tests/consolidation/ -x -q -k "reconciliation or approved_bound or canceled"   # owning subsystem, targeted
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q tests/integration/test_single_branch_approval_windows.py   # same pass count as before the promotion
time uv run --frozen pytest -q -n0 tests/consolidation/test_reconciliation_characterization.py   # budget <= 10 min
time uv run --frozen pytest -q -n auto --dist loadfile tests/consolidation/test_reconciliation_characterization.py   # budget <= 3 min
uv run --frozen ruff check tests/consolidation/characterization_support.py tests/consolidation/test_reconciliation_characterization.py tests/integration/single_branch_window_support.py tests/integration/test_single_branch_approval_windows.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/characterization_support.py tests/consolidation/test_reconciliation_characterization.py tests/integration/single_branch_window_support.py tests/integration/test_single_branch_approval_windows.py
uv run --frozen mypy tests/consolidation/characterization_support.py tests/integration/single_branch_window_support.py
make test-fast
```

- [ ] The in-process control test (T007 step 4) passes and would fail with a subprocess runner.
- [ ] Every resume cell (coordination topology only) asserts `state.json` holds `pre_interrupt_lane_tips` before resuming; every other resume combination is a `mode_not_applicable` cell naming `_resolve_pre_mutation_coord_sha`; zero hand-written `state.json`.
- [ ] Every NFR-002 named cell (a)-(h) (incl. both (c) cells: lanes and `single_branch`), every mutation-target cell (T012 step 2a) and every exception cell (T012 step 3) is present by key.
- [ ] The pruning rule (P1-P3) is in the test module docstring and the generated cell count matches it.
- [ ] `changed_cells(base_ref)` exists with its unit test; `changed_cells("HEAD")` prints `[]` after the golden file is committed.
- [ ] Runtime budget met (both times recorded).
- [ ] `tests/integration/test_single_branch_approval_windows.py` changed only its imports (the helpers moved to `single_branch_window_support.py`); same tests, same pass count.
- [ ] No production code changed (`git diff --stat` shows only the five owned files).
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP02" --entry "<summary>. <detail>"` for the runner design, the SIGKILL hook point, the R-09 answer, the pruning rule and the measured runtime; `--category tooling-friction` for any friction. The command works from any checkout and commits to the coordination surface itself.
- [ ] Never run `make test-full`.

## Risks & Mitigations

- **Vacuous mutations later**: the in-process control is mandatory.
- **Flaky golden**: unnormalized SHAs or temp paths; normalize everything.
- **Slow suite**: share builds; mark the module `integration` + `git_repo` like `test_approved_bound_residuals.py`.
- **Resume cell silently becomes a fresh run**: assert the frozen tips exist before resuming.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid to top** (the window-state axis and the in-process runner are design judgment; golden generation is mechanical).
- Review together with WP18 (routing hint): both decide which state a resume really reaches.
- Spot-check five random cells against a manual `spec-kitty consolidate` run on the same fixture.
- Confirm no production module changed.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
