# Tracer: Design Decisions

Mission: `ci-nightly-interpreter-matrix-45min-timeout-01M3G17F`

## Shard-identity roster shape (FR-016)

A plain Python module, `tests/architectural/_interpreter_shard_roster.py`
(not YAML under `.github/`), co-located with its only consumer
(`tests/architectural/test_interpreter_shard_coverage.py`). Rationale:
participates in `ruff`/import-linter checks like any other test-support
module; needs no new YAML-loading dependency; keeps the roster next to the
test that reads it rather than splitting the concern across a `.github/`
data file and a `tests/` consumer.

Fields per shard: `job_key` (must match `ci-nightly.yml`'s `jobs:` key
exactly), `paths` (positional pytest args for the shard's slice),
`ignores` (optional `--ignore` globs, used for "everything not explicitly
assigned elsewhere" shards), `suite_key` (the `--suite-key` literal that
shard's escalation step must use). See plan.md §A for the full dataclass
shape.

The roster is diffed against `ci-nightly.yml`'s live `jobs:` keys (via
`gates_for_target`'s reused raise-on-zero-gates behavior) to catch a shard
deleted from the job list entirely (FR-016's core ask), AND separately
diffed against each shard's live collected node-ids (via `collect_job_nodeids`
on a `Gate` built from the roster's own declared `paths`/`ignores`) to catch
a shard whose job key survives but whose selector was silently reassigned —
a gap `gates_for_target` alone cannot close (research.md §7's "shape gap"
caveat, independently re-confirmed during this plan's own read of
`BaselineTarget`'s 3-field shape).

## Guard-update strategy (FR-009/FR-010)

Dynamic discovery from the roster (`INTERPRETER_SHARD_JOB_KEYS = tuple(s.job_key
for s in INTERPRETER_SHARDS)`), not a second hardcoded literal list in the
guard file. Rationale: keeps the roster as the single source of truth for
shard identity — a third hardcoded list (roster + guard's old loop + a new
guard loop) would reintroduce exactly the kind of drift hazard this mission
exists to eliminate elsewhere.

Non-vacuity proof: two dedicated mutation tests operating on in-memory dict
edits of the already-parsed workflow YAML (mirroring this file's existing
tests' style, which already operate on parsed structures rather than
temp files in most cases) —
`test_guard_fails_when_a_shard_is_dropped_from_the_job_list` (delete one
roster-declared shard's `jobs:` entry) and
`test_guard_fails_when_shards_are_reverted_to_a_single_job` (replace all
shard entries with one synthetic pre-split `interpreter-matrix` job). Both
required by Standing Order #5 ("a gate-unmask cannot self-validate") and by
spec.md User Story 4's own Acceptance Scenario 2.

`FORBIDDEN_PR_PATH_TOKENS`'s existing `"interpreter-matrix"` substring entry
is left unchanged and continues to protect the new shape, because every new
shard job is deliberately named `interpreter-matrix-shard-<N>` (containing
that substring) rather than e.g. `py313-shard-<N>`.

## Suite-key naming scheme (FR-011/FR-015)

`interpreter-3.13-shard-<N>` — deliberately differs in SHAPE (adds
`-shard-<N>`), not only in matrix substitution, from the current single-job
key literal `"interpreter-${{ matrix.python-version }}"`. Rationale: FR-015's
own motivating hazard is "a copy-paste suite-key collision across shards ...
an easy mistake given the current single-job step's key literal" — a naming
scheme that differs only by an interpolated variable is exactly the kind of
copy-paste-prone shape that produces silent collisions; requiring an
explicit `-shard-<N>` literal per copy makes a forgotten find/replace visibly
wrong rather than silently identical.

Machine-checked via a new test, `test_nightly_suite_keys_are_pairwise_distinct`,
parsing every `--suite-key` literal out of `ci-nightly.yml`'s committed text
across ALL nightly jobs (not only the interpreter shards), backed by a
mutation test (`test_suite_key_uniqueness_guard_is_non_vacuous`) that
deliberately collides two shards' keys in a scratch copy and confirms the
assertion fails against it (SC-008).

## Shard boundary redraw (T009) — real measurement forced a 3->6 shard split

**Run 1 evidence** (`workflow_dispatch` run
[36294808024](https://github.com/spec-kitty/spec-kitty/actions/runs/36294808024),
dispatched 2026-09-27T04:36:39Z on `ubuntu-24.04`, `mode=full`):

| Shard (initial N=3 guess) | Real collected | Real "Run fast/unit suite" wall-clock | Job conclusion |
|---|---|---|---|
| shard-1 (`tests/unit tests/status tests/cli`) | 2203/2522 | 351s (5m51s) | `success` |
| shard-2 (`tests/specify_cli/runtime tests/charter tests/kernel`) | 3538/3550 | 639s (10m39s) | `success` |
| shard-3 ("everything else") | 29710/40184 | 2779s (46m19s) | **`cancelled`** at the 45min job timeout |

Shard-3 ("everything else") was catastrophically imbalanced — ~13x shard-1's
size and ~8x shard-2's — and hit the SAME 45-minute-cap-with-no-verdict
defect this mission exists to fix, exactly the "badly imbalanced partition"
scenario plan.md §B/§I anticipated. This is real, measured proof (not a
guess) that a coarse 3-way split is insufficient.

**Redraw method** (reproducible, NFR-006): a single fresh local
`pytest --collect-only -q -m "fast or unit" tests --ignore=tests/unit
--ignore=tests/status --ignore=tests/cli --ignore=tests/specify_cli/runtime
--ignore=tests/charter --ignore=tests/kernel` capture (2026-09-27, this
checkout) reproduced shard-3's original 29710-node-id selection. Every
node id's owning directory was bucketed at `tests/<dir>` granularity, one
level deeper for `tests/specify_cli/<dir>` specifically (since
`tests/specify_cli` alone was 14155/29710 — 40% of the remaining total, too
coarse a single unit to balance against). The resulting ~85 directory/file
buckets were partitioned into 4 bins via a **one-time, human-reviewed greedy
largest-first-to-smallest-bin (LPT) pass** over this single fresh count list
(sorted by count descending, break ties by path, assign each item to the
currently-smallest-total bin) — never SK-247's rejected mechanism. The
distinction: SK-247's defect is a **committed, positionally-paired duration
list that goes stale as the suite changes and is never re-verified against a
live recount**; this partition is instead a **direct function of one fresh,
real collection taken in the same session that authors the roster**, with no
committed/stale duration file anywhere in the mechanism — and, unlike
SK-247's silent fallback, this mission's own coverage-completeness test
(`test_interpreter_shard_coverage.py::test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap`)
independently re-verifies, on every future run, that the roster's declared
paths still union to exactly the live full selection, so drift after this
roster is written is a loud, named CI failure rather than a silently
shrinking or duplicating selection. Result: 4 new shards (3-6) at
7428/7428/7427/7427 collected tests — within 1 test of perfectly even.

**Final 6-shard shape**: shards 1-2 kept unchanged (real run-1 data already
proved them well-sized); the old shard-3 became shards 3-6. Full path lists
are in `_interpreter_shard_roster.py` (generated by a one-off script, not
hand-transcribed, to avoid transcription error across ~180 total path
entries).

**`timeout-minutes` derivation** (NFR-001, never copied unchanged):
- shard-1: 351s measured * ~2.6x headroom -> 15min (generous; shard-1 is by
  far the smallest, so absolute headroom-minutes cost is cheap).
- shard-2: 639s measured * ~1.9x headroom -> 20min.
- shards 3-6: NOT directly measured yet (they are a redraw of shard-3's
  bucket, not independently dispatched before finalizing this shape, to
  avoid spending a 2nd measurement-only run out of the operator's up-to-3
  budget). Extrapolated from shard-3's real aggregate rate over the SAME
  29710-test population (2779s / 29710 tests ≈ 0.0936s/test) scaled to each
  new shard's ~7427-7428 tests ≈ 695s (11.6min), headroomed to ~2.15x ->
  25min each. This is explicitly an EXTRAPOLATION, not a per-shard direct
  measurement — run 2 (validation) is where this estimate is actually tested
  against real per-shard wall-clock; if any of shards 3-6 run close to their
  25min budget, that would indicate this extrapolation under-estimated that
  specific bucket's real per-test cost (likely if that bucket is dominated by
  heavier CLI-invocation tests, e.g. `tests/specify_cli/cli`, vs. cheaper
  unit-style tests elsewhere in the population).

**Pre-existing Python-3.13-specific failures newly discovered**: because
shard-3's real run (before the redraw) actually completed almost to the end
before being cut off by the job timeout, its log shows several genuine
`FAILED` results unrelated to this mission's diff (e.g. a
`spec-kitty-events` envelope-snapshot version-pin mismatch, a decision
command shape-drift assertion, an installer concurrent-peer-convergence
test, a mission-type-fallback signal test). These are almost certainly
PRE-EXISTING on Python 3.13 — never visible before because the un-split
job never once produced a verdict — and must be triaged (searched for an
existing tracked issue; a new "Pre-existing Failure" issue filed if none
exists) BEFORE any of these specific tests are treated as accepted baseline,
per the charter's binding Pre-existing Failure Reporting Rule (spec.md Edge
Cases, SC-007). See the Activity Log / final report for the actual
triage outcome — this entry records the discovery, not yet the disposition.

## WP01 review-cycle-1 finding WP01-R1-003 — pre-existing-failure disposition CLOSED

The lane branch's own copy of this file (WP01, not yet merged to this
planning branch as of this note) records, under "Shard boundary redraw
(T009)", the newly-discovered Python-3.13-only pre-existing test failures in
shards 3/4 with the caveat "this entry records the discovery, not yet the
disposition." Review cycle 1 (`wp01.review-1.yaml`, finding WP01-R1-003)
flagged that the charter's binding Pre-existing Failure Reporting Rule had
not yet visibly been completed as of that diff.

Disposition, confirmed during WP01's fix-mode cycle 2 (this session, read-only
GitHub verification, no issues opened or edited by this session): the
evidence for the 28 pre-existing Python-3.13 failures across shards 3/4 was
posted to tracked issue
[#3189](https://github.com/spec-kitty/spec-kitty/issues/3189)
(comment by `MOES-Media`, 2026-09-27T09:57:27Z), with cross-provenance notes
recorded on the two auto-opened nightly-escalation issues
[#5169](https://github.com/spec-kitty/spec-kitty/issues/5169) (shard-3) and
[#5172](https://github.com/spec-kitty/spec-kitty/issues/5172) (shard-4)
clarifying these escalations originated from this mission's own
`workflow_dispatch` measurement/validation runs on the unmerged branch, not
from a nightly run on `main`. No further action is pending on WP01-R1-003.

## 2026-09-28 — takeover as #5263 (supersedes #5244)

- **Pin `--python "3.13"` on every shard's `uv run … pytest` line** rather than trusting
  `UV_PROJECT_ENVIRONMENT` plus `setup-python`. The env-pinning guard now requires it,
  with a positive control on the unpinned and wrong-version forms.
- **Fix the tokenizer, not the workflow shape.** A flag value may not start with `-`.
  The census diff is exactly the six shards becoming visible.
- **Supersede instead of patching in place** (operator decision). #5244's commits are
  carried unchanged, and `main` is merged in rather than rebased.
- **Fold #5128 into this PR and escalate it P3 → P0** (operator decision). The override
  tier's drift is what reds shard 6 on real 3.13. `release.yml` publishes only on a green
  nightly, which makes the drift a release blocker. The tier is deleted per the operator's
  triage, not resynced.
- **Move to ready only after the #5128 fold lands**, so the PR does not sit in ready while
  further commits are still coming.
