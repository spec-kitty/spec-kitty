# Independent Review — Dashboard Mock & Gate Fixes (PR #4674 final-gates regressions)

**Reviewer:** independent reviewer agent (no shared context with implementer)
**Mission:** cli-boundary-robustness-01M2NQCB / issue #4600 / PR #4674
**Handoff reviewed:** `dashboard-mock-and-gate-fixes-handoff.md`
**Verdict: APPROVED**

All three claimed fixes were independently reproduced and verified. Every
claim in the handoff held up exactly as stated — red/green transitions,
test counts, commit scope, allowlist rationale, and the coverage percentage
were all reproduced byte-for-byte or number-for-number. No src/ changes,
no env/config changes, no full-suite runs, no unrelated files, nothing
pushed, both checkouts clean.

## Setup

```
CORE=.../spec-kitty         (branch fix/cli-boundary-robustness, HEAD d8e05ee7d)
PR=.../review-pr            (branch issue-4600-cli-boundary-robustness, HEAD 2d0864eb8)
```

Both `.venv` were already populated by the implementer; reused directly.

## 0. Repo hygiene checks

```
$ git -C $CORE status   -> "nothing to commit, working tree clean", ahead of origin/fix/cli-boundary-robustness by 203 commits (pre-existing mission history, not pushed)
$ git -C $PR   status   -> "nothing to commit, working tree clean", ahead of origin/issue-4600-cli-boundary-robustness by 3 commits (the claimed fixes), not pushed
```

Confirmed clean in both checkouts, nothing pushed to any remote.

`git show --name-only` on all 6 commits (21a5aabec, 08f83da3b, d8e05ee7d in
core; 264f566d7, ccd787071, 2d0864eb8 in review-pr) shows each commit
touches only the files the handoff claims:
- 21a5aabec / 264f566d7: `tests/agent/test_commands.py` (core only) +
  `tests/dashboard/test_duplicate_prefix_rendering.py`
- 08f83da3b / ccd787071: `tests/architectural/test_no_dead_symbols.py` only
- d8e05ee7d / 2d0864eb8: `tests/doctrine/test_activation_parity_guard.py`,
  `tests/charter/test_enforcement_lattice.py`,
  `tests/charter/test_decision_documentation_on_implement.py` only

No `src/` files, no env/config files (`.env`, `*.yaml`/`*.yml`/`*.toml`
etc.) touched in any of the 6 commits. Grepped `git log -p` on those paths
for `SAAS_SYNC` — no hits. `SPEC_KITTY_ENABLE_SAAS_SYNC` confirmed untouched.

No stray large log files or full-suite run evidence found in the workspace
parent from this session's timeframe; all reproduce commands used targeted
node IDs/files, consistent with "no `tests/` wholesale, no `make
test-full`" claim.

## 1. Dashboard stale-mock fix

**Red, reproduced independently** (via a disposable detached worktree at
`264f566d7^`, removed afterward with `git worktree remove --force`):

```
$ cd <worktree at 264f566d7^>
$ .venv/bin/pytest tests/dashboard/test_duplicate_prefix_rendering.py -q
.....F.F                                                                 [100%]
FAILED test_dashboard_json_cli_renders_three_distinct_rows - TypeError("...<lambda>() got an unexpected keyword argument 'json_output'")
FAILED test_rendered_json_contains_every_mid8 - TypeError(...)
2 failed, 6 passed in 45.54s
```

Matches the claim exactly (TypeError, unexpected keyword `json_output`).

**Green, review-pr:**
```
$ cd $PR && .venv/bin/pytest tests/dashboard/test_duplicate_prefix_rendering.py -q
........                                                                 [100%]
8 passed in 1.21s
```

**Green, core (26 tests across both files):**
```
$ cd $CORE && .venv/bin/pytest tests/agent/test_commands.py tests/dashboard/test_duplicate_prefix_rendering.py -q
..........................                                               [100%]
26 passed in 157.31s
```

Both match the handoff's claimed counts (8/8 review-pr, 26/26 core).
Diffs confirmed test-only, matching the described fix pattern (`*, json_output: bool = False` keyword-accepting replacement functions).

## 2. Dead-code allowlist fix

Confirmed via `git show --name-only` that both `08f83da3b` (core) and
`ccd787071` (review-pr) touch only `tests/architectural/test_no_dead_symbols.py` — no `src/` changes.

**Rationale spot-checks:**

- `charter/activate.py`'s except-clause claim: read
  `src/specify_cli/cli/commands/charter/activate.py:172` directly. It reads
  `except UnknownMissionTypeError:` and the comment immediately below it
  explicitly names `MissionTypeEmptyActionSequenceError` as the case that
  "MUST surface rather than being folded into this same 'no previous state'
  branch (spec.md Edge Cases...)". This matches the handoff's paraphrase
  precisely — not a stretch.
- `doctor.py`'s dynamic dispatch claim: `src/specify_cli/cli/commands/doctor.py:207` defines `_auto_discover_doctor_siblings()`, and line 219 does
  `register = getattr(module, "register", None)` — confirms the
  gate-invisible dynamic-dispatch reach path for both `_env_file_doctor::register` and `_provenance_doctor::register`.

**Green, review-pr:**
```
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported -q  (implicit via full-file run below)
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py -q
..................................                                       [100%]
34 passed in 123.02s
```

**Green, core:**
```
$ .venv/bin/pytest tests/architectural/test_no_dead_symbols.py -q
..................................                                       [100%]
34 passed in 121.09s
```

34/34 in both checkouts, matching the claim exactly.

## 3. Coverage fix on consistency_check.py

Confirmed via `git show --name-only` that `d8e05ee7d` (core) and
`2d0864eb8` (review-pr) touch only the three named test files — no `src/`
changes.

**Read the new test code** (not just diffstat) in all three files:
- `tests/doctrine/test_activation_parity_guard.py::test_references_yaml_malformed_schema_fails_closed` — parametrized over 3 malformed-shape YAML documents (non-mapping root, non-mapping `catalog`, non-list `catalog.references`), asserts `report.coherent is False`, asserts a specific error-message fragment is present in `verification_errors`, and asserts the parity-check suggestion text. This is a real behavioral test exercising the three `isinstance` guards at lines 628/632/636, not a coverage-gaming stub.
- `tests/charter/test_enforcement_lattice.py::test_reconciler_or_operand_unresolvable_in_directive_repository_raises` and `tests/charter/test_decision_documentation_on_implement.py::test_directive_unresolvable_in_directive_repository_raises` — both construct a real DRG graph with active nodes/edges, monkeypatch `_resolve_directives` to return an empty repository (forcing the DRG↔repo disagreement), and assert `pytest.raises(RuntimeError, match="cannot resolve")`. This is a real fault-injection test hitting lines 1363 and 1504 respectively, not an assert-nothing stub.

**Green (targeted subsets), core:**
```
$ .venv/bin/pytest tests/doctrine/test_activation_parity_guard.py -q -k malformed_schema
...                                                                      [100%]
3 passed, 11 deselected in 6.93s
$ .venv/bin/pytest tests/charter/test_enforcement_lattice.py -q
........                                                                 [100%]
8 passed in 5.50s
$ .venv/bin/pytest tests/charter/test_decision_documentation_on_implement.py -q
......                                                                   [100%]
6 passed in 5.20s
```
Matches the claimed 3/8/6 exactly.

**Independent scoped diff-cover rerun** (own coverage/XML files, not reusing
the implementer's, scored against the frozen-core evidence's
`critical.statements.diff`), following the approach in
`coverage-target-manifest.md`:

```
$ cd $CORE
$ COVERAGE_FILE=/tmp/scoped-review.coverage .venv/bin/python -m pytest \
    tests/charter/test_consistency_check.py \
    tests/charter/test_enforcement_lattice.py \
    tests/charter/test_decision_documentation_on_implement.py \
    tests/doctrine/test_activation_parity_guard.py \
    tests/charter/test_tension_unreconciled.py \
    -m "not timing and not stress" \
    --cov=src --cov-report=xml:/tmp/scoped-coverage-review.xml -q
........................................................                 [100%]
56 passed, 1 deselected, 1 warning in 223.08s

$ .venv/bin/diff-cover /tmp/scoped-coverage-review.xml \
    --diff-file .../final-gates-ea5fc3678ebb-20260916T231123Z/critical.statements.diff \
    --fail-under=90
src/charter/activation/consistency_check.py (93.8%): Missing lines 307-308,558
Total:   48 lines
Missing: 3 lines
Coverage: 93%
```

This reproduces the handoff's before/after table exactly: 89.6% → 93.8% on
the file, 89% → 93% total, with the originally-missing lines
(628,632,636,1363,1504) now covered and only the pre-existing,
elsewhere-covered gap (307-308,558) remaining. The coverage improvement is
real, not fabricated.

Temp files (`/tmp/scoped-review.coverage`, `/tmp/scoped-coverage-review.xml`)
removed after verification.

## Process hygiene

- One disposable git worktree (`/tmp/review-pr-red-check`) created for the
  red-state repro; removed via `git worktree remove --force` immediately
  after use. `git worktree list` confirms it is gone.
- All pytest/diff-cover runs executed in the foreground or as tracked
  background bash jobs that were waited on to completion (no orphaned
  processes) — confirmed via `ps aux | grep pytest` returning empty after
  the last run.
- No servers, watchers, or persistent processes started.
- Both checkouts (`spec-kitty`, `review-pr`) confirmed `git status` clean
  at the end of the review, with no tracked-file modifications made by this
  reviewer.

## Outstanding items from the handoff (addressed)

- The `MissionTypeEmptyActionSequenceError` allowlist rationale was checked
  against the actual `charter/activate.py` except-clause wording — it
  matches.
- The `#4600 (FR-303)` tracker reference is a self-reference to this
  mission's own issue, following the stated existing convention (verified
  present verbatim in the allowlist comment); no action needed.
- Full (non-scoped) final-gates re-run was NOT performed by this reviewer
  either (out of scope: it would require running the full final-gates
  pipeline, not just targeted tests) — the scoped diff-cover rerun above is
  independent evidence the gap is closed, consistent with the handoff's own
  caveat that the scoped rerun is not a replacement for a real gate run.

## Verdict

**APPROVED.** All three fixes are real, correctly scoped (test/allowlist-only,
no src/ or env/config changes), and every quantitative claim in the handoff
(red counts, green counts, coverage percentages, missing-line lists) was
independently reproduced with matching results. No unrelated files were
touched in any of the 6 commits. Both checkouts remain clean and unpushed.
