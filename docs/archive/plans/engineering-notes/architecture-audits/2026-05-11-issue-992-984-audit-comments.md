---
title: 'Audit relationship to #992 and #984 — deep read'
description: 'Deep read relating the 2026-05 CaaCS audit to issues #992 and #984, classifying their strength on the findings under the brownfield-investigation paradigm.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Audit relationship to #992 and #984 — deep read

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

## Inputs

- **Audit referenced**: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` (CaaCS audit, 2026-05-08 base + 2026-05-09 multi-window expansion).
- **Prior crosscheck**: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-11-findings-vs-issues-update.md` (already classifies #992 as STRONG on F2 + brownfield; #984 as STRONG on F18, PARTIAL on F2).
- **Brownfield paradigm**: `brownfield-onboarding.paradigm.yaml` (investigate-before-changing, document/transfer first then refactor — DM-D).
- **Issues read on 2026-05-11**:
  - `gh issue view 992 --repo Priivacy-ai/spec-kitty --comments --json …` (full body + 1 comment).
  - `gh issue view 984 --repo Priivacy-ai/spec-kitty --comments --json …` (full body, 0 comments).
  - Metadata-only spot checks on linked tickets `#988, #989, #990, #991, #889` (Phase 1 of #992).

## Issue #992 — deep read

### Body summary

**Title**: *Epic: drain the bug queue by repairing domain boundaries*. **State**: OPEN. **Labels**: `bug`, `workflow`, `release`, `epic`. **Author**: Robert Douglass. **Assignee**: Stijn Dejongh. **Created**: 2026-05-05.

Issue 992 is a holistic queue-drain epic built on a survey of 10 open `bug` issues and 46 closed since 2026-04-21. Its core diagnosis: *"Spec Kitty currently has too many places acting as if they own workflow truth"* — `spec-kitty next`, `agent action implement/review`, `agent tasks move-task`, `agent tasks status`, `review`, `merge --dry-run`, real `merge`, dashboard materializers, SaaS sync, release/mission-review gates. Each is a projection of a few aggregates whose invariants are not centralized, producing the observed "whack-a-mole" pattern.

The epic proposes seven workstreams (W0–W6): TeamSpace canonical-import boundary, `WorkPackageLifecycle` authority, `ReviewCycle` aggregate, `MergeReadiness` parity, `SyncPublication` outcome model, `ReleaseEvidence` + review gates, and input/upgrade/encoding hygiene. Each names North Star invariants and concrete acceptance bullets. Queue-drain order is sequenced into Phase −1 (land 4 in-flight TeamSpace PRs), Phase 0 (cross-surface fixture harness), Phase 1 (active release bleeding: #991, #990, #988, #989, #889, #971), Phase 2 (promote aggregates), Phase 3 (older debt: #644, #662, #391). Definition-of-done requires *cross-boundary regression tests* and *dry-run-equals-real* parity.

The single comment, from stijn-dejongh (2026-05-07): the bug queue is accurate, but the work should *"start by reshaping the domain contracts and entry-points, then use the bug queue as a code-level acceptance criterion."* Reshape first, drain as proof.

### Linked work

| # | Title | State | Relevance |
|---|---|---|---|
| #988 | `next --json` can miss claimable WPs available to explicit agent action | OPEN | Phase 1 (W1 — WorkPackageLifecycle) |
| #990 | review-cycle artifact generation can wrap prior cycle frontmatter/body | OPEN | Phase 1 (W2 — ReviewCycle aggregate) |
| #991 | merge dry-run misses review artifact consistency failures | OPEN | Phase 1 (W3 — MergeReadiness parity) |
| #989 | new missions without `baseline_merge_commit` skip dead-code review | OPEN | Phase 1 (W5 — ReleaseEvidence) |
| #889 | `sync now` misclassifies teamspace ingress rejection as `server_error` | OPEN | Phase 1 (W4 — SyncPublication) |
| #822 | 3.2.0 stabilization epic | (open, parallel umbrella) | lifecycle subset under W1 |
| #391 | tech/functional debt epic | (open) | input/upgrade subset under W6 |
| #644 | encoding mixups | open | W6 |
| #662 | CI duplication | open | W5 |
| #945, #946, #961, #966, #783, #622, #551, #540 | closed lifecycle bugs | CLOSED | "Latent regression debt" under W1 |
| #904, #963, #960, #962, #949, #950, #676 | closed review-cycle bugs | CLOSED | W2 |
| #976, #953, #903, #716, #675, #574 | closed merge bugs | CLOSED | W3 |
| #952, #735, #746, #745, #744, #936 | closed sync bugs | CLOSED | W4 |
| #975, #967, #805, #830, #833, #968, #964 | closed release/CI bugs | CLOSED | W5 |
| #722, #721, #720, #674, #673, #760, #541, #539, #542 | closed input/upgrade bugs | CLOSED | W6 |
| Priivacy-ai/spec-kitty#980 | CLI TeamSpace mission-state repair | OPEN PR | Phase −1 cutover set |
| Priivacy-ai/spec-kitty-saas#150 | enforce TeamSpace ingress event contracts | OPEN PR | Phase −1 |
| Priivacy-ai/spec-kitty-runtime#19 | runtime side-log classification | OPEN PR | Phase −1 |
| Priivacy-ai/spec-kitty-tracker#14 | tracker TeamSpace mission payloads | OPEN PR | Phase −1 |
| Priivacy-ai/spec-kitty-events#20 | publish events 5.0.0 | OPEN PR | Phase −1 |

### Code paths the issue names

- `spec-kitty next`, `spec-kitty agent action implement/review` (W1)
- `spec-kitty agent tasks move-task`, `spec-kitty agent tasks status` (W1)
- `spec-kitty review`, `spec-kitty merge --dry-run`, real `spec-kitty merge` (W2, W3)
- dashboard/status materializers, SaaS sync/final-sync fan-out (W1, W4)
- `doctor mission-state --fix`, `--teamspace-dry-run` (W0)
- `_ensure_target_branch_checked_out`, repo-root resolution (mentioned indirectly via W1's "planning-artifact WPs could not resolve implementation workspace")
- No specific file-level paths are quoted; the epic operates at the *command-surface* level. The audit's F2 (`cli/commands/agent/{tasks,workflow,mission}.py`) is the implementation backing for those command surfaces but is not named in the issue body.

### Audit relationship — specific evidence

**F2 (`cli/commands/agent/{tasks,workflow,mission}.py` structural-remediation target)**

- #992 directly addresses the *concept* (multiple command surfaces independently owning the same truth) but does so at the domain-aggregate layer, not the file-structural layer.
- The audit adds evidence #992 lacks: specific complexity numbers (`finalize_tasks` CC=160, `move_task` CC=139, `status` CC=87, `review` CC=84, `map_requirements` CC=74), churn-and-co-change quantification (45 co-changes `tasks.py`↔`workflow.py` in 1y), and the bus-factor reading (89.5% single-author concentration in src/, 95.2% corpus-wide).
- The audit does not contradict #992; it sharpens it. Where #992 says "centralize invariants", the audit says "and while you do, the host file you are extracting from is a 3746-SLOC monolith with an F-160 function". Both diagnoses point at the same code.

**F15 (F2 hotspots ship without test updates ~70% of the time)**

- #992 implicitly addresses this through its Definition-of-Done bullet *"cross-boundary regression tests that prove the invariant at the next boundary"*, and Phase 0's *"cross-surface fixture harness"*. Neither names a numeric test-coverage target.
- The audit adds specific test:src churn ratios per file (`agent/tasks.py` 29.9%, `agent/workflow.py` 27.3%, `agent/mission.py` 31.6%) that justify why Phase 0 must come before Phase 1, not in parallel with it.
- No contradiction.

**Multi-window refactor-candidate confirmation**

- #992 does not reference the multi-window analysis; it does not need to. The audit confirms the F2 cluster is urgent under both full-history and 4-month velocity-adjusted lenses, which is independent confirmation of #992's "draining symptoms is not enough — reshape the contracts" thesis.

**Brownfield paradigm (DM-D, document/transfer first)**

- #992's structure (North Star Invariants → Workstreams → Phases → DoD) is itself a brownfield-shaped artifact. The comment from stijn-dejongh (2026-05-07) — *"start by reshaping domain contracts and entry-points, then use the bug queue as code-level acceptance"* — is a direct restatement of *investigate-before-changing*.
- The audit adds the missing direction: brownfield prescribes documenting the *current* domain contracts before reshaping. #992 jumps straight to target-shape; it does not require a transfer artifact for the current shape. That is a real gap.

### Useful audit comment for #992 (DRAFT — do not post)

```markdown
Adding some forensic backing from the recent CaaCS audit (`docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`, multi-window expansion `docs/archive/plans/engineering-notes/architecture-audits/2026-05-11-findings-vs-issues-update.md`) that lines up with this epic's diagnosis and may help calibrate Phase 0 / Phase 1 sequencing.

**Where the audit converges with this epic**

The audit's F2 finding is: the `src/specify_cli/cli/commands/agent/{tasks,workflow,mission}.py` cluster is the unambiguous structural-remediation target. Concretely:

- `agent/tasks.py`: 3746 SLOC, F-rated complexity, `finalize_tasks` CC=160, `move_task` CC=139.
- `agent/workflow.py`: F-rated, `status` CC=87, `review` CC=84.
- `agent/mission.py`: 2314 SLOC, `map_requirements` CC=74; `finalize_tasks` lives here despite the name.
- 45 co-changes between `tasks.py` and `workflow.py` in the trailing year (top temporal-coupling pair in src/).
- The cluster sits in the top-5 of *both* full-history and 4-month velocity-adjusted refactor-candidate lists — i.e., it is urgent under any time window.

That is the file-level shape underneath the "too many command surfaces own the same truth" diagnosis in the body. The audit therefore supports the comment from 2026-05-07: reshape the entry-points first, then drain the queue as acceptance.

**Where the audit adds evidence the epic does not have**

- F15 (audit): the F2 cluster ships without test updates in ~70% of commits (`tasks.py` 29.9% test:src ratio, `workflow.py` 27.3%, `mission.py` 31.6%). This is direct quantitative justification for Phase 0's "cross-surface fixture harness" requirement — the harness needs to exist before Phase 1 lands real workstream changes, otherwise lifecycle regressions ship invisibly. Worth promoting from "Phase 0 nice-to-have" to "Phase 0 blocker".
- F1 / bus factor (audit): 89.5% single-author concentration in src/. The doctrine artifact this epic produces (North Star Invariants → executable domain services) is the canonical mitigation; the epic implicitly addresses bus factor by lowering it from the file level to the aggregate level. Worth naming explicitly under "Non-Goals" or DoD.
- Brownfield paradigm (`brownfield-onboarding.paradigm.yaml`, DM-D): prescribes documenting the *current* contract before reshaping it. The epic specifies the target shape per workstream but does not require a transfer artifact for the current shape. Adding a one-paragraph "current contract" preamble per workstream would make rollback decisions cheaper.

**Suggested low-touch refinements**

- Add to Phase 0 acceptance: "Phase 1 workstreams may not land until the cross-surface fixture harness rejects at least one currently-passing F2-cluster test." (Forces real harness, not aspirational.)
- Tag W1/W2/W3 acceptance bullets with the specific F2-cluster file they touch, so the DoD is auditable at file level too, not only at command-surface level.

Happy to keep this here as audit context; not a blocker.
```

(≈400 words. Tone: additive, file-and-numeric-backed, no rework demand.)

## Issue #984 — deep read

### Body summary

**Title**: *agent tasks status can resolve the wrong checkout from a detached worktree*. **State**: OPEN. **Labels**: `bug`, `P1-bug`. **Author**: Robert Douglass. **Assignees**: (none). **Created**: 2026-05-05. No comments.

The bug repro: from a detached worktree at commit `e8eecc79` (post-merge of #981), `spec-kitty agent tasks status --mission stable-320-release-blocker-cleanup-01KQW4DF --json` reported all 4 WPs as `approved`, `done_count: 0`, `mission_number: null`. A fresh clone of `origin/main` at the same SHA reported all 4 as `done`, `done_count: 4`, `mission_number: 115`. Reducing `status.events.jsonl` directly in the detached worktree showed the correct `done: 4`. So: the command resolved back to the original local `main` checkout (divergent + stale) instead of reading the detached worktree.

**Impact**: post-merge verification can produce false negatives / false positives whenever reviewers use a detached worktree to verify a merged SHA without resetting their dirty local main.

**Suggested fix in body**: audit `_ensure_target_branch_checked_out`, `get_main_repo_root`, and related repo-root resolution in `agent tasks status` paths. For read-only status commands, prefer current-worktree artifact reads; or fail loudly. Add a regression test with two worktrees at different mission status.

### Linked work

No links to other issues or PRs in the body or comments. The only reference is to merged PR #981 (the SHA being verified, not a related fix).

### Code paths the issue names

- `_ensure_target_branch_checked_out` (function name)
- `get_main_repo_root` (function name)
- "repo-root resolution in `agent tasks status` paths"
- Implicit: `src/specify_cli/cli/commands/agent/tasks.py` (the CLI surface) and `src/specify_cli/agent_utils/status.py` (the rendering layer the audit flagged in F18).

The body does **not** explicitly name `agent_utils/status.py`. It names CLI behaviour and two specific function names. The function `get_main_repo_root` is the more interesting one for the audit story.

### Audit relationship — specific evidence

**F2 (`cli/commands/agent/{tasks,workflow,mission}.py`)**

- #984 is a symptom of F2: the bug surface is `agent tasks status`, which lives in `cli/commands/agent/tasks.py` and routes into `agent_utils/status.py`. The audit does not add new evidence here beyond what is already in F2.
- The audit does not contradict the issue; the function names cited in #984 are plausible call sites in the F2 cluster.

**F15 (test-update lag)**

- The "Suggested fix" requests a regression test with two worktrees — exactly the kind of test F15 says is systematically missing on this cluster. The audit reinforces the importance of *not* shipping the fix without that regression test.

**F18 (`src/specify_cli/agent_utils/status.py` under-tested, 19.0% test:src ratio, 570 SLOC, F-rated `_display_status_board` CC=53)**

- This is the strongest audit↔issue link. F18 says the kanban renderer module is under-tested; #984 reports the same module (or its caller) producing wrong reads under detached-worktree conditions.
- **Important nuance**: #984's pointer at `get_main_repo_root` suggests the bug may actually live in `agent_utils/status.py` (where the resolver is likely called) *or* in a shared repo-root resolution helper. The audit does not measure that helper's location specifically. The relationship is high-confidence but the exact file is not yet pinned by audit data.
- The F-53 `_display_status_board` renderer is **not** what's wrong in #984 — #984 is a *resolution* bug, not a *rendering* bug. The renderer just faithfully renders wrong inputs. That distinction matters for fix scope.

**Multi-window refactor-candidate confirmation**

- The 2026-05-11 multi-window refresh placed `agent_utils/status.py` as F#29 full-history and R#26 4-month — a slow-burn refactor candidate, not yet urgent. #984 is a concrete symptom that could escalate it. Worth noting in the issue if the fix shows the resolver is more deeply tangled than expected.

**Brownfield paradigm**

- DM-D prescribes documenting the current resolver contract before changing it. The fix proposed in the body (audit `_ensure_target_branch_checked_out`, `get_main_repo_root`, plus regression test) is brownfield-shaped: investigate first, then change. No paradigm gap.

### Useful audit comment for #984 (DRAFT — do not post)

```markdown
Some adjacent context from the recent CaaCS audit (`docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`) that may help scope the fix.

This bug sits inside two audit findings:

- **F18**: `src/specify_cli/agent_utils/status.py` is currently under-tested at a 19.0% test:src commit-ratio (21 src commits, 4 test commits, 570 SLOC). It also contains an F-rated `_display_status_board` (CC=53). It was flagged as the strongest "needs an investigation pass before its next change" file in the supporting-code tier.
- **F2**: the CLI entry path (`src/specify_cli/cli/commands/agent/tasks.py`, 3746 SLOC, `move_task` CC=139, `status` CC=87) is the urgent structural-remediation target across both full-history and 4-month windows.

That means whatever the actual resolver bug is (likely in or shared with `agent_utils/status.py` or a `get_main_repo_root` helper), it ships into a module that already has the lowest test ratio in the supporting tier and the highest churn / complexity in the core tier. F15 (audit) measured that ~70% of commits to the F2 cluster ship without matching test updates; the regression test requested in this issue's suggested-fix section is exactly the artifact F15 says is systematically missing.

One worth-pinning detail: this is a **resolution** bug, not a **rendering** bug. The F-53 `_display_status_board` faithfully renders whatever inputs it gets. So:

- The fix should not need to touch `_display_status_board` itself.
- The regression test should exercise the resolver in isolation (two worktrees, two different mission states, status command from each) before it exercises the rendered output. That keeps the test scoped and re-usable for the eventual F18 follow-up.

If the fix surfaces that `get_main_repo_root` is shared with `merge`, `next`, or `agent action`, that's relevant to issue #992's Workstream 1 (WorkPackageLifecycle authority) and worth cross-linking.

Audit references for whoever picks this up:
- `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — F2, F15, F18 in the findings section.
- `docs/archive/plans/engineering-notes/architecture-audits/2026-05-11-findings-vs-issues-update.md` §"Multi-window refresh" — `agent_utils/status.py` slow-burn entry.

Not a blocker for the fix; just noting the surrounding terrain.
```

(≈340 words. Tone: scoping aid, not redirection.)

## Cross-issue observations

**Are #992 and #984 related to each other?**

- **Yes, structurally**. #984 is a Phase 1-adjacent symptom of #992's Workstream 1: `agent tasks status` reading the wrong checkout is a *WorkPackageLifecycle / read-side projection* bug — exactly what #992's W1 promises to centralize. #984 is **not** in #992's enumerated Phase 1 list (#988, #989, #990, #991, #889, #971), but it belongs there on topic.
- **Same files**: yes. Both ultimately touch `cli/commands/agent/tasks.py` (the F2 cluster), and #984 likely also touches `agent_utils/status.py` (F18) plus a shared repo-root resolver.
- **Same root cause?** Partially. #992's framing — *multiple command surfaces independently owning the same truth* — fits #984: `agent tasks status` is silently inheriting a different "current repository" answer than the user expected, because resolution is not centralized. Adding #984 to #992's Phase 1 list (W1) would be a clean cross-link.

**Audit gaps relative to the two issues**

- #992 does not name the F15 test-update-lag finding by file/percentage. The audit can fill that in concretely.
- #984 does not name `agent_utils/status.py` even though F18 strongly implicates it. The audit can fill in the F18 connection and the resolver-vs-renderer distinction.
- The brownfield paradigm's "document the current contract before reshaping" prescription is absent from both issues; the audit adds that lens.

**Which comment is more impactful to post?**

- **#992** is the higher-impact target. It is the meta-epic; audit evidence injected here propagates to all Phase 1 work, helps justify Phase 0 sequencing, and the doctrine framing aligns with brownfield-onboarding. It is also assigned and active.
- **#984** is useful but narrower — the bug repro is already crisp, the suggested-fix is already correct, and the audit's contribution is mostly *scoping aid* and the resolver-vs-renderer distinction. Helpful but optional.

## Recommendation

### #992

- Option 1 (post as-is): viable. The draft is additive, file-numeric, no rework demand.
- Option 2 (slim): file references + audit doc link only. Loses the F15 sequencing argument and the brownfield "document current contract" suggestion — both of which are the highest-value pieces.
- Option 3 (don't post): the issue is already strong; the audit is a nice-to-have, not a blocker.

**Recommendation: Option 1 — post the draft as-is.** Justification: the F15-driven Phase 0 sequencing argument is genuinely new information and would meaningfully shift Phase 0's status from "scaffolding" to "blocker", which is the single highest-leverage change available to the epic.

### #984

- Option 1 (post draft as-is): viable. Adds the F18 link and the resolver-vs-renderer scoping note.
- Option 2 (slim): just "`agent_utils/status.py` is F18-flagged in the audit; regression test scope should be resolver-isolated; see audit at `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`." Three sentences.
- Option 3 (don't post): the issue's suggested-fix is already correct; the audit adds calibration, not direction.

**Recommendation: Option 2 — slim comment.** Justification: the bug is small and scoped; a long audit-context comment risks burying the existing fix-suggestion. A 3-sentence pointer to F18 and the resolver-vs-renderer distinction is enough.

## Methodology / caveats

- **No state changes** were made during this read: no comments posted, no labels altered, no issues touched. `gh issue view` calls were read-only.
- **Function names** cited in #984 (`_ensure_target_branch_checked_out`, `get_main_repo_root`) were not verified against current source. They are plausible based on naming conventions but a fix scoper should grep before committing to them.
- **Audit-file-vs-issue-file alignment**: the audit measured `src/specify_cli/agent_utils/status.py` at 570 SLOC with an F-53 `_display_status_board`. #984 does not explicitly name this file, only the CLI surface and two helper-function names. The link is inferential — strong, but inferential. The draft comments call this out honestly.
- **#992's Phase −1 (TeamSpace cutover PR set)** is not addressed by the audit at all; the audit's lens is structural-complexity, not migration-coordination. If a reviewer expects the audit to weigh in on Phase −1, they will be disappointed; that's not a contradiction, it's a scope mismatch.
- **No PR-level scan** was performed for in-flight fixes that might already address #984. The body cites no linked PR; the issue is plausibly still unowned.
- **Audit data is as of 2026-05-09 multi-window expansion**. Any commits to F2-cluster files between then and 2026-05-11 are not reflected in the numbers cited.
