---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: fix-6871-first-run-late-coord-01M6G9JR
mission_id: 01M6G9JRZRYNK7ZH67BG2XF312
generated_at: '2026-11-03T10:19:03.019842+00:00'
analyzer_agent: python-pedro
input_artifacts:
  spec.md:
    path: kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/spec.md
    sha256: 9d7522df09a9dd637b207d5e49a5df39908be0da6cd675518d74ec6a8da36e97
  plan.md:
    path: kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/plan.md
    sha256: acefe95c0f53940a40266ead602a54ef03a278562b6e17687e4278a692bb056f
  tasks.md:
    path: kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/tasks.md
    sha256: 1bc4e536ca3f69a15af9f4cebb9a24b35b1bd41558ca5c6e7e152edc6075b844
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  critical:
  medium:
  low:
  info:
  high:
findings: []
---

# Cross-Artifact Analysis: fix-6871-first-run-late-coord-01M6G9JR

**Scope**: `spec.md`, `plan.md`, `tasks.md`, the two WP files, and the code surfaces they name.
**Verdict**: no CRITICAL finding; the artifacts agree on the one change and the one window rule.

## Consistency

- Every `FR-###` in `spec.md` maps to a work package (`tasks.md` coverage table) and to a subtask
  that names the file it touches. No orphan subtask.
- `plan.md`'s Design section and `tasks.md` WP01 subtasks state the same rule in the same order
  (base selection → projection → assertion → approved-tip advance). They do not contradict.
- The two WP files' `requirement_refs` cover FR-001…FR-009 exactly once each.

## Ambiguities resolved before implementation

1. *"the gate"* — the issue means the projection teardown gate (`ProjectionTeardownGate`), not the
   reconciliation gate. The spec says "the tip this run verified (`coord_tip_after_projection`)",
   which is the gate's own compare-and-swap anchor, and the plan names the module. No leftover
   ambiguity in the code path.
2. *"survives"* — the spec's User Story 1 resolves it to "committed on the target ref before the
   branch is deleted", not "still readable in a worktree". The red test asserts the committed blob
   (`git show main:<path>`), not a working-tree file, matching the #6791 discipline.
3. *"first run"* — `is_resume=False`. The plan records that a resume's window is deliberately wider
   and must not be reused for a first run; the spec's Scope decisions section says why.

## Charter alignment

- Single canonical authority: the change selects a window base and calls the existing
  `bookkeeping_projection` seams; no second record selector or refusal text is introduced.
- Red-first: `tests/coordination/test_projection_teardown.py` carries three new cases, all verified
  failing at the base commit before the fix.
- No gate weakened: the resume base, the post-projection assertion, the projection teardown gate and
  the compare-and-swap branch delete are untouched; the first run is added to them.
- Terminology: "coordination commit", "late window", "coordination triple", "projection teardown
  gate" are used with their established meanings (module docstrings and ADR 2026-09-19-1).

## Coverage gaps accepted, with the reason

- **Issue #7082's single-agent / empty-lane-window shape** (`REVIEW_NOT_INDEPENDENT`, then
  `IMPLEMENTATION_MISSING`) is on the approval-evidence axis. It is not changed here: deciding
  whether one actor may review the work it implemented is a maintainer decision, and both refusals
  already name an executable recovery (`--attest-no-implementation <WP> --attest-reason ...`, and a
  genuinely different reviewer). The Mission pins that wording in
  `tests/consolidation/test_wp_evidence_recovery_wording.py` so the answer stays checkable, and
  reports the governance question to the operator instead of deciding it.
- **A first run that recorded no coordination anchor at all** keeps today's behaviour (no window
  can be built). Making it refuse is unprovable and would strand a Mission whose coordination
  placement does not resolve; it is named in the PR's `## Deferred`.

## Findings

None blocking. Proceed to implement.
