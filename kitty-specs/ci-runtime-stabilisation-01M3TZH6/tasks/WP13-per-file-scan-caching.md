---
work_package_id: WP13
title: Per-file caching of duplicated scans
dependencies: []
requirement_refs:
- FR-006
- C-007
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-runtime-stabilisation-01M3TZH6
base_commit: c318df2354fb9e47458fe4576ea64f79839edd27
created_at: '2026-10-01T08:57:38.571131+00:00'
subtasks:
- T055
- T056
- T057
- T058
phase: Phase 5 - Battery reshaping
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/test_interpreter_shard_coverage.py
- tests/architectural/test_clock_call_ban.py
- tests/architectural/test_no_dead_symbols.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – Per-file caching of duplicated scans

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

Two heavy battery files repeat an identical expensive computation inside one file:

- `test_interpreter_shard_coverage.py` re-runs the per-shard subprocess collections. They
  cost ~34 s locally and ~91 s on CI.
- `test_clock_call_ban.py` runs the whole-tree AST scan twice. That costs ~23 s locally and
  ~49 s on CI.

FR-006 asks for each distinct scan to be computed once per file, keyed on the resolved root
and the selection inputs, holding **findings, not syntax trees**. Self-mutation tests must
still scan their own tree. This matters more once the battery moves to 4 workers (FR-002):
the two duplicates sit in the ≥ 100 s files that drive the NFR-003 180 s bound (D-08).

Done means:

- One pure, `functools.cache`d function per file, keyed on (resolved root, selection inputs).
  It returns an **immutable** value (tuple/frozenset of node-id strings or `(relpath, violation)`
  pairs) and is cleared by a module-scoped autouse fixture at file end.
- Mutation, monkeypatch and self-mutation tests still reach the **uncached** primitive (or a
  different cache key). Each still fails on its injected violation.
- The red-first tests (T055) are red on the planning base and green on the tip.
- The second consumer in each file drops to under 1 s, measured with single-file
  `--durations` runs (T058).
- Dead-symbol file: **the once-per-file cache comes from PR #5503; this WP adds its file-end
  finalizer** (research D-37, R3 §2.2). PR #5503 merged into main before base `bc826fcbcb`.
  `tests/architectural/test_no_dead_symbols.py:1166-1167` is `@functools.lru_cache(maxsize=1)`
  on `_real_tree_inputs()`. It runs `_walk_modules()` once, but its lifetime is the **worker
  process**. The cached `RealTreeInputs.corpus` holds a `CorpusModule` for every `src/` module,
  and each one keeps the `ast.Module` and the full source (`tests/architectural/_symbol_key.py`
  ≈:151-153). So the syntax trees for all of `src/` stay resident on that worker after the file
  finishes. That breaks FR-006 ("findings, not syntax trees"). R3 §2.2 accepted the tree cache
  only as a reasoned exception, bounded to the file by a module-scoped `cache_clear()`
  finalizer. T058 restores that finalizer, and T055 adds its red-first test.
  `test_refresh_dead_symbol_hashes.py` and `_refresh_dead_symbol_hashes.py` no longer exist
  (deleted by #5503), so there is nothing to do there.

## Context & Constraints

- **Read first**: in `research.md`, decision rows D-17 and D-37 (D-37 supersedes D-17's
  dead-symbol clause), then R3 §2 "FR-006 — Per-file caching
  of repeated scans" (2.1 measurements, 2.2 design, 2.4 alternatives, 2.5 red-first tests,
  2.6 C-007 sequencing). Then `spec.md` (US6, FR-006, edge case "caches hold findings, not
  syntax trees"), `plan.md` IC-10 and `.kittify/charter/charter.md` (Standing Order #5:
  architectural gate discipline; ATDD-first).
- **#5503 has merged (C-007 satisfied)**: its diff (`git diff ecb5dd914a bc826fcbcb`) does not
  touch `test_interpreter_shard_coverage.py`, `test_clock_call_ban.py`, `_gate_coverage.py`,
  `_clock_gate_scan.py` or `tests/_support/wall_clock_assertions.py`. Those files are
  byte-identical across the rebase, so every anchor below still holds (re-verified 2026-10-01
  on `bc826fcbcb`). #5503 rewrote `test_no_dead_symbols.py`. Its anchors below were read on
  `bc826fcbcb`. Because #5503 is already on the base, editing the file is now sequenced after
  #5503, as C-007 requires. The only edit in that file is the file-end finalizer and its test.
  Leave `tests/conftest.py`, `_symbol_key.py`, `_dead_symbol_allowlist.py` and
  `test_dead_symbol_allowlist_contract.py` alone.
- **Why not cache inside `_gate_coverage.collect_job_nodeids`**: many other files run
  collections under tmp roots and monkeypatches, so the blast radius is too wide (R3 §2.4).
  `_gate_coverage.py` is also a pinned, format-excluded file that WP06/WP15 edit (D-25).
  Do not touch it.
- **Lifetime**: under `--dist loadfile` every test of a file runs on one worker, so a cache
  cleared at module teardown is "once per file". The clear also frees memory before the
  worker's next file (NFR-005 headroom).
- **C-009**: run each owned file individually. Never run `tests/architectural` as a whole,
  and never `make test-full`.
- **Formatting**: no owned file is in `[tool.ruff.format].exclude`, so normal
  `ruff format` applies.
- **Pinning inventory**: no owned file contains the inventory subject literals
  (`ci-quality.yml`, `sonarcloud`, `make test-fast`). Keep it that way, and no regeneration
  is needed.
- **Terminology**: "Mission", never "feature". Never bare "routing".

### Current-state anchors (verified 2026-10-01; re-verified post-rebase on `bc826fcbcb`)

| File | Anchor | Today |
|---|---|---|
| `test_interpreter_shard_coverage.py` (708 lines) | `from tests.architectural._gate_coverage import (... collect_job_nodeids ...)` (≈:46-55) | module-global name, monkeypatched by `_install_fake_collect_job_nodeids` (≈:629-644) via `monkeypatch.setattr(sys.modules[__name__], "collect_job_nodeids", _fake)`; `_fake` keys on `gate.job` |
| | `_FULL_SELECTION_GATE` (≈:86), `_shard_gate(shard)` (≈:95) | `Gate` is a **mutable, unhashable** dataclass (`_gate_coverage.py:288-307`) |
| | `test_no_shard_collects_zero_tests` (≈:550) | collects every roster shard |
| | `_coverage_completeness_violations(shards)` (≈:561) | collects the full selection **and every shard again**; the duplicate |
| | `test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap` (≈:591) | real consumer |
| | `test_coverage_completeness_check_fails_on_a_dropped_test_file` (≈:647), `…_duplicated_test_file` (≈:670) | mutation tests via the monkeypatched collector |
| `test_clock_call_ban.py` (435 lines) | `_violations_for_file(path)` (≈:60), `collect_call_ban_violations(paths)` (≈:66) | `scan.relpath` depends on module-global `scan.REPO_ROOT` |
| | `test_no_banned_wall_clock_call_outside_the_door` (≈:108), `test_every_call_exemption_entry_is_a_real_violation` (≈:134) | both call `collect_call_ban_violations(scan.iter_python_files())`; the duplicate |
| | `test_stale_exemption_removal_reds_the_gate` (≈:149) | monkeypatches `scan.REPO_ROOT` → `tmp_path`, calls the primitive directly |
| | planted-offender tests (≈:218-427) | never touch the real tree |
| Violation type | `tests/_support/wall_clock_assertions.py:2437` | `@dataclass(frozen=True, order=True) WallClockCallViolation(line, call, suggestion)`: hashable, immutable |
| Scan scope | `tests/architectural/_clock_gate_scan.py` | `REPO_ROOT`, `SCAN_ROOTS = (src, tests, scripts)`, `iter_python_files() -> list[Path]` (shared with `test_clock_import_ban.py`; do not change) |
| `test_no_dead_symbols.py` (2422 lines, on `bc826fcbcb`) | `@functools.lru_cache(maxsize=1)` `def _real_tree_inputs() -> RealTreeInputs` (:1166-1167) | process lifetime, never cleared; `functools` already imported (:116); no autouse fixture in the file today |
| | `RealTreeInputs.corpus: Mapping[str, CorpusModule]` (:1160) | `CorpusModule.tree: ast.Module` + `.source: str` (`_symbol_key.py:151-152`): every `src/` tree stays resident |
| | module docstring (:65-66), `RealTreeInputs` docstring (:1149), `_real_tree_inputs` docstring (:1168) | say "once per (test) session"; change to "once per file" |
| | in-file consumers of `_real_tree_inputs()` | `:1499` `test_no_public_symbol_in_all_is_unimported`; `:1728` `test_walk_modules_widening_contributes_on_live_tree`; `:1979` `test_wp01_runtime_bridge_facade_symbols_recognised_live_without_allowlist`; `:2086` `test_auto_exempt_disjoint_from_hand_allowlist`; `:2203` `test_bite_k_full_keyability_hand_and_auto_exempt`; `:2325-2326` `test_real_tree_inputs_are_read_only` (asserts `inputs is _real_tree_inputs()` inside one test, so it still holds); `:2344` `test_m13_corpus_floor_reds_on_a_quarter_of_the_modules`; `:2363` `test_m11c_gate_reads_the_widened_section_it_is_given` |
| Cross-file consumer (not owned) | `test_dead_symbol_allowlist_contract.py:197` M11 `test_m11_gate_reads_the_allowlist_file_it_is_given` → `gate._real_tree_inputs()` | today it gets a cache hit when it runs after the gate file in the same process. After the finalizer it walks `src/` again (~30 s more on that worker). Its docstring (:188-193) already expects one walk per xdist worker. Do not edit it. |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T055 – Red-first: cache-bypass and once-per-key tests

- **Purpose**: prove the two properties that make caching safe. Duplicate requests compute
  once, and self-mutation scans never get a cached real-tree result. These tests are red
  today because the cached helpers do not exist (`AttributeError`/`NameError` at call time).
- **Steps**:
  1. In `test_interpreter_shard_coverage.py`, add:
     - `test_collect_memo_invokes_the_collector_once_per_selection(monkeypatch)`: call
       `_collect_memo.cache_clear()`, install a counting fake `collect_job_nodeids` via the
       same `monkeypatch.setattr(sys.modules[__name__], ...)` seam, then call `_collect_memo`
       twice with equal keys and once with a different `ignores`. Assert 2 underlying calls,
       `_collect_memo.cache_info().hits == 1`, and that the return value is a `tuple`.
     - `test_mutation_controls_bypass_the_memo(monkeypatch)`: warm the memo through fake
       world A (`_collect_memo(...)` for every shard key). Then install fake world B with a
       planted missing file and call `_coverage_completeness_violations(INTERPRETER_SHARDS)`
       with **no** `collect` argument. Assert it reports B's gap. This proves the mutation
       tests can never be served cached results.
     - **Production path** — `test_real_consumers_collect_each_selection_once(monkeypatch)`:
       the memo-helper test above does not prove the two REAL consumers actually go through the
       memo. Clear the memo, install a **counting** fake for the uncached primitive
       `collect_job_nodeids` (the existing `_install_fake_collect_job_nodeids` seam, wrapped so
       it records one count per `(tuple(paths), tuple(ignores), marker_expr)` key) over a
       consistent fake world (shards disjoint, union == full selection), then call the real
       test functions `test_no_shard_collects_zero_tests()` and
       `test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap()` directly, in
       both orders (clear the memo between orders). Assert both pass and the counter shows
       **exactly one** underlying call per distinct key (every `INTERPRETER_SHARDS` gate plus
       `_FULL_SELECTION_GATE`) — a consumer that bypasses the memo shows a count of 2.
  2. In `test_clock_call_ban.py`, add:
     - `test_tree_call_sites_scans_once_per_root_and_rescans_a_new_root(tmp_path, monkeypatch)`:
       build tmp trees A and B with one offender each, and monkeypatch `scan.REPO_ROOT` to A.
       Wrap `_violations_for_file` with a counter via `monkeypatch.setattr(sys.modules[__name__], "_violations_for_file", ...)`.
       Calling `_tree_call_sites(A, files_A)` twice scans each file once. Switch
       `scan.REPO_ROOT` to B: `_tree_call_sites(B, files_B)` scans B fresh and returns B's
       offender, not A's.
     - `test_tree_call_sites_returns_an_immutable_value`: the result `isinstance(..., tuple)`.
     - `test_tree_call_sites_refuses_a_root_that_is_not_the_scan_root`: calling with
       `root != scan.REPO_ROOT.resolve()` raises `ValueError`. The relpaths are computed
       against `scan.REPO_ROOT`, so an honest key must name the same root (see T057).
     - **Production path** — `test_real_scan_pair_scans_each_file_once(monkeypatch)`: clear
       the memo; monkeypatch the uncached per-file primitive `_violations_for_file` with a
       **counting** fake returning `[]` (no AST parse, so the test stays cheap) and
       `load_call_exemptions` to return `frozenset()` (so the anti-staleness test has nothing to
       match). Call the real `test_no_banned_wall_clock_call_outside_the_door()` and
       `test_every_call_exemption_entry_is_a_real_violation()` directly. Assert both pass and
       every path in `scan.iter_python_files()` was scanned **exactly once** across the pair
       (counter values all 1, key set == the file list) — a consumer still calling the
       primitive directly shows 2.
  3. In `test_no_dead_symbols.py` (R3 §2.5 "Post-#5503" test), add
     `test_real_tree_inputs_cleared_at_file_end(request, monkeypatch)`. It is red today because
     no finalizer exists.
     - **Registration**: the autouse fixture `_clear_real_tree_inputs` is in
       `request.fixturenames`, and its fixture definition has module scope
       (`request._fixturemanager.getfixturedefs("_clear_real_tree_inputs", request.node)[-1].scope == "module"`,
       or the pytest-version-equivalent lookup).
     - **Behaviour, without dropping the real cache mid-file**: the fixture's teardown
       delegates to a plain helper `_release_real_tree_inputs()`. That helper resolves
       `_real_tree_inputs` from module globals **at call time** and calls its `cache_clear()`.
       Monkeypatch `_real_tree_inputs` with a fresh `functools.lru_cache(maxsize=1)` stub, warm
       it (`cache_info().currsize == 1`), call `_release_real_tree_inputs()`, and assert
       `currsize == 0`. Never call `cache_clear()` on the real cache inside a test: that would
       force a second `src/` walk (~30 s+) for every later consumer in the file.
  4. Run the three files' new tests and confirm they are **red**. Record that in the Activity
     Log. Run `test_no_dead_symbols.py` single-file only (≈149 s; C-009 allows single files).
- **Files**: all three owned files.
- **Parallel?**: No (first commit).
- **Notes**:
  - Each test clears the memo first, so test order and xdist placement cannot leak state.
  - Use only `monkeypatch`. Never mutate module globals by hand
    (`test_no_manual_global_state_mutation.py` is in the battery).

### Subtask T056 – Cache in `test_interpreter_shard_coverage.py`

- **Purpose**: remove the duplicate per-shard subprocess collections (~34 s local, ~91 s CI).
- **Steps**:
  1. Add the cached helper:
     ```python
     @functools.cache
     def _collect_memo(repo_root: Path, paths: tuple[str, ...], ignores: tuple[str, ...], marker_expr: str | None) -> tuple[str, ...]:
         gate = Gate(workflow="ci-nightly.yml", job="<memo>", shard=None, paths=list(paths), ignores=list(ignores), marker_expr=marker_expr)
         return tuple(collect_job_nodeids(gate))  # module global, resolved at CALL time
     ```
     plus a public-ish adaptor `_memo_collect(gate: Gate) -> list[str]` that calls
     `_collect_memo(REPO_ROOT.resolve(), tuple(gate.paths), tuple(gate.ignores), gate.marker_expr)`.
     The key is the selection-relevant fields, never `gate.job`, because `Gate` is unhashable.
     Take `REPO_ROOT` from the same place `collect_job_nodeids` defaults to
     (`_gate_coverage.REPO_ROOT`).
  2. Make `_coverage_completeness_violations(shards, collect=None)`. Inside it,
     `collect = collect or collect_job_nodeids`, resolved **at call time** from module globals,
     so the monkeypatched fake still wins for the mutation tests.
  3. Switch the two real consumers: `test_no_shard_collects_zero_tests` uses `_memo_collect`,
     and `test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap` calls
     `_coverage_completeness_violations(INTERPRETER_SHARDS, collect=_memo_collect)`.
  4. Leave both mutation tests (≈:647 and ≈:670) untouched. They call without `collect`.
  5. Add a module-scoped autouse fixture:
     ```python
     @pytest.fixture(autouse=True, scope="module")
     def _clear_collect_memo() -> Iterator[None]:
         yield
         _collect_memo.cache_clear()
     ```
  6. Update the module docstring's FR-006 note: what is cached, the key, the lifetime, and why
     mutation tests are unaffected.
- **Files**: `tests/architectural/test_interpreter_shard_coverage.py`.
- **Parallel?**: Yes with T057 (different file).
- **Notes**:
  - The memo returns a tuple. Existing callers do `set(...)` or truthiness, so a tuple is
    compatible. The adaptor returns `list(...)` if a caller needs a list type.
  - Do not cache `_FULL_SELECTION_GATE` differently. It goes through the same key path and
    is requested only once per file anyway.
  - Watch the test-execution order: either real test may run first, and both must hit the memo.

### Subtask T057 – Cache in `test_clock_call_ban.py`

- **Purpose**: remove the duplicate whole-tree AST scan (~23 s local, ~49 s CI).
- **Steps**:
  1. Add:
     ```python
     @functools.cache
     def _tree_call_sites(root: Path, files: tuple[Path, ...]) -> tuple[CallSite, ...]:
         if root != scan.REPO_ROOT.resolve():
             raise ValueError(f"_tree_call_sites keyed on {root} but scan.REPO_ROOT is {scan.REPO_ROOT}")
         return tuple(collect_call_ban_violations(files))
     ```
     It holds `(relpath, WallClockCallViolation)` findings only. ASTs are parsed and dropped
     inside `_violations_for_file`, never cached (the precedent: caching ASTs cost +1.1 GB RSS, D-17).
  2. Both real-tree tests call
     `_tree_call_sites(scan.REPO_ROOT.resolve(), tuple(scan.iter_python_files()))` and pass
     `list(...)` (or widen `_partition_call_sites` to `Sequence[CallSite]`) into `_partition_call_sites`.
  3. Leave `test_stale_exemption_removal_reds_the_gate` and every planted-offender test on
     the primitive `collect_call_ban_violations`. Even if one reached the cache, its key's
     root differs, so it would get a fresh scan.
  4. Add the module-scoped autouse `cache_clear()` fixture, as in T056.
  5. Add a docstring note next to the helper (FR-006, key, lifetime, findings-not-trees).
- **Files**: `tests/architectural/test_clock_call_ban.py`.
- **Parallel?**: Yes with T056.
- **Notes**:
  - `scan.iter_python_files()` returns a list, so convert it to a `tuple` for the key.
    `Path` objects are hashable.
  - Do not change `_clock_gate_scan.py`. `test_clock_import_ban.py` shares it and must keep parity.
  - The `ValueError` guard makes the key honest: the cached relpaths are relative to
    `scan.REPO_ROOT`, so a call naming another root must not get them.

### Subtask T058 – Dead-symbol file-end finalizer; measure before/after

- **Purpose**: bound the #5503 tree cache to its file (FR-006, R3 §2.2). Then show that the
  duplicate cost is gone (US6 independent test).
- **Steps**:
  1. **Finalizer** in `test_no_dead_symbols.py`. Put it next to `_real_tree_inputs()` (≈:1166):
     ```python
     def _release_real_tree_inputs() -> None:
         """Drop the real-tree inputs (trees + source of all of src/) when this file finishes (FR-006)."""
         _real_tree_inputs.cache_clear()  # module global, resolved at CALL time


     @pytest.fixture(autouse=True, scope="module")
     def _clear_real_tree_inputs() -> Iterator[None]:
         yield
         _release_real_tree_inputs()
     ```
     Import `Iterator` from `collections.abc`. Keep `lru_cache(maxsize=1)` and
     `RealTreeInputs` unchanged. Within the file, every consumer still shares one walk, so
     `test_real_tree_inputs_are_read_only` (:2325-2326) still holds. Update the three
     "once per (test) session" docstrings (:65-66, :1149, :1168) to "once per file, cleared at
     file end by `_clear_real_tree_inputs`". Say why: the cache holds `CorpusModule` trees and
     source, the one reasoned exception to "findings, not trees", and bounded to the file.
  2. **Verify every consumer**. Run
     `grep -n "_real_tree_inputs()" tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py`.
     The hits must match the anchor table: in-file `:1499`, `:1728`, `:1979`, `:2086`, `:2203`,
     `:2325-2326`, `:2344`, `:2363`, and cross-file M11 at `test_dead_symbol_allowlist_contract.py:197`.
     The line numbers move by the size of your insertion. Confirm with
     `-n0 --durations=12` that `_walk_modules` runs once for the whole file.
  3. **Expected cost (accepted)**: M11 loses its cross-file cache hit. Today, when
     `test_dead_symbol_allowlist_contract.py` runs after the gate file in the same process, it
     reuses the walk. After the finalizer it walks `src/` again, ~30 s more on that worker. Under
     CI's `--dist loadfile` it usually already pays that on its own worker (its docstring
     :188-193), so the battery-level effect is small. WP14's `known_drift` note records it.
  4. **Before** (on the planning base, one file at a time; C-009 allows single files):
     ```bash
     uv run --frozen pytest tests/architectural/test_interpreter_shard_coverage.py -n0 --durations=12 -q
     uv run --frozen pytest tests/architectural/test_clock_call_ban.py -n0 --durations=12 -q
     ```
     Record the two consumers' durations per file. Reference values (R3 §2.1, 32-core host):
     33.95 s + 58.76 s, and 22.70 s + 23.10 s.
  5. **After**, the same commands on the WP tip. Expect the second consumer at < 1 s, or
     reduced by the duplicated share for the union test, which still collects the full
     selection once. Record wall time and the per-test lines. Also record a single-file
     `test_no_dead_symbols.py -n0 --durations=12` wall time before/after. It should not change
     (one walk either way).
  6. Check that every self-mutation / mutation test still passes, **and** still fails when its
     injected violation is present. Temporarily break `_coverage_completeness_violations`'s
     overlap detection locally, confirm the mutation tests go red, then revert. Do the same for
     the clock gate's exemption partition. Record that the reverse check was performed. Do not commit it.
  7. Record the dead-symbol disposition in the Activity Log: "FR-006 dead-symbol file: the
     once-per-file walk comes from PR #5503 (`_real_tree_inputs` `lru_cache(maxsize=1)`). WP13 adds
     the module-scoped `_clear_real_tree_inputs` finalizer (R3 §2.2). The hash-refresh file was
     deleted by #5503 (C-007, D-37)." The orchestrator carries this into the issue matrix and
     WP19 evidence.
- **Files**: `tests/architectural/test_no_dead_symbols.py`. Evidence goes in the Activity Log.
- **Parallel?**: Step 1 can run in parallel with T056/T057 (different file). Steps 4-7 run after
  T056/T057.
- **Notes**: CI timings are about 2× local. The NFR-001/NFR-003 effect is judged later from
  WP12's battery runs, and NFR-005 from WP11's sampler readings, not here.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_interpreter_shard_coverage.py -q
uv run --frozen pytest tests/architectural/test_clock_call_ban.py tests/architectural/test_clock_import_ban.py -q
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -q                   # single file, ≈149 s
uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -q    # M11 cross-file consumer, ≈30 s
uv run --frozen pytest tests/architectural/test_no_manual_global_state_mutation.py -q   # monkeypatch discipline gate
make test-fast
uv run --frozen ruff check tests/architectural/test_interpreter_shard_coverage.py tests/architectural/test_clock_call_ban.py tests/architectural/test_no_dead_symbols.py
uv run --frozen ruff format --check tests/architectural/test_interpreter_shard_coverage.py tests/architectural/test_clock_call_ban.py tests/architectural/test_no_dead_symbols.py
uv run --frozen mypy tests/architectural/test_interpreter_shard_coverage.py tests/architectural/test_clock_call_ban.py tests/architectural/test_no_dead_symbols.py
```

Also run the T058 `--durations` commands. If mypy reports errors in lines you did not touch,
classify them as pre-existing (baseline-red gotcha) and note them. Your new code must add zero.
  **Pre-existing Failure Reporting Rule (charter, binding):** such a red needs a GitHub issue — cite the existing one or open one (command, failure summary, why it is pre-existing) — before you continue past it.

## Risks & Mitigations

- **A self-mutation test silently reads the real tree**: T055's bypass tests, plus the
  call-time resolution of `collect_job_nodeids`, plus the root guard in `_tree_call_sites`.
- **Cache keyed on an unhashable `Gate`**: key on the tuple of selection fields only.
- **Memory growth at 4 workers**: the two new caches hold findings only and are cleared at file
  end. The node-id tuples are a few MB at most. The dead-symbol tree cache (the one reasoned
  exception) is now bounded to its file by `_clear_real_tree_inputs`. Before WP13 it stayed
  resident for the worker's lifetime.
- **Finalizer clears the real cache mid-file**: T055's behaviour check drives a monkeypatched
  stub through `_release_real_tree_inputs()`, never the real `cache_clear()`.
- **Order dependence between tests**: every new test clears first, and the module fixture
  clears last.
- **#5503 already merged** (D-37, C-007): the only dead-symbol edit is the finalizer, sequenced
  after #5503. The lost M11 cross-file cache hit (~30 s on that worker) is accepted and recorded
  in WP14's `known_drift`.

## Review Guidance

- Red on the planning base (helpers/finalizer missing), green on the tip. Check this by running
  the new tests on the base, including `test_real_tree_inputs_cleared_at_file_end`.
- The cache keys contain no `gate.job` and no mutable objects. The return values are tuples.
  All three files have a module-scoped autouse clear. In `test_no_dead_symbols.py` it is
  `_clear_real_tree_inputs` → `_release_real_tree_inputs()` → `_real_tree_inputs.cache_clear()`.
  No test clears the real cache mid-file.
- Every `_real_tree_inputs()` consumer (in-file `:1499`, `:1728`, `:1979`, `:2086`, `:2203`,
  `:2325-2326`, `:2344`, `:2363`; cross-file M11 `test_dead_symbol_allowlist_contract.py:197`;
  base line numbers) still passes, and `_walk_modules` runs once per file.
- The two production-path tests drive the REAL consumer tests (not only the memo helper)
  through a counting fake of the uncached primitive and assert one call per distinct key / file.
- The mutation tests and `test_stale_exemption_removal_reds_the_gate` still reach the
  uncached primitive. The implementer recorded the reverse check (T058 step 6).
- No edits to `_gate_coverage.py`, `_clock_gate_scan.py`, `tests/conftest.py`, `_symbol_key.py`,
  `_dead_symbol_allowlist.py` or `test_dead_symbol_allowlist_contract.py`. The edit to
  `test_no_dead_symbols.py` is only the finalizer, its test and the docstring lines.
- The before/after durations and the dead-symbol disposition (#5503 cache + WP13 finalizer)
  are recorded.
- Confirm the implementer ran mypy as well as pytest on the changed test sources and that
  its diagnostics passed.
- **Definition of Done**: FR-006 is satisfied for all three files. The two duplicated scans are
  cached as findings, with the duplicate cost measured as gone. The #5503 dead-symbol tree cache
  is cleared at file end, so no syntax tree outlives its file. C-007 is honoured: the edit is
  sequenced after #5503 and the disposition is recorded.

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
