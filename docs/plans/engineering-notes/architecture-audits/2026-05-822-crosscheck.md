---
title: 'CaaCS findings ↔ #822 open sub-issues cross-check'
description: 'Cross-check mapping the 2026-05 CaaCS audit findings onto the open sub-issues of epic #822 (3.2.0 stabilization and release readiness), with per-issue state.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# CaaCS findings ↔ #822 open sub-issues cross-check

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

## Inputs

- **Audit**: `<repo-root>/docs/architecture/audits/2026-05-spec-kitty-caacs.md` (commit `bc64dec6ee37dbbd6bc21a0a1aa3195f2bab1b57`, 2026-05-08).
- **Epic**: [Priivacy-ai/spec-kitty#822](https://github.com/Priivacy-ai/spec-kitty/issues/822) — "Epic: 3.2.0 stabilization and release readiness", state OPEN.
- **Issues read** (state captured 2026-05-08/09 via `gh issue view`):

| # | State at read | Title (truncated) |
|---|---|---|
| 822 | OPEN | Epic: 3.2.0 stabilization and release readiness |
| 971 | OPEN | mypy strict gate fails on current baseline |
| 889 | OPEN | sync now misclassifies teamspace ingress rejection as server_error |
| 952 | **CLOSED** | Successful agent state transitions still leak SaaS final-sync errors (was reopened post-PR#959 per epic comment, now closed again at read time) |
| 662 | OPEN | Resolve automated CI workflow duplication |
| 825 | OPEN | Restore push-time SonarCloud after project quality gate cleanup |
| 595 | OPEN | Backlog: close Sonar quality-gate debt on release-path coverage and hotspot review |
| 771 | OPEN | spec-kitty merge: auto-rebase stale lanes onto updated mission branch |
| 631 | OPEN | Document workaround for MCP agent root confusion with worktrees on Windows |
| 630 | OPEN | Replace shell=True subprocess calls in review/baseline.py and acceptance_matrix.py |
| 726 | OPEN | sorted() in scan_for_plans should key on filename, not full path |
| 728 | OPEN | clear_mission_brief should use unlink(missing_ok=True) |
| 729 | OPEN | --show truncates brief_hash to 16 chars |
| 629 | OPEN | Add @pytest.mark.windows_ci test for os.symlink fallback |
| 644 | OPEN | Encoding mixups: stop assuming UTF-8 by default |
| 740 | OPEN | Notify users when SpecKitty starts being used and no upgrade is available |
| 323 | OPEN | Printing a page from the dashboard loses the end of it |
| 306 | OPEN | Offline queue fills at 10,000 events and starts dropping new sync events |
| 260 | OPEN | Worktree 'incompatbility' when changing to worktree sub-directory (referenced from #631) |
| 253 | OPEN | Confusion with worktrees (referenced as "docs evidence only") |
| 303 | OPEN | Use node-id set union in CI selector audit (epic says "do not schedule without current repro") |
| 317 | OPEN | Unable to install via pip (epic says "do not schedule without current repro") |

Issues from the epic body that were already closed at read time and are therefore **excluded from the main maps**: #967, #966, #964, #968, #904, #848 (epic's "blocker tranche" — closed by mission `stable-320-p1-release-confidence-01KQTPZC` per epic comments). Note on #952 in the closed-issue addendum below.

## Audit findings (canonical numbering for this doc)

The numbering follows the audit's executive summary, hotspot table, triage matrix, and cross-cutting observations. F1–F5 mirror the audit's own "Top findings" list; F6–F12 cover the additional structural items the audit raises explicitly elsewhere (triage matrix and cross-cutting observations).

- **F1 — Bus factor effectively 1.** 89.5% of `src/` commits in 1y are by one author; 14 of 15 top hotspots >90% single-author. (Audit §1, "Bus factor / knowledge map".)
- **F2 — `cli/commands/agent/{tasks,workflow,mission}.py` is the strongest refactor target.** Three files, ~7,955 SLOC, contain five of the seven worst-complexity functions in the repo (`finalize_tasks` CC=160, `move_task` CC=139, `status` CC=87, `review` CC=84, `map_requirements` CC=74). Top-three temporal-coupling pair (45 co-changes between `tasks.py` and `workflow.py`). Note: `finalize_tasks` lives in `mission.py`, not `tasks.py`, despite the name — itself a smell.
- **F3 — Pipeline trust is healthy.** Firefighting frequency is genuinely low (~0.3% of commits after stripping false positives). The team trusts the merge pipeline.
- **F4 — Project is alive and accelerating.** 1001 commits to `src/` in 1y, 2026-Q1 exceeds the previous five months combined; last 30 days = 193 commits.
- **F5 — Three empty `src/` leftover dirs.** `src/runtime/`, `src/dashboard/` (top-level — distinct from `src/specify_cli/dashboard/`), and `src/constitution/` contain only stale `__pycache__/`. Cleanup candidate.
- **F6 — Duplicated `task-prompt-template.md`.** `missions/software-dev/templates/task-prompt-template.md` and `templates/task-prompt-template.md` co-edited 15× in 1y. Likely connascence-of-meaning bug; one is dead-code-by-edit-count.
- **F7 — Template ↔ dispatcher coupling is load-bearing but high-volume.** Pairs #11, #14, #18, #19 in the temporal-coupling table all show command-template `.md` files co-changing with their CLI dispatchers 12–18×/y. Designed coupling, but worth a template-loader abstraction. (Audit cross-cutting observation #2.)
- **F8 — `cli/commands/charter.py` decomposition.** 2934 SLOC, MI=C, three E-rated functions (`interview` E=38). Effectively four CLI verbs in one file. (Triage matrix "Important + not urgent".)
- **F9 — `cli/commands/init.py` decomposition.** 1018 SLOC, F-94 `init`. Worst MI in the CLI command layer after `charter.py`. (Triage matrix.)
- **F10 — `next/runtime_bridge.py` is a hub, not a bridge.** 2552 SLOC, F-46, rank #21 by churn, rank #7 by SLOC. (Triage matrix.)
- **F11 — D-rated migrations need cleanup.** `m_0_10_8_fix_memory_structure.py` (F-47), `m_3_1_1_charter_rename.py` (D-27), `m_3_2_0_codex_to_skills.py` (D-24), `m_3_2_3_unified_bundle.py` (D-22). Parallelisable, low-risk. (Triage matrix.)
- **F12 — `sync/` package is a coherent cluster needing a second maintainer, not a refactor.** High internal coupling, low external coupling. (Cross-cutting observation #3 — explicit non-finding for refactor; finding for ownership.)
- **F13 — No `tests/` overlay.** Audit cannot tell a CC=160 function with 95% coverage from one with no tests. (Limitations #2 and follow-up #9 — explicit blind spot.)
- **F14 — No `kitty-specs/` overlay.** Strongest causal coupling in the codebase (feature-spec ↔ source) is invisible to the current run. (Limitations #1 and follow-up #10.)

## Forward map: Finding → matching #822 sub-issues

For each F#, listing every OPEN #822 sub-issue that overlaps. STRONG = direct topical match; PARTIAL = same area / adjacent concern; WEAK = distant relationship that requires interpretation.

### F1 — Bus factor = 1

No matching open sub-issue. The epic does not track the knowledge-transfer or co-maintainership question at all. **Zero matches.**

### F2 — `agent/{tasks,workflow,mission}.py` refactor target

No matching open sub-issue. The epic frames 3.2.0 strictly as stabilization, not refactor; it does not track the high-CC concentration in `agent/` despite this being the audit's strongest "both unstable and known-defective" signal. **Zero matches.**

### F3 — Pipeline trust healthy

This is a non-finding (positive signal). No issue should match.

| Issue | State | Strength | Reason |
|-------|-------|---------:|--------|
| #662 | OPEN | WEAK | "CI workflow duplication" is adjacent to pipeline trust — duplicate runs slow the gate but the gate itself is healthy. |
| #825 | OPEN | WEAK | Push-time SonarCloud being quarantined is a specific gate-quarantine, not a trust failure; matches the *theme* of pipeline maintenance. |
| #595 | OPEN | WEAK | Sonar quality-gate debt is gate hygiene, not trust failure. |

### F4 — Project alive and accelerating

Non-finding (positive signal). **Zero matches.**

### F5 — Three empty src/ leftover dirs

No matching open sub-issue. The epic does not track the cleanup. **Zero matches.**

### F6 — Duplicate `task-prompt-template.md`

No matching open sub-issue. The epic body and currently-open issues do not mention the template duplication. **Zero matches.**

### F7 — Template ↔ dispatcher coupling load-bearing

No matching open sub-issue. **Zero matches.**

### F8 — `cli/commands/charter.py` decomposition

No matching open sub-issue. **Zero matches.**

### F9 — `cli/commands/init.py` decomposition

No matching open sub-issue. **Zero matches.**

### F10 — `next/runtime_bridge.py` is a hub

No matching open sub-issue. **Zero matches.**

### F11 — D-rated migrations cleanup

| Issue | State | Strength | Reason |
|-------|-------|---------:|--------|
| #629 | OPEN | WEAK | Touches a migration (`m_0_8_0_worktree_agents_symlink.py`) but for Windows test coverage, not complexity rating. Same area, different concern. |

### F12 — `sync/` cluster needs a second maintainer

| Issue | State | Strength | Reason |
|-------|-------|---------:|--------|
| #889 | OPEN | PARTIAL | `sync now` misclassification touches `sync/batch.py` — one of the cluster files the audit calls out as healthy-but-monopolised. Issue is a behavioural bug, not an ownership question, but lives in the exact subsystem F12 names. |
| #306 | OPEN | PARTIAL | Offline queue drop-mode lives in `sync/queue.py` and `sync/emitter.py` — same cluster. Same caveat: behaviour bug, not ownership. |

### F13 — No tests/ overlay (audit blind spot)

No matching open sub-issue. **Zero matches.** (Test-related issue #967 was closed before this read.)

### F14 — No kitty-specs/ overlay (audit blind spot)

No matching open sub-issue. **Zero matches.**

## Reverse map: Open #822 sub-issue → matching audit findings

For each OPEN #822 sub-issue, which F# (if any) it matches.

| Issue | Title | Matches | Strength | One-line reason |
|-------|-------|---------|---------:|-----------------|
| #971 | mypy strict gate fails on baseline | F13 (test/quality overlay) | WEAK | Strict-mypy is type-coverage; audit explicitly notes it cannot see test/coverage overlays. Adjacent concern, not a direct call-out. |
| #889 | sync now teamspace classification | F12 | PARTIAL | Lives in `sync/batch.py`, a file in the cluster F12 says is healthy-but-monopolised. |
| #952 | **CLOSED** at read time | — | — | Excluded from main maps (see addendum). |
| #662 | CI workflow duplication | F3 | WEAK | Pipeline-hygiene topic; audit confirms pipeline trust is healthy so duplication is wastage, not risk. |
| #825 | Restore push-time SonarCloud | F3 | WEAK | Same theme as #662. |
| #595 | Sonar quality-gate debt | F3, F13 | WEAK | Gate debt is pipeline hygiene; coverage portion overlaps F13 (audit could not see coverage). |
| #771 | merge auto-rebase stale lanes | F2 (peripherally) | WEAK | `merge.py` is in the audit's hottest cluster (rank #5 churn, rank #4 temporal coupling at 26 co-changes with `implement.py`). The audit flags `merge.py` as F-63 `_run_lane_based_merge_locked`. Issue is about UX behaviour, not the F-rated function, but lives in the same file. |
| #631 | MCP worktree root confusion (docs) | None | — | Docs/UX issue; no audit signal on the worktree-MCP boundary. |
| #630 | shell=True subprocess on Windows | None | — | `review/baseline.py` and `acceptance_matrix.py` are not in the audit's top-30 hotspots. No structural signal. |
| #726 | sorted() filename key | None | — | One-line nit; not in any hotspot. |
| #728 | unlink(missing_ok=True) | None | — | One-line nit; not in any hotspot. |
| #729 | brief_hash truncation UX | None | — | UX/docs question; not in any hotspot. |
| #629 | symlink fallback Windows test | F11 | WEAK | Touches a migration (`m_0_8_0_…`) — same area as F11, different concern. The migrations the audit flags as D-rated are different files (`m_0_10_8`, `m_3_1_1`, `m_3_2_0`, `m_3_2_3`). |
| #644 | Encoding policy / UTF-8 assumptions | None | — | Cross-cutting policy concern; the audit did not surface encoding-handling as a hotspot. |
| #740 | "no upgrade available" UX | None | — | UX-only; not in any hotspot. |
| #323 | Dashboard print clipping | None | — | UI bug; the dashboard JS file (`dashboard/static/dashboard/dashboard.js`) is rank #15 by churn but the audit treats it as expected coupling with `dashboard/scanner.py` (rank #16). The print-CSS issue is not surfaced by churn. |
| #306 | Offline queue drop mode | F12 | PARTIAL | Lives in `sync/queue.py` and `sync/emitter.py` — F12 cluster. Behaviour bug, but same subsystem. |
| #260 | Worktree sub-directory incompatibility | F2 (peripherally) | WEAK | `core/worktree.py` is in the audit's hot cluster (rank #24). Issue is an MCP/editor-config problem, not a code-structure problem. |
| #253 | "Confusion with worktrees" (docs/UX) | None | — | Pure UX/onboarding; the epic notes this as docs evidence only. |
| #303 | CI selector audit set-union | None | — | CI workflow logic; not in audit scope. Epic says "do not schedule without current repro". |
| #317 | pip install failure | None | — | Packaging issue; not in audit scope. Epic says "do not schedule without current repro". |

## Two gap lists

### Gap list 1 — Audit findings without an open #822 issue

These are forensic signals that nobody is currently tracking under the 3.2.0 epic.

1. **F1 — Bus factor.** Audit's #1 finding. No issue tracking the knowledge-transfer / co-maintainership question.
2. **F2 — `agent/{tasks,workflow,mission}.py` refactor target.** Audit's strongest "both unstable and known-defective" signal. No issue tracking decomposition of `tasks.py` (3746 SLOC), `workflow.py` (1895 SLOC), or `mission.py` (2314 SLOC, contains the misnamed `finalize_tasks` F-160).
3. **F5 — Empty `src/` leftover dirs** (`src/runtime/`, `src/dashboard/`, `src/constitution/`). Trivial cleanup, not tracked.
4. **F6 — Duplicate `task-prompt-template.md`** at two paths, 15 co-edits/y. Connascence-of-meaning bug not tracked.
5. **F7 — Template ↔ dispatcher coupling abstraction.** Audit suggests evaluating a template-loader abstraction; not on the epic.
6. **F8 — `cli/commands/charter.py` decomposition** (2934 SLOC, three E-rated functions). Not tracked.
7. **F9 — `cli/commands/init.py` decomposition** (F-94 `init`, 1018 SLOC). Not tracked.
8. **F10 — `next/runtime_bridge.py`** (2552 SLOC, F-46 — bridge or hub?). Not tracked.
9. **F11 — D-rated migrations** (`m_0_10_8`, `m_3_1_1`, `m_3_2_0`, `m_3_2_3`). Migration cleanup not tracked.
10. **F12 — `sync/` cluster ownership.** Audit explicitly recommends "a second maintainer" rather than refactor; not tracked as an ownership/onboarding issue.
11. **F13 — Test-coverage overlay on F-rated functions.** Audit follow-up #9 ("re-run with `tests/` in scope"). Not tracked.
12. **F14 — `kitty-specs/` ↔ `src/` temporal coupling.** Audit follow-up #10. Not tracked.

### Gap list 2 — Open #822 sub-issues without forensic backing

These exist on the epic but the audit did not surface a structural signal under them. Some are valid scope-by-design (UX nits, docs); some may be over-tracked relative to the structural risk.

1. **#631** — MCP/worktree docs. UX/docs concern.
2. **#630** — `shell=True` on Windows. Files not in top-30 hotspots.
3. **#726** — `sorted()` key. One-line nit.
4. **#728** — `unlink(missing_ok=True)`. One-line nit.
5. **#729** — `brief_hash` truncation. UX question.
6. **#629** — Windows symlink test. Test gap (audit cannot see tests).
7. **#644** — Encoding policy. Cross-cutting policy; not a hotspot.
8. **#740** — Upgrade-available notification. UX-only.
9. **#323** — Dashboard print CSS. UI-only.
10. **#260** — Worktree sub-directory MCP confusion. Editor-config issue.
11. **#253** — Worktree onboarding confusion. Docs/UX.
12. **#303** — CI selector audit. CI logic, out-of-scope.
13. **#317** — pip install failure. Packaging, out-of-scope.

Items where the forensic backing is **WEAK / PARTIAL** rather than absent: #971 (F13 weak), #889 (F12 partial), #662 (F3 weak), #825 (F3 weak), #595 (F3+F13 weak), #771 (F2 weak), #306 (F12 partial). These are the only issues with any audit signal at all; everything else in gap list 2 has zero structural backing.

## Methodology / caveats

- **Issue state was checked at read time** (2026-05-08/09). Two issues that the prior research pass treated as open are now closed:
  - **#952** ("Successful agent state transitions still leak SaaS final-sync errors") — per the 2026-05-04 epic comment, was reopened during mission `stable-320-p1-release-confidence-01KQTPZC` after WP02 hosted-sync drain proof. At read time it shows CLOSED again. Excluded from main maps.
  - The epic's "blocker tranche" (#967, #966, #964, #968, #904, #848) was closed in the same mission. These were prominent in the epic body but are not currently open work; they are excluded from the main maps.
- **No interpretive quoting of issue content was needed.** Every match in the maps above is based on file/path references in the issue body or labels (e.g., #889 explicitly names `sync/batch.py`, #306 names `sync/queue.py` and `sync/emitter.py`, #629 names `m_0_8_0_…`).
- **No issues failed to fetch.** All 21 issues read returned full JSON via `gh issue view`.
- **Match strength is conservative.** Files-in-the-same-package counts as PARTIAL only when the audit explicitly names the package as a cluster (F12 `sync/`). Files-in-the-same-cluster but unnamed counts as WEAK (e.g., #771 for `merge.py` in F2's broader cluster).
- **The audit's tactic is forensic-history, not behavioural.** That is why so many open issues — UX bugs, one-line correctness nits, packaging concerns — have no audit backing. This is **not** evidence the issues are wrong; it is evidence that history-based forensics cannot see them. Cross-checking is direction-agnostic; a behavioural-test-oriented audit would produce a different gap list.

## Closed-issue note (informational only)

Five of the six already-closed epic-blocker issues had clear behavioural roots that the audit *would* surface if it had `tests/` and behavioural data in scope:

- **#967** (status test suite hangs) → would map to F13 (test overlay missing).
- **#966** (task-board progress reporting) → would map to F2 (`agent/status.py` is rank #30, in the same cluster).
- **#964** (skill YAML frontmatter) → no audit signal; mission template / packaging concern.
- **#968** (retired checklist leftovers) → would map to F11 (migration / cleanup theme).
- **#904** (stale rejected-review verdict) → would map to F2 (review-cycle policy, lives in `agent/workflow.py` cluster).
- **#848** (uv.lock / installed pin drift) → no audit signal; packaging concern.

Listed here only because they are mentioned prominently in the epic body and a reader of #822 may expect them in the main maps. They are out of scope for the active forward/reverse maps because they are no longer open.
