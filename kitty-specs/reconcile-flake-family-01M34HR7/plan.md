# Implementation Plan: Reconcile-flake family: transient same-SHA CI reconcile failures

**Branch**: `fix/reconcile-flake-family-4882` | **Date**: 2026-09-22 | **Spec**: `kitty-specs/reconcile-flake-family-01M34HR7/spec.md`
**Input**: Feature specification from `kitty-specs/reconcile-flake-family-01M34HR7/spec.md`

## Summary

Epic #4882 (children #4652, #4675, #4878) reports the same defect class three times: a reconcile
step reads racy-but-converging CI evidence, treats any instability as fatal on the first read, and
either raises (`fleet_verdict.py`/`fleet_main.py`) or fails a single-pass completeness check
(`reconcile_shards.py`) — training reviewers to dismiss red as noise. Per the spec's binding
Decision 1, this mission fixes the shared defect class once, across all three job shapes, not
three point-fixes.

The fix adds **one new stdlib-only, pytest-mockable bounded-retry primitive**
(`scripts/ci/reconcile_retry.py`) and wires it into three call sites with two structurally
different terminal behaviors:

- `fleet_verdict.py::report()` (#4878) and `fleet_main.py::report()` (#4652) — both retry their
  entire double-snapshot (snapshot → dedupe-check → re-snapshot → compare) as one unit; on
  exhausted budget they **skip silently, exit 0, print a diagnostic** (FR-004), relying on
  `ci-fleet-verdict.yml`'s repeated per-head `workflow_run` firings to reconcile later.
- A new `scripts/ci/wait_for_artifacts.py`, invoked from a new step in `.github/workflows/ci-aggregate.yml`
  ahead of the existing `actions/download-artifact` steps, polls GitHub Actions artifact
  visibility for the triggering run's SELECTED (must-be-fresh) shard artifacts; on exhausted
  budget it **falls through to the existing download-and-reconcile steps regardless** — the
  fail-closed decision stays entirely with `reconcile_shards.py::main()`, which is **not
  modified** by this mission (FR-005/FR-006, Key Entities item 3).

Pre-merge verification is unit tests only (Decision 2), because all three affected workflows fire
on `workflow_run`, which always executes the default-branch (`main`) copy of the workflow file and
every script it references — this mission's own PR cannot exercise its own fix through the real
trigger path (C-001). Post-merge confirmation is a bounded observation window (SC-004), not a
merge gate.

## Technical Context

**Language/Version**: Python 3.11+ (repo-wide requirement; `scripts/ci/*.py` already targets it).
**Primary Dependencies**: Python standard library only (`time`, `argparse`, `json`, `re`,
`urllib.request`) plus `pyyaml` (already a runtime dependency of `fleet_verdict.py`/
`fleet_main.py`/`reconcile_shards.py` for workflow/registry parsing). **No new dependency is
added** — NFR-002/C-004 forbid it, and the diff below introduces none.
**Storage**: N/A — these scripts read GitHub Actions API responses and local downloaded artifact
directories; no persistent storage.
**Testing**: `pytest`, run via `.venv/bin/python -m pytest tests/ci/...` (never bare `uv run`,
which re-syncs and can disturb a hand-built `.venv` — `AGENTS.md`/`CLAUDE.md`).
**Target Platform**: GitHub Actions `ubuntu-latest` runners (the workflow steps); the scripts
themselves are plain CPython 3.11+, platform-independent.
**Project Type**: Single project — this is CI-infrastructure tooling inside the existing
`scripts/ci/` + `.github/workflows/` + `tests/ci/` surfaces, not an application feature.
**Performance Goals**: Each retry/poll loop must stay well inside its job's existing
`timeout-minutes` budget (`ci-fleet-verdict.yml`'s `report`/`report-main` jobs: 15 min;
`ci-aggregate.yml`'s `collect` job: 15 min) — see NFR-001 budget rationale below.
**Constraints**: NFR-001 (bounded attempts/time), NFR-002/C-004 (stdlib-only), C-002 (fail-closed
floor inviolable), C-003 (never publish stale evidence), FR-009 (no cross-invocation coupling).
**Scale/Scope**: Three modified/added Python modules (~250–350 new/changed lines total, estimate),
one workflow YAML re-sequencing + one new step, test additions in `tests/ci/`. No new domain
entities (spec.md Key Entities: "not applicable in the conventional sense").

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This repository's governance document is the **charter** (`.kittify/charter/charter.md`), not a
"constitution" file — `AGENTS.md` and the charter itself both say the charter wins on any
disagreement, so this section maps the template's "Constitution Check" onto the charter's
Governing Principles and Quality & Tech-Debt Standing Orders.

| Charter rule | Check | Status |
|---|---|---|
| Single canonical authority (Governing Principles) | New retry primitive is ONE module reused by all three call sites, not three copies; `wait_for_artifacts.py` imports `reconcile_shards.py`'s existing `parse_registry`/`read_selected_modules` rather than re-deriving shard naming | PASS |
| Architectural alignment (Governing Principles; DIRECTIVE_001) | Change lands on the already-decided seam: a new `ci-aggregate.yml` polling step ahead of `download-artifact`, not inside `reconcile_shards.py::main()` (spec's own architecture-seam finding); `scripts/ci/` stays a flat module set, consistent with existing layout | PASS |
| ATDD-first / red-first (Standing Order #4, DIRECTIVE_041) | NFR-003 mandates every new retry test is first run against the unmodified surface and confirmed to fail the way it does today (existing `ValueError`, or non-zero exit with no retry) before the retry implementation lands | Planned — binding on implement phase |
| ATDD-First Discipline (binding per charter.md C-011) | Binds WP1–WP3, each of which introduces new functional code: each such WP's first commit must be the failing test alone, committed separately, BEFORE the implementation commit(s) — a stricter, commit-history-level requirement than the red-first row above; the reviewer verifies red-on-`planning_base_branch`, green-on-final-commit. **WP4 introduces no new functional code** — FR-009's cross-invocation isolation test (the only test content WP4 would otherwise carry, and one this plan explicitly exempts from red-first below) is instead committed inside WP2's own red-first commit sequence, alongside WP2's other FR-002/003/004/007 tests, which do have valid red-first anchors; WP4 is re-scoped to be a pure integration/verification WP — final tracer-file append + SC-001/SC-002/SC-003 full-suite re-run — with no commit of its own that could be RED on `planning_base_branch`. C-011's per-WP failing-first-commit requirement therefore does not apply to WP4 (see "Parallel Work Analysis / Dependency Graph" below for the re-scoping) | Planned — binding on implement phase (see tasks.md WP commit sequencing) |
| Campsite cleaning (Standing Order #2, DIRECTIVE_025) | Scoped narrowly to the five touched files; see "Campsite-clean scope" below | PASS (narrow, justified) |
| Mission tracer files (Standing Order #3) | Seeded now: `tracer-tooling-friction.md`, `tracer-approach.md`, `tracer-design-decisions.md` | DONE (seeded this phase) |
| Git & workflow discipline (Standing Order #7, DIRECTIVE_045) | One PR onto `main`; operator/merge-agent merges; no direct push | Planned — binding on implement/review phases |
| Red-main discipline (Standing Order #9) | ENGAGED, not bypassed: `fleet_main.py::report()` — the exact function this mission modifies under FR-003/FR-004 — is the P0-incident-filing mechanism Standing Order #9 governs. The retry/skip-and-defer change only defers on unresolved snapshot disagreement; it never suppresses a stabilized/confirmed red result (Invariant (a)/FR-007), so the red-main safety guarantee is preserved | PASS (engaged and preserved, not N/A) |
| Adversarial squad cadence (Standing Order #1) | Advisory; already run once post-spec (`kitty-specs/.../reviews/` — R1–R6 trail exists per `b089d6c34`). A post-plan pass is optional/advisory per the charter, left to the orchestrator to schedule | Advisory — orchestrator's call |

No violations requiring the Complexity Tracking table below; it is left empty per the template's
own instruction ("Fill ONLY if Constitution Check has violations").

## Gate Statement (verified in this checkout, not assumed)

This mission's diff touches only `scripts/ci/**`, `.github/workflows/{ci-aggregate,ci-fleet-verdict}.yml`,
`tests/ci/**`, and `kitty-specs/reconcile-flake-family-01M34HR7/**`. Gates this diff triggers, and
gates it does not, with the reason for each:

**Triggers, hard-enforced:**
- `ruff check .` and `ruff format --check .` — `ci-quality.yml:29-32` `lint` job, no
  `continue-on-error`; also duplicated as a second `lint` job inside `ci-router.yml` (belt and
  suspenders, verified at the same file, no path filter — runs unconditionally on every PR). Run
  `make format-check` before every commit (charter/CLAUDE.md instruction).
- `import-linter` (TID251 banned-API check) — `ci-router.yml`'s `import-linter` job
  (`uv run --frozen ruff check --select TID251 .`), unconditional on every PR (no path filter on
  the workflow's own `on:` trigger). The new modules use only stdlib + `pyyaml` + intra-repo
  imports already in use by their siblings, so no new banned import is expected, but the
  implement phase must actually run this locally before proposing the PR.
- `clean-install-verification` — `ci-quality.yml`, depends on `build-wheel`, unconditional on
  every PR (branch-protection-required per `protect-main.yml`'s own header comment). This mission
  adds no packaging surface change (no new dependency, no `pyproject.toml`/`uv.lock` edit), so it
  is expected to pass unaffected, but it is still a real gate this PR must clear.
- `ci-modules.yml`'s `ci` shard (`tests/ci/`) — the actual test *executor* for this diff.
  `ci-modules.yml` is triggered directly and independently by its own `pull_request`/`push`/
  `workflow_call`/`workflow_dispatch` events, not routed through `ci-router.yml`: `ci-router.yml`'s
  own `ci` filter group carries a header comment stating verbatim that "No job gates on this group
  BY DESIGN" (verified at `ci-router.yml`'s `changes` job). `ci-modules.yml`'s own
  `generate-matrix` job independently selects the `ci` module row (via
  `scripts/ci/gate_selection.select_modules`, reading `git diff` directly, against
  `.github/ci-module-registry.yml`'s `ci` module row — `roots: scripts/ci/**`,
  `.github/workflows/**`, verified directly in that file) for a diff touching those paths.
- `ci-aggregate.yml`'s `aggregate-gate` (`needs: [collect, diff-cover]`) — structurally reached
  by any PR, but `diff-cover`'s ≥90% floor does NOT apply to this diff (see below), so this gate
  is expected to pass with an empty/no-op scoring pass over this diff's changed lines.

**Triggers, advisory/non-blocking (reported, not required):**
- `sonar-pr` job in `ci-aggregate.yml` — verified `continue-on-error: true` at line 414 and
  excluded from `aggregate-gate`'s `needs: [collect, diff-cover]` set-equality check at line 622;
  a Sonar verdict is never promised as a gate by this plan.

**Does not apply, with reason (verified, not assumed):**
- **diff-cover ≥90% floor** — does not apply to this mission's own diff. Verified directly in
  `.github/ci-module-registry.yml`: the `ci` module row's `cov_targets` are `kernel` and
  `specify_cli.core`, not `scripts/ci`; `scripts/ci/**` is not `--cov`-instrumented by the module
  matrix that feeds `ci-aggregate.yml`'s coverage set (C-008). **This does not excuse omitting
  tests** — the standing order "every new branch/helper needs tests in the same PR" (CLAUDE.md
  "Sonar Expectations") still applies and is enforced by review, and NFR-003 independently
  requires the new unit tests regardless of any coverage percentage.
- **`mypy --strict`** — confirmed absent from every `.github/workflows/*.yml` file
  (`grep -rl mypy .github/workflows/` returns nothing). It is local discipline per
  CLAUDE.md/the charter's Technical Standards section, not a CI gate. New code in this mission
  should still be written to type-check cleanly under local `mypy --strict` as a matter of
  discipline, but a red local `mypy` run does not block this PR in CI.
- **`terminology guard`** (`tests/architectural/test_no_legacy_terminology.py`) — scoped to
  `src/charter/offering/` and user-facing prose; this mission touches neither.
- **`commit-msg` job** (`ci-router.yml`) — present and runs unconditionally on every PR, but as
  currently authored its only step is `git log --format=%s origin/<base>..HEAD || true`, which
  cannot fail regardless of commit message content (verified directly; the `|| true` makes the
  step vacuous). This is pre-existing drift, out of scope for this mission to fix; noted here so
  a reviewer does not mistake "the commit-msg job stayed green" for evidence of enforced commit
  message linting.
- **Standalone Bandit / pip-audit CI jobs** — searched `.github/workflows/*.yml` for `bandit` and
  `pip-audit`/`pip_audit`; no matching job found. Both are listed as dev dependencies in
  `pyproject.toml`, and Bandit's ruleset is already folded into `ruff check .` via the `S` rule
  family (`pyproject.toml`: `"S", # bandit security checks (≈ Sonar S2083)`), which is covered
  above. If either tool runs as an externally-configured required status check (the same pattern
  `protect-main.yml` documents for `clean-install-verification`, and SonarCloud uses), it is
  outside this checkout's visibility; NFR-002/C-004 (no new dependency, `uv.lock` untouched)
  makes a pip-audit finding structurally impossible from this diff regardless.

## Architecture Seam and File Placement (§2a.1)

**Seam**: `scripts/ci/**` + `.github/workflows/**` — this is CI-infrastructure tooling, not the
kernel/charter/glossary/runtime/mission_runtime/specify_cli product-code trio described in
CLAUDE.md's "Modularity SSOT" section, and not doctrine (`packs/`). It has its own dedicated test
tree (`tests/ci/`) and its own CI-router filter group (`ci`), confirmed above. No product-code
seam is touched by this mission.

**New/changed files and exact placement**:

1. **`scripts/ci/reconcile_retry.py`** (new) — a generic, stdlib-only bounded retry-with-backoff
   primitive shared by all three retrying call sites. Not GitHub-specific; takes an
   `attempt: Callable[[], T | None]` callable and returns the stabilized result or `None` on
   budget exhaustion. See "User Story 2" and "User Story 3" sections below for its exact shape
   and the FR-008 rationale for this placement over a fleet-verdict-only helper or three
   hand-copied loops.
2. **`scripts/ci/wait_for_artifacts.py`** (new, FR-005) — the artefact-visibility polling
   step/script. Chosen over inline YAML/bash polling and a third-party Marketplace retry Action,
   per FR-005's own framing, weighed as follows:
   - *Inline YAML/bash polling*: rejected — not independently pytest-mockable without shelling
     out to a real `gh api` call inside the test, which is exactly the untested-inline-shell
     pattern `reconcile_shards.py`'s own module docstring says shipped broken once already
     (`scripts/ci/reconcile_shards.py`'s docstring: "Extracted from the inline `ci-aggregate.yml`
     ... step ... the reason it shipped broken"). Repeating that pattern here would be ironic
     given the mission this file is part of.
   - *Third-party Marketplace retry Action*: rejected — adds a new supply-chain dependency this
     mission has no need for (NFR-002/C-004 already forbid new *Python* dependencies for the
     retry logic itself; while a Marketplace Action is not a `uv.lock` dependency, it is still a
     new pinned external trust surface this repo's SHA-pinning discipline (`DIR-051`, visible
     throughout `ci-aggregate.yml`) would have to onboard and maintain for no benefit over an
     in-repo script), and it is not natively pytest-mockable against this repo's own
     `GitHub`/`GitHubCLI` boundary.
   - *An in-repo, importable Python script under `scripts/ci/`* (chosen): mirrors the existing
     pattern of every other `scripts/ci/*.py` module (`source_eligibility.py`,
     `select_source_artifacts.py`, `aggregate_source.py`) — a pure decision core plus a thin CLI
     edge that reads trusted-checkout state and emits `$GITHUB_OUTPUT` lines, unit-tested directly
     with mocked GitHub API responses (mirroring the `GitHub`/`GitHubCLI` class boundary already
     defined in `fleet_verdict.py` and already imported/reused by `fleet_main.py`). This directly
     satisfies NFR-002/NFR-003(3)'s "pytest-mockable and stdlib-only" outcome requirement, is the
     path of least architectural novelty, and reuses `reconcile_shards.py`'s own exported
     `parse_registry`/`read_selected_modules` to avoid a second shard-naming authority.
3. **`scripts/ci/fleet_verdict.py`** (modified) — `report()`'s existing snapshot→dedupe→re-snapshot→
   compare→publish body is extracted into a private `_attempt(...)` helper returning a tri-state
   outcome (already-reported / ready-to-publish / unstable), then wrapped by
   `reconcile_retry.retry_with_backoff`. No change to `snapshot()`, `classify()`, `comment_body()`,
   or any other existing public function's signature or behavior.
4. **`scripts/ci/fleet_main.py`** (modified) — extends (3)'s tri-state shape with a fourth
   outcome, `_NothingToReport()`, for the pre-existing `elif evidence["state"] != "red"` early
   return (informational print, no publish — distinct from `_AlreadyReported()`, `_Ready(...)`,
   and the retry-triggering `None`); see the "`fleet_main.py::report()` rewiring" paragraph
   below and `tasks/WP02-fleet-verdict-fleet-main-retry.md` for the four-state contract and its
   boundary discussion. Otherwise imports `retry_with_backoff` from `reconcile_retry` alongside
   its existing imports from `fleet_verdict`.
5. **`.github/workflows/ci-aggregate.yml`** (modified) — (a) move the existing "Download the
   triggering run's selected-module set" step earlier in the `collect` job (from after
   `download-previous` to immediately after `select-current`), and (b) add a new step
   ("Wait for selected shard artefact visibility") between it and "Download the triggering run's
   shard artefacts", invoking `python3 scripts/ci/wait_for_artifacts.py`. See "User Story 3"
   below for exact sequencing and rationale.
6. **`.github/workflows/ci-fleet-verdict.yml`** — **no changes expected**. Its `report`/
   `report-main` jobs already just invoke `fleet_verdict.py`/`fleet_main.py`; the retry now lives
   inside those scripts, so the workflow YAML calling them is unchanged. Listed here only because
   the dispatch named it as a file to read; if implementation discovers a reason to touch it
   (e.g., a timeout budget adjustment), that is a deviation to flag explicitly, not a silent
   extension.
7. **`reconcile_shards.py`** — **unchanged**, both in shape and behavior, per spec.md Key Entities
   item 3 and the architecture-seam finding already decided at spec phase. It gains a new
   *importer* (`wait_for_artifacts.py` reads its pure helper functions) but that is read-only
   reuse, not a modification to the file itself.

## Generated Artifacts (§2a.2)

**Nothing is generated by a code-generation command for this mission.** This is direct
script/workflow-YAML authoring: `scripts/ci/*.py` are hand-written Python modules (no codegen
template renders them), `.github/workflows/*.yml` is hand-edited YAML (no `spec-kitty` command
regenerates workflow files), and `tests/ci/*.py` are hand-written pytest modules. The only
spec-kitty-generated artifacts touched by this mission are the mission's own planning documents
(`plan.md`, the tracer files, later `tasks.md`), produced by the `spec-kitty plan`/`tasks` CLI
commands themselves — those are the framework's own scaffolding, not something this mission's
*fix* generates.

## Contract Movement (§2a.3)

**No contract moves.** This is a CI-script/workflow fix, not a doctrine change:

- No doctrine schema, mission step contract, or action index is touched (`packs/` is untouched).
- No orchestrator-api surface is touched (`src/specify_cli/` product code is untouched).
- No vendored `spec-kitty-events`/`spec-kitty-tracker` package boundary is touched.
- `contracts/artefact-naming.md` as cited by spec.md is **not** a root-level canonical contract in
  this repository — it resolves to `kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/artefact-naming.md`,
  a prior mission's own artifact directory (see `tracer-tooling-friction.md`). This mission does
  not edit that file; the `must_be_fresh` floor it (thinly) documents is preserved unchanged in
  `reconcile_shards.py` itself, which remains the substantive source of truth for that guard.
- The one API surface that *does* gain a new caller is `reconcile_shards.py`'s already-exported
  `parse_registry`/`read_selected_modules` functions (both already in its `__all__`, i.e. already
  a declared public contract of that module) — `wait_for_artifacts.py` becomes a second consumer
  of an existing public contract. No signature change, so no version/compat concern.

## Campsite-Clean Scope (§2a.4)

Per charter Standing Order #2 (DIRECTIVE_025) and the "Reconciling change-scope tensions" section:
smallest-viable-diff picks the file set first, Boy Scout Rule governs cleanup strictly *inside*
that file set, Locality of Change is the brake on growing the file set. Scoped narrowly to the
five files this mission's functional change actually touches:

- **`scripts/ci/fleet_verdict.py`**: no dead code, duplicated literals, or effect-free exception
  handlers found in the surrounding `report()`/`snapshot()` region during this reading — the
  module is already tightly written elsewhere (see e.g. `_http_failure`'s careful redaction,
  `pages()`'s bounded-pagination refusal). **But `snapshot()` measures cyclomatic complexity 24
  (radon grade D), directly inside the touched region** — it is called twice inside `report()`/the
  planned `_attempt()` extraction, i.e. it is the literal double-snapshot body this mission wraps
  in retry. This IS a complexity-15-ceiling violation in the touched region; see the ceiling
  disposition below.
- **`scripts/ci/fleet_main.py`**: same absence of dead code/duplicated-literal/effect-free-handler
  drift, but **two complexity-15-ceiling violations sit directly in the touched region**:
  `snapshot()` measures 22 (radon grade D), and `report()` itself — the exact function this
  mission extracts into `_attempt()` — measures 18 (radon grade C) pre-extraction.
- **`.github/workflows/ci-aggregate.yml`**: the step re-sequencing itself (moving
  "Download ... selected-module set" earlier) is FUNCTIONAL (it is required for the new polling
  step to have selection data available), not a behavior-preserving tidy-up, so it does **not**
  belong in an opening campsite-clean commit — it belongs in the functional commit that adds the
  polling step, with its own clear rationale in the commit message.
- **`reconcile_shards.py`**: unchanged, so nothing to clean.
- **`ci-fleet-verdict.yml`**: unchanged (expected), so nothing to clean.

**Complexity-15-ceiling disposition (Standing Order #2's two allowed outcomes):** three functions
directly inside the touched region exceed the ceiling — `fleet_verdict.py::snapshot()` (24),
`fleet_main.py::snapshot()` (22), and `fleet_main.py::report()` (18, pre-extraction). This mission
does **not** scope an opening decomposition commit for them: `snapshot()` in both files is a
read-only evidence-gathering routine whose signature and behavior spec.md's Key Entities require
to stay unchanged, and decomposing it is a separate, non-trivial refactor disconnected from this
mission's retry-wiring goal (Locality of Change would reject folding it in as an unrelated file
extension). They are instead **frozen as baseline debt**: signature and behavior of `snapshot()`
in both files are unchanged by this mission per spec.md Key Entities; their complexity-15
decomposition is deferred and tracked separately, not silently absorbed into this mission's scope.
`fleet_main.py::report()`'s violation is different — this mission already restructures it (the
extraction into `_attempt()` is required anyway to make it retryable), so it is not left frozen.

**Extraction into `_attempt()` relocates complexity; it does not by itself resolve it.** The
Campsite-Clean Scope originally characterized the `_attempt()` extraction as "itself the
complexity-reducing move," but that is only true for the thin `report()` wrapper left behind —
`_attempt()` inherits most of `report()`'s existing branching (snapshot → dedupe-check →
re-snapshot → compare → publish-decision), so complexity moves to a new name unless the extraction
is done deliberately. This plan sets an explicit decomposition target for the WP that performs the
extraction: `_attempt()` must itself land at or under complexity 15, by further splitting the
evidence-comparison logic (snapshot agreement / disagreement classification) from the
publish-decision logic (what to do with an already-reported vs. ready-to-publish vs. unstable
outcome) into two smaller helpers, rather than moving `report()`'s entire body into `_attempt()`
as one block. The same target applies to `fleet_verdict.py`'s equivalent `_attempt()` extraction.
This converts the "no domain-matched debt was found" language below into an accurate, scoped
statement rather than an unqualified claim contradicted by the measurements above.

**Conclusion: no *opening* campsite-clean commit is needed for this mission** — the one
in-scope, in-touched-region complexity violation this mission can address (`fleet_main.py::report()`,
and `fleet_verdict.py::report()`'s equivalent shape) is addressed by the functional extraction
itself, held to the explicit `_attempt() <= 15` target above; the `snapshot()` violations in both
files are frozen as baseline debt per the disposition above, not "no domain-matched debt found."
One thing to actively watch during implementation, not fix pre-emptively: `fleet_verdict.py::report()`
is already a moderately long function; extracting its body into a private `_attempt()` helper (as
this plan requires anyway, to make it retryable) is the functional change and the tidy-up in the
same edit (Boy Scout Rule inside the touched file set, no added files) — but only counts as
tidy-up if `_attempt()` actually lands under the ceiling, per the target set above.

## Retry Budget Rationale (NFR-001)

Exact attempt counts/backoff are a plan-phase decision per NFR-001; both are picked here with a
stated rationale, not arbitrarily, and remain implement-phase-tunable within these bounds:

- **`fleet_verdict.py`/`fleet_main.py` double-snapshot retry (FR-002/FR-003)**: proposed **4
  attempts total (1 initial + 3 retries), backoff 2s → 4s → 8s (~14s total sleep, ~20s wall-clock
  including two API round-trips per attempt)**. Rationale: the instability this retry targets is
  a PR head or CI-run-list mutating *between* the two snapshot reads inside one job invocation —
  a short-lived race (another push landing, a run transitioning `in_progress` → `completed`
  during the read), not a systemic outage. A short, fast-escalating backoff resolves realistic
  same-invocation raciness while keeping each matrix-fanned-out `report` job (one per PR, per
  `ci-fleet-verdict.yml`'s `strategy.matrix`) fast — this job already has natural retry-by-later-event
  (FR-004), so it should fail fast to that fallback rather than hold the job open a long time.
  Total added wall-clock (≤~20s) is negligible against the job's 15-minute timeout.
- **`wait_for_artifacts.py` artefact-visibility poll (FR-005)**: proposed **8 attempts, backoff
  5s → 10s → 20s → 30s (cap), i.e. 5,10,20,30,30,30,30 between the 8 attempts ≈ 155s (~2.6 min)
  total bounded wait**. Rationale: this is the surface #4675's own comment thread says is
  *worsening* ("fails once, passes on retry no longer reliably holds") — a single retry is
  explicitly insufficient per the spec's own framing, so this budget is deliberately wider than
  the fleet-verdict pair's. **Working hypothesis, not a measured figure** (no GitHub Actions
  documentation citation, incident log, or measurement backs this): GitHub Actions artifact-listing
  propagation lag (the actual race) is assumed to be on the order of single-digit-to-tens-of-seconds
  after upload completion — SC-004's post-merge observation window is what validates or corrects
  this assumption, not this plan. On that assumption, an 8-attempt/~2.6-minute budget covers a
  materially wider window than the "one retry" baseline that is failing today, while staying under
  3 minutes against the `collect` job's 15-minute
  timeout — leaving ample headroom for the job's other steps (checkout, source prep, actual
  download, reconcile). If real post-merge observation (SC-004) shows this budget is still
  insufficient, that is an implement-phase or follow-up tuning input, not a reason to make the
  bound unbounded.

Both budgets are unit-tested for their bound itself (a mocked source that never stabilizes must
still terminate after exactly the stated attempt count, per NFR-001's own testability clause) —
this is independent of whether the *numbers* above survive implement-phase tuning. That generic
proof lives in `test_reconcile_retry.py` (the primitive's own test file, proving termination for
any `max_attempts`) and is **not** by itself sufficient to catch a call-site wiring bug (e.g.
`fleet_main.py` accidentally passing `max_attempts=3`). Each of the three call sites must therefore
independently pin its own wired constant: see the Project Structure / NFR-003 test-plan requirement
below.

## User Story 2 — `fleet_verdict.py` / `fleet_main.py`: retry-then-skip (FR-002/003/004/007/008/009)

**Structural shape**: both surfaces fire from a workflow (`ci-fleet-verdict.yml`) that re-fires
per head on every producer-workflow completion (`workflows: [CI Router, CI Modules, Packs, ...]`),
so "skip and let a later event redo it" is safe here (already the design's existing guarantee;
this mission only removes its externally-visible flake, per the mission's own framing).

**Shared primitive** (`scripts/ci/reconcile_retry.py`, new):

```python
def retry_with_backoff(
    attempt: Callable[[], T | None],
    *,
    max_attempts: int,
    backoff_seconds: Callable[[int], float],
    sleep: Callable[[float], None] = time.sleep,
) -> T | None:
    """Call attempt() up to max_attempts times. attempt() returns None to mean
    "not yet stable/visible, retry"; anything else is returned immediately.
    Sleeps backoff_seconds(i) between attempts (never after the last). Returns
    None if every attempt returned None — the CALLER decides what None means
    (skip-and-defer vs. fail loudly); this primitive makes no such decision.
    """
```

Generic, stdlib-only (`time.sleep` injected as `sleep` so tests never actually wait — this is
what makes NFR-003's "mock the retry window" tests fast and deterministic), and carries no
GitHub-specific or fleet-verdict-specific behavior — reused as-is by `wait_for_artifacts.py`
(User Story 3 below). See `tracer-design-decisions.md` entry 1 for the FR-008-scope judgment call
this generalization represents.

**Compatibility contract (binding, protects the third caller's independence)**: because
`retry_with_backoff` is shared across three call sites with two different terminal behaviors,
`reconcile_retry.py` itself MUST remain fully caller-agnostic going forward — no GitHub-specific
parameters (e.g. a PR-number or run-ID argument), no fleet-verdict-specific terminal-behavior
knobs (e.g. a flag that changes what `None` means), and no optional hooks added for one caller's
convenience. Any GitHub-specific or fleet-verdict-specific need belongs in that caller's own
`attempt()` closure, or a caller-side wrapper around `retry_with_backoff`, never inside
`reconcile_retry.py` itself. This is a constraint on future changes, not just a description of the
current design, so a later reviewer can hold a proposed change to it — it exists specifically to
protect `wait_for_artifacts.py`'s independence from the fleet-verdict pair's future evolution.

**`fleet_verdict.py::report()` rewiring** (FR-002/FR-004/FR-007/C-003):

`report()`'s existing body (snapshot → dedupe-check-against-comments → re-snapshot → compare) is
extracted into a private `_attempt(api, root, number, workflow_ids, replay) -> _Outcome` helper
returning one of: `_AlreadyReported()` (the existing dedupe short-circuit — success, nothing to
publish), `_Ready(body_text)` (snapshots agreed; ready to publish this stabilized evidence), or
`None` (the existing raise condition, converted to "retry" instead of an exception — this is the
FR-007/C-003-mandated change: the *whole* snapshot pair is retried, never partially reused).
`report()` becomes:

```python
outcome = retry_with_backoff(lambda: _attempt(...), max_attempts=4, backoff_seconds=...)
if outcome is None:
    print(f"[ci] deferred @{...}: evidence did not stabilize within retry budget")
    return
if isinstance(outcome, _Ready):
    ... publish outcome.body ...
```

This satisfies FR-002 (bounded retry on disagreement), FR-004 (skip-and-defer exit 0 on
exhaustion, no raise), FR-007/C-003 (retries the whole pair; `_attempt` never catches its own
"changed before publication" condition to fall through to stale data — it converts that exact
condition into `None`, and `None` can only ever trigger a retry-with-fresh-state or a skip, never
a publish using old data). The existing `verify_replay_checkout` / `dry_run` handling is preserved
unchanged around the retry loop (replay is an explicit, exact-revision operator action, not part
of the raciness this mission targets — it is not expected to need retrying, and Acceptance
Scenario reasoning in spec.md does not ask for it).

**`fleet_main.py::report()` rewiring** (FR-003/FR-004/FR-007): identical shape, importing
`retry_with_backoff` from `reconcile_retry` and wrapping its own snapshot→incident-lookup→
re-snapshot→compare body the same way. Its terminal behavior differs from `fleet_verdict.py`'s in
TWO pre-existing ways this mission preserves, not changes.

First, when there is no existing open incident and the (now-stabilized) evidence is not `red`, it
already prints and returns without raising (`elif evidence["state"] != "red": print(text,
end=""); return`). That branch's CONDITION and ACTION are unchanged — same check, same
print-and-return behavior — but it sits structurally inside `_attempt()`'s wrapped body, between
the incident lookup and the second/re-check `snapshot()` call. `evidence` is the variable bound by
`_attempt()`'s own first `snapshot()` call, so it is rebound fresh on every retry attempt by
construction; the `elif` is therefore necessarily re-evaluated on every attempt too, each time
against that attempt's own `evidence`. This is not an optional design choice the retry loop
happens to make — it is forced by `evidence` being rebound per attempt, since a branch cannot be
held "outside" a retry that redefines the variable it tests.

Second, `report()` keeps its own single pre-loop `snapshot()` call and `dry_run` check entirely
OUTSIDE `retry_with_backoff`/`_attempt()` (`scripts/ci/fleet_main.py:99-104`: `evidence =
snapshot(...)`; `text = body(...)`; `if dry_run: print(text, end=""); return`) — `_attempt()` is
never called on a dry run, and when it is called (non-dry-run path), it performs its own fresh
`snapshot()` call(s) per attempt rather than reusing this pre-loop `evidence`. This exists
specifically so `dry_run` stays read-only with no retry sleeps: a dry run short-circuits before
`retry_with_backoff` is ever entered, off a single un-retried snapshot. `fleet_verdict.py`'s
`report()` takes a different shape here — its `dry_run` check sits at the very end, after the
(now-wrapped) snapshot→dedupe→re-snapshot→compare sequence has already run, where it only chooses
print-vs-post for an already-computed `body`, rather than gating entry into the retry-wrapped body
at all.

**FR-009 (no cross-run coupling)**: both `_attempt` closures capture only their own call's local
`api`/`root`/`number`(or head)/`workflow_ids` arguments — no module-level mutable state, no shared
file, no lock. `retry_with_backoff` itself is a pure function with no global state. This is
directly testable (and tested, per NFR-003(4)) by running two `report()` invocations for two
different subjects with interleaved/concurrent mocked instability and asserting neither reads or
mutates the other's `API` test double. This test is committed as part of **WP2's** own red-first
commit sequence (not WP4's — see "Red-First Application Across All NFR-003 Test Surfaces" and the
Constitution Check's C-011 row above for why).

## User Story 3 — `ci-aggregate.yml` artefact-visibility polling (FR-005/006)

**Structural shape**: `ci-aggregate.yml` fires once per non-repeating `workflow_run` event (from
`CI Modules`); there is no later event to defer to, so this surface needs a real bounded wait
*in the workflow*, ahead of `actions/download-artifact`, not a skip — and `reconcile_shards.py::main()`
stays the single, unmodified, fail-closed terminus (Key Entities item 3).

**Why the poller targets only the SELECTED shard set, not the full registry** (judgment call,
`tracer-design-decisions.md` entry 2): `ci-modules.yml`'s diff-scoping deliberately SKIPS
unselected modules' matrix leaves entirely — their coverage artifacts are never produced, ever,
by design (documented in `ci-aggregate.yml`'s own header comment: "an UNSELECTED (unchanged)
module's leaf is SKIPPED, not run"). A poller that waited for the FULL registry set would exhaust
its entire budget on essentially every ordinary diff-scoped PR (since most modules are usually
unselected), adding ~2.6 minutes of pure latency to every CI Aggregate run for zero benefit, and
would make a "budget exhausted" log line indistinguishable between "the real race" and "this PR
just didn't select those modules" — actively harmful to on-call triage, which is the epic's
stated harm in the first place (User Story 1). The poller must therefore know which shards are
SELECTED (must-be-fresh) before it starts polling.

**Sequencing change this requires** — the "Download the triggering run's selected-module set"
step (currently positioned in `ci-aggregate.yml` *after* `download-previous`, i.e. after the
existing download steps this mission's new step must precede) moves earlier, to immediately after
"Select reports from executions retained by the source attempt" (`select-current`). Reordered
`collect` job step sequence:

```
checkout
→ Prepare exact source registry and diff  (unchanged)
→ Upload exact source data                 (unchanged)
→ Resolve run mode                          (unchanged)
→ Select reports from executions ...        (unchanged: select-current)
→ Download the triggering run's selected-module set   (MOVED earlier — was after download-previous)
→ Wait for selected shard artefact visibility          (NEW — FR-005)
→ Download the triggering run's shard artefacts        (unchanged: download-current)
→ Find the most-recent successful "CI Modules" run     (unchanged: last-success)
→ Download the fallback run's shard artefacts          (unchanged: download-previous)
→ Install PyYAML                                        (unchanged)
→ Reconcile shard artefacts by basename                (unchanged: reconcile_shards.py — NOT MODIFIED)
→ Upload reconciled coverage set                        (unchanged)
```

**New step's own `env:` block**: the `collect` job carries no job-level `env:` key (verified by
reading the full job) — every existing `run:` (shell) step in this job that needs `SOURCE_RUN_ID`/
`SOURCE_RUN_ATTEMPT`/`SOURCE_REPOSITORY` re-declares them as a step-local `env:` block (e.g.
`ci-aggregate.yml`'s "Prepare exact source registry and diff" and "Select reports from executions
retained by the source attempt" steps). Both of those cited steps *also* declare a fourth variable,
`GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`, alongside the three `SOURCE_*` ones
(`ci-aggregate.yml:107-112` and `:146-150`, verified directly). The two `uses: actions/download-artifact`
steps that bracket the insertion point (`download-current` at `ci-aggregate.yml:159-169` and
`download-selected-modules` at `:214-222`, verified directly) do **not** follow this pattern: they
consume the same `SOURCE_RUN_ID` value but inline the GitHub Actions expression
`${{ github.event.workflow_run.id || inputs.source_run_id }}` directly into their `with: run-id:`
input, with no `env:` block at all — the normal way an action input is wired, needing no `env:`
indirection the way a `run:` shell script does. The new "Wait for selected shard artefact
visibility" step is itself a `run: python3 scripts/ci/wait_for_artifacts.py ...` (shell) step, not
a `uses:` step, so it must follow the `run:`-step pattern and declare its own step-local `env:`
block. That block must declare **four** variables — `GH_TOKEN`/`SOURCE_RUN_ID`/`SOURCE_RUN_ATTEMPT`/
`SOURCE_REPOSITORY` — not just the three `SOURCE_*` ones: as documented a few lines below, the new
step reuses `fleet_verdict.py`'s `GitHub`/`GitHubCLI` request/`pages()` boundary, and
`GitHub.request()` reads `token = os.environ["GH_TOKEN"]` as a bare subscript
(`scripts/ci/fleet_verdict.py:142`), which raises `KeyError` if the variable is absent — there is no
fallback or degraded path. None of these four variables is available from anywhere else in the
job — the job carries no job-level `env:` key, and the `uses:`-step inlining pattern does not apply
to a `run:` step — so all four must be declared in this step's own `env:` block.

**`scripts/ci/wait_for_artifacts.py` (new)** — pure decision core + thin CLI edge, mirroring the
existing `source_eligibility.py`/`select_source_artifacts.py` shape:

- Reads the already-checked-out `.github/ci-module-registry.yml` via `reconcile_shards.py.parse_registry`
  (imported, not re-derived) and the already-downloaded `out/aggregate/selected/selected-modules.json`
  via `reconcile_shards.py.read_selected_modules` (imported) to compute the must-be-fresh
  `RegistryShard` set — the exact same predicate `reconcile_shards.py::reconcile()` will apply
  later in the same job, computed once and reused, not redefined.
- Computes each must-be-fresh shard's expected GitHub Actions **artifact name** using the same
  regex `select_source_artifacts.py` already defines and matches against
  (`module-tests-{module}-shard-{n}-of-{count}-attempt-{attempt}-reports`, imported/reused, not
  reimplemented) — `attempt` allows any value `<= SOURCE_RUN_ATTEMPT`, matching
  `select_source_artifacts.py`'s own carried-forward-attempt tolerance.
- Polls `GET actions/runs/{SOURCE_RUN_ID}/artifacts` (paginated, via the same `GitHub`/`GitHubCLI`
  request/`pages()` boundary already defined in `fleet_verdict.py`, imported here as its third
  consumer) through `reconcile_retry.retry_with_backoff`, with `attempt()` returning the found
  artifact-name set once every expected name is present, or `None` otherwise.
- **On budget exhaustion, exits 0 regardless** (never raises, never sets a failing exit code) and
  prints a diagnostic naming which expected shard artifacts were still not visible — the workflow
  falls through unconditionally to the existing `actions/download-artifact` steps, which download
  whatever is actually available; `reconcile_shards.py::main()` then applies its own unchanged,
  already-tested fail-closed guard against whatever that turns out to be (FR-006). This is the
  key architectural point repeated from the spec: the poller widens the window, it does not decide
  completeness — deciding completeness stays `reconcile_shards.py`'s job alone, unconditionally,
  every time.

**Acceptance Scenario 2 (spec.md US3, exhausted budget) is satisfied by construction**: because
`wait_for_artifacts.py` never touches exit code or `reconcile_shards.py`, and `reconcile_shards.py`
is provably unmodified by this mission's diff, its existing `::error::ci-aggregate: ... refusing
to silently treat this run as complete ...` annotation and non-zero exit are structurally
unreachable to regress from this change.

## Safety Invariants — explicit preservation statement

- **Invariant (a)** (never post from stale snapshot, FR-007/C-003): preserved by construction —
  `_attempt()`'s "changed before publication" branch becomes a retry trigger (`None`), never a
  fallback-to-first-snapshot publish. Unit-tested directly (NFR-003(1)/(2)): a mocked `snapshot()`
  sequence that disagrees on attempts 1–2 and agrees on attempt 3 must publish attempt 3's
  evidence, never attempt 1's.
- **Invariant (b)** (`reconcile_shards.py`'s fail-closed floor, FR-006/C-002): preserved by
  construction — the file is not modified by this mission's diff at all. Unit-tested by re-running
  the existing `tests/ci/test_reconcile_shards.py` suite unmodified (SC-003 baseline) plus a new
  integration-style unit test in `tests/ci/test_wait_for_artifacts.py` asserting that when the
  poller exhausts its budget, `reconcile_shards.py::main()` (invoked against whatever directory
  state the test constructs) still exits 1 and still prints the `::error::` line, i.e. the two
  modules' unit tests compose to demonstrate the end-to-end floor without needing a real workflow
  run.

## Red-First Application Across All NFR-003 Test Surfaces

NFR-003's red-first clause ("run against the unmodified surface first, confirm it fails the way
today's code does") is walked through concretely for every required test surface, not only the two
pre-existing tests being re-pinned (see "Existing Test That Must Change" below):

- **`wait_for_artifacts.py`'s new recovery/terminal tests** — there is no pre-fix entry point (the
  module does not exist before this mission), so "red-first through the pre-existing entry point"
  cannot apply literally. Red-first here means: write the new recovery/terminal tests first against
  a stub single-attempt (no-loop) version of the polling function, confirm they fail the way a
  single, unretried poll attempt fails today (a transiently-missing artifact is treated as
  permanently missing), then add `retry_with_backoff` wiring and confirm the same tests pass.
- **FR-009's cross-invocation isolation test** — explicitly **exempted** from red-first: there is
  no pre-fix analog to run red against, because pre-fix code holds no retry state to leak in the
  first place (the isolation property trivially holds before this mission, since there is nothing
  stateful to isolate yet). This is an intentional, named exemption, not an oversight — it is
  stated here so the implement phase does not skip it silently or try to force a red-first run that
  cannot exist. Because this test has no red-first anchor of its own, it is committed as part of
  **WP2's** own red-first commit sequence — alongside WP2's other FR-002/003/004/007 tests, which
  do have valid red-first anchors (see "Existing Test That Must Change" and the new-retry-test
  bullet above) — rather than left as a standalone test obligation for WP4. This is how the plan
  resolves this exemption against the new ATDD-First Discipline (C-011) row in the Constitution
  Check table above: WP4 is re-scoped to carry no new-code test obligation at all (see "Parallel
  Work Analysis / Dependency Graph" below).
- **The NEW (non-re-pinned) recovery-path tests inside `test_fleet_verdict.py`/`test_fleet_main.py`**
  — distinct from the one existing test each file re-pins (below), these are brand-new tests
  exercising the retry-then-publish and retry-then-skip paths. They are run red-first against the
  *unmodified* `report()` (i.e. before `_attempt()`/`retry_with_backoff` wiring lands), where they
  are expected to fail the old way — an unretried `ValueError` raise on the first snapshot
  disagreement — then confirmed green once the retry wrapper is in place.

## Existing Test That Must Change, and Why That Is Not a Regression

`tests/ci/test_fleet_verdict.py::test_publication_rechecks_head_and_never_mutates_existing_comments`
currently asserts `report()` **raises** `ValueError(match="changed before publication")` when the
PR head moves between the two snapshot reads. That assertion targets exactly the pre-fix behavior
this mission changes (raise → retry → skip-on-exhaustion). Per charter Standing Order #4 ("judge
the test, not git-blame... stale → re-pin"), this is a **stale assertion of the behavior under
repair**, not a valid regression guard to preserve as-is: it must be updated to assert the new
contract (no raise; either eventual publish of stabilized evidence, or a silent skip with the
FR-004 diagnostic line, depending on how the test's mock is shaped) as part of this mission's
functional commit, not left red or deleted. NFR-003's red-first clause is satisfied here in the
inverse direction from a brand-new test: this *existing* test already fails-the-old-way today by
design; the implement phase's job is to re-pin it to the new contract and confirm the new retry
code makes it pass, not to leave it asserting behavior the mission is explicitly removing. The
equivalent `fleet_main.py` test (`test_attempt_change_during_publication_refuses_stale_verdict`)
needs the identical re-pinning treatment, but not necessarily the identical *outcome* shape:
unlike `fleet_verdict.py`'s tri-state contract (where this section's "publish, or FR-004 skip"
framing above is exhaustive), `fleet_main.py::_attempt()` is four-state (see the
"`fleet_main.py::report()` rewiring" paragraph above and WP02's four-state contract), so this
test's re-pin may land in a third, non-retried `_NothingToReport()` terminal path
(informational print, no publish, no FR-004 diagnostic — the pre-existing not-red early
return) instead of either "publish" or "FR-004 skip." This section's binary framing above
describes `fleet_verdict.py`'s re-pin only; WP02 traces which of the three paths
`fleet_main.py`'s actual mock behavior lands in. Flagged explicitly here so a reviewer does not
mistake an edited assertion in these two pre-existing tests for weakened coverage — the
replacement assertions must still prove invariant (a) holds (see previous section), just
against the new retry contract instead of the old immediate-raise contract, whichever of the
three terminal paths each re-pinned test's traced mock behavior actually lands in.

## Project Structure

### Documentation (this mission)

```
kitty-specs/reconcile-flake-family-01M34HR7/
├── plan.md                          # This file
├── tracer-tooling-friction.md       # Seeded this phase
├── tracer-approach.md               # Seeded this phase
├── tracer-design-decisions.md       # Seeded this phase
└── tasks.md                         # Phase 2 output (spec-kitty tasks — not created by plan)
```

No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` are produced by this plan:
there is no unresolved technical unknown left after reading the actual code (no "Phase 0 research"
question remains open), no new data model (Key Entities: "not applicable"), and no new API
contract is introduced (Contract Movement section above: none moves). Producing empty placeholder
files for these would be process theater, not phase output — omitted deliberately.

### Source Code (repository root)

```
scripts/ci/
├── reconcile_retry.py      # NEW — generic bounded retry/backoff primitive (stdlib-only)
├── wait_for_artifacts.py   # NEW — FR-005 artefact-visibility polling step/script
├── fleet_verdict.py        # MODIFIED — report() retries via reconcile_retry
├── fleet_main.py           # MODIFIED — report() retries via reconcile_retry
└── reconcile_shards.py     # UNCHANGED — imported from (parse_registry, read_selected_modules)

.github/workflows/
├── ci-aggregate.yml        # MODIFIED — step reorder + new polling step
└── ci-fleet-verdict.yml    # UNCHANGED (expected)

tests/ci/
├── test_reconcile_retry.py      # NEW — the shared primitive's own unit tests
├── test_wait_for_artifacts.py   # NEW — FR-005/006 mocked-GH-artifacts-API tests
├── test_fleet_verdict.py        # MODIFIED — new retry tests + one re-pinned existing test
└── test_fleet_main.py           # MODIFIED — new retry tests + one re-pinned existing test
```

**NFR-003 exact-attempt-count requirement (per call site, not only the shared primitive)**: beyond
`test_reconcile_retry.py`'s generic termination proof (any `max_attempts`), each of
`test_fleet_verdict.py`, `test_fleet_main.py`, and `test_wait_for_artifacts.py` MUST additionally
assert the mock's exact call count at that call site's exhausted-budget path — e.g.
`assert mock_snapshot.call_count == 4` (or the equivalent attempt-counting assertion) for the
`fleet_verdict.py`/`fleet_main.py` pair, `== 8` for `wait_for_artifacts.py`'s artifact poller. This
pins this plan's stated budget numbers (Retry Budget Rationale, NFR-001) at each site where they
are actually wired, catching a call-site wiring bug (e.g. an accidental `max_attempts=3`) that the
shared primitive's own generic test cannot see.

**Structure Decision**: Single project, `scripts/ci/` seam (see "Architecture Seam" above). This
is the entire structure; no `src/`, `backend/`, `frontend/`, `ios/`, or `android/` options from the
template apply, and are omitted rather than left as dead placeholders.

## Complexity Tracking

*No Constitution/Charter Check violations were found (see table above); this table is
intentionally left empty per the template's own instruction.*

## Parallel Work Analysis

### Dependency Graph

```
WP1: scripts/ci/reconcile_retry.py + tests/ci/test_reconcile_retry.py
     (the shared primitive; both other waves import it)
        │
        ├────────────────────────────────────┐
        ▼                                    ▼
WP2: fleet_verdict.py + fleet_main.py         WP3: wait_for_artifacts.py +
     retry wiring + their tests                    ci-aggregate.yml step reorder/add +
     (FR-002/003/004/007/009 — includes            its tests (FR-005/006)
     FR-009's cross-invocation isolation
     test, committed inside WP2's own
     red-first commit sequence; see
     "Red-First Application" above)
        │                                    │
        └──────────────────┬──────────────────┘
                            ▼
WP4: final tracer-file append + SC-001/SC-002/SC-003 full-suite re-run.
     Pure integration/verification — introduces NO new functional code and
     carries no test of its own, so charter C-011's per-WP red-first-commit
     requirement does not apply to it (see Constitution Check above).
```

### Work Distribution

- **Sequential work**: WP1 must land first (or at minimum its interface must be fixed) before WP2
  and WP3 can import it. WP4 depends on both WP2 and WP3 completing — it runs the full-suite
  re-run (which needs all WPs' code present to be meaningful) and appends the closing tracer
  entries. WP4 is a pure integration/verification WP, not a new-code WP: it carries no test of its
  own (FR-009's cross-invocation isolation test now lives inside WP2's own commit sequence — see
  the re-scoping in the Dependency Graph above and the Constitution Check's C-011 row).
- **Parallel streams**: WP2 and WP3 touch fully disjoint files (`fleet_verdict.py`/`fleet_main.py`/
  their tests vs. `wait_for_artifacts.py`/`ci-aggregate.yml`/its tests) and can run concurrently
  once WP1's `retry_with_backoff` signature is fixed.
- **Agent assignments**: left to the tasks phase / implement-phase orchestrator to bind to actual
  WP IDs; this plan only establishes that WP2/WP3 are safely parallelizable and WP1/WP4 are not.

### Coordination Points

- **Sync schedule**: WP2 and WP3 both re-run `tests/ci/test_reconcile_retry.py` (WP1's own tests)
  as part of their own validation before integrating, per the repo's blast-radius test policy.
- **Integration tests**: FR-009's cross-invocation isolation test — committed inside WP2's own
  red-first commit sequence, not WP4's (see the Dependency Graph re-scoping above) — is the
  integration point that proves WP2's two surfaces (fleet_verdict/fleet_main) don't share state.
  WP4's own integration step is the full-suite re-run (SC-001/SC-002/SC-003), which verifies that
  WP1–WP3's work composes correctly.

## PR Shape (§2a.6)

**Default: one PR for this mission**, per the mission's default posture and per the dispatch's
explicit instruction. Total footprint is bounded and estimable now: 2 new small modules
(`reconcile_retry.py` estimated ~30–50 lines; `wait_for_artifacts.py` estimated ~80–120 lines
following the existing `source_eligibility.py`/`select_source_artifacts.py` shape), 2 modified
functions (`fleet_verdict.py::report()`, `fleet_main.py::report()` — extraction + wrapping, not a
rewrite), one workflow-YAML re-sequencing + one new step, and test additions in `tests/ci/`
following existing patterns in the same files. This plan's assessment is that ONE reviewable PR is
realistic and appropriate for this scope — but per the dispatch's instruction, if implementation
reveals the diff is larger or more review-heavy than this estimate (e.g. the `wait_for_artifacts.py`
artifact-name-matching logic proves more involved than expected), **that determination is flagged
for the orchestrator/operator to decide on splitting — it is not decided unilaterally here or by
the implement phase.**

## Deviations, Blockers, and Judgment Calls for Reviewers (summary)

1. **FR-008's shared-helper decision is generalized beyond its literal framing**: a single
   `reconcile_retry.py` primitive is shared by all three retrying surfaces, not just the
   `fleet_verdict.py`/`fleet_main.py` pair FR-008 names. Rationale in "User Story 2" above and
   `tracer-design-decisions.md` entry 1. Reviewers should confirm this generalization is welcome,
   not scope creep.
2. **`ci-aggregate.yml`'s "Download ... selected-module set" step must be re-sequenced**, not just
   have a new step inserted next to it — a real reordering of existing steps, justified in "User
   Story 3" above and `tracer-design-decisions.md` entry 2 (polling the full registry would waste
   the entire budget on every diff-scoped PR). Reviewers should confirm this reordering has no
   other dependency this plan missed (e.g. whether any later step implicitly relies on the
   selected-module-set download happening after `download-previous` — this plan's reading of the
   job found no such dependency, but the implement phase should re-verify against the live file
   before merging the reorder).
3. **Two pre-existing tests must be edited, not just extended** — `test_fleet_verdict.py`'s and
   `test_fleet_main.py`'s "publication rechecks head" tests assert the exact pre-fix raise
   behavior this mission removes. See "Existing Test That Must Change" above for the full
   rationale; flagged so review does not read an edited assertion in those two tests as weakened
   coverage.
4. **`contracts/artefact-naming.md` as cited in spec.md does not exist at that path** in this
   repository; it resolves to a prior mission's own `kitty-specs/.../contracts/` directory whose
   relevant section is a one-line stub. This plan does not fix that (out of scope; a
   doctrine/tooling gap, not a defect in the code under fix), but flags it so a reviewer checking
   the spec's citation does not lose time on a broken repo-root-relative path.
5. **Exact retry-budget numbers (4 attempts/~20s for the fleet-verdict pair; 8 attempts/~155s for
   the artefact poller) are this plan's proposal with a stated rationale, not the spec's own
   numbers** (the spec deliberately leaves exact counts to the plan phase, per NFR-001). Reviewers
   should sanity-check these against the job timeout budgets cited above and adjust at implement
   time if real observed GitHub Actions artifact-propagation latency (SC-004's post-merge watch)
   suggests otherwise.
6. **WP4 was re-scoped in this revision to resolve a charter C-011 contradiction the prior review
   round flagged**: FR-009's cross-invocation isolation test — originally WP4's only test content —
   now lives inside WP2's own red-first commit sequence, alongside WP2's other FR-002/003/004/007
   tests (which do have valid red-first anchors, unlike FR-009's test — see "Red-First Application"
   above). With that test moved out, WP4 is re-scoped to a pure integration/verification WP: the
   final tracer-file append plus the SC-001/SC-002/SC-003 full-suite re-run, introducing no new
   functional code and carrying no test of its own. Rationale: charter C-011 requires each WP that
   introduces new functional code to open with a failing-test-only commit that is RED on
   `planning_base_branch`; FR-009's isolation test has no such red anchor (there is no pre-fix retry
   state to leak, so the property trivially holds before this mission), so a WP built only around
   that test could not satisfy C-011 on its own terms. Moving the test into WP2 (which does have
   red-first anchors) and re-scoping WP4 to carry zero test obligations means C-011's per-WP
   failing-first-commit requirement does not apply to WP4 at all, rather than being satisfied by it
   vacuously. See the Constitution Check's C-011 row and the "Parallel Work Analysis / Dependency
   Graph" section above for the detail.
