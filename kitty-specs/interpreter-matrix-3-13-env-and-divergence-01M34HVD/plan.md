# Implementation Plan: interpreter-matrix 3.13 leg: env resolution and real 3.13 divergence

**Branch**: `issue-4866-interpreter-matrix-3-13` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See
`packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the
execution workflow. (The scaffold `.venv/bin/spec-kitty plan --json`
produced for this mission used a stale template shape — see "Tooling drift
flagged" at the end of this document; this plan is authored against the
current canonical template at
`packs/built-in/missions/software-dev/templates/plan-template.md`.)

## Summary

Issue #4866: the nightly `interpreter-matrix` job's `uv run` step silently
discards the preceding `uv sync --python 3.13 --all-extras`, re-syncing to
`.python-version`'s 3.11.15 with default extras on every invocation, so the
leg has reported a confident-looking but entirely wrong red for 7
consecutive nights. Per operator decisions Q1=B and Q2=B (spec
Clarifications), this mission (a) pins interpreter/extras on the `uv run`
step itself (FR-001), (b) fixes the 4 confirmed `dir_fd`-related kernel
test-double failures that block the leg's first *genuine* 3.13 run (FR-002),
(c) root-causes or timeboxes-and-falls-back a shared-`.venv` mid-run
corruption hazard under `-n auto` (FR-003), (d) re-measures the 3.13 `fast
or unit` selector against a now-stable environment (FR-004), (e) discharges
the charter's Pre-existing Failure Reporting Rule for the 21 pre-existing
3.11 failures (FR-005), and (f) states an explicit, evidenced disposition
for any residual red the leg still reports at close (FR-006). This is a
CI-workflow + test-infrastructure fix, not a product-code change; the leg
may legitimately still report red when this mission closes (Edge Case (c)),
and that is honest signal, not mission failure.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor, unchanged). The mission's
subject matter spans two interpreters: 3.11 (the `.python-version` floor,
untouched behaviourally) and 3.13 (the nightly leg's actual target,
currently mis-pinned). No source-language version requirement changes.

**Primary Dependencies**: `uv` 0.11.28 (pinned in this checkout; CI installs
it via `astral-sh/setup-uv@20cfd1bf9` / advertised as `v10.0.1`), `pytest`
+ `pytest-xdist` (`-n auto`), `PyYAML` (already imported by
`scripts/ci/gate_selection.py`; reused for the new FR-001 YAML-parsing
test — no new dependency), GitHub Actions (`ci-nightly.yml`'s
`interpreter-matrix` job), the `gh` CLI (manual `workflow_dispatch`).

**Storage**: N/A — no persistent data model; this mission edits a CI
workflow definition and Python test fixtures/doubles (see spec.md's Key
Entities section, which already states this explicitly).

**Testing**: `pytest`, `fast`/`unit` markers, `pytest-xdist -n auto`. One new
unit test file under `tests/ci/` (YAML-parsing, no workflow execution). The
existing kernel/core test doubles under `tests/kernel/` and
`tests/specify_cli/core/` are the FR-002 fix target themselves.

**Target Platform**: GitHub Actions `ubuntu-latest` runner (the nightly
leg's real execution environment) + local Linux dev checkout (verification,
since `ci-nightly.yml` gives this PR no CI safety net — see "Verification
route" below).

**Project Type**: Single project — CI-workflow-and-test-infrastructure fix,
not a product feature. There is no frontend/backend or mobile/API split to
choose between; the "Option 1/2/3" structure below reflects that.

**Performance Goals**: N/A in the product-feature sense. NFR-001 bounds
*verification* runtime instead: every `fast or unit` / `-n auto` run in this
mission's plan/tasks/implementation carries an explicit, bounded timeout
comfortably above the readiness report's measured ~411s (3.13) / ~485s
(3.11) baseline, run in the foreground (SK-99 — Claude subagents
auto-background and strand at 120s; see
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md`).

**Constraints**: C-001 (blast radius: `ci-nightly.yml`'s
`interpreter-matrix` job + the three named kernel/core test-double files +
whatever FR-003 names), C-002 (does not expand into #3189's scope), C-003
(no CI safety net for the workflow-file diff), C-004 (ATDD-first applies,
including to the workflow-YAML fix), NFR-001 (bounded verification
runtime), NFR-002 (no new silent-success path), NFR-003 (cross-interpreter
neutrality of the kernel-shim fix).

**Scale/Scope**: 1 CI workflow job (`interpreter-matrix` in
`ci-nightly.yml`), 3 named kernel/core test-double files, 0–1 additional
call-site file named by the FR-003 investigation (or, if the timebox is
exhausted or the call site is under `src/`, a `UV_PROJECT_ENVIRONMENT`
pin added to the same workflow job plus one regression test), 1 new test
file (`tests/ci/`), up to 2 new GitHub issues (the FR-005 pre-existing-
failure report; a venv-corruption follow-up issue if the FR-003 fallback is
taken), 1 comment/cross-link on #3189 (FR-006 disposition).

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Walked against `.kittify/charter/charter.md` directly (not a generic
checklist):

- **Single canonical authority** — PASS. This mission does not add a second
  authority for anything; the `uv run` flags fix reconciles the run step
  with the sync step's existing, already-canonical flags rather than
  inventing a new pinning mechanism.
- **Architectural alignment / shared-package boundaries** — N/A. No
  `src/kernel/`, `src/charter/`, `src/runtime/`, `src/mission_runtime/`, or
  `src/specify_cli/` production code changes are in scope (C-001); if
  FR-003 ultimately names a `src/` call site, Edge Case (a) explicitly
  forbids fixing it here — see "The venv-corruption spike" below.
- **Doctrine pack tiers (`built-in` vs `internal`)** — N/A. No
  `packs/built-in/` or `packs/internal/` doctrine artifact is touched.
- **ATDD-first (binding, C-011)** — APPLIES, addressed concretely below
  ("ATDD-First").
- **Glossary & terminology adherence** — N/A. No `Mission`/`Feature`
  terminology surface, no `docs/context/` glossary edit.
- **Standing Order 2 (campsite cleaning)** — addressed explicitly below
  ("Campsite-clean scope"); conclusion: not warranted here, with a stated
  reason.
- **Standing Order 3 (mission tracer files)** — three tracer files already
  seeded at spec authoring; appended during this plan-authoring pass (see
  end of this document) and again during implementation per the
  `mission-tracer-files` procedure.
- **Standing Order 4 (test remediation & bug-fix discipline)** — the 4
  `dir_fd` kernel failures are classified as a **stale test double**, not a
  product defect: 3.13's `shutil.rmtree` legitimately changed to use
  `os.open(..., dir_fd=...)`; the shim didn't model the new kwarg. Fixed at
  the test-double level (FR-002), never by relaxing the underlying
  assertion.
- **Standing Order 6 (canonical sources)** — the plan scaffold this mission
  produced via `.venv/bin/spec-kitty plan --json` did NOT match the
  checkout's own canonical `packs/built-in/missions/software-dev/templates/plan-template.md`
  (stale doc-note path, "Constitution Check" instead of "Charter Check",
  "Parallel Work Organization" instead of "Implementation Concern Map").
  Verified live, the cause is this checkout's own stale, git-tracked
  project-tier override at `.kittify/overrides/missions/software-dev/
  templates/plan-template.md` (last touched 2026-04-17) — OVERRIDE is the
  documented highest-priority template-resolution tier, so the `plan`
  command correctly picked it up ahead of the canonical template (updated
  2026-08-15); this is not a `plan`-command defect (see "Tooling drift
  flagged" at the end for the full diagnosis). Per AGENTS.md's "Use
  Canonical Sources, Never Improvise", this plan is authored against the
  current canonical template rather than the stale override output, and
  the drift is flagged rather than silently worked around.
- **Standing Order 7 (git & workflow discipline)** — PRs only; the
  programme merge agent merges (never this mission's own agents). One
  topic branch (`issue-4866-interpreter-matrix-3-13`), already checked out,
  targets `main`.
- **Standing Order 9 (red-main & release discipline)** — the leg may
  legitimately still report red at mission close if genuine, tracked (per
  #3189) 3.13 divergence remains beyond the 4 fixed `dir_fd` failures; that
  is honest signal per Standing Order 9, not a mission failure, *provided*
  the FR-006 disposition has happened (addressed below).
- **Pre-existing Failure Reporting Rule** — addressed explicitly below
  ("The baseline").
- **ATDD-First Discipline (C-011)** — addressed explicitly below.
- **Tracker Ticket Assignment Rule** — #4866 is expected to already be
  assigned to the Human-in-Charge per this rule; not re-verified here (out
  of this plan's scope, but flagged as a pre-condition the implementer
  should confirm at claim time if not already done).

No charter violation requires a Complexity Tracking entry (see below).

## Project Structure

### Documentation (this mission)

```
kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/
├── plan.md              # This file
├── spec.md              # Already authored, 3-round-adversarial-squad-passed
├── tracer-tooling-friction.md   # Seeded; appended during plan authoring
├── tracer-approach.md           # Seeded; appended during plan authoring
├── tracer-design-decisions.md   # Seeded; appended during plan authoring
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT this phase)
```

No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` are
warranted for this mission — there is no data model (see Technical Context
→ Storage) and no new API/contract surface (see "Contracts" below). If
`/spec-kitty.tasks` insists on scaffolding these, they should stay empty or
explicitly state N/A rather than invent content.

### Source Code (repository root)

**Seam.** This change lands on:

- `.github/workflows/ci-nightly.yml` — specifically the `interpreter-matrix`
  job (currently lines ~174–241), its `uv run` step's `run:` string, and
  (only if the FR-003 fallback is taken) that same job's environment
  (`UV_PROJECT_ENVIRONMENT` pin).
- `tests/kernel/test_lock_parity.py` — `_WindowsMandatoryLockSimulator.wrap_open`'s
  `_open` shim.
- `tests/kernel/test_no_follow.py` and `tests/specify_cli/core/test_no_follow.py`
  — the `plant_symlink` monkeypatch shim (two independent copies, both
  non-parametrized `test_read_rejects_symlink_planted_before_open`).
- Whatever call site FR-003's bounded investigation names — per Edge Case
  (a), this is *expected* to be a test/fixture under `tests/` (most likely
  `tests/upgrade/`, `tests/specify_cli/upgrade/`, or a skill-installer test
  module — the readiness report's own suspicion). **If the named call site
  is under `src/` instead, it is explicitly NOT fixed in this mission** —
  treated identically to a timebox-exhausted finding: apply the
  `UV_PROJECT_ENVIRONMENT` fallback mitigation and file the `src/` call
  site as a follow-up issue, cross-linked from this mission's PR.
- One new test file, `tests/ci/test_interpreter_matrix_env_pinning.py`
  (FR-001's ATDD pin), and — only if FR-003's fallback branch is taken — a
  new test added to `tests/upgrade/test_migration_robustness.py` (FR-003(b)'s
  regression check; see "The venv-corruption spike" for why that module was
  chosen over a step alongside the `ci-nightly.yml` change itself).

No `src/kernel/`, `src/charter/`, `src/runtime/`, `src/mission_runtime/`, or
`src/specify_cli/` file is expected to change. This is not a
single/web/mobile product-structure decision in the template's sense — the
"Option 1/2/3" placeholders below do not apply and are removed rather than
filled in.

**Generated artifacts.** None move. This mission does not regenerate the
doctrine pack manifest (`spec-kitty doctrine regenerate-graph`), does not
touch the Contextive glossary corpus, and does not refresh any of the 17
agent-command copies (`.claude/`, `.codex/`, `.agents/skills/`, etc.) — it
is a workflow-YAML + test-fixture change with no doctrine-artifact or
agent-template surface in its blast radius.

**Contracts.** None move. No doctrine schema, mission step contract, action
index, orchestrator-api surface, or `spec-kitty-events` / `spec-kitty-tracker`
package change is in scope. `Canonical Sources` in spec.md already verified
this against the live checkout (`packs/built-in/agent_profiles/`,
`packs/built-in/missions/mission-steps/` exist and are unrelated); this plan
re-confirms it at the plan-authoring layer rather than re-deriving it.

**Structure Decision**: single project, CI-workflow + test-fixture fix. The
directories named under "Seam" above are the complete, final touched-file
set (modulo the one FR-003-named call site).

## The gate set for this mission

Verified live against this checkout's `.github/workflows/*.yml`,
`scripts/ci/gate_selection.py`, `.github/ci-module-registry.yml`, and
`docs/configuration/linting-cutoff-policy.md` — not assumed from the gate
names alone, because two of them turned out to disagree with what the live
code does (flagged below).

| Gate | Enforced here? | Reasoning |
|---|---|---|
| **commitlint** | **Not enforced (blocking).** | `ci-router.yml`'s `commit-msg` job only runs `git log --format=%s ... \|\| true` — it does not invoke `commitlint` at all in this checkout's live workflow. `docs/configuration/linting-cutoff-policy.md` separately documents commitlint as running but only in "informational mode" (`continue-on-error`, PR-comment-only). Either way it cannot block this PR. This mission still runs `npx --no-install commitlint --from main --to HEAD` locally before PR-prep per this mission's own tracer file (SK-64: this mission's scaffold commit and any `tasks(...)`/`analyze(...)`-typed commit will fail commitlint's `type-enum` list — a known, unrelated tooling gap, not something to fix in-mission). |
| **markdown lint on changed `.md`** | **Not enforced (blocking).** | `ci-router.yml`'s `markdownlint` job runs `npx --yes markdownlint-cli2 "**/*.md" \|\| true` — the trailing `\|\| true` makes the step (and therefore the job, and therefore `router-gate`'s dependency on it) always succeed regardless of findings. Confirmed informational-only by `docs/configuration/linting-cutoff-policy.md` too. This mission's own `.md` edits (spec.md/plan.md/tasks) carry no blocking risk. |
| **Architecture/docs consistency** (`tests/architectural/` layer-rules, docs-consistency suites) | **N/A to this mission's diff.** | No `src/` import-graph or layer change is in scope (C-001); `tests/architectural/` in full is only required for cross-cutting changes (pytest.ini, pyproject.toml, conftest, markers, packaging) per AGENTS.md's "Test policy" — none of which this mission touches. If FR-003 names a call site under `tests/`, the targeted test file(s) it touches are run, not the whole architectural tree. |
| **Doctrine schema freshness** (`spec-kitty doctrine regenerate-graph` gate) | **N/A.** | No `packs/built-in/` or `packs/internal/` doctrine artifact is touched (see "Generated artifacts"/"Contracts" above). |
| **Contextive glossary** | **N/A.** | No terminology/glossary content change; this mission touches CI YAML and Python test fixtures only. |
| **TID251 banned-API** | **Enforced, and applies.** | `ci-router.yml`'s `import-linter` job ("import boundaries (TID251)") is enforced across the entire `tests/` tree (AGENTS.md/pyproject.toml both confirm no whole-directory `tests/` exemption exists). This mission edits files under `tests/kernel/` and `tests/specify_cli/core/` and possibly one more under `tests/`, so the gate applies; the fix widens existing shim signatures (`**kwargs`/`dir_fd` parameter) without adding a new banned import, so it is expected to pass trivially, but the implementer must not casually add a new import to those files without checking it against the banned-API list. |
| **Typer JSON error surface** (`tests/architectural/test_json_contract_enumeration.py`) | **N/A.** | This mission adds no new Typer CLI command or JSON contract surface. |
| **`patch()` target validation** (`tests/architectural/_p1_census_oracle.py`, `_fixtures/patch_seam_control/*`) | **N/A / low-risk.** | This mission's FR-002 fix widens existing helper *signatures*; it does not add a new `mock.patch()` call. If FR-003's investigation or fix touches a call site that mocks `uv`/`subprocess` invocations, the implementer must run this gate's test file against that specific file before considering the WP done. |
| **Bandit (security lint)** | **Not wired into any live workflow.** | Grepped every file under `.github/workflows/*.yml` for `bandit` — zero hits. `docs/configuration/linting-cutoff-policy.md` claims Bandit is a "blocking" check run inside `ci-quality.yml`, but the live `ci-quality.yml` in this checkout has exactly four jobs (`lint`, `build-wheel`, `clean-install-verification`, `uv-lock-check`) and none of them runs Bandit. **This is a doc/code disagreement — a doc defect per the charter's docs doctrine ("code is the source of truth... a doc/code disagreement is a doc defect"), not something this mission fixes (out of C-001's blast radius), but flagged here rather than silently trusted.** |
| **pip-audit** | **Not wired into any live workflow** (same finding and same doc-defect flag as Bandit, both claimed "blocking" by the same stale doc section). `pip-audit>=2.7.0` is a declared dev dependency in `pyproject.toml` but has no CI job invoking it in this checkout. |
| **`uv.lock` freshness** | **Enforced, and applies trivially.** | Two separate jobs check it: `ci-router.yml`'s `uv-lock` job (`uv lock --check`, in `router-gate`'s `needs:`) and `ci-quality.yml`'s `uv-lock-check` job (in `quality-gate`'s `needs:`). This mission does not touch `pyproject.toml` or add/remove a dependency, so `uv.lock` is untouched and this gate passes by construction — but the implementer must not forget it exists if a WP unexpectedly needs a new test dependency (e.g. if `PyYAML` were not already available — it is, see Technical Context). |
| **Coverage-floored shards** (task framing: "kernel ≥90%, mission-loader ≥90%") | **Reframed to what's actually enforced.** | No per-module named floor ("kernel ≥90%", "mission-loader ≥90%") exists as a distinct gate in this codebase — grepped `.github/ci-module-registry.yml` and both `module-tests.yml`/`ci-modules.yml` for a per-module `fail-under`/floor value and found none, and no `mission-loader` (or `mission_loader`) module row exists in the registry at all. The **actual** enforced mechanism is the single **`diff-cover` PR gate in `ci-aggregate.yml`** ("diff-cover PR gate (>=90% changed critical-path lines)", `scripts/ci/validate_diff_coverage.py` + `diff-cover --fail-under=90`), which scores changed lines under `src/` against the reconciled per-module shard coverage (the registry's `kernel` row, `roots: src/kernel/**`, is one contributor to that reconciled set — not a separately-gated floor). See "Kernel coverage floor" below for how this mission holds it. |
| **`make lint` / `make typecheck`** | **Advisory `[INFO]` in CI, not enforced — local discipline only.** | `ci-quality.yml`'s `lint` job runs `ruff check .` and `ruff format --check .` **directly** (not via `make lint`), and that job **is** enforced (in `quality-gate`'s blocking `needs:`) — so ruff itself is a real, blocking gate even though `make lint` the Makefile target is never invoked by CI. `mypy --strict` (`make typecheck`) is invoked by **no** live workflow in this checkout (grepped every `.github/workflows/*.yml` for `mypy` — zero hits). Do not claim "CI will catch a type error" for this mission's diff; run `make typecheck` locally as discipline, not as a safety net. |
| **SonarCloud** | **No Sonar verdict is promised for this PR, for two separable reasons.** | (1) The standalone nightly-scan workflow `sonar.yml` triggers on `schedule`/`workflow_dispatch` only — it will not run against this PR at all. (2) `ci-aggregate.yml`'s `sonar-pr` job *does* run per PR (via a `workflow_run` chain off "CI Modules"), but it is `continue-on-error`, explicitly "reported, not required", and excluded from the terminal blocking `aggregate-gate` job by a `needs:` set-equality assertion (AGENTS.md's "Sonar Expectations" section, verified against `ci-aggregate.yml` directly). So neither Sonar surface produces a blocking verdict on this PR either way — state this plainly in the PR body rather than implying a green Sonar check validates anything. |
| **`ci-windows.yml`** | **N/A to this mission's diff.** | AGENTS.md's "Branches and CI" names this as "also live," so it is checked explicitly rather than silently omitted. Verified live: its `windows_critical` paths-filter (`.github/workflows/ci-windows.yml`, `pyproject.toml`, `pytest.ini`, a named list of Windows-marked test files, and a `src/**` catch-all) does not include any file this mission touches (`.github/workflows/ci-nightly.yml`, `tests/kernel/test_lock_parity.py`, `tests/kernel/test_no_follow.py`, `tests/specify_cli/core/test_no_follow.py`, the new `tests/ci/test_interpreter_matrix_env_pinning.py`, or, on the FR-003 fallback branch, `tests/upgrade/test_migration_robustness.py`); a live grep for the `windows_ci` marker across those files finds two hits (`ci-nightly.yml:120` a comment, `ci-nightly.yml:124` a `pytest -m "stress and not windows_ci"` marker expression), both inside `ci-nightly.yml` itself for an unrelated nightly stress job — none of the actually-touched test files (`test_lock_parity.py`, either `test_no_follow.py` copy, `test_migration_robustness.py`) carry the marker, and neither `ci-nightly.yml` hit is a `ci-windows.yml` `windows_critical` paths-filter entry, so this doesn't change the N/A conclusion. C-001/Charter Check already keep `src/**` out of this mission's scope entirely, so the filter's `src/**` catch-all clause cannot fire either. |
| **`docs-pages.yml`** | **N/A — structurally cannot gate any PR.** | Also named "also live" by AGENTS.md. Verified live: its `on:` block is `push` only (`branches: [main, 2.x]`), with no `pull_request` trigger at all, so it never runs against this or any PR regardless of paths touched. |
| **`check-spec-kitty-events-alignment.yml`** | **N/A to this mission's diff.** | Also named "also live" by AGENTS.md. Verified live: its `pull_request`/`push` path filters are scoped to `pyproject.toml`, `uv.lock`, `.kittify/release/shared-package-compatibility.json`, `scripts/release/**`, and its own workflow file — none of which this mission touches. |

## Kernel coverage floor (≥90%)

This mission's FR-002 fix widens the **signatures** of two existing helper
shims (`_WindowsMandatoryLockSimulator.wrap_open`'s `_open`, and the
`plant_symlink` monkeypatch) to accept and pass through `dir_fd` — it adds
zero new lines under `src/kernel/**`; only `tests/kernel/**` and
`tests/specify_cli/core/**` change. Since the enforced coverage mechanism
(the `ci-aggregate.yml` `diff-cover` gate) scores **changed critical-path
lines under `src/`**, and this mission's diff contains no changed `src/`
line at all (in the FR-002 branch; the FR-003 branch is bounded to `tests/`
too, or applies the fallback in `.github/workflows/ci-nightly.yml`, also not
`src/`), the floor is not at risk **by construction** — there is no new
`src/` line for the gate to under-cover. This holds regardless of the
FR-003 investigation's outcome, because Edge Case (a) already forbids
touching `src/` in this mission even if a `src/` call site is found. If a
future reviewer finds this reasoning wrong (e.g. because the FR-003
fallback's `UV_PROJECT_ENVIRONMENT` pin somehow required a `src/`-level
change — it should not, since it is a workflow-YAML env key), that must be
called out explicitly at review time rather than assumed away.

## The baseline

Measured 3.11 baseline for the `fast or unit` selector: **21 failed /
34659 passed** (per the readiness report, carried into spec.md). This
mission distinguishes pre-existing red from introduced red as follows:

- **IC-01 (baseline capture, see Implementation Concern Map)** runs the
  exact command `.venv/bin/python -m pytest -m "fast or unit" -q` on 3.11
  **first, before any implementation change lands**, with an explicit
  bounded timeout (≥600s per NFR-001), and records the exact pass/fail/
  error counts and the failure-ID list. Every later re-measurement (FR-004)
  is diffed against this recorded set, not against memory or the readiness
  report's prose.
- This is the same concern that discharges the charter's **Pre-existing
  Failure Reporting Rule**: FR-005 already commits to option (a) — a fresh
  GitHub issue reporting the 21 pre-existing 3.11 failures, since #3284 is
  **closed** (confirmed live: `gh issue view 3284` — cannot serve as the
  open report the rule requires) and #4866 itself reports the *environment*
  defect, not these 21 failures as their own tracked item. IC-01 opens that
  issue with the command run + failure summary + why they're believed
  pre-existing (also red at the merge-base, per the charter's stale-venv/
  baseline-red gotcha classification in AGENTS.md), and links it from this
  mission's PR.
- IC-01 is sequenced **early** and is **independent** of the other six
  concerns — it does not block or wait on FR-001/002/003.
- **Tasks-phase amendment:** the sentence above describes IC-01's own
  *inputs* (nothing blocks IC-01), which is still true. What changed since
  this plan was written: the tasks phase originally added a
  WP01→{WP02,WP03,WP04} gate encoded as a `dependencies: [WP01]` edge on
  all three in `wps.yaml`, so the *other* three concerns waited on IC-01's
  WP even though this plan-level sentence predates that tightening.
  **Correction (ledger SK-25, remediation 2026-09-22):** that
  `dependencies:` edge was itself a mistake — it encoded a pure scheduling
  constraint ("capture the 3.11 baseline before any change lands") as a
  data dependency, which produced a false lane cycle
  (`lane-a -> lane-planning -> lane-a`, since WP01/WP05/WP06/WP07 all bundle
  into `lane-planning`). The edge was removed from `wps.yaml` (WP02/WP03/WP04
  now carry `dependencies: []`); the ordering requirement itself is still
  real and still binding, but it is now enforced by the orchestrator's
  **dispatch sequencing** (do not dispatch WP02/WP03/WP04 until WP01 is
  `approved`/`done`) and by prose in WP02/WP03/WP04's own task files, not by
  a `dependencies:` edge. See the Implementation Concern Map's own amendment
  note (under IC-02/IC-03/IC-04) and `tracer-tooling-friction.md`'s
  "Correction: SK-25" entry for the full disclosure — this remains a
  reasoned, disclosed strengthening of IC-01's role, not a contradiction of
  IC-01's "independent" framing above.

## ATDD-First (binding, C-011)

Every implementation concern's WP follows red→green with the reviewer
verifying RED on `planning_base_branch` and GREEN on the final commit.

**FR-001 (workflow-YAML flags fix).** New test file:
`tests/ci/test_interpreter_matrix_env_pinning.py` — precedent:
`tests/ci/test_sonar_project_version.py` (a `tests/ci/` test that parses a
non-Python artifact by loading the module/file directly, not via `uv run`
or workflow execution). Assertion shape, concretely:

1. `yaml.safe_load()` the real `.github/workflows/ci-nightly.yml`. Precedent
   for parsing workflow YAML directly with `yaml.safe_load` in this repo:
   `scripts/ci/gate_selection.py` already does exactly this for a sibling
   GitHub Actions workflow — it loads `ci-router.yml` (via its
   `DEFAULT_ROUTER_PATH` constant; not `ci-nightly.yml`, which has no
   `changes` job at all) and walks that file's own `changes` job filters —
   establishing the in-repo pattern of parsing workflow YAML directly with
   `yaml.safe_load` rather than inventing a new convention here. (A second,
   closer precedent for a `tests/ci/` test parsing a non-Python artifact by
   loading the file directly is `tests/ci/test_sonar_project_version.py`,
   already cited above.)
2. Walk to `workflow["jobs"]["interpreter-matrix"]["steps"]`, find the
   step whose `run:` string contains `pytest -m "fast or unit"` (the `uv
   run` step, not the preceding `uv sync` step).
3. Assert **that step's own `run:` string** — not the job's or file's full
   YAML text — contains `--python` and `--all-extras` (or `--no-sync`).
   This is the load-bearing precision C-004 already calls out: the
   preceding `uv sync` step (line ~205) already carries `--python
   --all-extras`, so a whole-text match would be vacuously green even
   before the fix lands.
4. Commit this test **first**, as its own commit, showing RED against the
   current file (the `uv run` step currently lacks those flags). The
   FR-001 implementation commit (adding the flags) follows and turns it
   GREEN.

**How the reviewer demonstrates RED for a test of a nightly-only workflow
that no PR check runs**: the YAML-parsing test itself runs under ordinary
`pytest` — it is a Python test parsing a YAML file on disk, not a workflow
execution — so it goes RED/GREEN locally via an ordinary
`.venv/bin/python -m pytest tests/ci/test_interpreter_matrix_env_pinning.py -v`
invocation regardless of `ci-nightly.yml`'s own `schedule`/`workflow_dispatch`-only
trigger surface. This is deliberately different from *verifying the real
job*, which has no CI safety net at all (see "Verification route" below).

**FR-002 (kernel `dir_fd` fix).** Per spec C-004, no new test file is
required: the ATDD pinning **is** the pre-existing tests' own current RED
state on 3.13. Concretely — the WP:

1. Runs `.venv/bin/python -m pytest tests/kernel/test_lock_parity.py
   tests/kernel/test_no_follow.py
   tests/specify_cli/core/test_no_follow.py -v` on a real 3.13 interpreter
   **before** any shim-signature change, and records the exact currently-
   ERRORing test IDs (5 total per spec: 3 in `test_lock_parity.py`
   — including the named
   `test_naive_second_open_of_a_held_lock_raises_under_simulation`, plus its
   two sibling tests in the same file, enumerated by this same collection
   run rather than guessed in advance — and the one non-parametrized
   `test_read_rejects_symlink_planted_before_open` in each of the two
   separate `test_no_follow.py` copies). This run **is** the WP's red-first
   evidence; `planning_base_branch` already carries this RED state, so
   there is nothing to commit before the fix commit — the fix commit itself
   is the only commit this WP needs, and the reviewer's job is to confirm
   RED-before/GREEN-after by re-running the exact command on the base
   commit and the final commit.
2. Confirms GREEN with the same command on the final commit.
3. Confirms NFR-003 (no 3.11/3.12 behaviour change) by running the same
   command on a 3.11 interpreter before and after — the counts and outcomes
   must be identical.

**FR-003's own regression check (whichever branch is taken).** Whether the
WP lands a named-call-site fix (option a) or the `UV_PROJECT_ENVIRONMENT`
fallback (option b), its regression check is new test/assertion content and
therefore gets its own ATDD red-first treatment: write the assertion
(targeted call-site check, or the pinned-venv identity/extras check) RED
against the not-yet-fixed/not-yet-pinned state, then GREEN after the fix or
pin lands, as a commit sequenced the same way as FR-001's.

## Verification route (no CI safety net)

`ci-nightly.yml` triggers on `schedule` + `workflow_dispatch` only — never
`pull_request` or `push` (confirmed by direct read of the file's `on:`
block). A PR that edits this workflow file gets **zero** automatic CI
signal from the very workflow it changes. This mission's verification is
therefore, concretely:

1. **Local reproduction** of the exact `uv sync` + `uv run` step pair,
   mirroring `ci-nightly.yml`'s own commands byte-for-byte
   (`uv sync --frozen --all-extras --python 3.13`, then the fixed `uv run
   --frozen pytest -m "fast or unit" -q --junitxml=... --python
   "${{ matrix.python-version }}" --all-extras` — evaluated with a literal
   `3.13` locally, not the GitHub Actions expression), on a real Python
   3.13 interpreter. This is IC-03's own acceptance evidence (User Story 1,
   Acceptance Scenario 2) and does not require any GitHub Actions run at
   all.
2. **A manual dispatch** of the real workflow against the mission branch —
   `gh workflow run ci-nightly.yml --ref issue-4866-interpreter-matrix-3-13`
   — inspected via `gh run watch` / `gh run view --log`. This is the *only*
   check that exercises the real `interpreter-matrix` job end-to-end
   (SC-001).

   **This manual dispatch is an outward-facing action on a public repo and
   requires explicit operator authorization before it is run — it is not
   self-authorized by the phase agent or a WP subagent, even though the
   spec's own acceptance scenarios name the exact command.** It is
   sequenced as the **last** concern (IC-07, "final verification"), after
   IC-02/IC-03/IC-04/IC-05/IC-06 have all landed on the mission branch
   (matching IC-07's own "Sequencing/depends-on" field in the
   Implementation Concern Map below), so a single dispatch validates the
   whole mission's final
   state — including the post-fix re-measurement and the residual-red
   disposition, not just the three underlying fixes — rather than being run
   repeatedly per-fix or early against an intermediate state. The
   implementer stops at this step and asks the
   operator for a go-ahead before invoking `gh workflow run`.

No requirement or acceptance scenario in this plan claims a normal PR check
will validate the workflow-file diff. The ordinary per-PR CI (ruff,
`tests-cli`, etc.) still runs against this PR because `.github/workflows/**`
is a routed path in `ci-router.yml`'s `changes` filter — but that only
proves the YAML is well-formed and the touched test files pass their own
shard; it never executes `interpreter-matrix`'s own `schedule`/
`workflow_dispatch`-only trigger surface.

## Campsite-clean scope (Standing Order 2)

**No distinct, behaviour-preserving campsite-clean commit is warranted for
this mission.** Applying the charter's "Reconciling change-scope tensions"
order:

1. **Smallest-viable-diff** already picks a narrow, pre-named file set —
   one workflow job's `run:` string, two shim-helper signatures (in three
   files), and whatever FR-003 names.
2. **Boy Scout Rule** would license opportunistic cleanup *strictly inside*
   that file set, without adding files. The live reads already performed
   during spec authoring (`tracer-approach.md`: direct reads of both shim
   files and the workflow file) found no independently-diagnosed Sonar
   finding, lint violation, or over-long function in the touched surfaces
   — there is nothing domain-matched to fold in.
3. **Locality of Change** is therefore never tested here: there is no
   candidate cleanup to weigh against it.

If a genuine touched-area defect surfaces mid-implementation (e.g. the
shim-signature widening itself trips a lint/type finding), Standing Order 2
still licenses fixing it in place — but that is a reactive Boy Scout
response to something found while implementing, not a scheduled first
commit invented to fill this section.

## Write scopes / concurrency

Verified live, twice: once during spec authoring
(`tracer-approach.md`) and again during this plan-authoring pass
(`gh pr list --state open --json files`, run directly against this
checkout). **Only 2 PRs are currently open repo-wide**:

- **#4886** `fix/ownership-boundary-preservation` — touches
  `.github/ci-module-registry.yml`, `pyproject.toml`, `src/specify_cli/
  asset_preservation/**`, `src/specify_cli/cli/commands/init.py`,
  `src/specify_cli/skills/installer.py`, several `src/specify_cli/upgrade/
  migrations/*.py`, and their test mirrors. No overlap with
  `.github/workflows/ci-nightly.yml`, `tests/kernel/`, or
  `tests/specify_cli/core/`.
- **#4879** `issue-4860-next-dependency-selection` — touches
  `src/runtime/next/decision.py` and `tests/next/test_next_claimable_payload.py`
  only. No overlap.

**No write-scope conflict** with either open PR.

**Pytest shared test-venv lock (#3283)** — checked live
(`gh issue view 3283`): this issue is **CLOSED as COMPLETED (2026-09-08)**,
predating this mission's spec authoring. The underlying hazard it described
(a session-scoped shared-`.venv` fixture's 60s lock wait racing a >90s
`pip install -e .`, cascading setup errors across unrelated xdist workers)
is understood as **resolved**, not a currently-open capacity ceiling — this
plan does not treat it as an active blocker, correcting the framing implied
by the dispatch brief. It remains useful *historical context* for why the
venv-corruption spike (IC-04) should not stack multiple simultaneous
`-n auto` reproduction runs against other concurrently-running lanes: the
underlying shared-fixture contention pattern is mitigated, not proven
structurally impossible to re-trigger under heavy concurrent load.

## The venv-corruption spike (FR-003, Edge Case (a)) — largest schedule risk

This is the mission's largest unknown. Made operationally concrete:

**Bounded work package**: IC-04, "Root-cause or timebox-and-fallback the
shared-`.venv` mid-run corruption".

**Timebox**: **3 hours of wall-clock investigation time, or 5 `-n auto`
reproduction attempts against named suspect subsystems, whichever is
reached first.** Justification: each `-n auto` reproduction of the `fast or
unit` selector costs ~411s (3.13) per the readiness report's own
measurement — 5 attempts is ~34 minutes of pure repro-run time, leaving
ample budget within 3 hours for the grep enumeration, cross-referencing,
and `-k`-subset narrowing steps below. This directly applies the
tracer-tooling-friction.md SK-99 discipline (repeated `-n auto` attempts
are each ~7 minutes; budget for them explicitly rather than discovering the
strand failure mode mid-investigation).

**Exact sequence, in order:**

1. `grep -rn "uv sync\|uv run\|subprocess.*uv " tests/ src/` to enumerate
   every candidate call site that could shell out to `uv` during a `fast or
   unit` collection.
2. Cross-reference the hits against which test modules actually collect
   under the `fast or unit` marker set (`pytest --collect-only -q -m "fast
   or unit"` intersected with the grep hits), narrowing the candidate list
   to modules that can actually run in the reproduction.
3. **Reproduce first with `-n auto`** against a hand-built,
   `UV_PROJECT_ENVIRONMENT`-isolated 3.13 `.venv` (mirroring the readiness
   report's own accidental reproduction) — parallel execution is required
   to trigger the hazard; a serial run will not reproduce it.
4. Narrow via `-k` subsets by suspect subsystem — the readiness report's own
   suspicion (upgrade / skill-installer families that legitimately shell
   out to `uv` while testing spec-kitty's own bootstrap tooling) is the
   first subsystem to isolate with `-k`, rather than re-running the full
   ~35k-item selector on each attempt.

**Evidence that ends the spike successfully**: a named call site (exact
file + line) **plus** a regression test proving the shared `.venv`'s
interpreter identity does not move across a `fast or unit` / `-n auto` run
(FR-003 AC option (a)'s targeted call-site assertion).

**Exact fallback commit if the timebox is exhausted** (or the named call
site is under `src/` — Edge Case (a) treats both identically):

- Pin the leg's `.venv` via a per-interpreter `UV_PROJECT_ENVIRONMENT` path
  added to **`ci-nightly.yml`'s `interpreter-matrix` job**, specifically as
  an `env:` key on the job (or on the "Sync dev environment on this
  interpreter" step) scoped by `${{ matrix.python-version }}`, e.g.
  `UV_PROJECT_ENVIRONMENT: .venv-py${{ matrix.python-version }}` — the
  implementer records the exact key/value chosen at implementation time.
- Land the FR-003(b) lightweight regression check (interpreter identity +
  installed-extras set unchanged before/after a `fast or unit` / `-n auto`
  run) as a **small standalone test added to
  `tests/upgrade/test_migration_robustness.py`** — the module already
  hosting `test_concurrent_upgrade_handled`, the hazard's own original
  repro. Chosen over "a step added alongside the fallback's own
  `ci-nightly.yml` change" because the assertion is inherently dynamic
  (before/after a real `-n auto` run) and belongs beside the test that
  first surfaced the hazard, exercised by the same selector/marker set,
  rather than only asserted as a static CI-YAML fact.
- File a follow-up issue carrying the reproduction evidence already
  gathered: the `multiprocessing.spawn`-child-reports-3.11 traceback
  signature, the suspect-subsystem list from step 2/4 above, and what was
  ruled out — cross-linked from this mission's PR.
- **If the named call site is under `src/`**: apply the same fallback
  mitigation (never fix `src/` in this mission) and file the `src/` call
  site itself as a separate follow-up issue with the evidence gathered,
  cross-linked from this mission's PR.

## Re-measurement (FR-004, Edge Case (b))

**IC-05, "Re-measure `fast or unit` on 3.13"**, runs **after** IC-04 (the
venv-corruption fix or its documented fallback) lands — depends on IC-04
only, not on IC-02 (the kernel fix), though it is natural to sequence after
IC-02 too so the re-measurement reflects the mission's best current state.

Command: `.venv/bin/python -m pytest -m "fast or unit" -q -n auto
--junitxml=out/reports/xunit-remeasure-3.13.xml` on a **freshly synced**
3.13 `.venv`, with an **explicit bounded timeout of 900s** on the
invocation itself (comfortably above the ~411s baseline, per NFR-001/SK-99
— never relying on the shell's default), run in the foreground.

> **Mission-closing correction — the most consequential of this mission's
> documentation corrections; read before reusing this pattern.** The
> command above, taken literally, re-syncs the checkout's own `.venv` to
> 3.13 (`.venv/bin/python`). **Following it literally would have
> destroyed WP01's authoritative 3.11 baseline environment** —
> `evidence-baseline-3.11.md` records that WP01 synced this same
> checkout's `.venv` to 3.11 specifically to capture that baseline, and a
> later WP re-syncing `.venv` to 3.13 would silently overwrite it, with
> no record left for a later agent or reviewer running
> `.venv/bin/python -V` expecting 3.11.15. WP05 did **not** follow this
> instruction literally: on orchestrator instruction, it used a
> dedicated, isolated project environment
> (`UV_PROJECT_ENVIRONMENT=.venv313`, gitignored, kept inside this
> checkout rather than `/tmp`) and confirmed `.venv/bin/python -V` was
> still `Python 3.11.15` before and after its run — see
> `evidence-remeasurement-3.13.md`'s opening discrepancy note for the
> full record of the override. **The corrected instruction for any
> future mission reusing this pattern: never re-sync the checkout's own
> `.venv` to a second interpreter version for a measurement run — use a
> dedicated `UV_PROJECT_ENVIRONMENT` (e.g. `.venv313`) instead, and leave
> the checkout's `.venv` at whatever interpreter its own baseline/primary
> work depends on.** This plan's text above is left as originally
> written, not silently edited, per this mission's append-only
> correction convention (see the "Tasks-phase amendment" notes elsewhere
> in this document for the same convention applied earlier).

This run is the licensed instance of the charter's "explicit cross-cutting
change" full-suite exemption (Edge Case (b)): it re-runs the *same*
`fast or unit` selector `ci-nightly.yml`'s own job uses (not an unscoped
`pytest tests/`), because the venv-corruption fix changes how the shared
test environment itself behaves during a broad parallel run — exactly the
class of shared-infrastructure change the exemption contemplates.

**Who consumes the resulting number**: FR-006's disposition decision (file
the residual against #3189, or call it zero/small-and-fixable) and the PR
body's evidence section — the exact command, counts, and the failure-ID
diff against the IC-01 3.11 baseline are recorded in both places, not
asserted from memory.

## Residual-red disposition (FR-006, Edge Case (c))

**IC-06, "Disposition + issue filing"**, follows IC-05 directly (same
concern group; a distinct step, not a distinct file-set). Concretely:

- Compares the IC-05 re-measured failure/error set against the 4 `dir_fd`
  failures already fixed by IC-02 (FR-002, the kernel `dir_fd` fix — not
  IC-03/FR-001, the `uv run` flags fix, which has no relationship to the
  kernel shim signatures).
- If a residual beyond those 4 exists: files it as a comment/update on
  **#3189** (already open, already the workflow's own declared home for
  above-3.12 divergence per its inline comment) — or, if #3189's own scope
  doesn't cleanly absorb the specific findings, a new issue cross-linked to
  it — attaching the exact re-measured evidence (command, counts,
  failure-ID diff).
- States plainly in the PR body which of the three FR-006 dispositions
  applies: residual is zero, residual is small-and-fixable-in-scope (and
  was fixed), or residual is large-and-out-of-scope (filed against #3189,
  leg legitimately still red). The PR body never claims "nightly turns
  green" unless the IC-05 re-measurement, after IC-02/IC-03/IC-04, in fact
  shows zero residual.

## PR shape

**Default: ONE PR for this entire mission** — spec-kitty's own rule (per
the charter's Collaboration Strategy: the orchestrator claims, plans, and
"runs the implement→review loop to completion" against one mission branch/
PR), not Team Kitty's per-WP-PR convention. This mission's narrow,
already-tightly-scoped blast radius (C-001) does not obviously demand a
per-WP split. A per-WP split should be recommended **only** with a stated
reason if the aggregate diff genuinely cannot be reviewed in one sitting —
and that decision belongs to the orchestrator/operator at PR-prep time, not
to this plan.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

No entries — the Charter Check above found no violation requiring
justification.

## Implementation Concern Map

*Implementation concerns are NOT work packages and are NOT executable
units. `/spec-kitty.tasks` translates these into executable WPs — one
concern may become multiple WPs; multiple small concerns may merge into one
WP. These are not labelled with WP-style IDs or sequencing language beyond
the `depends-on` field, per the canonical template's own instruction —
given how narrowly this mission is already scoped, each concern below is
expected to map close to 1:1 onto a future WP, but that slicing decision
belongs to `/spec-kitty.tasks`, not this plan.*

**Tasks-phase amendment (mission interpreter-matrix-3-13-env-and-divergence-01M34HVD):**
`/spec-kitty.tasks` deliberately tightened this plan's task graph beyond the
"Sequencing/depends-on" wording below: WP02/WP03/WP04 (the WPs mapped 1:1
from IC-02/IC-03/IC-04 via `plan_concern_refs`) must not be claimed until
WP01 (IC-01's baseline-capture WP) reaches `approved`/`done`. This is a
disclosed strengthening for the charter's Pre-existing Failure Reporting
Rule's sake (IC-01's own purpose — a clean, recorded pre-implementation
baseline every later WP's evidence is measured against), not a
contradiction of this map's design intent.

**Correction (ledger SK-25, remediation 2026-09-22):** this gate was
originally encoded as `dependencies: [WP01]` on WP02/WP03/WP04 in
`wps.yaml`. That was a mistake: it expressed a pure scheduling constraint as
a data dependency and, because WP01/WP05/WP06/WP07 all bundle into the same
`lane-planning`, produced a false lane cycle
(`lane-a -> lane-planning -> lane-a`) at `finalize-tasks --validate-only`.
The edge was removed from `wps.yaml` — WP02/WP03/WP04 now carry
`dependencies: []` — and the ordering requirement is enforced instead by
the orchestrator's **dispatch sequencing** plus prose in WP02/WP03/WP04's
own task files (see each file's "Must not begin until WP01's baseline
capture is complete" paragraph). It is *not* enforced by
`dependency_readiness_for_wp` or any other `dependencies:`-graph mechanism.
See `tracer-tooling-friction.md`'s "Correction: SK-25" entry for the full
remediation record. WP05 also has a genuine data dependency on WP01 (WP05
reads WP01's baseline evidence file as an actual input), distinct in kind
from WP02/WP03/WP04's scheduling-only ordering — but that edge is
currently expressed as prose in WP05's own task file rather than a declared
`dependencies:` entry: `finalize-tasks`'s disagree-loud gate rejects adding
it to `wps.yaml` today (a genuine tooling gap, not a design choice — see
`tracer-tooling-friction.md`'s follow-up entry after the SK-25 correction).
`wps.yaml`'s WP05 entry remains `dependencies: [WP02, WP04]`; WP05 is safe
in practice because both of those declared dependencies transitively wait
on WP01 already. IC-02, IC-03, and IC-04 remain independent **of one
another** — only the
WP01-first ordering is new; the "none"/"independent" language in each
concern's own "Sequencing/depends-on" field below describes that
inter-concern independence and predates the tasks-phase gate.

### IC-01 — Baseline capture + Pre-existing Failure Reporting Rule discharge

- **Purpose**: Establish the recorded, falsifiable 3.11 `fast or unit`
  baseline (21 failed / 34659 passed) before any change lands, and open the
  fresh GitHub issue FR-005 commits to.
- **Relevant requirements**: FR-005.
- **Affected surfaces**: none (read-only measurement) + a new GitHub issue.
- **Sequencing/depends-on**: none — runs first, independent of every other
  concern.
- **Risks**: none material; the only risk is skipping this and later being
  unable to distinguish introduced-vs-pre-existing red.

### IC-02 — Fix the 4 confirmed `dir_fd` kernel test-double failures (FR-002)

- **Purpose**: Widen the two kernel/core test-double shims
  (`_WindowsMandatoryLockSimulator.wrap_open`'s `_open` shim, and the
  `plant_symlink` monkeypatch shim duplicated across two files) to accept
  and pass through the `dir_fd` keyword argument that 3.13's
  `shutil.rmtree` now legitimately passes, unblocking the leg's first
  genuine 3.13 run. Standing Order 4 classifies this as a stale test
  double, not a product defect (see Charter Check above).
- **Relevant requirements**: FR-002, NFR-003 (cross-interpreter
  neutrality — the fix must not change 3.11/3.12 behaviour).
- **Affected surfaces**: `tests/kernel/test_lock_parity.py`,
  `tests/kernel/test_no_follow.py`,
  `tests/specify_cli/core/test_no_follow.py`. No new test file required —
  per spec C-004, the ATDD pinning **is** the pre-existing tests' own
  current RED state on 3.13 (see "ATDD-First" above).
- **Sequencing/depends-on**: none — independent, like IC-03 (FR-001) and
  IC-04 (FR-003). **Tasks-phase amendment:** this concern's WP (WP02) must
  not be dispatched until WP01 (baseline capture) is `approved`/`done`,
  enforced by dispatch sequencing + prose (not a `wps.yaml` `dependencies:`
  edge, per ledger SK-25) — see the amendment note at the top of this
  section.
- **Risks**: low, per the "ATDD-First" section's own characterization —
  the fix widens existing shim signatures to accept `dir_fd`; it adds zero
  new lines under `src/kernel/**` (see "Kernel coverage floor" above), and
  NFR-003's before/after 3.11 comparison is the concrete guard against any
  behaviour change.

### IC-03 — Pin interpreter/extras on the `uv run` step (FR-001)

- **Purpose**: Make the `interpreter-matrix` job's `pytest` invocation
  actually run under the interpreter/extras the preceding `uv sync` step
  resolved, instead of silently re-syncing to `.python-version`.
- **Relevant requirements**: FR-001, NFR-002 (fail loudly, never silently
  re-sync to the wrong interpreter again).
- **Affected surfaces**: `.github/workflows/ci-nightly.yml`
  (`interpreter-matrix` job's `uv run` step), new file
  `tests/ci/test_interpreter_matrix_env_pinning.py`.
- **Sequencing/depends-on**: none functionally, but naturally lands before
  IC-07 (final verification) since IC-07 dispatches the real job.
  **Tasks-phase amendment:** this concern's WP (WP03) must not be dispatched
  until WP01 (baseline capture) is `approved`/`done`, enforced by dispatch
  sequencing + prose (not a `wps.yaml` `dependencies:` edge, per ledger
  SK-25) — see the amendment note at the top of this section.
- **Risks**: low — a single-line flag addition; the risk is entirely in
  getting the ATDD test's assertion scoped to the `uv run` step's own
  `run:` string (not the whole job/file) per C-004.

### IC-04 — Root-cause or timebox-and-fallback the venv-corruption hazard (FR-003)

- **Purpose**: Identify (or bound-and-document an inability to identify)
  the call site that silently rebuilds the shared `.venv` from 3.13 back to
  3.11 mid-run under `-n auto`, so the 3.13 divergence figure is measured
  against a stable environment.
- **Relevant requirements**: FR-003, NFR-001 (bounded verification
  runtime), NFR-002 (fail loudly).
- **Affected surfaces**: whatever call site is named (expected `tests/`;
  `src/` is out of scope per Edge Case (a)), or, on the fallback path,
  `.github/workflows/ci-nightly.yml` (`UV_PROJECT_ENVIRONMENT` pin) +
  `tests/upgrade/test_migration_robustness.py` (regression check) + a new
  follow-up GitHub issue.
- **Sequencing/depends-on**: none — independent of IC-03; IC-05 depends on
  this concern. **Tasks-phase amendment:** this concern's WP (WP04) must
  not be dispatched until WP01 (baseline capture) is `approved`/`done`,
  enforced by dispatch sequencing + prose (not a `wps.yaml` `dependencies:`
  edge, per ledger SK-25) — see the amendment note at the top of this
  section.
- **Risks**: the mission's largest schedule risk (see "The venv-corruption
  spike" above for the full timebox/sequence/fallback contract).

### IC-05 — Re-measure `fast or unit` on 3.13 post-fix (FR-004)

- **Purpose**: Replace the distrusted 429-only-on-3.13 figure with a clean
  re-measurement against a now-stable environment, before any further
  scoping decision is made.
- **Relevant requirements**: FR-004.
- **Affected surfaces**: none (read-only measurement, recorded in the PR
  body / tests-run evidence).
- **Sequencing/depends-on**: IC-04 (must run after the venv fix/fallback
  lands); naturally also after IC-02.
- **Risks**: bounded-runtime discipline (NFR-001) — must carry an explicit
  ≥600s timeout, foreground, per SK-99.

### IC-06 — Residual-red disposition + #3189 filing (FR-006)

- **Purpose**: State, in writing, one of the three FR-006 dispositions for
  any re-measured residual beyond the 4 fixed `dir_fd` failures.
- **Relevant requirements**: FR-006.
- **Affected surfaces**: a comment/update on #3189 (or a new cross-linked
  issue), plus the PR body's evidence section.
- **Sequencing/depends-on**: IC-05.
- **Risks**: none material — this is a disposition/documentation step, not
  a code change.

### IC-07 — Final verification (local repro + operator-authorized manual dispatch)

- **Purpose**: Validate the whole mission's diff against the real
  `interpreter-matrix` job, since no PR check exercises it (C-003).
- **Relevant requirements**: SC-001 (and, transitively, confirms
  IC-02/IC-03/IC-04's fixes hold together in the real CI environment).
- **Affected surfaces**: none (verification only).
- **Sequencing/depends-on**: IC-02, IC-03, IC-04, IC-05, IC-06 (the kernel
  `dir_fd` fix, the interpreter/extras fix, the venv-corruption
  fix/fallback, the post-fix re-measurement, and the residual-red
  disposition must all have landed on the mission branch first, so
  `/spec-kitty.tasks`'s literal translation of this field into a WP
  dependency edge cannot unblock the operator-gated dispatch before the
  mission's final state — including IC-05's re-measurement and IC-06's
  disposition — is reached; this matches the "Verification route" section
  above, which also names this as "the last concern").
- **Risks**: **requires explicit operator authorization before the manual
  `gh workflow run ci-nightly.yml --ref issue-4866-interpreter-matrix-3-13`
  dispatch is executed** — this is an outward-facing action on a public
  repo and is never self-authorized by the phase agent or a WP subagent.

---

## Tooling drift flagged (not silently resolved)

`.venv/bin/spec-kitty plan --mission interpreter-matrix-3-13-env-and-divergence-01M34HVD --json`
(spec-kitty-cli 4.0.0rc5, run from this checkout) scaffolded a `plan.md`
that does **not** match this checkout's own canonical template at
`packs/built-in/missions/software-dev/templates/plan-template.md`: it
referenced a stale execution-workflow path
(`src/doctrine/missions/software-dev/command-templates/plan.md`, which does
not exist post-doctrine-absorption into `src/charter/offering/`), used
"Constitution Check" instead of the current "Charter Check", and used a
"Parallel Work Organization" section instead of the current "Implementation
Concern Map" (IC-##) structure.

**Root cause, verified live against this checkout: a stale project-tier
override, not a `plan`-command defect.** This checkout carries a
git-tracked override file at `.kittify/overrides/missions/software-dev/
templates/plan-template.md` (last touched 2026-04-17) that still has
exactly this stale shape — the same "Constitution Check" heading, the same
"Parallel Work Organization" section, the same stale
`src/doctrine/missions/software-dev/command-templates/plan.md` path. The
canonical template at `packs/built-in/missions/software-dev/templates/
plan-template.md` was updated to "Charter Check" / "Implementation Concern
Map" on 2026-08-15, but the override was never re-synced to match.
`src/charter/activation/template_resolver.py` documents the resolution
order as OVERRIDE > LEGACY > ORG > GLOBAL_MISSION > GLOBAL >
PACKAGE_DEFAULT, `src/charter/offering/resolver.py` lists
`.kittify/overrides/missions/{mission}/{templates,command-templates}/` as
resolution step 1, and `docs/architecture/mission-system.md`'s own
template-resolution table agrees ("Project override" is priority 1, the
package default is the fallback). OVERRIDE is the highest-priority tier by
design, so the `plan` command did exactly what it is built to do: it
resolved this repo's own tracked-but-stale override ahead of the updated
canonical template. The mechanical observation above (the scaffold
mismatched the canonical shape) is accurate; the causal attribution to a
`plan`-command defect is not.

Per AGENTS.md's "Use Canonical Sources, Never Improvise" directive, this
plan is authored against the current canonical template rather than the
stale override output. This is **not fixed in this mission** —
refreshing/regenerating the stale override at
`.kittify/overrides/missions/software-dev/templates/plan-template.md` is a
one-line local fix, but it sits outside C-001's blast radius (this
mission's scope is the `interpreter-matrix` CI job and the named kernel
test doubles, not `.kittify/overrides/`). If a follow-up is filed, it
should be scoped correctly: there is currently no mechanism that warns
when a project-tier override has silently drifted from an updated
canonical template, so the actionable upstream ask is a feature request
for override-staleness detection — not a report of "a live defect in
spec-kitty's own plan command."
