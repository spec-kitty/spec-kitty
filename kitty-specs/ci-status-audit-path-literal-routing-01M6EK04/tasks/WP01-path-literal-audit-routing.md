---
work_package_id: WP01
title: Route the path-literal audit on a status diff
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
- C-001
- C-002
- C-003
- C-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: >-
  Planning artifacts for this mission were generated on main. During
  /spec-kitty.implement this WP may branch from a dependency-specific base, but completed
  changes must merge back into main unless the human explicitly redirects the landing
  branch.
base_branch: main
base_commit: 33b5a3e97f
created_at: '2026-11-02T17:00:00.000000+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-11-02T17:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/ci-router.yml
create_intent:
- tests/ci/test_path_literal_audit_routing.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/ci/test_path_literal_audit_routing.py
- .github/workflows/ci-router.yml
- tests/release/ci_retirement_scrub.json
- tests/architectural/test_no_duplicate_suite_execution.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6879'
---

# Work Package Prompt: WP01 – Route the path-literal audit on a `status/**` diff

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objective

Close spec-kitty#6879: a `src/specify_cli/status/**` diff must run
`tests/audit/test_no_legacy_path_literals.py` per PR, so a re-scattered
`Path.home() / ".spec-kitty"` literal is caught on its own pull request instead of a day
later as a nightly red.

The change is CI wiring only — no `src/` change, and the guard file itself is not modified
(C-002). It adds one src-backed router group (`path_literal_audit`), one blocking router
job gated on it (`tests-path-literal-audit`) that runs exactly that one test file, and a
live-routing regression guard so the wiring cannot silently regress.

Read first: `spec.md` (grounding + FRs), `plan.md` (design decisions 1-5, IC map).

## Context

- The router has exactly two hand-authored routing sources —
  `tests/release/ci_retirement_scrub.json` (`groups[].roots`, the SSOT) and
  `.github/workflows/ci-router.yml` (the dorny filter block transcribed from it + the job
  `if:` gates). Everything else is derived and asserted:
  `tests/architectural/test_ci_router_transcription_guards.py`,
  `tests/architectural/test_ci_quality_path_filters.py`,
  `tests/architectural/test_gate_selection_authority.py`,
  `tests/architectural/test_workflow_coherence.py`.
- `scripts/ci/gate_selection.py` parses both sources; never add a third path→group map.
- Precedent for a narrow extra lane: `tests-events-consumers` (#6605) — its commit
  `3d6754b8fe` is the shape to copy (group, output, job, `router-gate` needs,
  `AUTHORIZED_PER_CHANGE_SUITE_JOBS` row with rationale, and a `tests/ci` pin).
- Precedent for a router job: `mission-state-audit` (#5864) — commit `aaccc6b6dc`.
- `AUTHORIZED_SUITE_INVOCATIONS_PER_JOB = 1` per job, so the lane must run its pytest
  selection in ONE invocation.
- The guard module is `pytestmark = [pytest.mark.integration]` and carries no `fast`/`unit`
  marker; `-m "fast or unit"` deselects all 8 tests (verified locally). The lane's pytest
  command must therefore carry no marker expression, and a zero-collected exit 5 must fail
  the job.

## Subtasks

### T001 — Red-first: the live-routing regression guard

Add `tests/ci/test_path_literal_audit_routing.py` (`pytestmark = pytest.mark.fast`, so the
`ci` module shard runs it on every PR). It must read the LIVE authorities — `load_router()`
from `scripts/ci/gate_selection.py` for routing, `yaml.safe_load` of the workflow for the
job shape, `tests.ci._gh_if.eval_gh_if` for the `if:` goldens — and assert:

1. `select_gates(["src/specify_cli/status/locking.py"]).matched_groups` contains
   `path_literal_audit`, and the job gated on that group exists and its pytest step names
   `tests/audit/test_no_legacy_path_literals.py` (positive control);
2. the same for `src/kernel/paths.py` and `tests/audit/test_no_legacy_path_literals.py`
   (FR-003), plus the opposite assertion for `src/specify_cli/paths/windows_paths.py`:
   `unmatched_src` is True (run-all) and the group does NOT match, because naming that
   unmapped keystone directory would narrow the FR-004 sensor (C-005);
3. negative controls on the same fixture: `docs/**`, `src/specify_cli/dashboard/**` and a
   `packs/**` path do NOT match the group (non-vacuity: proves the probe can distinguish);
4. the lane's pytest invocation tokenises to exactly one path argument — that guard file —
   with no `-m`/`--ignore`/`-k` narrowing (FR-002/FR-005), and the job is in
   `router-gate`'s `needs` and not in `router_gate.ADVISORY_JOB_NAMES` (NFR-002);
5. the job's `if:` evaluates false under the prose-only golden context and true when only
   `changes.path_literal_audit` is lit.

Run it: it must FAIL before T002-T004 (that is the red-first proof). Record the failure
output in the WP activity log.

### T002 — The routing authorities

- `tests/release/ci_retirement_scrub.json`: add a row for `path_literal_audit` to
  **`non_src_router_groups`** with roots, in this order:
  `**/specify_cli/status/**`, `**/kernel/paths.py`,
  `tests/audit/test_no_legacy_path_literals.py`, plus a `note` citing #6879, the guard limb
  and why the row is NON-src (`**/` spelling; a src-backed group must also be a
  module-registry row, which is out of scope, C-001/C-005). The `**/` spelling is what keeps
  `src/specify_cli/paths/**` unmapped so the FR-004 catch-all still forces run-all there.
- `.github/workflows/ci-router.yml`: transcribe those globs VERBATIM into the dorny filter
  block as group `path_literal_audit`; add the `changes.outputs` row in the same fold shape
  as its siblings. Do **NOT** add it to the FR-004 `unmatched` step's union and do **NOT**
  add it to `architectural-heavy`'s `if:` — the transcription guards require the union and
  the battery OR-list to equal the src-backed group set exactly, and this group is not in
  it.

### T003 — The job, its gating and its requiredness

- Add job `tests-path-literal-audit` (display name `tests (path-literal audit)`):
  `needs: [changes, prose-scan]`, `timeout-minutes` ≤ 10, the same fork-guard +
  label-guard shape as the other gated jobs, `if:` = the group being true AND
  `needs.prose-scan.outputs.prose_only != 'true'`; steps: checkout, setup-uv
  (python 3.12, `enable-cache`), `uv sync --frozen --all-extras` in its own named step,
  `./.github/actions/sync-packs`, then one pytest run over the single file with no marker
  expression (add `--junitxml=out/reports/xunit-path-literal-audit.xml` if the repo's lane
  convention wants it). Add a comment block stating the #6879 grounding, the 8-test count
  and why the marker filter is absent.
- Add `tests-path-literal-audit` to `router-gate`'s `needs:` (that is what makes the lane
  blocking; it is not an `ADVISORY_JOB_NAMES` entry).
- Do not touch `architectural-heavy`'s `if:` (see T002).

### T004 — The duplicate-suite ledger row

`tests/architectural/test_no_duplicate_suite_execution.py`: add
`("ci-router.yml", "tests-path-literal-audit")` to `AUTHORIZED_PER_CHANGE_SUITE_JOBS` with
a rationale that names: one invocation, one file, the guard's only per-PR home, and why no
existing lane can host it (battery partition + one-invocation-per-job). This is the only
structural edit outside the two routing authorities and it is additive.

### T005 — Verification sweep

Run and record, from the repo root with the mission's venv:

- `uv run --frozen python -m pytest tests/ci -q -n auto --dist loadfile`
- `uv run --frozen python -m pytest tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_same_tier_uniqueness.py -q`
- `uv run --frozen python -m pytest tests/audit/test_no_legacy_path_literals.py -q` (the
  lane's own selection — 8 passed)
- the lane's real command shape against a planted literal (make the guard red on purpose,
  confirm the command exits non-zero, then restore) — production-path non-vacuity.
- `uv run --frozen ruff check` on the touched Python files.

No gate may be skipped, xfailed or weakened. If a red is pre-existing, reproduce it on
pristine `origin/main` in a clean worktree before attributing it.

### T006 — Changelog fragment (deferred to wrap-up)

The changelog fragment is `docs/changelog/unreleased/<pr>.internal.md` (non-user-facing:
CI routing) and needs the PR number, so it is written after the PR exists, in the
wrap-up step, not inside this WP's commit series.

## Definition of Done

- T001's guard test exists and is green; its failure before the wiring is recorded.
- Every structural router guard listed in T005 is green; no guard was edited to accept the
  change except the additive T004 ledger row.
- The lane's pytest selection collects 8 tests with no marker filter, and a planted
  literal in a `status/**` file would fail that exact command.
- No `src/` change, no guard-file change, no registry change (C-001, C-002).
