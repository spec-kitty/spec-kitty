---
work_package_id: WP02
title: 'Selector: loud mismatch, file granularity, single base enumeration'
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-004
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Foundations
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/shard_select.py
- tests/ci/test_shard_select.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- scripts/ci/shard_select.py
- tests/ci/test_shard_select.py
- tests/architectural/test_module_length_agreement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Selector: loud mismatch, file granularity, single base enumeration

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

WP01 extracted the selector behaviour-preserving into `scripts/ci/shard_select.py`. This WP
extends that single authority (C-010, D-01) with three capabilities the battery partition needs,
and fixes #5092 acceptance criterion 2:

1. **Loud mismatch (FR-005)** — in test granularity (module rows) a timing-length mismatch still
   uses uniform weights (module rows keep their assignment), but now prints a GitHub
   `::warning title=shard timings::…` annotation **and** appends one line to
   `$GITHUB_STEP_SUMMARY`. Never silent again.
2. **File granularity** — weights keyed by repo-relative test-file path; a file with no timing
   gets the **median** of the known weights (never uniform-for-all); missing and stale keys are
   reported loudly through the same channel.
3. **Single base enumeration (D-24)** — `enumerate_base_files(...)` is THE list of battery test
   files. The WP05 plugin and the WP06 gate-model partition both call it; a WP06 test proves they
   agree.
4. **Battery partition math** — `battery_parts(...)` computes `fast`, `1/n` … `n/n` from base
   files, the fast roster, `shard_count` and per-file timings (R1 D-SEL). It lives here, in the
   shared selector, because both the plugin (WP05) and `_gate_coverage` (WP06) must compute the
   same partition ("via the shared selector", tasks.md T024) and neither of them owns this file.
5. `tests/architectural/test_module_length_agreement.py` imports the shared marker constant
   instead of carrying its own copy.

Definition of Done ties: FR-005 (loud, both granularities), FR-004 (partition is computable by one
pure function from data the registry and timings hold), C-010 (no second enumeration, no second
LPT).

## Context & Constraints

- Read first: `tasks.md` global rules; `research.md` D-01, D-24, D-29, D-31 and R1 §1 "D-SEL",
  §4d "FR-005 behaviour", §4e; `contracts/battery-partition.md` (partition semantics 1-4);
  `data-model.md` ("Battery shard partition", "Shard timings").
- Depends on WP01: `MODULE_SELECTION_MARKER_EXPR`, `lpt_assign`, `lpt_loads`,
  `positional_weights`, `resolve_module_test_dirs`, and the `module` CLI already exist. Anchor on
  those names; WP01 removed the inline heredoc from `.github/workflows/module-tests.yml`.
- Module scope stays **stdlib-only** (WP01 rule: `capture_shard_timings.py` is exercised with
  `python -I -S`).
- **No local heavy suites** (C-009). Collect-only runs of `tests/architectural` are not test runs
  (the quickstart uses them); the full-battery *run* is forbidden.
- Lane discipline: `uv run --frozen …`; never `git stash`. Terminology: Mission; "gate selection".
- Complexity ≤ 15 per function; constants for literals used ≥ 3 times; every new branch tested.

### Current-state anchors (verified 2026-10-01; WP01 changes the first row)

| What | Where |
|---|---|
| Silent uniform fallback | was `module-tests.yml:251-252`; after WP01 it is `shard_select.positional_weights` |
| Consumer marker copy | `tests/architectural/test_module_length_agreement.py:111` `_CONSUMER_MARKER_EXPR = "not performance and not stress"`, used at :283 in `_live_collected_count` |
| Pinning-inventory anchor in that file | `tests/release/pinning_rule_inventory.json` records `test_module_length_agreement.py::<module-docstring>` at **line 63**. Do not edit lines 1-93 (the module docstring), or the line shifts and the inventory needs regeneration |
| Default `python_files` | pytest default (`test_*.py`, `*_test.py`); `pytest.ini` does not override it (pinned by `test_module_shard_registry.py::test_pytest_ini_does_not_override_python_files_4388`, :441-471) |
| Battery tree | `tests/architectural`: 239 `test_*.py` files on disk on `bc826fcbcb` (238 at planning; #5503 deleted `test_refresh_dead_symbol_hashes.py` and added `test_dead_symbol_allowlist_{contract,loader}.py`, D-37) (one nested: `tool_artifact_enrolment/test_enrolment_inventory.py`), no `*_test.py`; ~36 `_*.py` helpers; `conftest.py`; non-test dirs `_fixtures/`, `_workflow_fixtures/`, `_exemptions/`, `fixtures/`, `census/`, … |
| Base selection | `ci-router.yml` job `architectural-heavy` (≈ lines 555-606): `pytest tests/architectural -m "not performance and not stress and not timing"` with 4 whole-file `--deselect`s: `test_no_legacy_terminology.py`, `test_layer_rules.py`, `test_pyproject_shape.py`, `test_archive_root_byte_identical.py` |
| Measured | collect-only of that base selection: **3394/3602 tests** (208 deselected) on `bc826fcbcb`, ~3 s locally (3357/3565 at planning) |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first tests: loud mismatch, file mode, enumeration, partition

- **Purpose**: Pin each new behaviour before implementing it (ATDD, charter ATDD-First Discipline). All are red today
  because the functions do not exist or the fallback is silent.
- **Steps** (all in `tests/ci/test_shard_select.py`, appended to WP01's tests):
  1. **Loud mismatch, module mode**: call the `module` CLI path's weight step with 5 node ids and
     3 durations, `monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))`,
     capture stdout with `capsys`. Assert: weights are uniform; stdout has exactly one line
     starting `::warning title=shard timings::` naming the module, `3 committed` and
     `5 collected`; the summary file has exactly one appended line. Assert the agreeing case
     prints nothing and writes nothing. With `GITHUB_STEP_SUMMARY` unset, the annotation still
     prints and no file is written.
  2. **WP01 characterization stays green**: the T001 reference test must still pass. Loud
     reporting changes output channels, not assignments.
  3. **File mode**: `resolve_file_weights(["a.py","b.py","c.py"], {"a.py": 10.0, "b.py": 30.0, "z.py": 5.0})`
     → weights `a=10, b=30, c=20` (median of the known weights *of base files*), mismatch record
     lists `missing=("c.py",)` and `stale=("z.py",)`. No timings at all → every weight `1.0` and
     a record whose reason says "no timings for this key". The median uses only timings of base
     files, so stale keys never skew it.
  4. **Never uniform-for-all when some timings exist**: with 1 of 10 files timed, the 9 untimed
     files get that single timing (median of one), not `1.0`.
  5. **Enumeration semantics** on a synthetic tree under `tmp_path`: `pkg/test_a.py`,
     `pkg/b_test.py`, `pkg/sub/test_c.py`, `pkg/conftest.py`, `pkg/_helper.py`,
     `pkg/_fixtures/test_fixture_like.py`, `pkg/.hidden/test_d.py`,
     `pkg/__pycache__/test_e.cpython-312.pyc`, `pkg/data/test_f.txt`. With
     `deselect=("pkg/b_test.py",)` expect exactly `("pkg/_fixtures/test_fixture_like.py", "pkg/sub/test_c.py", "pkg/test_a.py")`,
     sorted, posix. (`_fixtures` IS recursed by pytest's default `norecursedirs`; only the
     file-name rule excludes `_`-prefixed *files*. Verify that claim with a real
     `pytest --collect-only` on the same tree inside the test and assert equality, so the test
     encodes pytest's behaviour rather than our belief about it.)
  6. **Enumeration vs real collection of the battery** (mark `@pytest.mark.slow`, one subprocess,
     ~3-15 s): run `sys.executable -m pytest tests/architectural --collect-only -q -p no:cacheprovider`
     with the 4 base `--deselect`s and **no** `-m` filter, cwd = repo root. Assert the set of
     files with ≥ 1 collected item == `enumerate_base_files(["tests/architectural"], deselect=…, root=REPO_ROOT)`.
     Without a marker filter every enumerated file that defines a test is collected; marker
     filtering is per item and file-independent, so this is the exact contract the partition
     proof relies on. If some enumerated file legitimately defines zero tests, assert it is
     listed by name in a small, commented constant (expected: empty today).
  7. **`battery_parts`**: base `[f"t/test_{i:02d}.py" for i in range(12)]`, roster `[t/test_00, t/test_05]`,
     `shard_count=2`, timings for 8 files. Assert: keys `{"fast","1/2","2/2"}`; `fast` == roster;
     parts pairwise disjoint; union == base; deterministic under shuffled input order of base,
     roster and timings dict; loads skew ≤ 20 % for these weights; a roster entry not in base
     raises `ValueError` naming it; `shard_count < 1` raises.
  8. Commit the red state (import errors / failing assertions) before implementing.
- **Files**: `tests/ci/test_shard_select.py`.
- **Parallel?**: No.
- **Notes**: Use `pytest.mark.fast` for pure tests, `pytest.mark.slow` for the subprocess one
  (both are in `pytest.ini` `markers`).

### Subtask T007 – Implement loud mismatch in test granularity

- **Purpose**: FR-005 / #5092 AC2 for module rows, assignment unchanged.
- **Steps**:
  1. Introduce a frozen dataclass `WeightResolution(weights: tuple[float, ...], missing: tuple[str, ...], stale: tuple[str, ...], reason: str | None)`
     with a `mismatch` property (`reason is not None`).
  2. Change `positional_weights` into `resolve_positional_weights(node_ids, durations) -> WeightResolution`;
     on a length mismatch: uniform weights plus
     `reason=f"{len(durations)} committed durations vs {len(node_ids)} collected — uniform weights"`.
     Keep a thin `positional_weights` wrapper only if something still calls it; otherwise delete
     it (no dead code).
  3. `report_mismatch(resolution: WeightResolution, *, label: str, stream: TextIO = sys.stdout) -> None`:
     prints `::warning title=shard timings::{label}: {reason}` (plus missing/stale counts and up
     to 10 names in file mode), and appends one line `- shard timings — {label}: {reason}` to the
     file named by `$GITHUB_STEP_SUMMARY` when set. Escape `%`, `\r`, `\n` in the annotation
     message per GitHub's workflow-command rules (factor a tiny helper, test it).
  4. Call it from the `module` CLI with `label=f"module {module}"`.
  5. Today this fires for the allow-listed modules in `test_module_length_agreement.py`'s
     `_MISMATCH_ALLOWLIST` (19 entries). That visibility is intended (research R1 §4d); say so in
     the docstring.
- **Files**: `scripts/ci/shard_select.py`.
- **Parallel?**: After T006.
- **Notes**: Do not change `module-tests.yml`; WP01's step already calls the CLI.

### Subtask T008 – File-granularity mode, `enumerate_base_files`, `battery_parts`

- **Purpose**: The battery cannot use positional pairing (its test count drifts daily); it needs
  file keys, a single enumeration and one partition function (D-01, D-24, contract semantics 1-4).
- **Steps**:
  1. `DEFAULT_PYTHON_FILES: Final = ("test_*.py", "*_test.py")` and
     `NORECURSE_DIR_PATTERNS: Final` mirroring pytest's default `norecursedirs`
     (`*.egg`, `.*`, `_darcs`, `build`, `CVS`, `dist`, `node_modules`, `venv`, `{arch}`) plus
     `__pycache__`. Cite pytest's documented default in a comment.
  2. `enumerate_base_files(paths: Sequence[str], *, deselect: Iterable[str] = (), root: Path, python_files: Sequence[str] = DEFAULT_PYTHON_FILES) -> tuple[str, ...]`:
     walk each path under `root` (sorted, deterministic), skip directories matching
     `NORECURSE_DIR_PATTERNS`, keep files whose basename matches a `python_files` glob
     (`fnmatch`), drop `conftest.py` and any basename starting with `_`, drop exact whole-file
     `deselect` entries (entries containing `::` are node-level and are **not** whole-file —
     ignore them here and document why), return sorted repo-relative posix paths. A path argument
     that is itself a file is enumerated if it matches.
  3. `resolve_file_weights(files: Sequence[str], file_durations: Mapping[str, float]) -> WeightResolution`:
     median (`statistics.median`) of the timings of files present in `files`; missing files get
     that median; no usable timings → `1.0` each with a reason; stale = timing keys not in
     `files`, sorted.
  4. `@dataclass(frozen=True) class BatteryPartition: parts: Mapping[str, frozenset[str]]; loads: Mapping[str, float]; resolution: WeightResolution`.
  5. `battery_parts(base_files, roster, shard_count, file_durations) -> BatteryPartition`:
     - validate `shard_count >= 1`, every roster entry ∈ base (else `ValueError` listing them);
     - `fast` = frozenset(roster);
     - remaining = sorted(base − roster) (pre-sorted by path for determinism);
     - weights via `resolve_file_weights(remaining, file_durations)`;
     - `lpt_assign(list(zip(remaining, weights)), shard_count)` → keys `f"{i}/{shard_count}"`
       (1-based); loads from the same placement (`lpt_loads` over the same order, or compute in
       one pass — but one algorithm only).
  6. Optional CLI subcommand `battery-parts --registry … --timings … --root .` printing each part
     with its file count and predicted load: helps WP05/WP14 humans; keep it ≤ 30 lines.
  7. `uv run --frozen mypy --strict scripts/ci/shard_select.py`; ruff clean.
- **Files**: `scripts/ci/shard_select.py`.
- **Parallel?**: Independent of T007 after T006.
- **Notes**: Registry and timings parsing (YAML) stay in the callers (plugin, gate model); this
  module takes plain data so it remains stdlib-only and trivially testable.

### Subtask T009 – `test_module_length_agreement.py` imports the shared marker constant

- **Purpose**: Third copy of the marker removed (C-010). After WP01 the module-tests selector and
  the capture use `MODULE_SELECTION_MARKER_EXPR`; the length gate must measure the same selection.
- **Steps**:
  1. Replace line 111's literal with
     `from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR as _CONSUMER_MARKER_EXPR`
     in the import block (below the module docstring), keeping the name `_CONSUMER_MARKER_EXPR`
     so `_live_collected_count` (:283) is untouched. Keep and shorten the comment at :106-110 to
     point at the shared constant.
  2. Do **not** edit the module docstring (lines 1-93); the pinning inventory anchors line 63.
  3. Add one fast self-check in that file: `assert _CONSUMER_MARKER_EXPR == "not performance and not stress"`
     is *not* what we want (that re-pins a literal); instead assert it `is` the shared constant
     object, which proves the import, not a copy.
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: Yes, any time after WP01.
- **Notes**: `tests/architectural` is a package (`tests/__init__.py`), so the repo root is on
  `sys.path` under pytest; `test_gate_selection_authority.py` already imports `scripts.ci.*`.

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_shard_select.py tests/ci/test_capture_shard_timings.py -q
uv run --frozen pytest tests/architectural/test_module_length_agreement.py -q     # full file: its slow tests collect every module tree (minutes, not a heavy suite)
uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q
make test-fast
uv run --frozen ruff check scripts/ci/shard_select.py tests/ci/test_shard_select.py tests/architectural/test_module_length_agreement.py
uv run --frozen ruff format --check .
uv run --frozen mypy --strict scripts/ci/shard_select.py
python3 scripts/ci/derive_pinning_inventory.py --stdout > /tmp/inv-tip.json   # compare with the base: no new delta
```

- Manual smoke (collect-only, record output in the Activity Log):
  `uv run --frozen python -c "from pathlib import Path; from scripts.ci.shard_select import enumerate_base_files as e; print(len(e(['tests/architectural'], deselect=['tests/architectural/test_no_legacy_terminology.py','tests/architectural/test_layer_rules.py','tests/architectural/test_pyproject_shape.py','tests/architectural/test_archive_root_byte_identical.py'], root=Path('.'))))"`
  — expect 235 on `bc826fcbcb` (239 files − 4 deselected; 234 at planning; re-count at implementation time).
- The pinning inventory is green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37). Add no delta (`--check` stays green); do not regenerate.

## Risks & Mitigations

- **Enumeration diverges from pytest** (a custom collector, a `collect_ignore`, a changed
  `norecursedirs`) → T006 step 6 compares against a real collection; WP05's runtime self-check
  and WP06's proof catch any later gap as an overlap, never a silent loss.
- **Annotation spam**: one line per module-row shard is acceptable; file mode lists at most 10
  names plus counts.
- **Median of a skewed distribution** under-weights a new heavy file until recapture. Accepted
  (D-29); the warning names the file, and WP14 seeds real timings.
- **Inventory line drift** if the docstring of `test_module_length_agreement.py` is touched —
  don't touch it.

## Review Guidance

- **Red on planning base, green on WP tip**: run `tests/ci/test_shard_select.py` at the T006
  commit (new tests red: missing functions, silent fallback) and at the tip (green).
- Confirm module-row assignments are unchanged: WP01's characterization test is still present
  and green, unmodified.
- Confirm the median ignores stale keys, and that "no timings" yields `1.0` **with** a reported
  reason (loud), never silently.
- Confirm `enumerate_base_files` is the only file walk in the diff (no second enumeration in
  tests: tests compare against pytest, not against a re-implementation).
- Confirm `battery_parts` rejects a roster file outside the base and is order-independent.
- `mypy --strict` and both ruff gates clean; complexity ≤ 15.
- FR-005 (loud mismatch, both granularities) and FR-004 (partition function) acceptance.

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

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
