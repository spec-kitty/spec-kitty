# Contract — Router two-authority model (E5)

The path→job routing has exactly **two hand-authored sources**; everything else is derived + asserted.

## The two authorities
1. **dorny filter block** (`changes` job): `group → globs[]` (path→group).
2. **job `if:` gates**: `if: needs.changes.outputs.<group>` (group→job).

## Derived (asserted against the two, never hand-maintained)
- The catch-all unmatched OR-list; the aggregator `needs:` set; the completeness oracle.

## Invariants
1. A `src/**` change matched by **no** group forces `run-all` (loud unmatched alarm), never a silent skip.
2. `docs`/`corpus` are non-src → excluded from the unmatched loop (data, not code).
3. **Gate-selection authority (FR-016/#2476):** ONE importable function **parses these two authorities**
   (does not re-encode them) and answers "which shards/gates does this diff select" — reused by **CI
   routing** and **local pre-PR parity** (no second parser). Built with **T1 (router)**; consumed by L3.
4. **Non-vacuous completeness oracle:** reads the **real on-disk** workflow YAML; fails if any test is
   zero-gated or an enumerated must-run gate is unwired; carries a planted-orphan negative test (#2967).
5. Reintroducing filters updates `test_ci_quality_path_filters.py` **in lockstep** (it currently asserts the
   husk has *no* filter).
6. `on.paths` (Gate-0) and dorny `filters:` (Gate-1) stay in lockstep OR the workflow runs on every PR with
   Gate-0 dropped (#3008 hazard); corpus keeps its exit-5 floor.

## Module shard registry (E7, matrix realization)
- Per-module shards are a **matrix over a committed module registry** inside a **bounded** set of reusable
  workflows (≤ GitHub's 20-unique-reusable-workflows-per-caller limit), **not** ~40 separate `module-*.yml`.
  The registry (module → roots, `--cov` target, tier, shard_count) is the single data source; adding a
  module is a registry row, not a new workflow file.

### Diff-scoped matrix (mission ci-modules-diff-scoping)
- The module matrix is **registry-generated THEN authority-scoped**, never a second re-encoded map: every
  registry row still gets a matrix leaf every run (`ci-modules.yml`'s `generate-matrix` job iterates
  `modules[]` generically), but each leaf carries a `selected` flag computed via
  `scripts/ci/gate_selection.py`'s `select_modules` — the SAME single gate-selection authority
  `ci-router.yml`'s path routing consumes (invariant 3 above). A module the diff did not select still
  instantiates its `test` job leaf; that leaf is gated `if: matrix.selected == 'true'`, reporting a neutral
  SKIPPED check — filtering it out of `include:` instead would report NO check at all and hang a
  required-check gate forever.
- `mode == 'full'` (workflow_dispatch, or a `workflow_call` invocation with `mode: full`) and the FR-004
  fail-closed unmatched-src case both select every module (run-all), matching `ci-router.yml`'s own
  run-all semantics exactly. A push whose pre-push SHA is the null SHA (first push / force push — a
  degenerate base `git diff` cannot resolve) also forces full selection.
- **Push is diff-based, exactly like a PR.** `ci-router.yml`'s `changes.outputs.*` no longer folds in
  `github.event_name == 'push'` as a run-all condition (pinned by
  `test_ci_router_transcription_guards.py::test_changes_outputs_never_force_run_all_on_push`); `ci-modules.yml`
  diff-scopes push the same way it scopes a PR.
- **`ci-nightly.yml` is the full-run home.** Since push is no longer always-full-scope, the nightly lane
  (`ci-nightly.yml`) carries its own `generate-full-matrix` + `full-module-matrix` jobs that realize the
  SAME committed registry unconditionally selecting every module/shard, calling `module-tests.yml` (the
  single-job reusable shard) directly with `mode: full` — this is the cross-module post-merge safety net
  that replaces the old push-always-full-scope behavior (operator decision). It does **not**
  `uses: ./.github/workflows/ci-modules.yml` (a nested multi-job reusable-workflow call): the
  architectural gate-coverage model's local-`uses:` splicer
  (`tests/architectural/_gate_coverage.py::_splice_local_uses`) requires a spliced reusable workflow to
  define exactly one job — `module-tests.yml` qualifies, `ci-modules.yml` (a 3-job matrix orchestrator)
  does not.
- **`ci-aggregate.yml` stays whole-tree via selection-aware backfill (Approach C), never a shrunk expected
  set.** `ci-modules.yml`'s `generate-matrix` job publishes the resolved selected-module set as the
  `selected-modules` artifact. `ci-aggregate.yml`'s `collect` job downloads it and reconciles per module: a
  SELECTED (changed) module missing from the triggering run's shards fails closed exactly as before —
  never served from the stale-artefact fallback, even when the fallback has it, so a genuine shard failure
  on changed code can never be masked by old green. An UNSELECTED (unchanged, provably byte-identical to
  the fallback source) module missing from the triggering run is backfilled from the most recent
  successful "CI Modules" run (the PR branch's own prior run, else the default branch's) — safe because
  `diff-cover` only scores the actual diff, which lives entirely in selected/fresh modules, so backfilling
  unchanged coverage cannot mask a regression while keeping whole-tree/Sonar coverage coherent. When no
  selection info is available at all (a legacy/pre-feature run, or a download failure), every missing shard
  remains fallback-eligible, matching the pre-Approach-C behavior. Manual `workflow_dispatch` replay
  downloads neither the fallback run nor the selection artifact, so it always requires complete evidence
  from its exact source attempt (no backfill at all).
