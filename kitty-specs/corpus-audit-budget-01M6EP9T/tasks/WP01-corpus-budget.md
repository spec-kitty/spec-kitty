---
work_package_id: WP01
title: Measure and calibrate the corpus recovery contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-5716-corpus-audit-budget
merge_target_branch: issue-5716-corpus-audit-budget
branch_strategy: Planning artifacts for this mission were generated on issue-5716-corpus-audit-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5716-corpus-audit-budget unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Measure, decide, validate
history: []
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent:
- .github/workflows/corpus-budget-diagnostic.yml
execution_mode: code_change
owned_files:
- tests/upgrade/test_mission_corpus_recovery.py
- .github/workflows/corpus-budget-diagnostic.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# WP01 — Measure and calibrate the corpus recovery contract

## Load Profile and Context

Load `python-pedro` through `spec-kitty agent profile show python-pedro` and the implement-action charter context before editing. Read this Mission's spec, plan, research and review feedback. Use the canonical owned-checkout runtime commands; do not hand-edit event logs, lane state or review verdicts.

## Objectives & Success Criteria

Obtain one bounded, uncensored hosted measurement of the exact failing node, including total and per-audit durations. Apply only an independently approved, evidence-calibrated correction and validate the entire existing contract. Preserve all eleven audits, memberships, inventories, gates, corruptions and healthy controls. A failure that prevents calibration must be reported honestly, not patched around to pass.

## Context & Constraints

Issue #5716 blocks unrelated PR #7071. Current-main logs show the shared 240-second backstop interrupts the later healthy-control loop. A local diagnostic stalled earlier at the existing 180-second subprocess boundary and does not size a CI limit. No permanent value has been selected.

Only this package's owned files may be changed for implementation. Do not touch production source, #7071's integration fixture, `pytest.ini`, module registries, shard timings, generated docs surfaces, other Missions, credentials, branch protections or required checks. Planning/research artifacts are maintained by the orchestrator outside this code-change ownership set.

## Subtasks & Detailed Guidance

### T001 — Hosted measurement

Create temporary workflow `.github/workflows/corpus-budget-diagnostic.yml`, limited to this diagnostic, on `ubuntu-24.04`, read-only permissions, `fetch-depth: 0`, the repository's pinned actions/dependencies and canonical warmup action. Use a push-only trigger restricted to branch `issue-5716-corpus-audit-budget` and path `.github/workflows/corpus-budget-diagnostic.yml`: one deliberate file addition starts one measurement, while Mission bookkeeping pushes do not. Do not use PR events or a new dispatch-only workflow (not registered on default). Check out before invoking the local warmup action, following `module-tests.yml`; use warmup mode `pr` and derive the same full-package coverage flags to avoid an unmeasured coverage-overhead difference. Do not open/bind a PR while the temporary workflow exists: the existing workflow-set equality gate would correctly fail. Never expand the workflow allowlist for this disposable job. Run only `tests/upgrade/test_mission_corpus_recovery.py::test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes`, serially, with diagnostic outer timeout <=900 seconds and job <=25 minutes. Do not change its inner subprocess timeout. Use a runner-temporary instrumentation plugin to time the real audit/CLI calls, corpus construction, inventories, recovery and gates, preserving return values/exceptions and distinguishing nested timings. Use an explicit runner-temp basetemp with `-o tmp_path_retention_policy=all`; otherwise successful pytest teardown removes the existing CLI evidence. Upload only logs, metrics, JUnit, source/runner/cache identifiers and the `cli-evidence` subtree even on failure, never the entire historical corpus. Publish the compact timing summary to the job summary as well as artifacts. Record compared-main SHA and `git diff --stat <main>...<measured> -- src/ tests/ pytest.ini` (expected empty). No retries.

### T002 — Decision checkpoint

Wait for the actual hosted result. Ask an independent evidence reviewer, distinct from the implementer and the final test-integrity reviewer, to assess source fidelity, all original controls, total/per-audit measurements and explicit bounded headroom. If measurement is incomplete or exposes a real failure, report and investigate within scope rather than guessing a final budget. All eleven audits must be recorded in their actual interleaved order: original, recovered, landed, then four attack/control pairs. An individual audit approaching the unchanged 180-second limit is a distinct bottleneck, not justification for raising the total alone. If total completes below 240 seconds, report the result without claiming that one green run calibrates CI variance; use the existing failure evidence and explicit headroom rationale, or stop for further measurement approval. Production semantics or scheduling changes require operator approval.

### T003 — Final correction

Apply only the justified test-local execution limit or demonstrated localized correction. If that correction belongs to a shared test fixture helper, first amend and revalidate the package ownership through the canonical tasks command; production source, `pytest.ini` and shard/scheduling policy still require scope approval. Remove disposable workflow wiring before opening the final PR, once its immutable run evidence is retained. Preserve a readable record of the measured source and final source. No global budget change or integrity-assertion edits.

### T004 — Validation and independent review

Validate the existing contract under the proposed final correction on the hosted upgrade shard. A local run is useful but cannot replace hosted validation: retain a recurrence of the documented early inner-180-second stall separately, do not assume its cause, and never size the CI budget from it. Any new failure signature is a real finding to classify. Run only directly affected fast siblings and named relevant architectural gates; CI owns full suites. Verify normal upgrade shard behavior and record any remaining pre-existing failures. Obtain an independent reviewer who did not implement the correction, and report every test added/changed with KEEP/RETIRE/SPLIT verdict, regression guarded and existing coverage.

## Test Strategy

Read CI before local execution. The sole expensive diagnostic is the named corpus test; never run a whole architectural/e2e/integration/performance suite, `make test-full`, or `-n auto`. Use `-n 0` for the diagnostic, at most `-n 2 --dist loadfile` for focused fast files. Lint/format only touched Python files with `uv run --frozen ruff check ...` and `ruff format --check --force-exclude ...`; match any existing configured type check applicable to changed typed code. No new type-ignore/noqa or relaxed gate.

Apply DIRECTIVE_041 and development-assist-test-cleanup: existing behavioral tests over realistic data, no inert self-comparison, config-value assertion, transient-shape pin, duplicate assertion or redundant control. At most one new focused test per distinct uncovered behavior; prefer existing coverage. Do not add a test just to assert a timeout marker.

## Review Guidance

The deliverable is not 'a larger timeout'. It is a completed measured contract plus the smallest justified correction. Review the evidence before its proposed value. Confirm every original attack and healthy control remains and real assertion failures still propagate. Distinguish an insufficient total budget from an individual slow/hung CLI invocation. No approval while a required implementation question remains unresolved.

## Progress & Status

Use canonical `agent tasks add-history`, `mark-status`, and `move-task` commands and the runtime-generated review surface. Never edit status frontmatter or event history by hand.
