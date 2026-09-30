---
title: 'Mission Retrospective: 01KSMG8Y — Pre-Doctrine Test Stabilization'
description: 'Retrospective for the 01KSMG8Y Pre-Doctrine Test Stabilization mission: goal, the NFR-001 ≤ 75-failure gate, scope WP01-WP11, and the learnings carried forward.'
doc_status: deprecated
updated: '2026-05-30'
---
# Mission Retrospective: 01KSMG8Y — Pre-Doctrine Test Stabilization

**Date**: 2026-05-27
**Branch**: feat/pre-doctrine-stabilization-remediation
**Merge commit**: 56de9d565
**Retro author**: human-in-charge + claude-sonnet-4-6

---

## Mission Card

| | |
|---|---|
| **Goal** | Reduce confirmed test failures from ~249 to ≤75 before doctrine/charter feature work proceeds |
| **Gate** | NFR-001: ≤75 failures on full `PWHEADLESS=1 pytest tests/` run |
| **Scope** | WP01–WP09 (parallel fixes), WP10 (test-mark CI audit), WP11 (rebaseline + closeout) |
| **Pre-mission** | ~249 failures |
| **Post-mission** | 138 failures (19534 passed, 2 errors, 873s) |
| **Delta** | −111 failures (44% reduction) |
| **Gate met** | ❌ NO — 63 failures above threshold |

---

## Results by work package

| WP | Title | Review cycles | Outcome |
|----|-------|:---:|--------|
| WP01 | TOML escape fix + snapshot refresh | 1 | ✅ Approved, closed #1302 |
| WP02 | README Governance + chokepoint guards | 1 | ✅ Approved, closed #1308, #1309; partial #1310 |
| WP03 | Doctrine / glossary anchor + tactic repair | 1 | ✅ Approved, closed #1304 |
| WP04 | Status / lifecycle event drift | 1 | ✅ Approved, closed #1306 |
| WP05 | Charter integration suite regressions | **2** | ✅ Approved (cycle 2), closed #1307 |
| WP06 | `next` CLI exit-code regressions | 1 | ✅ Approved, closed #1305 |
| WP07 | Shared-package events drift residual | 1 | ✅ Approved, closed #1301 |
| WP08 | Charter synthesizer determinism | 1 | ✅ Approved, closed #1303 |
| WP09 | Misc debt — auth / invocation / mypy / mission switching | 1 | ✅ Approved; partial #1310; re-deferred #1317, #1318 |
| WP10 | CI test-mark audit | 1 | ✅ Approved |
| WP11 | Full-suite rebaseline + closeout | — | ✅ Human-in-charge (post-merge) |

10 of 11 WPs approved on first review cycle. 1 required a second cycle (WP05).

---

## What Went Well

### 1. Parallel sprint was genuinely effective

All 9 independent WPs (WP01–WP09) ran in parallel using background agents. The lane-based worktree model kept them isolated — no cross-WP file conflicts during implementation. Wall-clock time for all 9 implementations was roughly equal to the time a single sequential WP would have taken.

### 2. Tight issue-to-WP traceability

Each sub-issue (#1301–#1310) mapped cleanly to one or two WPs. The mission's planning upfront — confirming scope, owner, and acceptance gate per issue — meant reviewers had clear criteria and implementations had clear targets.

### 3. WP05 cycle 2 found a better solution

The cycle-1 rejection for WP05 was legitimate: the implementation touched `runtime_bridge.py` which was owned by WP06. The cycle-2 fix relocated the logic to `decision.py/_build_prompt_or_error`, which is both a more architecturally correct home for prompt-file resolution and eliminated the merge conflict risk. The review cycle did its job.

### 4. All 6 WP05 integration tests pass

The T017–T022 charter integration tests all pass on the feature branch. The functional goal of WP05 was met; the cycle-2 issue was purely about ownership boundaries, not correctness.

### 5. Mission merge completed without file conflicts

Despite 11 lanes merging into a single feature branch, the owned-files declarations in WP frontmatter kept lanes genuinely non-overlapping. `spec-kitty merge` completed cleanly on the first attempt after the two pre-merge blockers were resolved.

---

## Blockers and Friction

### 1. Review artifact `verdict` field not auto-synced with override fields

**What happened**: WP05 review-cycle-2.md was created with `verdict: rejected` (from the initial review template). The review passed, and the override fields (`review_artifact_override_at`, `review_artifact_override_reason`, etc.) were populated — but the `verdict:` key itself was not updated to `approved`. The `spec-kitty merge` gate reads `verdict`, not the override fields, so it blocked with `REJECTED_REVIEW_ARTIFACT_CONFLICT`.

**Resolution**: Manually changed `verdict: rejected` → `verdict: approved`, committed, pushed, re-ran merge.

**Root cause**: The override mechanism and the merge gate read different fields. Either the override flow should update `verdict`, or the merge gate should check override fields as authoritative when present.

**Recommendation**: When `review_artifact_override_actor` is populated, the merge gate should treat the override as the canonical verdict and log a warning instead of blocking. Alternatively, `move-task --to approved` with `--review-feedback-file` should atomically update `verdict:` in the latest review cycle artifact.

---

### 2. `TARGET_BRANCH_NOT_SYNCHRONIZED` before merge

**What happened**: The feature branch had 68 commits that hadn't been pushed to the remote when `spec-kitty merge` was invoked. The merge gate requires the remote to be synchronized before proceeding.

**Resolution**: `git push origin feat/pre-doctrine-stabilization-remediation`, then retry.

**Root cause**: No reminder or check at the point of invoking merge. This is a reasonable guard, but the error message could include the exact `git push` command needed.

**Recommendation**: The merge gate pre-flight should print the push command when it detects unsynchronized branches.

---

### 3. WP11 frontmatter missing `agent` and `shell_pid`

**What happened**: The `spec-kitty accept` check required `agent` and `shell_pid` fields in WP11 frontmatter. WP11 is a `human-in-charge` planning artifact and was created without these fields.

**Resolution**: Added `agent: "human:none:human-in-charge:human-in-charge"` and `shell_pid: "0"` to WP11 frontmatter, then force-approved.

**Root cause**: The WP template for `execution_mode: planning_artifact` with `role: human-in-charge` doesn't emit these fields. The accept check's field requirements weren't reflected in the template.

**Recommendation**: The `human-in-charge` WP template should include these fields with canonical placeholder values so newly created WPs don't fail accept checks.

---

### 4. `spec-kitty accept` misrouted (feature branch vs. mission branch)

**What happened**: Running `spec-kitty accept --mission pre-doctrine-test-stabilization-01KSMG8Y` on the feature branch (`feat/pre-doctrine-stabilization-remediation`) showed all WPs in `planned` — because the status events live on the mission branch (`kitty/mission-pre-doctrine-test-stabilization-01KSMG8Y`).

**Resolution**: Skipped `accept` and proceeded directly to `spec-kitty merge`.

**Root cause**: The accept command doesn't clearly communicate which branch it reads state from, and the feature branch check-out gives a misleading all-planned view.

**Recommendation**: `spec-kitty accept` should either auto-detect the mission branch from the mission slug or print a clear error: "Status events for this mission are on branch X; check out that branch or pass `--read-from-branch X`."

---

### 5. WP05 cycle 1: DoD file-ownership constraint not surfaced prominently

**What happened**: The implementing agent modified `runtime_bridge.py` despite the WP DoD explicitly stating "No changes to `runtime_bridge.py` in this lane (unless WP06 merged)." This was a straightforward DoD violation.

**Resolution**: Reviewer caught it; cycle-2 fixed it. No functional regression.

**Root cause**: The DoD constraint was listed as prose in the WP body but not surfaced as a machine-checkable invariant. The implementing agent read the WP but didn't weight the constraint highly enough against the pragmatic appeal of the simpler implementation location.

**Recommendation**: File-ownership constraints in `owned_files` should be surfaced as a pre-commit assertion: if a commit touches a file not in the WP's `owned_files`, the commit should be blocked with a clear message pointing to the WP file that owns it.

---

## Test Debt Analysis: Remaining 138 Failures

### Cluster A — Invocation CLI (21 failures) — **Priority: High**

`tests/specify_cli/invocation/cli/` (advise, do, profiles, invocations)

WP09 T037 addressed the `mode_of_work` field mismatch but the deeper routing architecture for the invocation subsystem is broken. These tests were not confirmed regressions in the original triage (#1310) — they are structural. Needs a dedicated remediation mission.

### Cluster B — Cross-cutting: encoding + versioning (19 failures) — **Priority: Low**

`tests/cross_cutting/encoding/` (9), `tests/cross_cutting/versioning/` + `test_version_isolation_integration.py` (10)

Pre-existing environment-specific failures. The encoding tests require a `spec-kitty encode` CLI surface not present in this build. The versioning tests fail due to subprocess version isolation issues in the test environment. Not mission-scope regressions.

### Cluster C — Planning workflow integration (9 failures) — **Priority: Medium**

`tests/tasks/test_planning_workflow_integration.py`

Repo-root detection failures in worktree context. These would have been latent during the mission itself (worktrees were used throughout) but didn't surface as implementation blockers. The `find_repo_root` function has edge-case failures in worktree subdirs and missing-git scenarios.

### Cluster D — Checklist template (9 failures) — **Priority: Low** (deferred)

`tests/specify_cli/test_command_template_cleanliness.py` (checklist)

The `spec-kitty.checklist` skill package is absent — explicitly re-deferred to #1317 per C-008 (re-deferred items must have a filed follow-on issue). Not a regression introduced by this mission.

### Cluster E — Finalize-bootstrap regressions (7 failures) — **Priority: High**

`tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py`

Typed frontmatter migration path is broken. These test the `finalize-tasks` bootstrap flow that every new mission creation depends on. If these failures reflect real bugs (not just test-environment drift), they are a blocker for mission creation reliability.

### Cluster F — Skills snapshots (8 failures) — **Priority: Medium**

`tests/specify_cli/skills/test_command_renderer.py` (codex, vibe snapshots)

Snapshot drift from WP01 template changes. These are "update the snapshot" tasks — low complexity, high failure count. Should have been part of WP01's scope. The snapshot update is a one-command fix; the failure count is misleading relative to the effort required.

### Cluster G — Prompt-file invariant (3 failures) — **Priority: Medium**

`tests/next/test_prompt_file_invariant.py`

New tests added by WP05 T019 (`_build_prompt_or_error` path) are failing in the error-handling branches (path missing on disk, OSError from stat). The core happy path passes. The implementation in `decision.py` needs the error branches to be hardened.

### Cluster H — Misc / architectural (63 failures) — **Priority: Low–Medium**

`test_intake` (7), `test_cli_smoke` (3), `test_acceptance_regressions` (6), architectural tests (5), audit tests (2), and others.

Mixed bag of pre-existing debt and test-environment-specific failures. Some (intake CLI, acceptance regressions, architectural dead-module checks) indicate real production surface issues; others (charter epic golden path E2E, clean-install-next) are environment-specific.

---

## Process Observations

### The parallel sprint model works at scale

Running 9 WPs in parallel with background agents, scheduling reviews as each completed, then unblocking dependents immediately — this is the right model for a mission of this shape. The primary bottleneck was review throughput, not implementation.

### Gate calibration matters

NFR-001 (≤75 failures) required eliminating ~174 of ~249 failures. The mission's 10 implementation WPs were scoped to confirmed regressions from the triage list (#1301–#1310). The math assumed those confirmed regressions accounted for ≥174 failures. In practice, many of the 249 original failures were pre-existing environment-specific debt that the WPs didn't touch. A gate grounded in "eliminate confirmed regressions" rather than an absolute floor would have been more achievable.

**Recommended for future missions**: Gate as "eliminate N% of confirmed regressions" rather than "reach floor of M absolute failures" when the baseline contains significant pre-existing debt of uncertain scope.

### Snapshot tests should travel with the change that breaks them

WP01 changed command templates. That change broke 8 codex/vibe snapshot tests. The snapshots should have been updated in the same WP01 commit. The current pattern — implement the change, leave the snapshots for "the next person" — creates a trailing failure count that makes the overall picture look worse than it is and creates work for the next mission.

### Owned-files enforcement needs tooling support

The WP05 cycle-1 failure was foreseeable. The `owned_files` manifest in WP frontmatter is authoritative, but there's no enforcement at commit time. A git hook or pre-move-task check that validates changed files against the WP's `owned_files` would catch this class of error before it costs a review cycle.

---

## Action Items

| Priority | Action | Owner | Tracking |
|----------|--------|-------|---------|
| High | Fix merge gate to treat `review_artifact_override_*` fields as canonical when present | spec-kitty core | File issue |
| High | Investigate finalize-bootstrap regressions (Cluster E — 7 failures on a mission-critical path) | next mission | File issue |
| High | Remediate invocation CLI subsystem regressions (Cluster A — 21 failures) | next mission | File issue |
| Medium | Add `git push` command to `TARGET_BRANCH_NOT_SYNCHRONIZED` error output | spec-kitty core | File issue |
| Medium | `human-in-charge` WP template: add canonical `agent` + `shell_pid` defaults | spec-kitty core | File issue |
| Medium | Update codex/vibe snapshots from WP01 template changes (Cluster F — 8 failures, one command) | quick fix | File issue |
| Medium | Harden `_build_prompt_or_error` error branches for path-missing and OSError cases (Cluster G) | WP05 follow-up | File issue |
| Medium | Add pre-move-task check: validate changed files against `owned_files` | spec-kitty core | File issue |
| Low | Resolve Cluster B (encoding/versioning) — characterize as environment-specific or real | triage | File issue |
| Low | Gate calibration: document "confirmed-regression elimination %" approach for future missions | planning process | CLAUDE.md note |

---

## Files Owned by This Mission

All changes landed in merge commit `56de9d565` on `feat/pre-doctrine-stabilization-remediation`.

```
docs/01KSMG8Y-closeout/baseline.md    — post-mission test baseline
docs/01KSMG8Y-closeout/retro.md       — this document
```
