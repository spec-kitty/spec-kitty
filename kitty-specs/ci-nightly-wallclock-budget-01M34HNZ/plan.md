# Implementation Plan: CI Nightly Wall-Clock Budget (split perf/e2e/stress; re-derive `charter` shard_count)

**Branch**: `issue-4865-ci-nightly-wallclock-budget` | **Date**: 2026-09-22 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md`, confirmed
review findings in `reviews/spec.confirmed.yaml` (all folded into the committed spec — see "Spec-phase
review findings already resolved" below), and this plan's own direct inspection of the touched files.

**Note**: This template is filled in by the `/spec-kitty.plan` command per
`packs/built-in/missions/software-dev/command-templates/plan.md`.

---

## Summary

Two independent, spec-confirmed defects on the nightly CI wall-clock surface, planned as one mission
because they share root cause (a budget/shard-count value set without fixture-aware, per-suite
measurement) and share touched infrastructure (`.github/ci-module-registry.yml` /
`.github/ci-shard-timings.json`), but are otherwise decomposable and independently testable:

1. **#4865 (P1)** — split `.github/workflows/ci-nightly.yml`'s `performance-and-e2e` job (lines 68-172,
   `timeout-minutes: 60` at line 71) into three independent jobs — `performance`, `e2e`, `stress` — each
   with its own `timeout-minutes` sized from **real, freshly-pulled GitHub Actions timing data** for the
   cited run (not guessed — see "Real evidence used to size the new budgets" below), its own job
   conclusion, and the same exit-0/exit-5-skip/fail-loud convention the current job already uses.
   `nightly-summary`'s `needs:` list (line 337) grows from
   `[performance-and-e2e, interpreter-matrix, full-module-matrix]` to
   `[performance, e2e, stress, interpreter-matrix, full-module-matrix]`.
   `tests/architectural/test_performance_marker_guard.py`'s three tests that hardcode the literal
   `"performance-and-e2e"` (lines 280, 313, 350) are updated to the three new job names (FR-010) — this is
   in-scope maintenance the spec explicitly requires, not evidence of a trigger regression.
2. **#4864 (P2)** — run `scripts/ci/capture_shard_timings.py --module charter --write`, then re-derive
   `.github/ci-module-registry.yml`'s `charter` row `shard_count` (line 143, `shard_count: 5` at line 151)
   from the recaptured, fixture-aware timings via the EXISTING
   `test_inter_shard_skew_within_twenty_percent` gate's own LPT method (`_lpt_bin_pack`/`_skew_of` in
   `tests/architectural/test_module_shard_registry.py:104-122`) — the same method already used correctly
   for the 7 modules with populated `module_capture_provenance` (`auth`, `ci`, `dashboard`, `merge`,
   `specify_cli_runtime`, `status`, `unit`). The `agent`/`upgrade` wall-clock÷target heuristic (commit
   `349b73fc0`) is explicitly rejected as a precedent (C-002) — confirmed by direct inspection of those
   rows' own comments (`.github/ci-module-registry.yml:126-133` `upgrade`, `:166-171` `agent`), both of
   which say "inter-shard skew stays 0%" — i.e. those rows are themselves *still* vacuous under the skew
   gate, which is exactly the defect class this mission closes for `charter`, not a pattern to copy.

Technical approach: this is entirely CI-workflow YAML + one registry-YAML row + one generated-JSON
artefact (via its one sanctioned producer) + one architectural test file's job-name literals updated, plus
one new, small, committed architectural test file (PLAN-VERIFY-002's mandatory non-vacuity proof — see
"Red-first / revert discipline" below). No
`src/kernel`, `src/charter`, `src/runtime`, `src/mission_runtime`, or `src/specify_cli` production code is
touched, so no kernel/CLI/runtime layering boundary (CLAUDE.md "Modularity SSOT",
`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`) is crossed. The #4865 half is
verified where a pytest process cannot reach at all — live GitHub Actions job topology — via a real,
recorded `workflow_dispatch` run. The #4864 half's non-vacuity claim now carries a durable, committed,
CI-re-runnable pytest proof (`tests/architectural/test_charter_shard_skew_sensitivity.py`, PLAN-VERIFY-002)
in addition to a durably-recorded, illustrative spot-check command+output in the PR description — so
neither half's evidence path rests on a verbal claim alone.

## Spec-phase review findings already resolved

`reviews/spec.confirmed.yaml` records 8 confirmed R1-R6 findings against an earlier spec draft
(SPEC-GOV-001/002, SPEC-ARCH-001/002/003, SPEC-VERIFY-001/002/003/004). Direct comparison against the
currently committed `spec.md` (git log shows `ea001948f fix(spec): address confirmed spec-phase review
findings` landed after `spec.confirmed.yaml`) confirms all are already folded in:
FR-010/AC4/SC-004 now correctly scope the guard-file edit as expected maintenance (SPEC-ARCH-001); AC3 no
longer cites `agent`/`upgrade` as an LPT precedent (SPEC-VERIFY-001, confirmed absent from the current
spec text); SC-006 now requires the spot-check's command and both skew values recorded as durable evidence
(SPEC-VERIFY-004); FR-009/NFR-006 require the dispatch run's URL and job conclusions recorded, not left
verbal (SPEC-VERIFY-003); C-003/"Scope boundary (binding)" now name all 13 out-of-scope modules including
`review` (SPEC-GOV-001); the Summary's line citation uses "line ~150" (SPEC-GOV-002); C-004 is unchanged on
the disposition-ledger-comment drift point (SPEC-ARCH-003) — this plan states that acceptance explicitly
below rather than re-litigating it. This plan does not re-open any of these; it builds on the
already-corrected spec.

Separately — not one of the 8 findings above, but a distinct, deliberate plan-level decision stated here
explicitly rather than left implicit: this plan elevates spec.md's SC-006 unit test from "Optionally...
not required" to a MANDATORY plan-level requirement (PLAN-VERIFY-002; see "Red-first / revert discipline"
below for the full reasoning). spec.md itself is unchanged — this is a reasoned strengthening this plan
makes, not a spec correction.

## Real evidence used to size the new budgets (grounds FR-002/NFR-002, not guessed)

Pulled fresh via `gh run view 35683539593 --repo spec-kitty/spec-kitty --json jobs` (the exact run
`spec.md`'s Summary cites), the `performance-and-e2e` job's own step timestamps give the **real**
per-suite wall-clock the old blended job never exposed:

| Step | Started (UTC) | Ended (UTC) | Duration | Conclusion |
|---|---|---|---|---|
| Set up job + checkout + uv install/sync | 03:32:39 | 03:32:57 | 18s | success |
| `performance`-marked suite | 03:32:57 | 03:56:38 | **23m41s** | success |
| `e2e`-marked suite | 03:56:38 | 04:21:22 | **24m44s** | success |
| `stress`-marked suite | 04:21:22 | *(cancelled)* 04:37:40 | **>=16m18s (truncated, never completed)** | `in_progress` at cancellation |
| Job total | 03:32:39 | 04:37:40 | 65m01s | `cancelled` |

This confirms two things the spec states qualitatively and this plan now grounds numerically: (a)
`performance` and `e2e` both completed and passed — their real durations are known, not estimated; (b)
`stress` never finished — its `16m18s` is a **lower bound only**, exactly why NFR-002 requires its true
duration be measured fresh via the FR-009 dispatch rather than assumed. `timeout-minutes` values below
(none a bare copy of the old shared `60`): `performance` and `e2e` are derived from this real data with
headroom now; `stress` is sized in two stages — a generous measurement-only value first, a real
data-derived value second — because, unlike `performance`/`e2e`, no completed real duration exists yet to
derive from:

- **`performance`**: `timeout-minutes: 35` (observed 23m41s; ~1.5x headroom, rounded).
- **`e2e`**: `timeout-minutes: 40` (observed 24m44s; ~1.5x headroom, rounded — slightly larger than
  `performance`'s budget because its observed run was itself slightly longer).
- **`stress`**: two-stage sizing, because the cited run's `stress` step never completed (truncated at
  cancellation, only a `>=16m18s` lower bound is known) and a single guessed placeholder risks reproducing
  the exact truncation defect (#4865) this mission exists to fix if that guess turns out too tight — there
  would then be no completed duration left to re-derive a real value from.
  - **Stage A — `timeout-minutes: 90`, a deliberately GENEROUS, MEASUREMENT-ONLY value, used only for the
    FIRST `workflow_dispatch` (FR-009, Phasing § Phase 1 step 1e below).** `90` is not sized from the
    `>=16m18s` lower bound at all — its only job is to let `stress` reach a real completion without risking
    a second truncation. It is also, incidentally, a number distinct from the old shared cap of `60`, so it
    cannot be mistaken for a bare, unrevised copy of the retired job's cap (spec.md's AC1 falsifiability
    clause). **Stage A's `90` is NEVER the value that ships** — see Stage B.
  - **Stage B — the tightened, FINAL production `timeout-minutes`, derived AFTER Stage A's dispatch
    completes.** The FR-009 pre-merge `workflow_dispatch` is a HARD prerequisite: after Stage A's dispatch
    (Phase 1 step 1e) reports `stress`'s actual COMPLETED job duration, Phase 1 step 1f UNCONDITIONALLY
    re-derives `stress`'s true `timeout-minutes` from that completed duration using the same
    ~1.5x-headroom method already used for `performance`/`e2e`, and updates `ci-nightly.yml`'s `stress` job
    with the derived value in a SEPARATE, subsequent `fix(ci)` commit, before the PR is considered done. This
    re-derivation happens regardless of whether Stage A's `90`-minute measurement-only budget "happened to
    be tight enough" — it is not conditional on Stage A proving insufficient. **The shipped Stage B
    `timeout-minutes` for `stress` must differ from `60` unless a genuine re-derivation from the dispatch's
    measured duration independently lands on that same number**, and must also differ from Stage A's `90`
    unless the re-derivation independently lands there too (Stage A is calibrated loose on purpose, so
    landing there would be coincidence, not the expected outcome). **Contingency if Stage A itself
    truncates — bounded to at most 2 widen-and-redispatch attempts on a concrete escalation ladder**: if
    step 1e's dispatch STILL fails to let `stress` complete inside the `90`-minute Stage A ceiling, that is
    real signal that the suite is even longer than expected — Stage B does NOT proceed from a truncated
    duration; instead, re-dispatch with a further-widened, still measurement-only ceiling on this ladder:
    `90` (original Stage A) -> `150` (widen attempt 1) -> `300` (widen attempt 2, the FINAL ceiling this
    contingency permits) — repeating Stage A at most twice more, only then performing Stage B's re-derivation
    (Phasing § Phase 1 step 1f carries this contingency explicitly). **If `stress` still does not complete
    within the `300`-minute final ceiling, this is no longer a "just needs more time" situation** — treat it
    as a genuine, unexpected test-suite defect (an infinite loop or deadlock, not a slow-but-finite suite):
    do not widen further; apply the charter's Pre-existing Failure Reporting Rule (file the GitHub issue
    before continuing past it — see "Baseline honesty" below for the full rule) and escalate to the operator
    instead of continuing to widen indefinitely. **Note on the confirmation method for this specific case**:
    Baseline honesty's stated confirmation method for the Pre-existing Failure Reporting Rule ("confirmed
    still red on `upstream/main` via the merge-base") does not cleanly transfer here — `upstream/main`'s
    `stress` suite is never isolated long enough to hang or complete on its own today (it is always
    truncated early by the OLD shared 60-minute job cap, exactly the defect this mission fixes), so there is
    currently no way to confirm on `upstream/main` that a >300-minute `stress` hang is pre-existing. The
    issue filed for THIS case should instead describe the situation honestly as "a suite that could not be
    shown to complete within a generous, newly-isolated budget" and let the operator/maintainers judge from
    there, rather than claiming a false pre-existing-on-main confirmation that cannot actually be performed.
    This three-step ladder (`90` -> `150` -> `300`) stays
    comfortably under GitHub Actions' documented per-job execution-time ceiling for hosted (`ubuntu-latest`)
    runners (6 hours / 360 minutes) — considered explicitly here, not overlooked. Each widen-retry timeout
    bump is itself an edit to `ci-nightly.yml`'s `stress` job `timeout-minutes` value — this workflow's
    `on.workflow_dispatch.inputs` block exposes only `mode` (`full`/`pr`), not a timeout-override input
    (confirmed by reading `.github/workflows/ci-nightly.yml`), so a widen retry is necessarily a file-edit
    action, not a dispatch-parameter-only one — and gets its own small, functional `chore(ci)` commit,
    consistent with Stage B's "SEPARATE, subsequent commit" discipline above; it is never folded into Stage
    B's final re-derivation commit or into any other unrelated change.

Because the three suites become **independent GitHub Actions jobs** (no `needs:` dependency chain between
them — only `nightly-summary` depends on all three), they run in parallel where runners are available;
during Stage A (the first dispatch, `stress` timeout `90`) the workflow's worst-case bound is
`max(35, 40, 90) = 90` minutes, bounded by the slowest job's CEILING, not its expected duration — `90` is a
generous measurement ceiling, not a duration estimate, so this figure overstates the likely real
wall-clock. Once Stage B re-derives `stress`'s tightened production `timeout-minutes` from its actual
completed duration (Phasing § Phase 1 step 1f), the realistic wall-clock bound becomes
`max(35, 40, <Stage B value>)`, materially better than the ~65-minute serial baseline unless `stress` alone
turns out to exceed it. This is a beneficial side effect of the split, not a stated goal, and is not
required by any FR/SC — noted here so the PR description can mention it honestly without overclaiming it as
an intentional deliverable, and without citing Stage A's loose `90` as if it were the shipped bound.

**Worst-case cumulative mission wall-clock (acknowledged, not hidden).** Stacking this section's own bounded
widen ladder atop NFR-004's already-flagged Phase 2 cost gives the mission's own worst-case total: the
contingency above permits up to `90 + 150 + 300 = 540` minutes of Phase 1 dispatch-wait if `stress` truncates
at every ceiling on the ladder before Phase 1's dispatch conclusion is even reached, and Phase 2's recapture
(NFR-004) costs a further ~110 minutes once Phase 1 concludes — **up to ~650 minutes (~11 hours) in the
pathological worst case, across both phases combined.** This is framed the same way NFR-004 frames Phase 2's
~110-minute cost: an accepted, sized, non-hidden cost, not a target or an expectation, and not something this
plan expects to happen. The TYPICAL case is far shorter: Stage A's first `90`-minute attempt is expected to
succeed, since the cited run's `stress` step was already observed running for `>=16m18s` before truncation
(see the table above) — comfortably inside `90` minutes on a first attempt, with no widening at all. See also
"Phasing" below for the same figure stated at the point it becomes relevant to sequencing.

## Seam / layering

Every file this mission touches:

- `.github/workflows/ci-nightly.yml` — CI workflow YAML (job split, timeout sizing, `needs:` update).
- `.github/ci-module-registry.yml` — registry YAML, `charter` row only (`shard_count` + a derivation
  comment).
- `.github/ci-shard-timings.json` — generated JSON, regenerated only by its one sanctioned producer
  (`scripts/ci/capture_shard_timings.py --module charter --write`), never hand-edited.
- `tests/architectural/test_performance_marker_guard.py` — one architectural test file, three tests'
  hardcoded job-name literals updated (FR-010).
- `tests/architectural/test_charter_shard_skew_sensitivity.py` — NEW architectural test file
  (PLAN-VERIFY-002), the mandatory committed non-vacuity proof for `charter`'s recomputed skew; imports
  `test_module_shard_registry.py`'s `_lpt_bin_pack`/`_skew_of` helpers, does not modify that file.

None of these are `src/kernel/**`, `src/charter/**`, `src/glossary/**`, `src/runtime/**`,
`src/mission_runtime/**`, or `src/specify_cli/**`. This mission crosses **no** enforced module-layering
boundary (`tests/architectural/test_layer_rules.py`, `test_pyproject_shape.py`, the `landscape` fixture) —
confirmed by the touched-file list above containing zero `src/` paths. `scripts/ci/capture_shard_timings.py`
is **read and run**, never edited (C-002 requires using it as-is); `tests/architectural/test_module_shard_registry.py`
(the skew gate itself, `_lpt_bin_pack`/`_skew_of`) is **read and consumed** for its method, never edited —
the mission re-derives `shard_count` BY that gate's own algorithm, it does not change the gate.

## Gate set — what's enforced, what's not, and why

Verified in this checkout, not assumed:

- **`ruff format --check .` IS enforced** (`ci-quality.yml`, `ci-router.yml`,
  `tests/architectural/test_ruff_format_enforcement.py` in `make test-full`, #3952). Confirmed locally:
  `uv run ruff format --check tests/architectural/test_performance_marker_guard.py
  tests/architectural/test_module_shard_registry.py scripts/ci/capture_shard_timings.py` → "3 files already
  formatted" (baseline clean before this mission's edit). Run the same check on
  `test_performance_marker_guard.py` again after FR-010's edit, and on the new
  `test_charter_shard_skew_sensitivity.py` (PLAN-VERIFY-002) once it is written (Phase 2d), before commit.
  `.github/*.yml` files are
  YAML, outside `ruff`'s domain — no formatter gate applies to them; C-005 additionally scopes this
  mission's Python-format obligation to files it actually touches, not a repo-wide sweep.
- **SonarCloud `sonar-pr`** (`ci-aggregate.yml`) DOES run on this PR but is `continue-on-error` and
  excluded from the terminal `aggregate-gate` (C-007) — reported, not required. No action needed beyond
  awareness; the PR description should note it per CLAUDE.md's Sonar Expectations ("PR description must
  call out remaining Sonar UI work") only if Sonar actually flags something once the PR is open.
- **`ci-aggregate.yml` diff-cover >=90%** (C-006): `diff-cover` scores against `coverage.xml` files
  produced by `coverage.py` instrumenting Python execution (confirmed by reading `ci-aggregate.yml`'s
  `diff-cover` job, lines 263-372 — it consumes reconciled `coverage.xml` shard artefacts, not a YAML/JSON
  parser). `.github/*.yml` and `.github/ci-shard-timings.json` are not Python source and generate no
  coverage data, so diff-cover has **nothing to score for those files** — they are structurally outside
  its domain, not excluded via a flag. The **only** files in this diff diff-cover can meaningfully measure
  are `tests/architectural/test_performance_marker_guard.py`'s three edited test functions and the new
  `tests/architectural/test_charter_shard_skew_sensitivity.py`'s test function(s) (PLAN-VERIFY-002). Since
  `tests/architectural` is an always-on, de-serialized special tier (`ci-module-registry.yml`
  `special_tiers.architectural`) that runs on every PR, and a test function's own body executes whenever
  pytest collects and runs it, both files' lines are covered *by definition* the moment the architectural
  suite runs — this gate is expected to pass trivially for this diff, not a risk to actively manage.
- **commitlint** on every commit — plan the campsite/functional split (below) so each commit message is a
  clean, single-purpose Conventional Commit; do not carry forward meta.json's known-invalid scaffold commit
  message shape (spec.md Correction #8 — handled at PR-prep time, not this plan's concern).
- **markdown lint** on changed `.md` — this plan and the tracer files are the only `.md` this mission
  touches; keep headings/lists well-formed (no gate-breaking raw HTML, no unclosed fences).
- **Coverage-floored shards (kernel 90%, mission-loader 90%)**: NOT touched by this diff — no `src/kernel/**`
  or mission-loader source line changes anywhere in this mission's file list.
- **TID251 banned-API, Bandit, pip-audit**: not applicable — no new Python imports, no new dependency, no
  `pyproject.toml`/`uv.lock` change.
- **`uv.lock` freshness**: this mission adds no dependency and touches no `pyproject.toml` — `uv.lock` is
  untouched; confirm with `git diff --stat` before commit that `uv.lock` shows no diff.
- **`tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent`**: the
  mission's central P2 gate. Must recompute a non-~0% skew for `charter` for at least one plausible
  `shard_count` post-recapture (FR-008/NFR-003) — verified by the SC-006 spot-check described under
  "Red-first / revert discipline" below, since the test's own aggregate pass condition
  (`checked_multi_shard >= 1` across all 21 modules) already passes today regardless of `charter`
  specifically (confirmed by reading `test_module_shard_registry.py:282-300` — the loop's per-module skew
  check only appends to `problems` on `skew > _MAX_SKEW`, and the floor assertion counts ANY module with
  `shard_count > 1`, of which several already exist independent of `charter`).
- **`tests/architectural/test_performance_marker_guard.py`**: `test_nightly_workflow_never_triggers_on_pull_request`
  and `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` (lines 217-247) must show zero
  new violations — these are the two tests FR-005/C-001 actually bind. The other three
  (`test_nightly_suite_steps_are_fail_loud` line 266, `test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing`
  line 298, `test_nightly_workflow_houses_performance_and_interpreter_jobs` line 345) hardcode
  `"performance-and-e2e"` (lines 280, 313, 350) and WILL fail once FR-001 removes that job key — this is
  FR-010's expected, in-scope edit, not a violation to chase down as a regression.

## Red-first / revert discipline (including for YAML-only changes)

Standing Order #4 (test remediation & red-first) and ATDD-First Discipline (C-011) both require a
"failing-first" artifact. For a workflow-YAML change, "failing" cannot mean a pytest RED in the usual
sense for the live-topology claims — the plan states precisely what each AC's real falsification mechanism
is, per file:

**#4865 job split (FR-001-FR-005):**

- **What a static test CAN verify** (and does, unchanged by this mission): `test_nightly_workflow_never_triggers_on_pull_request`
  and `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs` prove no `pull_request` trigger
  exists anywhere and no forbidden marker-selection token (`FORBIDDEN_PR_PATH_TOKENS`,
  `test_performance_marker_guard.py:199-208`) leaked onto a PR-triggered workflow. These are real,
  re-runnable, CI-gated proofs — run them before AND after the split (before: passing against the
  single-job shape; after: passing against the three-job shape) to show C-001/FR-005 hold across the
  change.
- **What ONLY a live dispatch can verify** (AC1-AC4, SC-001-SC-003, NFR-001, NFR-002): that GitHub Actions
  actually reports three independent job entries with three independent conclusions; that `stress`
  completes to a real `success`/`failure` verdict instead of `cancelled`; that `nightly-summary`'s echoed
  output reports a line for each of the three. A pytest process parses YAML — it cannot observe a live
  Actions run's job topology or a runner's wall-clock. **The falsification path**: revert the split (restore
  the single `performance-and-e2e` job), dispatch `ci-nightly.yml` with `mode: full` on the reverted branch,
  and observe ONE job entry with ONE blended conclusion (exactly run `35683539593`'s own shape, reproduced
  above) — that reverted-state dispatch IS the "red" baseline; the post-split dispatch (FR-009, this plan's
  Phasing § Phase 1 step 1e below) is the "green" that proves the fix. Both runs' URLs and job conclusions get recorded per
  NFR-006 (see "Verification path" below) — this mission does NOT need to actually perform a fresh "revert
  and re-dispatch" cycle, because run `35683539593` (2026-09-22, already cited in the spec, already pulled
  with real timestamps above) IS that red-baseline evidence, captured before this plan's change lands. No
  redundant revert-dispatch is planned; the existing red run is cited as-is, with its URL/timestamps in the
  PR description.

**#4864 registry re-derivation (FR-006-FR-008, SC-005-SC-007):**

- **What the aggregate test CANNOT prove alone** (SPEC-VERIFY-004 / SC-006, already resolved in spec):
  `test_inter_shard_skew_within_twenty_percent` passing after recapture does not by itself prove `charter`
  specifically became non-vacuous, because the test's floor assertion is satisfied by ANY multi-shard
  module.
- **The durable, committed non-vacuity proof — MANDATORY, not optional (PLAN-VERIFY-002)**: spec.md's SC-006
  describes this unit test only as an optional strengthening ("Optionally, a narrow `charter`-specific unit
  test... would be a stronger, re-runnable alternative proof, but is not required"). **This plan
  deliberately elevates that optional spec item to a MANDATORY plan-level requirement — a reasoned
  divergence stated here explicitly, not a spec edit** (spec.md itself is unchanged) — because charter
  Standing Order #5 states "a gate-unmask cannot self-validate," and an uncommitted, non-re-runnable ad-hoc
  snippet cannot meet that bar: a durable, CI-re-runnable proof is required here, not merely permitted. This
  mission therefore commits a small, real, CI-re-runnable test —
  `tests/architectural/test_charter_shard_skew_sensitivity.py`, a narrowly-scoped sibling module
  (`test_module_shard_registry.py` itself stays read-only, per Seam / layering above) — that imports
  `test_module_shard_registry.py`'s `_lpt_bin_pack`/`_skew_of` helpers plus the recaptured
  `module_test_durations["charter"]`, and asserts `charter`'s own recomputed skew at its derived
  `shard_count` is non-zero and above a concrete floor (e.g. `>1%`, tightened once the real recaptured
  number is known). This is the standing order's evidence of record: durable and independently
  re-executable by CI on every future PR touching the `charter` row, not merely a transcribed
  command+output in the PR description. Written and run in Phase 2 (see Phasing below).
- **The spot-check (SC-006), with a concrete, pre-declared, non-degenerate rule (PLAN-VERIFY-001)**: after
  recapture, additionally run a short ad-hoc Python snippet (documented, not committed — a supplementary,
  human-readable illustration alongside the committed test above, not the sole proof) that imports the same
  helpers and the recaptured `module_test_durations["charter"]`, and computes:
  1. skew at `charter`'s genuinely LPT-derived `shard_count` (expected: <=20%, passing);
  2. skew at a **deliberately-wrong `shard_count`, fixed by this concrete, collision-free rule, stated here
     in the plan BEFORE implementation sees any skew numbers so it cannot be adjusted post-hoc to produce a
     convenient result**: `max(2, derived_shard_count // 2)` for every `derived_shard_count >= 3`, but
     `derived_shard_count * 2` when `derived_shard_count == 2` — the one case where
     `max(2, derived_shard_count // 2)` silently degenerates to a no-op: `max(2, 2 // 2) = max(2, 1) = 2`,
     IDENTICAL to `derived_shard_count` itself, which would compare `charter`'s skew at `shard_count=2`
     against skew at `shard_count=2` — proving nothing while appearing to validate the gate. (Verified
     directly against `tests/architectural/test_module_shard_registry.py`'s real `_lpt_bin_pack`/`_skew_of`:
     for every integer `derived_shard_count >= 3`, `max(2, derived_shard_count // 2)` is strictly less than
     `derived_shard_count`, so `derived_shard_count == 2` is the only collision case and the `* 2` branch
     above closes it.) This rule additionally, as before, explicitly excludes `shard_count == 1` (at
     `shard_count == 1`, `_lpt_bin_pack` places every duration into a single bin, so `_skew_of`'s
     `(max(bins) - min(bins)) / max(bins)` formula always returns exactly `0.0` for ANY data — a degenerate
     choice that would make the "wrong" case visually indistinguishable from the "correct" case) and
     excludes any value within 1 of `len(module_test_durations["charter"])` (near-degenerate — each bin
     would hold ~1 test, an artificially-perfect-looking pack unrelated to real imbalance). Expected:
     **>0% and plausibly >20%**, proving the recomputed skew is sensitive to `shard_count` where it was flat
     ~0% for every value 1-4211 before recapture.
  Both commands and both numeric outputs get recorded verbatim — in the PR description under a
  "Non-vacuity spot-check" heading, per SC-006/NFR-006 — alongside the committed test's pass result.

## Campsite-clean decision

Direct inspection of the touched-file neighborhood for real, domain-matched debt (file:line, not invented
busywork):

- **Found, and fixed as a DISTINCT, preceding campsite-clean commit (Commit A), per Standing Order #2
  (PLAN-GOV-001)**: `.github/workflows/ci-nightly.yml:72-73` — the current `performance-and-e2e` job
  declares `strategy: { fail-fast: false }` with **no `strategy.matrix`**. Per GitHub Actions' own
  semantics, `fail-fast` only has effect on a matrix strategy; without one, this key is inert (dead
  configuration) — confirmed by reading the job body (lines 68-172): no `matrix:` key appears anywhere
  under it.
  **Commit A (campsite-clean)** removes lines 72-73 from the EXISTING single `performance-and-e2e` job
  only — no other change in that commit; the job still exists, still runs the same three suites, same
  `timeout-minutes: 60`. This is distinct, behavior-preserving (an inert key is removed; nothing observable
  changes), and PRECEDES the functional change, per Standing Order #2's literal text (charter.md ~64-67)
  and the "Reconciling change-scope tensions" section (~140-145): "an opening campsite-clean is a distinct,
  behavior-preserving step that precedes the functional change."
  **Commit B (functional, FR-001 — `feat(ci)`)** then performs the three-job split on top of the now-clean
  job — none of the three new jobs carry the dead key forward, because Commit A already removed it from
  their shared ancestor.
  An earlier version of this plan folded the removal into the functional commit and justified it as
  avoiding "churn with zero net behavioral or textual difference" — the charter text does not carve out a
  churn-based exception to Standing Order #2's distinct-preceding-commit requirement, so that reasoning has
  been corrected to the two-commit sequence above (see Phasing § Phase 1, steps 1a-1b, below).
- **Checked and found clean, no folding needed**: no `TODO`/`FIXME`/`XXX` markers in any of the four
  pre-existing touched files (grep confirmed empty; the new committed test file added by this mission for
  PLAN-VERIFY-002 is not pre-existing debt by construction — it does not exist until Phase 2d); no repeated
  non-trivial literal appearing >=3 times in `ci-nightly.yml`/`ci-module-registry.yml` that would trigger
  the Sonar S1192 "hoist to a constant" rule (the `actions/checkout@<sha>` pin repeats 3x today by
  necessary GitHub Actions per-job convention, not avoidable duplication — this repo does not use YAML
  anchors elsewhere in this file, so introducing one here would be a stylistic departure out of proportion
  to this mission's scope); `ruff format --check` already passes clean on all three pre-existing
  touched/read Python files before any edit (confirmed above) — no format debt to fix as a precondition.
- **No other domain-matched debt found.** The disposition-ledger `reason:` comments naming
  `performance-and-e2e` (`.github/ci-module-registry.yml:622,641,669,692`) and the comment in
  `tests/e2e/test_worktree_owned_root_concurrency.py:377` are real prose drift this split will cause, but
  C-004 explicitly puts them out of this mission's diff (SPEC-ARCH-003, confirmed still accepted in the
  current spec) — not folded here, not treated as campsite debt, per the spec's own binding scope fence.

## Blast radius

Downstream consumers of the three files this mission changes:

- **`ci-nightly.yml` job names**: any downstream automation naming `performance-and-e2e` literally (a
  dashboard query, a Slack alert rule, a status-check branch-protection reference, or a sibling repo's
  workflow that watches this job's conclusion via the GitHub API) breaks silently the moment this merges —
  it will simply stop finding that job name. This repo's own `nightly-summary` and
  `test_performance_marker_guard.py` are the only in-repo consumers found by grep (already covered by
  FR-003/FR-010); `team-kitty-missions` and `muster-missions` were not found by this mission's own grep
  sweep to reference `performance-and-e2e` by name, but neither checkout was searched directly (out of this
  worktree's reach) — call this out in the PR description as an unverified-but-likely-low-risk external
  surface, per CLAUDE.md's "no follow-up issues... escalate" guidance rather than silently assuming zero
  risk.
- **`.github/ci-module-registry.yml`'s `charter` row shape**: `scripts/ci/capture_shard_timings.py`,
  `module-tests.yml`'s shard-selection step, and `tests/architectural/test_module_shard_registry.py` are
  the only in-repo consumers of a row's `shard_count`/`test_dirs` fields; none of this mission's edits
  change the row's SHAPE (field names, types) — only the `shard_count` value and its comment — so no
  consumer's parsing logic is at risk, only the derived shard count itself (correct-by-construction if the
  LPT re-derivation is done correctly, verified by the spot-check above).
- **`.github/ci-shard-timings.json`'s `charter` entries**: same consumers as above, plus any future
  `capture_shard_timings.py --module charter` re-run (idempotent — `merge_capture` replaces the module's
  three parallel tables together, confirmed by reading `capture_shard_timings.py:217-243`).

## Generated-artifact discipline

`.github/ci-shard-timings.json` is a **generated file** (`schema_version`, `module_test_durations`,
`module_capture_provenance`, etc.) — this mission's plan states explicitly it is regenerated ONLY by:

```
scripts/ci/capture_shard_timings.py --module charter --write
```

Never hand-patched. Verification before touching the registry row:

1. Run the command above from the repo root.
2. Confirm `module_capture_provenance["charter"]` is populated (not `None`) — shape matches the `auth`
   reference record already in the file (`run_id`, `command`, `captured_at`, `test_dirs`, `selection`,
   `unique_tests_measured`, `exit_code`, `producer`), per SC-005.
3. Confirm `exit_code` is `0` in that provenance record (a non-zero exit means the capture run itself hit a
   test failure or error — per the charter's Pre-existing Failure Reporting Rule, treat any such failure as
   requiring a filed GitHub issue BEFORE proceeding, not as accepted baseline; see "Baseline honesty"
   below).
4. Only after 2-3 confirm clean does the registry's `charter` row `shard_count` get edited, using the
   freshly-recaptured `module_test_durations["charter"]` fed through `_lpt_bin_pack`/`_skew_of` to find the
   smallest `shard_count` that keeps skew <=20% (mirroring the derivation already correctly done for `auth`
   et al.) — documented in a code comment on the row analogous to the existing `agent`/`upgrade`-row
   comment style, but stating the LPT derivation basis explicitly (not the rejected heuristic's framing).

## Known collision — PR #4886

`gh pr view 4886` (or equivalent) should be re-checked at implementation time, but per the spec's own
verified Correction #7: PR #4886 is open and touches `.github/ci-module-registry.yml`'s `core_misc` row
(a `test_dirs` addition) — distant from, and non-overlapping with, this mission's `charter`-row-only edit
(C-004). A clean merge is **not assumed**. If #4886 lands first: re-apply this mission's `charter`-row diff
on top of the updated upstream file (a 3-way merge should auto-resolve given the two edits target disjoint
line ranges, but this plan does not assume that — re-run `git diff` against the new base and hand-verify
only the `charter` row changed before re-pushing). If this mission's PR lands first, #4886 inherits the
same obligation in the other direction — out of this mission's control, noted for the record only.

## Verification path — pre-merge manual `workflow_dispatch`

Per the spec's "Verification reality" section and NFR-006 (already in the committed spec, resolving
SPEC-VERIFY-003): neither fix's real acceptance criterion is provable by a unit test alone. The plan's
evidence-gathering step is:

1. **After Commits A and B land on this mission's branch** (Commit A, `chore(ci)`: campsite-clean dead-key
   removal; Commit B, `feat(ci)`: FR-001-FR-005/FR-010 job split + guard-test update, `stress` running
   Stage A's generous, measurement-only `90`-minute budget — see Phasing § Phase 1 steps 1a-1d), push the
   branch and dispatch:
   `gh workflow run ci-nightly.yml --ref issue-4865-ci-nightly-wallclock-budget -f mode=full`
   (push access with `push: true, maintain: true` is available per the dispatch brief). Capture: the run
   URL, each of `performance`/`e2e`/`stress`/`interpreter-matrix`/`full-module-matrix`'s conclusions, and
   confirm `out/reports/xunit-nightly-stress.xml` exists in the `stress` job's uploaded artifact (not just
   assumed from a "success" conclusion) — satisfies SC-001/SC-002/SC-003/NFR-001/NFR-002/NFR-006. This
   dispatch is also the FIRST dispatch that Phase 1 step 1f (PLAN-ARCH-001) uses to UNCONDITIONALLY
   re-derive `stress`'s tightened, FINAL production `timeout-minutes` (Stage B) from its measured COMPLETED
   duration — capture `stress`'s actual completed job duration explicitly here, not just its conclusion,
   since Stage B's re-derivation depends on it. If `stress` STILL fails to complete inside Stage A's `90`
   minutes, that duration is not usable for Stage B — follow step 1f's contingency (re-dispatch with a
   further-widened, still measurement-only ceiling, capped at the bounded `90` -> `150` -> `300`-minute
   ladder from "Real evidence used to size the new budgets" above, at most 2 widen attempts, each its own
   small `chore(ci)` commit) until a real completed duration is captured — or, if the `300`-minute final
   ceiling is also exceeded, stop widening and treat it as a genuine test-suite hang/deadlock, applying the
   charter's Pre-existing Failure Reporting Rule (see "Baseline honesty" below — note the confirmation-method
   caveat recorded under "Real evidence used to size the new budgets" above, since the standard
   `upstream/main` confirmation does not transfer to this specific case) and escalating to the operator
   instead. **Record every dispatch this contingency actually performs** — not just the first — with its own
   run URL and job conclusion, so the PR description (Phase 3, NFR-006) can list however many dispatches the
   ladder actually took.
2. **After the FR-006-FR-008 commit(s) land** (recapture + registry re-derivation), the SAME or a follow-up
   dispatch's `full-module-matrix` job's `charter` shards are inspected for per-shard wall-clock (visible in
   the run's job list) — satisfies User Story 2's AC4 (long pole no worse than, ideally more balanced than,
   the pre-fix 27m20s/27m41s/17m37s/21m13s/16m22s spread cited in the spec).
3. Record all of the above — **EVERY dispatch run's URL and conclusion, not just "both": however many the
   Stage A widen ladder actually took, from 1 (Stage A's first dispatch succeeded) up to 3 (Stage A plus
   both widen attempts at `150` and `300`)** — plus job conclusions, the widen-retry commit hash(es) if any
   widen attempt happened, the SC-006 spot-check command+output, the xunit artifact confirmation, and — if
   the `300`-minute escalation clause actually triggered — the filed Pre-existing-Failure-Reporting-Rule
   issue's URL and a note on how it was resolved before the mission continued — in the PR description under
   clearly labeled headings (or a dedicated review-evidence note if the PR description would otherwise be
   unwieldy), per NFR-006. This is the durable evidence a later reviewer checks instead of trusting a verbal
   claim, per the charter's Standing Orders throughline.

This is NOT "wait for the next nightly" or "wait for the 03:17 UTC cron" — both are explicitly rejected as
the evidence path by the spec's Verification Reality section.

## Baseline honesty

Issue #3284 ("23 known-red on main") is CLOSED and is **not** cited as this mission's baseline (Correction
#2). Before the first change lands, run a scoped baseline (this diff only touches `.github/` YAML plus one
architectural test file — the relevant scoped baseline is `tests/architectural/`, specifically the two test
files this mission reads/writes):

```
uv run --frozen pytest tests/architectural/test_module_shard_registry.py tests/architectural/test_performance_marker_guard.py -q
```

Run this BEFORE any change, and record pass/fail counts. If pre-existing failures are hit (a failure red on
`issue-4865-ci-nightly-wallclock-budget`'s current HEAD, i.e. before this plan's own commits, that is
unrelated to this mission's diff): per the charter's binding **Pre-existing Failure Reporting Rule**, a
GitHub issue MUST be filed — command run, failure summary, why judged pre-existing (e.g. confirmed still
red on `upstream/main` via the merge-base) — **before** treating it as accepted baseline context. This is
the one sanctioned exception to the "no follow-up issues" scope rule (SC-008); it does not apply
unconditionally — only if a pre-existing failure is actually encountered during this mission's execution.

## Phasing

Spec-confirmed independent (User Story 1 and User Story 2 each carry an "Independent Test" clause proving
neither requires the other). Sequencing chosen for this plan, with reasoning:

**Cumulative wall-clock, non-hidden.** Phase 1's own widen-ladder contingency (see "Real evidence used to
size the new budgets" above) permits up to `90 + 150 + 300 = 540` minutes of dispatch-wait in the worst case,
before Phase 2's ~110-minute NFR-004 recapture cost even starts — up to **~650 minutes (~11 hours)** total in
the pathological worst case across both phases. Stated here, at the point where the phase sequence itself
determines that these costs stack rather than overlap, as an accepted/sized cost, not a target.

1. **Phase 0 — baseline.** Run the scoped `tests/architectural/` baseline (above) before any change lands.
   File a GitHub issue if a pre-existing failure surfaces (conditional, per Baseline honesty above).
2. **Phase 1 — #4865 job split (FR-001-FR-005, FR-010).** Chosen first because it is P1 (more severe harm —
   active information loss and coverage loss today) and because it is the smaller, more mechanical of the
   two changes (a YAML restructuring + one test file's literal updates), so landing it first gives an early,
   cheap `workflow_dispatch` evidence cycle (Phase 1 dispatch below) before committing to the more
   expensive Phase 2 recapture. Per the corrected Campsite-clean decision above (PLAN-GOV-001), this phase
   now opens with a DISTINCT, preceding, behavior-preserving campsite-clean commit (Commit A) before the
   functional split commit (Commit B) — no debt is folded into the functional commit.
   - 1a. **Commit A (campsite-clean, distinct, preceding, behavior-preserving).** Edit `ci-nightly.yml`:
     remove the dead `strategy: { fail-fast: false }` key (lines 72-73) from the EXISTING single
     `performance-and-e2e` job only — no other change in this commit; the job still exists, still runs the
     same three suites, same `timeout-minutes: 60`. Confirm via `git diff` that only those two lines
     changed. Commit as a `chore(ci)`-scoped Conventional Commit (Standing Order #2).
   - 1b. **Commit B (functional, FR-001 — `feat(ci)`).** Edit `ci-nightly.yml`: replace the now-clean single
     `performance-and-e2e` job with three jobs (`performance` timeout 35, `e2e` timeout 40, `stress`
     timeout **90 — Stage A, a deliberately generous, MEASUREMENT-ONLY value, not final; see "Real
     evidence used to size the new budgets" above**), each preserving the existing
     `env:`/checkout/uv-sync/suite-step/upload-artifact/fail-loud-terminal-step shape (the `fail-fast` key
     is already gone, from Commit A — nothing further to strip here). Update `nightly-summary`'s `needs:`
     (line 337) and its echoed report step to list all three.
   - 1c. Edit `tests/architectural/test_performance_marker_guard.py`: update the three hardcoded-job-name
     tests (lines 280, 313, 350) to iterate/assert against `performance`, `e2e`, `stress` in place of
     `"performance-and-e2e"` (keep `"interpreter-matrix"` unchanged in the shared tuples where present).
     Folded into Commit B (same functional change these tests assert against) — this test-literal update is
     FR-010's expected maintenance, not campsite debt.
   - 1d. Run `ruff format --check` on the edited Python file; run the two pull_request-trigger-detection
     tests plus the three updated tests locally
     (`uv run --frozen pytest tests/architectural/test_performance_marker_guard.py -q`).
   - 1e. Dispatch `ci-nightly.yml` (`mode: full`) on this branch — this is the FIRST dispatch (Verification
     path step 1), run under Stage A's generous `90`-minute `stress` budget specifically so `stress` can
     reach a real completion instead of truncating again. Record evidence, including `stress`'s actual
     COMPLETED measured job duration (the value Stage B re-derives from).
   - 1f. **Unconditional stress-timeout re-derivation — Stage B (PLAN-ARCH-001).** From step 1e's dispatch,
     take `stress`'s real COMPLETED job duration and re-derive its tightened, FINAL production
     `timeout-minutes` using the same ~1.5x-headroom method used for `performance`/`e2e` above. Edit
     `ci-nightly.yml`'s `stress` job with the derived value and commit as a small, functional `fix(ci)`
     follow-up, SEPARATE from Commit B (Stage A). This step is UNCONDITIONAL — it runs regardless of whether
     Stage A's `90`-minute measurement-only budget happened to be sufficient in step 1e's dispatch; Stage A's
     `90` is never itself the shipped value. The shipped Stage B value must differ from `60` unless a genuine
     re-derivation independently lands on that same number. **Contingency**: if step 1e's dispatch STILL
     truncates `stress` before it completes (i.e. even Stage A's generous `90`-minute ceiling was
     insufficient), do not proceed to Stage B from a truncated duration — re-dispatch with a further
     widened, still measurement-only ceiling on the bounded escalation ladder from "Real evidence used to
     size the new budgets" above: `150` (widen attempt 1), then `300` (widen attempt 2, the FINAL ceiling —
     at most 2 widen-and-redispatch attempts total, staying comfortably under GitHub Actions' documented
     6-hour/360-minute per-job ceiling for hosted runners), only then performing the Stage B re-derivation
     above. Record each of these dispatches' own run URL and job conclusion (Verification path step 1,
     Phase 3/NFR-006). Each widen-retry timeout bump is its own small, functional `chore(ci)` commit to
     `ci-nightly.yml`'s `stress` `timeout-minutes` (a file edit, not a dispatch parameter — see "Real
     evidence used to size the new budgets" above), separate from Commit B and from the eventual Stage B
     commit. **If `stress` still has not completed within the `300`-minute final ceiling**, stop widening —
     this is a genuine, unexpected test-suite defect (hang/deadlock), not a sizing problem: apply the
     charter's Pre-existing Failure Reporting Rule (file the GitHub issue before proceeding further — see
     "Baseline honesty" above; and see "Real evidence used to size the new budgets" above for why the
     standard `upstream/main` pre-existing confirmation does not transfer to this specific case, and the
     alternative confirmation wording to use instead) and escalate to the operator rather than continuing the
     contingency loop.
3. **Phase 2 — #4864 recapture + re-derive (FR-006-FR-009 for this half, NFR-003/NFR-004).** Chosen second:
   it is P2 (correctness-of-measurement, not active outage) and its ~110-minute serial cost (NFR-004) is
   better paid once the cheaper Phase 1 evidence cycle has already validated the branch is otherwise sound.
   - 2a. Run `scripts/ci/capture_shard_timings.py --module charter --write` (budget ~110 minutes serial
     wall-clock — this is its own explicit step, not folded into "edit a YAML number," per NFR-004). Verify
     `module_capture_provenance["charter"]` populated, `exit_code == 0` (Generated-artifact discipline
     steps 2-3 above). If `exit_code != 0`, apply Baseline honesty's Pre-existing Failure Reporting Rule
     before proceeding.
   - 2b. Compute `charter`'s LPT-derived `shard_count` from the recaptured `module_test_durations["charter"]`,
     mirroring the method already correct for `auth` et al. Edit `.github/ci-module-registry.yml`'s
     `charter` row `shard_count` (line 151) and add a derivation-basis comment (SC-007).
   - 2c. Run the SC-006 spot-check (Red-first / revert discipline above, using the pre-declared,
     non-degenerate, collision-free deliberately-wrong `shard_count` rule, PLAN-VERIFY-001): compute and
     record skew at the derived `shard_count` AND at the deliberately-wrong `shard_count` the rule selects
     (`max(2, derived_shard_count // 2)`, or `derived_shard_count * 2` if `derived_shard_count == 2` — see
     Red-first / revert discipline above for the full rule and why the plain `// 2` form alone would
     silently degenerate to a no-op at `derived_shard_count == 2`).
   - 2d. **Write and run the mandatory committed non-vacuity test (PLAN-VERIFY-002).** Add
     `tests/architectural/test_charter_shard_skew_sensitivity.py` asserting `charter`'s recomputed skew at
     its derived `shard_count` is non-zero and above the concrete floor stated in Red-first / revert
     discipline above. Run `ruff format --check` on the new file; run
     `uv run --frozen pytest tests/architectural/test_charter_shard_skew_sensitivity.py -q` to confirm it
     passes against the real recaptured data.
   - 2e. Run `uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q` to confirm the
     gate itself passes post-recapture.
   - 2f. A second (or the continuation of the Phase 1) `workflow_dispatch` (`mode: full`) run gives the
     `full-module-matrix` `charter`-shard evidence for User Story 2's AC4 (Verification path step 2).
4. **Phase 3 — PR assembly.** One PR (spec-kitty's default mission shape — not tk's one-PR-per-WP rule;
   this mission has no `lanes.json`/WP split, confirmed by `meta.json`'s `"topology": "single_branch"`).
   PR description assembles: **EVERY `workflow_dispatch` run's URL and job conclusion (NFR-006) — however
   many the Stage A widen ladder actually took, from 1 (Stage A's first dispatch reached a real `stress`
   completion) up to 3 (Stage A plus both widen attempts at `150` and `300`); never assume exactly "both"**,
   `stress`'s two-stage sizing — Stage A's generous measurement-only `90`-minute budget used for the first
   dispatch, the completed duration that dispatch (or, if widened, the widen attempt that succeeded)
   measured, and Stage B's tightened FINAL production `timeout-minutes` re-derived from it (PLAN-ARCH-001) —
   **the widen-retry commit hash(es), if any widen attempt happened** — the SC-006 spot-check command+output
   using the pre-declared, collision-free deliberately-wrong `shard_count` rule (PLAN-VERIFY-001), the new
   committed `test_charter_shard_skew_sensitivity.py`'s pass result (PLAN-VERIFY-002), the Phase 0 baseline
   result, any filed pre-existing-failure issue (conditional) — **including, if the `300`-minute escalation
   clause actually triggered, that filed Pre-existing-Failure-Reporting-Rule issue's URL and a note on how it
   was resolved before the mission continued** — and the scoped test commands run (per AGENTS.md/CLAUDE.md §6
   Test policy). Tracer files continue to be appended during implementation per Standing Order #3 (already
   seeded — see below), not re-seeded.

## Constitution Check

*GATE: re-checked at plan time against `.kittify/charter/charter.md`.*

- **Single canonical authority**: `.github/ci-shard-timings.json` remains the sole authority for measured
  durations (regenerated only via its one producer); `.github/ci-module-registry.yml` remains the sole
  authority for the per-module test matrix. No second, divergent authority is introduced. PASS.
- **Architectural alignment**: no `src/**` module boundary is crossed (Seam/layering above). PASS.
- **ATDD-first / red-first**: satisfied per file-type-appropriate falsification (Red-first / revert
  discipline above) — a live dispatch stands in for a pytest RED where pytest structurally cannot observe
  the live-topology claim; the `charter` skew non-vacuity claim, by contrast, now IS a pytest-RED-capable
  assertion via the mandatory committed `test_charter_shard_skew_sensitivity.py` (PLAN-VERIFY-002), with
  the ad-hoc spot-check kept only as a supplementary illustration. PASS, with the boundary explicitly
  stated rather than hand-waved.
- **Campsite cleaning (#2)**: real, minimal, domain-matched debt found (dead `fail-fast` key) and removed
  via a DISTINCT, preceding, behavior-preserving Commit A (`chore(ci)`) — not folded into the functional
  Commit B (`feat(ci)`) (see Campsite-clean decision and Phasing § Phase 1, steps 1a-1b, above; corrected per
  PLAN-GOV-001); no manufactured busywork. PASS.
- **Architectural gate discipline (#5)**: the mission's entire P2 half exists to close a vacuous-gate defect
  per this standing order's own language ("a gate-unmask cannot self-validate") — the MANDATORY committed,
  re-runnable `tests/architectural/test_charter_shard_skew_sensitivity.py` (Red-first / revert discipline
  above, corrected per PLAN-VERIFY-002, and deliberately elevated beyond spec.md's own "optional" SC-006
  framing per the acknowledgement in "Spec-phase review findings already resolved" and Red-first / revert
  discipline above) is the concrete, durable, independently re-executable non-vacuity proof this standing
  order requires; the ad-hoc SC-006 spot-check snippet is retained only as a supplementary, human-readable
  illustration in the PR description, not the standing order's evidence of record. PASS, directly addressed
  against the corrected, committed-test mechanism.
- **Mission tracer files (#3)**: already seeded (`tracer-approach.md`, `tracer-design-decisions.md`,
  `tracer-tooling-friction.md` all present and populated from the spec phase); this plan does not re-seed
  them, and implementation continues appending to them. PASS.
- **Pre-existing Failure Reporting Rule**: encoded as a conditional, explicit step in Baseline honesty and
  Phase 2a above — not silently absorbed. PASS.
- **Git & workflow discipline (#7)**: single PR onto `main` per spec-kitty's default shape; this plan does
  not merge or push to `main` directly; `safe-commit --to-branch issue-4865-ci-nightly-wallclock-budget` is
  this plan-commit's own mechanism (see Steps). PASS.

No constitution violations requiring the Complexity Tracking table below (left empty/not applicable).

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/
├── spec.md                    # authoritative, committed, not edited by this plan
├── plan.md                    # this file
├── reviews/spec.confirmed.yaml # spec-phase adversarial findings, already resolved in spec.md
├── tracer-approach.md          # seeded at spec phase, appended during implementation
├── tracer-design-decisions.md  # seeded at spec phase, appended during implementation
├── tracer-tooling-friction.md  # seeded at spec phase, appended during implementation
└── tasks/                      # Phase 2 output (/spec-kitty.tasks — not this plan's job)
```

No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` are produced by this plan — this
mission has no data model, no API contract, and no open research question left after the spec phase's
direct-inspection corrections; producing empty placeholders for those artifacts would be busywork against
the charter's smallest-viable-diff principle.

### Source / infrastructure touched (repository root)

This is a CI/YAML-and-test-file mission (one existing architectural test file edited, one new one added),
not a `src/`-code mission — the template's Option 1/2/3 source trees do not apply. The concrete, real
touched-file set is:

```
.github/
├── workflows/
│   └── ci-nightly.yml              # FR-001-FR-005: job split, timeout sizing, needs: update
├── ci-module-registry.yml          # FR-006-FR-008: charter row shard_count + derivation comment (only)
└── ci-shard-timings.json           # generated; regenerated via scripts/ci/capture_shard_timings.py only

scripts/ci/
└── capture_shard_timings.py        # READ + RUN (the mission's one sanctioned producer); not edited

tests/architectural/
├── test_performance_marker_guard.py         # FR-010: 3 hardcoded job-name tests updated
├── test_module_shard_registry.py            # READ ONLY: consumed for its LPT method; not edited
└── test_charter_shard_skew_sensitivity.py   # NEW (PLAN-VERIFY-002): mandatory committed non-vacuity test
```

**Structure Decision**: no new directory, no new workflow file (T044(a)'s "registry row, not a new
workflow file" invariant is preserved — this mission adds zero new files to `.github/workflows/`), no new
`src/**` production module. One new file is added — `tests/architectural/test_charter_shard_skew_sensitivity.py`
— the mandatory committed non-vacuity test required by PLAN-VERIFY-002; it is test-only, lives alongside
the existing architectural tests, and adds no new production Python module. The realization otherwise stays
within the four originally-scoped files plus the generated JSON artefact they produce/consume.

## Complexity Tracking

*No Constitution Check violations require justification — table intentionally left empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Parallel Work Analysis

Not applicable — `meta.json` declares `"topology": "single_branch"` (no `lanes.json`, no WP split), and
this plan's own Phasing section above sequences the work as one continuous lane (Phase 0 → 1 → 2 → 3), each
phase's evidence gate (baseline / dispatch / spot-check) a prerequisite for the next. A single implementer
(or a single delegated subagent context) carries the mission through; no dependency graph or agent
ownership map is needed beyond the phase order already stated.
