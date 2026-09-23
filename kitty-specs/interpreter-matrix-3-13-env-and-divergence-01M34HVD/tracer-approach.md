# Tracer: Approach

Seeded at spec authoring (2026-09-22). Reasoning trail for how this spec was
built, what was verified live vs. taken from the readiness report, and what
was deliberately left out.

## What I verified against the live repo rather than trusting the readiness report at face value

- **The `uv run` step's missing flags**: re-read `.github/workflows/ci-nightly.yml`
  lines ~174–241 directly. Confirmed the sync step passes `--python
  "${{ matrix.python-version }}" --all-extras` but the run step
  (`uv run --frozen pytest -m "fast or unit" -q --junitxml=...`) carries
  neither. Matches the readiness report exactly.
- **The `test` extra's contents**: re-read `pyproject.toml`'s
  `[project.optional-dependencies].test` block directly — confirmed
  `pytestarch`, `respx`, `pytest-benchmark` (via `pytest_benchmark` import
  name) are all declared there, none in default/base dependencies. Matches.
- **`uv` version**: ran `uv --version` in this checkout — `0.11.28`, matching
  the readiness report's pinned-tool assumption.
- **The `dir_fd` test doubles**: read `tests/kernel/test_lock_parity.py`'s
  `_WindowsMandatoryLockSimulator.wrap_open` and
  `tests/kernel/test_no_follow.py` / `tests/specify_cli/core/test_no_follow.py`'s
  `plant_symlink` shims directly. Both `_open`/`plant_symlink` signatures
  are `(path, flags, mode=0o777)` with no `**kwargs` or `dir_fd` parameter,
  confirming the `TypeError` mechanism the readiness report describes is
  structurally real, not just observed in one run.
- **Open PR overlap**: ran `gh pr list --state open` myself rather than
  trusting the readiness report's "3 PRs, none overlapping" claim as still
  current (the mission brief itself flagged this as something that "can
  change" and told me to re-verify). Found only **2** open PRs now (#4886,
  #4879) — #4877 from the readiness report is no longer open (merged or
  closed since 2026-09-22's earlier probe). Neither open PR touches
  `.github/workflows/ci-nightly.yml`, `pyproject.toml`'s extras, or the
  kernel test files this mission touches. Confirmed clean to proceed.
- **#3189 and #3284 state**: ran `gh issue view` on both directly. #3189
  confirmed OPEN ("no pytest job runs above Python 3.12..."). #3284
  confirmed CLOSED ("main full suite has 23 untracked failures..."),
  matching the brief's instruction that it cannot alone discharge the
  Pre-existing Failure Reporting Rule.
- **`ci-nightly.yml`'s trigger surface**: read the workflow file's own `on:`
  block context alongside the interpreter-matrix job to confirm no
  `pull_request`/`push` trigger exists for this workflow — matches Edge
  Case (d)'s claim.

I did **not** re-run the full `fast or unit` selector on 3.11/3.12/3.13
myself during spec authoring — that would duplicate the readiness report's
own multi-hundred-second reproduction runs for no additional grounding value
at the spec-writing stage, and risks exactly the SK-99 strand hazard for a
step that doesn't need it (spec authoring doesn't require a fresh failure
count; it requires the *shape* of FR-004's re-measurement requirement to be
correct, which the file-level verification above already grounds). The
re-measurement itself is the mission's own FR-004/SC-004 deliverable, to be
executed by an implementation WP with the SK-99 timeout discipline applied.

## How I resolved the four tensions

See `tracer-design-decisions.md` for the compact, scannable version. The
narrative reasoning:

- **(a) Unbounded investigation**: I did not invent a wall-clock number in
  the spec — that's a plan/tasks-level sizing decision — but I refused to
  leave the tension as an open question either, per the mission brief's
  explicit instruction not to hand-wave it. The spec states the *shape*
  (bounded spike, `-k`-scoped attempts against named suspect subsystems,
  not an unbounded bisection) and the *fallback contract* (interim
  mitigation + follow-up issue with evidence, not silent abandonment) so a
  later plan-phase agent has a concrete contract to size against instead of
  reinventing the resolution from scratch.
- **(b) Re-measurement vs. 429 baseline**: straightforward — User Story 4
  plus explicit FR-004/SC-004 make the re-measurement a first-class
  deliverable, not an implicit assumption. I also addressed the charter
  exemption question directly rather than assuming it: the full-suite-run
  reservation in the charter's Testing Requirements section is written
  around `pytest tests/`, not the `fast or unit` selector specifically, and
  the re-measurement only ever needs to run that same selector
  (`ci-nightly.yml`'s own job scope), so I scoped the exemption narrowly to
  that selector rather than licensing an unscoped full-repo run.
- **(c) Residual red disposition**: I picked one disposition (file against
  #3189, accept honest red) and justified it against the workflow's own
  pre-existing inline comment disclaiming #3189's scope — this wasn't a
  judgment call invented from nothing, it's consistent with a decision the
  codebase had already made about where above-3.12 divergence work lives.
  I explicitly wrote Success Criteria to NOT claim "nightly turns green"
  anywhere, per the brief's direct instruction.
- **(d) No CI safety net**: verified directly (see above) rather than taken
  on faith, then threaded through every acceptance scenario in the spec by
  naming the exact local command or manual dispatch each one uses, so no
  acceptance scenario implicitly assumes a PR check that will never fire.

## What I deliberately did NOT include, and why

- **A specific wall-clock timebox number for the venv-corruption
  investigation** (e.g. "2 hours" or "N reproduction attempts") — that's a
  plan/tasks-phase sizing decision informed by WP granularity and available
  compute, not a spec-phase one. The spec commits to the *contract*
  (bounded, evidenced, with a fallback), not a specific number that would
  be arbitrary at this stage.
- **Any specific fix for the venv-corruption call site** — unknown at spec
  time by design; FR-003/Edge Case (a) describe the investigation's shape,
  not a pre-supposed answer.
- **Widening the interpreter matrix beyond 3.13, or the suite selector
  beyond `fast or unit`** — explicitly out of scope per C-002, matching the
  operator's Q1 framing and the workflow's own inline #3189 disclaimer.
- **A canonical-sources concern** — checked `packs/built-in/agent_profiles/`
  and `packs/built-in/missions/mission-steps/` exist on this checkout and
  confirmed this mission's blast radius (CI workflow + kernel test files)
  doesn't touch either, rather than inventing a concern that doesn't apply
  just to fill out the section.

## What I verified live during tasks authoring (2026-09-22)

- **Re-ran `gh pr list --state open --json number,title,headRefName,files`
  myself** (after `unset GITHUB_TOKEN`) rather than trusting plan.md's own
  snapshot ("Only 2 PRs are currently open repo-wide": #4886, #4879) as
  still current. Result at tasks-authoring time: **only 1 PR is now open**
  — `#4879` (`issue-4860-next-dependency-selection`, touching
  `src/runtime/next/decision.py` and
  `tests/next/test_next_claimable_payload.py` only). `#4886` is no longer
  open (merged or closed since plan authoring). **No overlap** with this
  mission's touched surfaces (`.github/workflows/ci-nightly.yml`,
  `tests/kernel/`, `tests/specify_cli/core/`, `tests/ci/`,
  `tests/upgrade/**`, `tests/specify_cli/upgrade/**`,
  `tests/specify_cli/skills/**`) — confirmed clean to proceed, same
  conclusion as plan.md, but against fresher data.
- **Write-scope disjointness across this mission's own 7 WPs**: verified by
  inspection of `wps.yaml`'s `owned_files` lists (and confirmed
  mechanically — `finalize-tasks --validate-only` computed lanes with zero
  `ownership_warnings` and zero overlap errors). Final disjoint partition:
  WP02 → `tests/kernel/test_lock_parity.py`, `tests/kernel/test_no_follow.py`,
  `tests/specify_cli/core/test_no_follow.py`; WP03 →
  `.github/workflows/ci-nightly.yml`, `tests/ci/test_interpreter_matrix_env_pinning.py`;
  WP04 → `tests/upgrade/**`, `tests/specify_cli/upgrade/**`,
  `tests/specify_cli/skills/**`; WP01/WP05/WP06/WP07 each own one distinct
  new `kitty-specs/.../evidence-*.md` file. **Deliberate design choice**:
  WP04's `owned_files` excludes `.github/workflows/ci-nightly.yml` even
  though its Branch B fallback may need to add a `UV_PROJECT_ENVIRONMENT`
  env key to that same file — WP03 is the sole declared owner of that file
  (avoiding an ownership-overlap rejection, since the `tasks-finalize`
  ownership validator rejects two narrow WPs claiming the same file
  regardless of dependency edges). WP04's own prompt documents this
  explicitly and authorizes the fallback edit as a small, rationale-recorded
  out-of-map edit if Branch B is taken, rather than fabricating a second
  ownership claim or force-linearizing WP03/WP04 (which plan.md's IC map
  deliberately keeps independent).
- **Chokepoint**: WP07 (final verification) depends on all of
  WP02/WP03/WP04/WP05/WP06 — every other WP in the mission. This mirrors
  plan.md's IC-07 dependency edges exactly, and is additionally stated in
  words, twice: in WP07's own prompt ("Context" section, "THIS WP IS A
  GENUINE CHOKEPOINT") and here. The chokepoint is real and intentional —
  it serializes the mission's only check against the real
  `ci-nightly.yml` job (C-003, no PR-triggered CI) behind every other WP's
  completion, so a single operator-authorized dispatch validates the
  mission's *final* state, not an intermediate one.
- **PR shape**: **ONE PR confirmed**, per plan.md's own "PR shape" section
  and re-confirmed here at tasks-authoring time. Reasoning: the full
  expected diff across all 7 WPs is small and narrowly bounded — one
  workflow-file line-class addition (WP03), two kernel/core test-double
  shim signature widenings across three files (WP02), a bounded
  investigation with either a single named-call-site fix or a
  `UV_PROJECT_ENVIRONMENT` env-key addition plus one new test (WP04), and
  four new planning-evidence markdown files with zero production-code
  impact (WP01/WP05/WP06/WP07). This is comfortably reviewable by a human
  in one sitting — I did **not** find a case for recommending a per-WP
  split, and no WP's own prompt raises one either.

## What I verified live during plan authoring (2026-09-22), beyond the spec's own verification pass

- **Re-ran `gh pr list --state open --json files` myself** rather than
  trusting the spec-authoring pass's snapshot as still current at plan
  time. Same result: 2 open PRs (#4886, #4879), neither touching
  `.github/workflows/ci-nightly.yml`, `tests/kernel/`, or
  `tests/specify_cli/core/`.
- **Read the actual live gate mechanics** rather than accepting the
  dispatch brief's gate-name list at face value: read `ci-quality.yml`,
  `ci-router.yml`, `ci-aggregate.yml`, `ci-nightly.yml`'s
  `interpreter-matrix` job, `scripts/ci/gate_selection.py`, and
  `.github/ci-module-registry.yml` directly. Found and flagged (in
  plan.md's gate table and this tracer set's tooling-friction entry): (1)
  commitlint and markdownlint are both non-blocking (`|| true` /
  `continue-on-error`) in the live workflows; (2) Bandit/pip-audit are
  documented as blocking but wired into no live workflow — a doc/code
  disagreement; (3) there is no per-module "kernel ≥90%"/"mission-loader
  ≥90%" coverage floor — the real mechanism is `ci-aggregate.yml`'s single
  diff-cover ≥90% critical-path gate; (4) `make lint`/`make typecheck` are
  never invoked by CI (ruff runs directly in `ci-quality.yml`'s `lint` job
  and IS blocking; mypy is invoked by no workflow at all); (5) two separate
  Sonar surfaces exist (`sonar.yml`, schedule/workflow_dispatch-only; and
  `ci-aggregate.yml`'s `sonar-pr` job, which does run per-PR but is
  `continue-on-error` and excluded from the blocking `aggregate-gate`) —
  neither produces a blocking verdict on this PR.
- **Checked issue #3283's live state** (`gh issue view 3283`) rather than
  accepting the dispatch brief's framing of it as an active capacity
  ceiling — found it CLOSED as COMPLETED on 2026-09-08, predating spec
  authoring. Corrected the framing in plan.md accordingly.
- **Diffed the scaffolded `plan.md` against the canonical template**
  (`packs/built-in/missions/software-dev/templates/plan-template.md`)
  rather than filling in the scaffold as given, and found it stale (see
  tracer-tooling-friction.md). Authored the plan against the canonical
  template's structure (Charter Check, Implementation Concern Map)
  instead.
