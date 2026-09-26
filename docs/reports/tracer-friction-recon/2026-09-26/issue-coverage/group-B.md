---
doc_status: active
updated: '2026-09-26'
---

# Planner-Priti — Group B issue-coverage check

**Group B themes:** coord-branch-worktree (76), status-lanes-move-task (45), merge-accept-pipeline (28), event-log-reducer (6), multi-clone-environment (6), zeitgeist-moment-publication (3), destructive-op-safety (2), safe-commit-git-plumbing (2). That is **168 tracer items from 51 missions**.

**Profile applied:** planner-priti (role planner; modes: decomposition, sequencing, risk-analysis, prioritisation; directive 003 decision-documentation). I also applied the plan-action charter tactics `analysis-extract-before-interpret` (extract the items, then cluster), `problem-decomposition` (one cluster = one fixable thing) and `eisenhower-prioritisation` (P-levels on the drafts). I worked read-only on GitHub and the repo; nothing was filed, commented or labelled.

**Verdicts:** CLOSED-ONLY 4, COVERED 9, PARTIAL 14, UNCOVERED 5 (32 clusters). 20 items were design notes or already-resolved context and were left unclustered (listed under Honest limits).

## Clusters → verdict → issues

| ID | Kind | Cluster (short) | Missions / items | Max sev | Verdict | Open issues | Closed issues |
|---|---|---|---|---|---|---|---|
| B-01 | both | Commit placement/bookkeeping resolves the destination from the meta.json target_branch frozen at specify time (protected main) instead of the live mis… | 5 / 13 | high | **PARTIAL** | #3477(p), #4625(p), #3536(e), #3553(a) | #3466, #2739 |
| B-02 | both | Mission create/specify on a protected main mints no non-protected mission branch (SK-09): HEAD stays on main with an untracked scaffold; for coord top… | 5 / 8 | high | **PARTIAL** | #4632(p), #3477(p), #2533(a), #2602(a) | #2739 |
| B-03 | both | There is no operator-facing command to flatten or clear an existing coordination branch: the CLI's own remedy text prescribes it, operators hand-edit … | 2 / 3 | high | **PARTIAL** | #2618(p), #3272(p), #4169(a), #4979(a) | — |
| B-04 | cause | Planning or primary branch history diverges from the coordination and lane branches (a rebase after coord exists, or planning edits made directly on t… | 2 / 2 | high | **COVERED** | #2273(e), #4905(a) | — |
| B-05 | both | Lane branches go stale relative to the mission tip | 4 / 5 | high | **PARTIAL** | #3945(p), #3936(p), #4889(a), #1711(a) | — |
| B-06 | cause | The implement/claim bootstrap auto-commits kitty-specs content (WP frontmatter, base_commit, status) onto the lane branch | 4 / 5 | high | **COVERED** | #3931(e), #4905(p), #2570(p) | #2980 |
| B-07 | improvement | Agents working inside a lane have no discoverable seam for writing mission tracer or planning files to the coord/primary surface | 5 / 5 | high | **PARTIAL** | #3931(p) | #2980 |
| B-08 | cause | Status commands (move-task, mark-status, status emit) run from a lane-worktree cwd read the lane's frozen status copy, which gives a false 'Illegal tr… | 4 / 5 | high | **COVERED** | #2570(e), #2160(p) | #2549 |
| B-09 | cause | Coord/primary split-brain for lifecycle artifacts | 6 / 7 | high | **COVERED** | #2160(e), #2334(e), #5025(p), #2683(p), #5023(p) | — |
| B-10 | cause | Coord-husk reads | 1 / 4 | high | **COVERED** | #5002(e), #4979(e) | #4966 |
| B-11 | cause | Implement and the guards ignore the mission's declared single_branch topology | 6 / 9 | high | **PARTIAL** | #4828(p), #1619(p), #2602(a) | — |
| B-12 | cause | implement/claim is not transactional | 5 / 5 | high | **PARTIAL** | #3968(p), #3969(p), #4075(a), #4003(a), #3897(p) | — |
| B-13 | cause | Lane identity has two uncoordinated sources: the static lanes.json WP-to-lane plan and the dynamic --base sequential allocator | 2 / 2 | high | **UNCOVERED** | #3433(a), #3944(a) | #4945 |
| B-14 | cause | mark-status/move-task reliability under the (now retired) sync store: silent hangs (exit 124), LayoutCutoverIncompleteError tracebacks on success, 'pr… | 6 / 8 | high | **CLOSED-ONLY** | #2555(p) | #3680, #3715, #3625 |
| B-15 | both | The mark-status surface is unscoped and dishonest | 5 / 7 | high | **UNCOVERED** | #3578(a), #4937(a) | #2962 |
| B-16 | cause | Tool-authored bookkeeping is left uncommitted or only partly committed (move-task, mark-status, setup-plan, review verdicts) | 7 / 7 | high | **COVERED** | #3933(e), #4228(e), #3471(p), #5007(e), #2570(p) | — |
| B-17 | cause | The issue-matrix gate fires at per-WP approved/done instead of at the mission terminus, so no WP can advance while any mission-wide issue lacks a verd… | 3 / 3 | high | **COVERED** | #5007(e), #5011(p) | — |
| B-18 | cause | After a reject->fix->approve cycle, the merge review-artifact gate refused with REJECTED_REVIEW_ARTIFACT_CONFLICT, because approvals were status trans… | 3 / 3 | high | **CLOSED-ONLY** | — | #2275 |
| B-19 | both | Acceptance-matrix lifecycle: the auto-stubbed matrix is not surfaced until accept blocks on it, a descoped FR leaves a stale pending row, and accept's… | 3 / 4 | medium | **COVERED** | #4162(e), #4232(p), #4243(p) | — |
| B-20 | both | Accept/merge fail-open | 2 / 4 | high | **PARTIAL** | #4891(e), #3894(p), #4934(a), #4943(a) | — |
| B-21 | improvement | Gate numbers and acceptance are measured before lane consolidation | 2 / 3 | high | **PARTIAL** | #3966(p), #3894(p) | — |
| B-22 | cause | Writers to shared mission artifacts are not serialised | 2 / 3 | high | **COVERED** | #4887(e), #4974(e), #2482(e) | — |
| B-23 | cause | safe-commit has no WP-lifecycle awareness | 4 / 4 | high | **UNCOVERED** | #3468(a), #4161(a) | — |
| B-24 | cause | safe_commit's `git stash push --staged`/`pop --index` round-trip mangled the index on partially staged or untracked files: spec-commit reported commit… | 2 / 3 | high | **CLOSED-ONLY** | #4722(a) | #4888 |
| B-25 | both | Destructive-op residuals | 4 / 4 | high | **PARTIAL** | #4762(p), #4228(p), #3970(a), #4933(a) | #4907 |
| B-26 | cause | Zeitgeist approval moments are dropped | 2 / 3 | high | **UNCOVERED** | #4809(a), #3044(a), #4215(a) | — |
| B-27 | both | Multi-clone and shared-host hazards | 4 / 6 | high | **PARTIAL** | #4228(p), #4666(a), #4252(a), #3215(a) | — |
| B-28 | cause | Event-log birth and read-semantics drift | 4 / 4 | medium | **PARTIAL** | #4027(e), #4963(a) | #3780, #2960 |
| B-29 | improvement | Status-transition UX: `agent status emit --help` shows the illegal for_review->approved in one step, and the error does not name the legal next hop | 2 / 4 | medium | **PARTIAL** | #3859(p), #4574(a) | — |
| B-30 | cause | Branch-context resolver blind spots | 3 / 3 | medium | **UNCOVERED** | #1619(a) | — |
| B-31 | cause | Semantic merge hazards that git and lint do not catch | 2 / 2 | high | **PARTIAL** | #1979(p), #3936(a) | — |
| B-32 | cause | Subtask completion inference fails open | 1 / 3 | high | **CLOSED-ONLY** | — | #2511 |

Fit key: (e) exact, (p) partial, (a) adjacent.

## Cluster detail (gaps and notes)

### B-01 — PARTIAL
Commit placement/bookkeeping resolves the destination from the meta.json target_branch frozen at specify time (protected main) instead of the live mission/PR branch, so spec-commit, plan/tasks auto-commit, finalize-tasks, move-task and status emit refuse PROTECTED_BRANCH_REFUSED while HEAD is on a non-protected branch; lanes are also cut from that stale main (SK-11/12/13/21).
- Evidence: `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:9`; `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:22`; `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:297`; `kitty-specs/org-activation-scan-dirs-01KZY1PT/tracer-tooling-friction.md:224`
- Tracer-cited: SK-09, SK-10, SK-11, SK-12, SK-13, SK-21
- #3477 (open, partial): specify --topology single_branch from a checkout on main persists a dead-on-arrival target_branch: main — Covers the scaffold writing the poison value (single_branch only); not placement honouring the live branch nor recovery.
- #4625 (open, partial): safe-commit refuses main while specify targets it: two branch policies in one CLI — Policy split, not the stale-meta placement read.
- #3536 (open, exact): commit-router: lanes-topology status-transition bookkeeping refused (PROTECTED_BRANCH_REFUSED) with no coord branch to fall back on — Exactly the LANES sub-case (items 44/105, SK-11).
- #3553 (open, adjacent): finalize-tasks target_branch persist: attribution-baseline edge, #1619 reconciliation, --json schema — Follow-ups of the #3482 escape-hatch fix.
- #3466 (closed, exact): finalize-tasks: --target-branch escape hatch does not reach WP-status bookkeeping — Closed 2026-08-18 by PR #3482; tracer evidence (missions 2026-08-09..08-14) predates the fix.
- #2739 (closed, partial): spec-commit / commit-router: un-followable refusals ... on protected-primary + coord-topology missions — Closed 2026-09-03; B01/B02 guidance fixes. Evidence predates close.
- **Gap:** No open issue asks for (a) a sanctioned CLI to retarget a mission's recorded target_branch (#3466 noted no migrate subcommand exists) or (b) placement to detect meta-vs-live-branch divergence and name a followable remedy. Evidence all predates the #3482/#2739 fixes, so a re-verification is needed before filing.

### B-02 — PARTIAL
Mission create/specify on a protected main mints no non-protected mission branch (SK-09): HEAD stays on main with an untracked scaffold; for coord topology the coordination branch exists without a materialised worktree, safe-commit refuses both main and the coord branch (HEAD not on it) and spec-commit's materialise-then-retry fallback builds the coord worktree from HEAD without the uncommitted files, so the retry fails identically.
- Evidence: `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-tooling-friction.md:21`; `kitty-specs/legacy-cleanup-split-dossier-queue-migration-01M0MGHB/tracer-tooling-friction.md:55`; `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/tooling-friction.md:66`; `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:7`
- Tracer-cited: #2367, #2581, SK-09, SK-12
- #4632 (open, partial): mission create permits protected-branch scaffolding while safe-commit refuses — reconcile or document the split — Open triage question only; no behaviour change proposed.
- #3477 (open, partial): specify --topology single_branch from a checkout on main persists a dead-on-arrival target_branch: main — single_branch variant; proposes refusing at scaffold or recording a mission branch.
- #2533 (open, adjacent): PR-bound mission with --start-branch gets redundant coord topology; coordination worktree stranded empty — Stranded-empty coord worktree + spec-commit split-brain fallback.
- #2602 (open, adjacent): Revisit pr_bound=>coord topology derivation for solo --start-branch missions — Topology derivation half.
- #2739 (closed, partial): spec-commit / commit-router: un-followable refusals ... (B01/B02) — Closed 2026-09-03; legacy-cleanup evidence (2026-08-22, 3.2.6rc3) predates.
- **Gap:** Coord-topology variant on protected main (deadlock: no commit path at all) and the materialise-then-retry fallback not carrying the caller's uncommitted planning files are not in any open issue; #4632 is still an undecided triage question.

### B-03 — PARTIAL
There is no operator-facing command to flatten or clear an existing coordination branch: the CLI's own remedy text prescribes it, operators hand-edit meta.json under a doctrine exception, and a manual flatten loses the genesis->planned bootstrap events that lived only on the coord branch, so implement or next then reports 'WP not finalized' until finalize-tasks is re-run.
- Evidence: `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:19`; `kitty-specs/common-docs-structural-move-01KW3SBK/tracers/tooling-friction.md:43`; `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:20`
- Tracer-cited: #900, #903, SK-01
- #2618 (open, partial): Unify flatten_mission() into a single canonical seam (doctor --fix vs mission close --discard divergence) — Internal seam; doctor --fix only covers never-created branches.
- #3272 (open, partial): Flatten drops the coord status surface's cut-over seed events — Same lost-events mechanism, for backfill seeds rather than WP bootstrap events.
- #4169 (open, adjacent): mission close --discard cannot commit its own flatten when target_branch has been deleted — Another flatten entry point.
- #4979 (open, adjacent): doctor coordination --fix ... flattens a live coord mission as 'never created' — The inverse hazard: an unwanted flatten.
- **Gap:** Nothing tracks a sanctioned `mission flatten` for a live (created) coordination branch that carries the full coord event log, including WP bootstrap events, onto the primary surface.

### B-04 — COVERED
Planning or primary branch history diverges from the coordination and lane branches (a rebase after coord exists, or planning edits made directly on the PR branch). Lane allocation then conflicts on lanes.json and status files that may not be hand-edited, and no CLI re-strands coord or the lanes onto the new base.
- Evidence: `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:17`; `kitty-specs/verdict-seam-boundary-hardening-01KZG179/tracers/tooling-friction.md:12`
- Tracer-cited: #3209, SK-01
- #2273 (open, exact): feat(coordination): add first-class 'rebase mission onto moved base' operation for coord branch + lane worktrees — Same recovery gap and the same manual procedure.
- #4905 (open, adjacent): coord / lanes_with_coord: 'agent action implement' commits tasks/WP01-*.md onto the coordination branch — add/add PlanningCommitMergeConflictError — Same PlanningCommitMergeConflictError symptom, from a different cause.

### B-05 — PARTIAL
Lane branches go stale relative to the mission tip. implement cuts lanes from a base that predates the mission's own latest commits (a false 0-failure baseline), reuses a surviving stale lane branch even with --base, and each mission-branch status write leaves the open lanes stale on shared kitty-specs, so dependent-lane allocation and consolidation conflict.
- Evidence: `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:21`; `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:25`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:3`; `kitty-specs/charter-catalog-coherence-01M2XQQF/tracer-tooling-friction.md:23`
- Tracer-cited: #4972
- #3945 (open, partial): Offer implement --include-approved to base a claim on approved sibling lanes — Covers approved-sibling content missing from a lane base, not a stale mission tip or stale-branch reuse.
- #3936 (open, partial): Dependency-lane auto-merge conflict has no guided resolution or overlap warning — Covers the consolidation-conflict symptom.
- #4889 (open, adjacent): implement WP## silently re-cuts a deleted lane branch from the coordination tip — The inverse case (branch deleted); this cluster is a surviving stale branch that gets reused.
- #1711 (open, adjacent): stale/frozen worktree lane rewind is reported as generic force override — Diagnostic only.
- **Gap:** No open issue says implement must (a) cut or refresh lanes from the current mission tip, or (b) detect that an existing lane branch is not a descendant of the mission tip and offer a reset or merge-forward (--base currently does not override). #4972 residual (lanes/stale_check refuses on .kittify/metadata.yaml conflicts) is also untracked.

### B-06 — COVERED
The implement/claim bootstrap auto-commits kitty-specs content (WP frontmatter, base_commit, status) onto the lane branch. safe-commit only warns, and move-task or the review gate hard-refuses later. The gate's suggested remedy, a directory-wide `git restore` from the planning tip, deletes issue-matrix/acceptance-matrix files or pulls in unrelated planning.
- Evidence: `kitty-specs/common-docs-structural-move-01KW3SBK/tracers/tooling-friction.md:66`; `kitty-specs/custom-mission-guard-failure-blocking-inert-01M0STY0/tracer-tooling-friction.md:193`; `kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT/tracer-tooling-friction.md:10`; `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:26`
- Tracer-cited: #1862, #2160
- #3931 (open, exact): WP prompt says write kitty-specs in the lane; move-task then blocks it — Covers the warn-then-block lag (F-25/F-33), the overly broad restore remedy (F-30: should restore from the merge-base) and the template/gate contradiction.
- #4905 (open, partial): coord / lanes_with_coord: 'agent action implement' commits tasks/WP01-*.md onto the coordination branch — The coordination-branch variant of the claim commit carrying a PRIMARY-kind WP file.
- #2570 (open, partial): Multi-lane /implement loop friction (lanes topology) — Friction #2 (lane-branch pollution).
- #2980 (closed, exact): commit guard WARNS, move-task BLOCKS — Closed. Re-observed after close (per #3931 and custom-mission-guard, 2026-08-24), so this is a regression or an incomplete fix.

### B-07 — PARTIAL
Agents working inside a lane have no discoverable seam for writing mission tracer or planning files to the coord/primary surface. Direct kitty-specs edits in the lane commit silently and then block move-task. An `agent tracer-append` command exists (write-side-seam mission), but the mission-tracer-files procedure and the WP prompts never route agents to it.
- Evidence: `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/tooling-friction.md:20`; `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/tasks/WP10-tracer-writer.md:58`; `kitty-specs/coord-authority-trio-degod-01KX7094/tracers/implement.md:116`; `kitty-specs/mission-resolver-port-01KX1C05/tracer-tooling-friction.md:19`
- Tracer-cited: #2549, #2980
- #3931 (open, partial): WP prompt says write kitty-specs in the lane; move-task then blocks it — Template/gate contradiction; does not name tracer-append as the fix.
- #2980 (closed, adjacent): commit guard WARNS, move-task BLOCKS — Closed.
- **Gap:** Doctrine gap: packs/built-in/procedures/mission-tracer-files.procedure.yaml does not mention `spec-kitty agent tracer-append` or lane routing (checked in the repo). No issue asks to wire the existing seam into the procedure and prompts.

### B-08 — COVERED
Status commands (move-task, mark-status, status emit) run from a lane-worktree cwd read the lane's frozen status copy, which gives a false 'Illegal transition planned->for_review', and/or commit status.* onto the lane branch while printing 'Using planning repo's kitty-specs'. The cd also persists across harness shell calls and silently corrupts later state writes.
- Evidence: `kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/tracer-tooling-friction.md:113`; `kitty-specs/common-docs-structural-move-01KW3SBK/tracers/tooling-friction.md:53`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-approach.md:18`; `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:43`
- #2570 (open, exact): Multi-lane /implement loop friction (lanes topology): ... move-task lane-branch pollution ... — Friction #2: status commands must route to the resolved surface regardless of cwd and read the reconciled log.
- #2160 (open, partial): Coord topology: unify artifact authority for task/status surfaces — Parent epic.
- #2549 (closed, exact): move-task --force from a lane worktree commits placement-partition status.* to the lane branch — Closed 2026-08-15 (PR #3437). Evidence from 2026-08-31 and 2026-09-06 postdates the close, so this is a residual or regression.
- **Gap:** Residual after #2549. #2570 is still open, but it would help to add the post-close witnesses (next-committed-state-authority, runtime-advance-guard) to it.

### B-09 — COVERED
Coord/primary split-brain for lifecycle artifacts. Review cycles, acceptance/issue matrices, analysis reports and cutover seeds get written to one partition while the gates read the other. Artifacts end up committed on both sides, and a squash merge clobbers the newer tracer or matrix copy with an older one.
- Evidence: `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:11`; `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tracer-tooling-friction.md:12`; `kitty-specs/reliability-papercut-sweep-01KWD0V5/tracers/tooling-friction.md:40`; `kitty-specs/tasks-py-degod-01KWF08S/tracers/tooling-friction.md:46`
- Tracer-cited: #2160, #2275
- #2160 (open, exact): Coord topology: unify artifact authority for task/status surfaces during the implement/review loop — P0 epic for this class.
- #2334 (open, exact): Cross-worktree planning-artifact duplication: kitty-specs state lives in N copies
- #5025 (open, partial): accept: a hand-written acceptance-matrix.json on the planning branch is silently ignored under coord
- #2683 (open, partial): research and plan split artifact authority in coord-topology missions
- #5023 (open, partial): Decision ledger is dual-partitioned: PRIMARY working-tree reads/writes vs COORD commit routing

### B-10 — COVERED
Coord-husk reads. When the coordination worktree is not materialised, reads fall through to the empty primary (decision open -> MISSION_NOT_FOUND; tracer-append clobbers a populated file with a fresh header). `doctor coordination --fix` without the remote coord branch is an adjacent unresolved surface.
- Evidence: `kitty-specs/coord-read-fail-closed-01M38VVH/tracer-tooling-friction.md:10`; `kitty-specs/coord-read-fail-closed-01M38VVH/tasks/WP02-tracer-fail-closed.md:49`; `kitty-specs/coord-read-fail-closed-01M38VVH/tracer-design-decisions.md:3`; `kitty-specs/coord-read-fail-closed-01M38VVH/tracer-design-decisions.md:7`
- Tracer-cited: #4950, #4959, #4966, #4979
- #5002 (open, exact): Epic: Coord husk reads empty primary — an unmaterialised coordination worktree must fail closed — Epic still has 2 of 4 children open.
- #4979 (open, exact): doctor coordination --fix in a checkout without the remote coordination branch flattens a live coord mission — The adjacent surface the tracer explicitly left out of scope.
- #4966 (closed, exact): decisions service resolves meta.json via the coord husk — Closed; fixed by the coord-read-fail-closed mission.

### B-11 — PARTIAL
Implement and the guards ignore the mission's declared single_branch topology. The workspace resolver honours a stale multi-lane lanes.json over meta.json, so implement allocates a lane worktree and the code commit is stranded on an undeclared lane branch. lanes.json is computed with lanes and sparse worktrees are left orphaned. The for_review ancestry guard and dependency-lane auto-merge demand a lane-planning branch that is never created, and events stamp execution_mode 'worktree'. Related facet: topology defaults do not scale down for small fixes.
- Evidence: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:211`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:662`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:710`; `kitty-specs/spdd-reasons-activation-split-brain-01M1K6VN/tracer-tooling-friction.md:469`
- #4828 (open, partial): First-class single-branch-direct implement mode for solo sequential missions — The positive capability; does not describe the defect that single_branch is already declared but ignored.
- #1619 (open, partial): Epic: Unify mission execution context across coord/main/lane topology — Umbrella.
- #2602 (open, adjacent): Revisit pr_bound=>coord topology derivation for solo --start-branch missions — Topology-sizing facet (item 10).
- **Gap:** No issue says: when meta.json topology is single_branch, implement/allocator/lanes computation and the for_review implementation-commit guard must use the mission's write branch and never create or require lane branches (SK-69/91/199/152/146).

### B-12 — PARTIAL
implement/claim is not transactional. It mutates meta.json (the vcs lock), WP frontmatter, lanes.json and charter metadata before gating or allocation fails, which leaves dirty out-of-scope files in the shared checkout. The claim moves a WP to in_progress without generating its prompt. A failed allocation parks the WP in blocked, recoverable only with --force. finalize-tasks --target-branch mutates frontmatter before failing.
- Evidence: `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/design-decisions.md:35`; `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-tooling-friction.md:267`; `kitty-specs/coord-primary-partition-lock-01KWZ46V/tracer-tooling-friction.md:19`; `kitty-specs/org-activation-scan-dirs-01KZY1PT/tracer-tooling-friction.md:224`
- Tracer-cited: #2795, SK-13
- #3968 (open, partial): Init/transition preflight: echo topology, worktrees ... and next mutation before mutating (P1.5) — Preflight visibility, not atomicity.
- #3969 (open, partial): Explicit abandon / resume / clean-partial semantics
- #4075 (open, adjacent): finalize-tasks persists TasksCompleted before failed status-bootstrap commit — Same mutate-before-fail class in finalize-tasks.
- #4003 (open, adjacent): meta.json raw reads in git/ref_advance.py bypass the fail-closed reader (_meta_change_is_vcs_lock_only) — Code for the vcs-lock dirty classification (#2795 cause).
- #3897 (open, partial): Epic: Mission-lifecycle robustness — preflight + abandon/clean-partial — Parent epic.
- **Gap:** No issue requires implement/claim to gate before mutating, and to roll back meta/frontmatter/lease on failure (including prompt generation being atomic with the claim, and a failed allocation not leaving WPs blocked).

### B-13 — UNCOVERED
Lane identity has two uncoordinated sources: the static lanes.json WP-to-lane plan and the dynamic --base sequential allocator. The allocator minted a lane-b colliding with the planned lane-b (two live WPs sharing one worktree). WPs added after planning have no lanes.json entry, default to lane-a, and trip the staleness gate.
- Evidence: `kitty-specs/org-pack-authoring-diagnostics-01KZY463/tracer-tooling-friction.md:204`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:139`
- #4945 (closed, adjacent): re-running finalize-tasks after removing an executed WP re-letters the surviving lanes onto existing lane branches — Closed 2026-09-24; a lane-identity instability, but a different trigger.
- #3433 (open, adjacent): a work package present in the event log but absent from tasks/ passes both status doctor and lane computation
- #3944 (open, adjacent): Provide a documented way to add a subtask to a WP after finalize-tasks — Post-finalize additions, for subtasks only.
- **Gap:** Searched: 'lanes.json post-planning WP', '--base allocator lane collision', 'lane-a default'. Nothing open.

### B-14 — CLOSED-ONLY
mark-status/move-task reliability under the (now retired) sync store: silent hangs (exit 124), LayoutCutoverIncompleteError tracebacks on success, 'project sync store is locked', and writes swallowed by a body_queue 'project_only layout' precondition.
- Evidence: `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-tooling-friction.md:282`; `kitty-specs/cascade-asset-silent-drop-01M0RME0/tracer-tooling-friction.md:306`; `kitty-specs/cascade-org-inert-01M07E9P/tracer-tooling-friction.md:9`; `kitty-specs/custom-mission-guard-failure-blocking-inert-01M0STY0/tracer-tooling-friction.md:152`
- #3680 (closed, exact): Writers stall ~4 min on cutover_pending machine layout — Closed 2026-08-31; evidence (2026-08-17..08-24) predates.
- #3715 (closed, exact): sync: project-store-migrate hard-fails ...; machine stuck in cutover_pending — Closed 2026-08-31.
- #3625 (closed, exact): project sync store is locked on large stores is SQLite BEGIN IMMEDIATE self-contention — Closed 2026-08-27.
- #2555 (open, partial): Coord-topology implement-review loop friction: move-task recovery cascade, sync-daemon hang — Still open; its sync-daemon hang item is now moot.
- **Gap:** Likely resolved: src/specify_cli/sync/ no longer exists and there are no 'project_only layout' strings in src. No post-close witnesses. Suggest trimming the stale sync-hang item from #2555.

### B-15 — UNCOVERED
The mark-status surface is unscoped and dishonest. Subtask IDs restart at T001 in every WP and mark-status has no --wp flag, so it silently writes to the first WP and reports success; status emit also lacks --wp. It prints 'row updated' when nothing changed. Its only statuses are done/pending, so a legitimately skipped subtask must be recorded falsely as done.
- Evidence: `kitty-specs/cascade-org-inert-01M07E9P/tracer-tooling-friction.md:11`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:684`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:724`; `kitty-specs/reconcile-flake-family-01M34HR7/tracer-tooling-friction.md:79`
- #3578 (open, adjacent): Rolling a work package back to planned resets its subtask roster with no operator-visible signal
- #4937 (open, adjacent): move-task gate refusals exit 0 — Same 'dishonest outcome' class, different command.
- #2962 (closed, adjacent): mark-status cannot find subtask IDs the shipped template tells you to author — Closed 2026-07-28.
- **Gap:** Confirmed in code: tasks.py mark_status takes only task_ids/--status done|pending/--mission/--owned-checkout/--auto-commit/--json, with no --wp. Searched 'mark-status --wp', 'subtask collide', 'mark-status success no write'.

### B-16 — COVERED
Tool-authored bookkeeping is left uncommitted or only partly committed (move-task, mark-status, setup-plan, review verdicts). Every dirty-tree gate (record-analysis, merge, implement's 'Planning artifacts not committed', advance_branch_ref) then refuses on the tool's own writes or another mission's writes, forcing manual commits between every WP.
- Evidence: `kitty-specs/reliability-papercut-sweep-01KWD0V5/tracers/tooling-friction.md:37`; `kitty-specs/dossier-guard-reexport-analyze-cleanup-01M0NHRT/tracer-tooling-friction.md:334`; `kitty-specs/charter-epic-golden-path-nfr-budget-01M35H35/tracer-tooling-friction.md:141`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:790`
- Tracer-cited: #2102, #2251
- #3933 (open, exact): setup-plan/move-task commit only a subset of their own writes; commit_sha null
- #4228 (open, exact): record-analysis refuses on any dirty path and its remediation (commit or stash) is unsafe in a shared checkout
- #3471 (open, partial): Auto-commit-off parallel-lane setup churn
- #5007 (open, exact): Execution friction: ... review-cycle artifacts block the next WP transition — Friction 2.
- #2570 (open, partial): Multi-lane /implement loop friction (allocator serialized behind its own uncommitted frontmatter write)

### B-17 — COVERED
The issue-matrix gate fires at per-WP approved/done instead of at the mission terminus, so no WP can advance while any mission-wide issue lacks a verdict (--force and --done-override-reason do not bypass it). finalize-tasks also clobbers a populated matrix, and the evidence check is lexical.
- Evidence: `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:12`; `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:24`; `kitty-specs/verdict-seam-boundary-hardening-01KZG179/tracers/tooling-friction.md:13`
- #5007 (open, exact): Execution friction: per-WP approval gated by mission-wide issue-matrix — Friction 1.
- #5011 (open, partial): Residual: finalize-tasks scaffolds issue matrix from spec.md only — Adjacent to the finalize-regenerates-matrix facet.
- **Gap:** The 'finalize clobbers a populated issue-matrix' facet (verdict-seam, 2026-08-08) is not stated explicitly in #5007; consider adding it as a comment.

### B-18 — CLOSED-ONLY
After a reject->fix->approve cycle, the merge review-artifact gate refused with REJECTED_REVIEW_ARTIFACT_CONFLICT, because approvals were status transitions and not persisted artifacts.
- Evidence: `kitty-specs/reliability-papercut-sweep-01KWD0V5/tracers/tooling-friction.md:44`; `kitty-specs/tasks-py-degod-01KWF08S/tracers/tooling-friction.md:44`; `kitty-specs/tasks-py-degod-wave2-01KWH9EQ/tracers/tooling-friction.md:17`
- Tracer-cited: #2275
- #2275 (closed, exact): move-task --to approved over rejected latest review artifact does not persist an approved artifact — merge blocked by REJECTED_REVIEW_ARTIFACT_CONFLICT — Closed 2026-08-05 (PR #3211, verdict-seam rebuild). All evidence (2026-06-30..07-02) predates.
- **Gap:** Resolved. No post-close witnesses in the tracer corpus.

### B-19 — COVERED
Acceptance-matrix lifecycle: the auto-stubbed matrix is not surfaced until accept blocks on it, a descoped FR leaves a stale pending row, and accept's artifact checks are a hardcoded software-dev list that mutates optional_missing in place.
- Evidence: `kitty-specs/tasks-py-degod-01KWF08S/tracers/tooling-friction.md:45`; `kitty-specs/verdict-seam-boundary-hardening-01KZG179/tracers/tooling-friction.md:15`; `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-design-decisions.md:50`; `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-design-decisions.md:62`
- Tracer-cited: #2330, #3016, #3085
- #4162 (open, exact): The acceptance matrix ships as placeholder scaffold, hard-blocks accept, and has no command to populate it
- #4232 (open, partial): acceptance-matrix.json is a finalize-time snapshot of functional ids only — Later-added or descoped criteria.
- #4243 (open, partial): acceptance-matrix scaffold only emits FR-* rows; no CLI path to add NFR/SC/C criteria
- **Gap:** Descoped-FR auto-retire and config-driven, mission-type-aware artifact checks are only implied. Low priority.

### B-20 — PARTIAL
Accept/merge fail-open. AcceptanceSummary.ok ignores skipped/blocked checks (the mechanism behind #4891), and merge does not re-verify acceptance, so accept is the only chokepoint. The tracer deliberately left merge-side defense-in-depth unticketed, in the PR body only.
- Evidence: `kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/tracer-design-decisions.md:15`; `kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/tracer-design-decisions.md:40`; `kitty-specs/terminus-safety-invariant-01M2XFT7/tracers/design-decisions.md:29`; `kitty-specs/accept-fail-closed-missing-lanes-01M3CC1V/tracer-design-decisions.md:43`
- Tracer-cited: #4764, #4891
- #4891 (open, exact): accept silently skips the entire acceptance-matrix gate when lanes.json is absent — Open P0; the tracer mission is its fix.
- #3894 (open, partial): Epic: Shared integration-view builder for accept and merge (P0.3) — Shared view, not a merge-side acceptance assertion.
- #4934 (open, adjacent): orchestrator-api accept-mission never evaluates the acceptance summary — Second accept door that bypasses the check.
- #4943 (open, adjacent): merge records WPs done and lands a mission whose issue-matrix rows are still 'in-mission' — Merge-side gate gap for the issue matrix.
- **Gap:** No issue for merge asserting a valid, current acceptance record (accepted_at and accept_commit reachable, summary ok) before landing. The tracer said explicitly that this lives only in a PR body.

### B-21 — PARTIAL
Gate numbers and acceptance are measured before lane consolidation. Approved lanes are not yet merged into the mission branch, so counts look like regressions, and nothing in the spec-kitty output flags that the approved lanes are unconsolidated. The acceptance matrix's only reader runs pre-consolidation, which makes the enforcer circular.
- Evidence: `kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/tracer-tooling-friction.md:94`; `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/tracers/design-decisions.md:109`; `kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/tracer-approach.md:103`
- Tracer-cited: #3884
- #3966 (open, partial): accept evaluates the shared integration view, not a pre-consolidation primary checkout — Fixes accept's surface only.
- #3894 (open, partial): Epic: Shared integration-view builder for accept and merge
- **Gap:** No issue asks status/next/gate output to warn 'N approved lanes not yet consolidated' or to record the branch/commit alongside every gate count.

### B-22 — COVERED
Writers to shared mission artifacts are not serialised. The verdict lock covers verdict-vs-verdict only, finalize/accept/gate writers of the acceptance matrix are unlocked, the #2482 restage clobber is still open, and parallel WP agents race on status.events.jsonl.
- Evidence: `kitty-specs/dossier-guard-reexport-analyze-cleanup-01M0NHRT/tracer-tooling-friction.md:334`; `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-design-decisions.md:46`; `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-design-decisions.md:50`
- Tracer-cited: #2482, #4858
- #4887 (open, exact): Verdict-matrix RMW serialization is opt-in at command sites, not enforced at the shared write seam
- #4974 (open, exact): accept writes acceptance-matrix.json back from its pre-check snapshot with no lock
- #2482 (open, exact): Stray primary matrix residue can clobber a fresher coord-side acceptance-matrix on re-stage

### B-23 — UNCOVERED
safe-commit has no WP-lifecycle awareness. It accepts and pushes implementation commits for a WP still in planned (the event log and git disagree), and emits ACTIVE_WP_CONTEXT_AMBIGUOUS/STALE/SCOPE_VIOLATION noise when implement was skipped. An orchestrator that dispatches without transitioning its predecessors leaves dependents refused on dependencies_not_satisfied.
- Evidence: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:421`; `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:80`; `kitty-specs/accept-path-remediation-honesty-01M0TWZP/tracer-tooling-friction.md:247`; `kitty-specs/custom-mission-guard-failure-blocking-inert-01M0STY0/tracer-tooling-friction.md:235`
- #3468 (open, adjacent): Scope-guard false positives ... flagged ACTIVE_WP_SCOPE_VIOLATION — Different false-positive causes.
- #4161 (open, adjacent): next --result success advances the mission FSM past implement's gates, desyncing it from lanes — A lane/FSM desync, different door.
- **Gap:** Searched 'safe-commit planned WP commit', 'committed-but-planned WP detection'. Nothing open.

### B-24 — CLOSED-ONLY
safe_commit's `git stash push --staged`/`pop --index` round-trip mangled the index on partially staged or untracked files: spec-commit reported committed:false 'unchanged' on a real diff and left a dangling stash. The fix swapped in `git commit --only` and dropped the whole-index backstop.
- Evidence: `kitty-specs/verdict-seam-boundary-hardening-01KZG179/tracers/tooling-friction.md:7`; `kitty-specs/user-content-preservation-01M3549Q/tracer/approach.md:12`; `kitty-specs/user-content-preservation-01M3549Q/tracer/approach.md:24`
- Tracer-cited: #4888, Priivacy-ai/spec-kitty#588
- #4888 (closed, exact): safe_commit stash dance fails on partially staged files — Closed; fixed by the user-content-preservation mission (2026-09-22). verdict-seam evidence (2026-08-08) predates it.
- #4722 (open, adjacent): safe-commit: a nonexistent requested path is either silently 'success' or aborts the whole batch — Open; a neighbouring false-success in the same command.
- **Gap:** Resolved. Residual design note: the whole-index backstop assert_staging_area_matches_expected is no longer called (tracer cites Priivacy-ai/spec-kitty#588, a pre-move repo). Worth one regression test, no issue needed.

### B-25 — PARTIAL
Destructive-op residuals. Unguarded `git branch -D` of lane or start branches (is-merged guard deferred). `git checkout <branch> -- kitty-specs/<mission>/` into the coord worktree clobbers the authoritative event log. `git stash` in a lane worktree steals a sibling lane's WIP because the stash stack is repo-global. Removal paths once reported 'Removed' while content was preserved.
- Evidence: `kitty-specs/refactor-stable-gate-substrate-01KWK3FY/tracers/tooling-friction.md:8`; `kitty-specs/user-content-preservation-01M3549Q/tracer/design-decisions.md:13`; `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-tooling-friction.md:16`; `kitty-specs/merge-destructive-op-safety-01M2XQF8/tracer-design-decisions.md:15`
- Tracer-cited: #2691, #4907
- #4762 (open, partial): merge --delete-branch --keep-worktree prints 'Cleaned up N lane branch(es)' while every git branch -D was refused — Misreporting only; no is-merged guard.
- #4228 (open, partial): record-analysis ... remediation (commit or stash) is unsafe in a shared checkout — Covers stash being unsafe across worktrees, for one command's advice.
- #3970 (open, adjacent): Machine-readable cleanup postcondition report
- #4933 (open, adjacent): merge silently discards uncommitted edits to any tracked file named meta.json
- #4907 (closed, exact): guard_destructive_removal 'Removed' misreport — Closed by user-content-preservation.
- **Gap:** No open issue tracks the deferred is-merged guard before `git branch -D` (src uses -D in mission_create.py, missions/_create.py, mission_type.py, orchestrator_api/commands.py). Nothing guards path checkouts over coord status files, and no doctrine says 'never stash in lanes'.

### B-26 — UNCOVERED
Zeitgeist approval moments are dropped. `--review-result-json` records `review_result`, but StatusTransitionPayload requires `evidence` for approved/done, so every approval's WPStatusChanged fails validation and is not broadcast (a WARNING printed next to 'OK'). A logged-out session also silently skips publication.
- Evidence: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:338`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:383`; `kitty-specs/coordination-doctor-branch-safety-01M35EN8/tracer-tooling-friction.md:8`
- #4809 (open, adjacent): Post-merge regression from #4801: arbiter override re-emits legacy prose review_ref and the moment drops — Same 'moment drops at payload validation' class, different field (review_ref).
- #3044 (open, adjacent): Epic: review-artifact & verdict integrity — A plausible parent.
- #4215 (open, adjacent): Make Zeitgeist status useful immediately
- **Gap:** Code check: zeitgeist_bridge._normalise_evidence returns None unchanged when metadata.evidence is None, and nothing maps review_result onto evidence, so the tracer's mechanism looks live. Three semantic searches (zeitgeist/approval/evidence/review_result) found nothing.

### B-27 — PARTIAL
Multi-clone and shared-host hazards. Two concurrent missions in one clone collide, because planning runs in the root checkout and HEAD switched mid-specify, landing a stray commit on the other mission's branch. The upstream remote is named `skupstream` in some clones and `upstream` in others, so the documented `git fetch upstream` fails. Clone mains lag canonical by hundreds of commits, and shared-host CPU contention makes runs take 10x their estimates.
- Evidence: `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:5`; `kitty-specs/verdict-matrix-rmw-preservation-01M32M9G/tracer-tooling-friction.md:9`; `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md:638`; `kitty-specs/merge-destructive-op-safety-01M2XQF8/tracer-tooling-friction.md:9`
- #4228 (open, partial): record-analysis refuses on any dirty path ... unsafe in a shared checkout — Concurrent missions in one checkout, for record-analysis only.
- #4666 (open, adjacent): Pytest prompt reaper deletes concurrently generated live CLI handoff prompts in the same checkout
- #4252 (open, adjacent): Resolve newly created owned-checkout missions in subsequent planning commands — The owned-checkout isolation mechanism exists.
- #3215 (open, adjacent): Shadow Clone helper: derive root from git worktree, guard non-CLI venvs, document per-clone re-auth
- **Gap:** Nothing makes mission create/specify detect a checkout already occupied by another in-flight mission's planning (HEAD owner), and nothing normalises the canonical-remote name used by workflows and docs.

### B-28 — PARTIAL
Event-log birth and read-semantics drift. Missions born after the event log never get status_phase seeded, and backfill-runtime-state writes the field while reporting 'Flipped: 0 / Skipped: 1' (and writes the string "1"). get_wp_lane and wp_snapshot_state disagree on missing-log semantics. A blank agent:"" annotation silently blanks attribution. The presence-tag tuple is hardcoded rather than derived.
- Evidence: `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/tasks/WP10-tracer-writer.md:61`; `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:255`; `kitty-specs/mission-type-guard-registry-01KZY2FG/tracer-design-decisions.md:112`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-design-decisions.md:27`
- Tracer-cited: #2960, #3780
- #4027 (open, exact): upgrade m_zz runtime-state backfill: _record_partial_writes/_summarize_changes key on CutoverResult.flipped — The backfill-summary misreport.
- #4963 (open, adjacent): migrate backfill-runtime-state on a mission with no event log turns done and for_review WPs into 'claimed'
- #3780 (closed, partial): missing-log semantics unification — Closed (cited by next-committed-state-authority).
- #2960 (closed, partial): blank actor annotation — Closed (cited).
- **Gap:** Unconfirmed whether status_phase is now seeded at create (no status_phase in missions/_create.py or core/mission_creation.py; it is only set by emit, merge and backfill). Hardcoded _PRESENCE_FILE_TAGS has no coverage test.

### B-29 — PARTIAL
Status-transition UX: `agent status emit --help` shows the illegal for_review->approved in one step, and the error does not name the legal next hop. --reason never reaches status.json notes and there is no note-only annotation. Every caller is labelled actor 'user' (SK-125). Re-claiming with a different --agent is a silent no-op that keeps the old identity. add-history appends after a trailing ### footer.
- Evidence: `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:327`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:621`; `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-tooling-friction.md:790`; `kitty-specs/coord-primary-partition-lock-01KWZ46V/tracer-tooling-friction.md:24`
- #3859 (open, partial): Unify the acting-identity flag across orchestrator-api verbs (--agent vs --actor) — The identity facet.
- #4574 (open, adjacent): Consume factory launch-binding env (SK_FACTORY_*) as exact actor/session/mission attribution
- **Gap:** The help example, legal-next-hop error, note-only annotation and re-claim identity update are untracked.

### B-30 — UNCOVERED
Branch-context resolver blind spots. planning_base_branch and merge_target report the mission's own target branch rather than the real branch-off commit for stacked-PR topologies, so the ATDD red-first base must be derived by hand. A stale primary_branch in config (an old topic branch) is accepted without validation.
- Evidence: `kitty-specs/bare-prose-requirements-uncounted-01KZYV3C/tracer-tooling-friction.md:7`; `kitty-specs/cascade-org-inert-01M07E9P/tracer-tooling-friction.md:7`; `kitty-specs/next-committed-state-authority-01M1CA8W/tracer-tooling-friction.md:10`
- Tracer-cited: #3520
- #1619 (open, adjacent): Epic: Unify mission execution context across coord/main/lane topology — Umbrella only.
- **Gap:** Tracer-cited #3520 is a PR, not an issue. Grepped for 'stacked', 'planning_base', 'primary_branch', 'branch-context': no open issue.

### B-31 — PARTIAL
Semantic merge hazards that git and lint do not catch. A textually clean rebase crashed at runtime with TypeErrors (divergent signatures, __all__ conflicts with no correct side), and parallel WPs append to the same enforced registries (upstream_contract.json, commands.py).
- Evidence: `kitty-specs/journal-project-consent-3030-01KYKWQS/tracer-tooling-friction.md:239`; `kitty-specs/design-phase-orchestrator-api-01M1HE6M/tracer-tooling-friction.md:155`
- Tracer-cited: #3826
- #1979 (open, partial): a WP can change a shared source contract pinned by a test outside its owned_files — break is invisible to per-WP review, surfaces only at merge — Cross-WP contract break surfacing at merge.
- #3936 (open, adjacent): Dependency-lane auto-merge conflict has no guided resolution or overlap warning
- **Gap:** No issue for a post-consolidation smoke or import check, or for planning-time detection of shared append-only registries across parallel WPs.

### B-32 — CLOSED-ONLY
Subtask completion inference fails open. _infer_subtasks_complete did not read the primary surface at four callers (a per-door patch for #2511), and two subtask-row walkers disagreed on section-exit semantics.
- Evidence: `kitty-specs/coord-shadows-arm-closeout-01KXAST2/tracers/emit-class-closure.md:3`; `kitty-specs/coord-shadows-arm-closeout-01KXAST2/tracers/subtask-row-canon.md:7`; `kitty-specs/coord-shadows-arm-closeout-01KXAST2/tracers/claim-liveness.md:11`
- Tracer-cited: #2511
- #2511 (closed, exact): _infer_subtasks_complete fail-open door — Closed; the coord-shadows-arm-closeout mission (2026-07-12) did the class closure.
- **Gap:** Code check: core/subtask_rows.py now has a single _walk_wp_section, so the duplicate-walker facet looks resolved.

## Draft issues (NOT filed), in priority order

### [P1] specify/mission create on a protected branch: mint the mission branch (or refuse) before topology derivation; fix coord materialise-then-retry losing uncommitted scaffold  _(from B-02, PARTIAL)_
- **Scope:** Decide #4632 in favour of one policy: create either mints/checks out a non-protected mission branch before deriving topology or refuses with --start-branch guidance. The spec-commit coord fallback must carry the caller's uncommitted files into the materialised worktree or commit via plumbing.
- **Labels:** domain:git, domain:onboarding, workflow
- **Dependencies / sequencing:** Needs a #4632 policy decision first. Shares the placement seam with B-01. #2533/#2602 cover the topology-derivation half.

### [P1] single_branch topology is ignored: implement allocates lane worktrees, guards demand lane-planning branches, commits strand on undeclared lanes  _(from B-11, PARTIAL)_
- **Scope:** Make the workspace resolver, lane computation, dependency auto-merge and the for_review implementation-commit guard resolve against meta.json topology. For single_branch, write to the mission branch and skip lanes. Stamp the correct execution_mode. Regression test covers implement + for_review on a single_branch 2-WP mission.
- **Labels:** domain:git, workflow, reliability, catfooding
- **Dependencies / sequencing:** Same allocator/resolver as B-05 and B-13, so sequence those three in one mission. #4828 (the positive mode) should build on this fix.

### [P1] implement/claim: gate-before-mutate and roll back claim side effects on failure (meta vcs lock, frontmatter, lease, prompt file)  _(from B-12, PARTIAL)_
- **Scope:** Order implement so that every refusal happens before any write. Make the claim transition, lease and prompt generation one unit. A failed allocation restores the prior lane (not blocked) and leaves no out-of-scope dirty files. Tests cover each failure arm.
- **Labels:** reliability, workflow, domain:status
- **Dependencies / sequencing:** Same code path as #4075 (finalize) and the #3897 epic. Parallel-safe with B-11.

### [P1] merge: independently assert mission acceptance (accepted_at/accept_commit valid and current) before lane consolidation  _(from B-20, PARTIAL)_
- **Scope:** Defense-in-depth behind #4891/#4934. Merge refuses when acceptance is absent or stale relative to the integration view, instead of trusting that accept ran. Share the predicate with accept via the #3894 integration view.
- **Labels:** domain:merge, reliability, domain:status
- **Dependencies / sequencing:** Depends on the #4891 fix landing and the #3894 integration-view builder, so the predicate is shared.

### [P1] Zeitgeist: approval moments dropped — review_result is not mapped onto the evidence StatusTransitionPayload requires for approved/done  _(from B-26, UNCOVERED)_
- **Scope:** At the bridge (or emit), derive an evidence bundle from review_result for approved/done transitions, or have the validator accept review_result. Add a regression test that `move-task --to approved --review-result-json` offers exactly one moment. Also surface 'not published: logged out' once per session.
- **Labels:** domain:hosted, domain:status, reliability
- **Dependencies / sequencing:** Independent and small; the first to pick up (a Team Kitty user-visible loss on every approval).

### [P2] Commit placement: detect meta.json target_branch vs live-branch divergence and add a sanctioned `mission retarget` (post-#3482 re-verify of SK-12/13)  _(from B-01, PARTIAL)_
- **Scope:** Re-run the SK-12/13 repro (specify on main, then work on a PR branch; spec-commit/plan/finalize/move-task) on current main. If it still refuses, add a `spec-kitty agent mission retarget --target-branch` that rewrites meta/lanes/WP frontmatter atomically and make every placement refusal name it.
- **Labels:** domain:git, workflow, reliability, catfooding
- **Dependencies / sequencing:** Do this first by re-verifying on main (the evidence predates #3482 and #2739). Pair it with B-02: both come from the same meta-vs-live-branch placement seam under #2017 and #1619.

### [P2] Add a sanctioned `spec-kitty mission flatten` for live coord missions that migrates the full coord event log (bootstrap + seeds)  _(from B-03, PARTIAL)_
- **Scope:** Expose the #2618 canonical seam as an operator command for an existing coordination branch. It carries status.events.jsonl, including genesis->planned and backfill seeds, onto primary, so next/implement need no finalize-tasks re-run. Replaces the hand-edit remedy the CLI prints today.
- **Labels:** domain:git, workflow, reliability
- **Dependencies / sequencing:** Builds on the #2618 canonical seam and extends #3272 (seed events) to WP bootstrap events. Unblocks the B-01 recovery path.

### [P2] implement: refresh or reset lane branches that are not descendants of the current mission tip (--base must override a surviving stale lane)  _(from B-05, PARTIAL)_
- **Scope:** On claim, compare the lane branch against the mission tip. If it is behind or diverged and has no unique WP commits, fast-forward or reset it; otherwise refuse with a merge-forward remedy. Make --base authoritative. Add a regression test for the false-baseline case.
- **Labels:** domain:git, workflow, reliability
- **Dependencies / sequencing:** Independent of the others. Coordinate with #3945 (approved-sibling base) and #4889 (inverse re-cut) in the same allocator code (lanes/worktree_allocator.py).

### [P2] Route lane-origin tracer appends through `agent tracer-append` in the mission-tracer-files procedure and the implement/review prompts  _(from B-07, PARTIAL)_
- **Scope:** Update the built-in mission-tracer-files procedure and the implement/review step prompts to tell lane-confined agents to use `spec-kitty agent tracer-append` and never edit kitty-specs in the lane. Optionally make the lane pre-commit guard block, not warn, for tracer paths.
- **Labels:** domain:charter, workflow, catfooding
- **Dependencies / sequencing:** A doctrine-only change in packs/built-in (regenerate-graph gate). Removes most of the B-06 triggers without code changes. Can land in parallel.

### [P2] Lane identity: --base allocation must reuse the WP's lanes.json lane; post-planning WPs must be registered (or refused) in lanes.json  _(from B-13, UNCOVERED)_
- **Scope:** Make lanes.json the single lane-identity authority. The --base allocator reuses the assigned lane_id and never mints a colliding sequential slot. Adding a WP after finalize-tasks registers it in lanes.json or fails loudly instead of defaulting to lane-a.
- **Labels:** domain:git, workflow, reliability
- **Dependencies / sequencing:** Same allocator as B-05 and B-11. Lanes.json-authority decision needed first.

### [P2] mark-status: add --wp scoping (refuse ambiguous subtask IDs), report honest no-ops, and add a terminal `skipped` subtask status  _(from B-15, UNCOVERED)_
- **Scope:** Resolve subtask IDs within the given --wp and refuse cross-WP ambiguity instead of picking the first match. Report no-op when no row changed. Accept `skipped`/`not_applicable` as terminal for the for_review subtask gate. Add --wp to `agent status emit` for symmetry.
- **Labels:** domain:cli, domain:status, usability
- **Dependencies / sequencing:** Independent CLI surface. Parallel-safe.

### [P2] safe-commit: refuse (or require --force) implementation commits for a WP that is not claimed; detect committed-but-planned WPs  _(from B-23, UNCOVERED)_
- **Scope:** When the active WP resolves to planned or blocked, refuse the commit with a 'claim first' remedy. Add a doctor/status check listing WPs with lane commits but no claim event, so orchestrator-skipped transitions surface before dependency gating.
- **Labels:** domain:git, domain:status, reliability
- **Dependencies / sequencing:** Independent. Pairs with a doctor check.

### [P2] Guard lane/start-branch deletion with an is-merged/unique-commit check before `git branch -D` (deferred from merge-destructive-op-safety)  _(from B-25, PARTIAL)_
- **Scope:** Route every `branch -D` site through guard_destructive_removal-style logic: refuse when the branch has commits unreachable from the target or coord tip, unless an explicit override is given. Add agent-facing doctrine not to use `git stash` or path checkouts over coord status files.
- **Labels:** domain:git, reliability, domain:merge
- **Dependencies / sequencing:** Extends guard_destructive_removal from the user-content-preservation mission. Independent of the rest.

### [P2] mission create/specify: refuse or isolate when the checkout is occupied by another in-flight mission; resolve the canonical upstream remote by URL, not name  _(from B-27, PARTIAL)_
- **Scope:** Preflight check: if HEAD is another active mission's branch or the tree has another mission's uncommitted planning, refuse or offer an owned checkout. Workflows/docs resolve the spec-kitty/spec-kitty remote by URL instead of assuming `upstream`.
- **Labels:** workflow, domain:git, catfooding
- **Dependencies / sequencing:** Builds on the owned-checkout mechanism (#4252) and the #4228 scoping fix.

### [P3] Warn when approved lanes are unconsolidated and stamp branch@sha on every gate count  _(from B-21, PARTIAL)_
- **Scope:** `agent tasks status`, `next` and the pre-review/accept gates print the approved-but-unconsolidated lanes and the measured ref, so pre-consolidation counts are never mistaken for regressions.
- **Labels:** workflow, usability, domain:merge
- **Dependencies / sequencing:** Depends on the #3894/#3966 integration view.

### [P3] Seed status_phase at mission create (birth invariant) and derive artifact-presence tags from the guard tables  _(from B-28, PARTIAL)_
- **Scope:** Ensure new missions satisfy the dogfood birth invariant without backfill, writing an integer. Replace the hardcoded _PRESENCE_FILE_TAGS 9-tuple with a derivation from the registered guard tables, or add a coverage test.
- **Labels:** domain:status, tech-debt
- **Dependencies / sequencing:** Independent. Coordinate with #4027 (backfill summary).

### [P3] status emit / move-task UX: fix the illegal help example, name the legal next hop, add note-only annotation, update identity on re-claim  _(from B-29, PARTIAL)_
- **Scope:** Correct the --help example (for_review->in_review->approved). Make illegal-transition errors list the legal targets. Add `agent status annotate --note`. Warn or update the recorded agent when re-claiming with a different --agent. Stop labelling CLI callers 'user'.
- **Labels:** domain:cli, usability, domain:status
- **Dependencies / sequencing:** Independent; a good-first-issue-sized bundle.

### [P3] branch-context: expose the real fork-point / stacked-PR base and validate configured primary_branch against the repo default  _(from B-30, UNCOVERED)_
- **Scope:** Add a `fork_point`/`stacked_on` field so red-first baselines and reviewers see base drift. Warn when primary_branch is not the remote default branch.
- **Labels:** domain:git, usability
- **Dependencies / sequencing:** Independent. Low urgency.

### [P3] Post-consolidation smoke check and plan-time warning for shared append-only registries across parallel WPs  _(from B-31, PARTIAL)_
- **Scope:** After lane consolidation, run an import/CLI smoke (and recompute __all__ consumers) before reporting success. At finalize-tasks, flag files that several parallel WPs append to (registries, barrels) as overlap surfaces.
- **Labels:** domain:merge, workflow
- **Dependencies / sequencing:** Depends on the B-21 consolidation signal.

### Suggested sequencing (planner view)
1. **Do first (important and cheap):** B-26 (Zeitgeist approval drop) and B-07 (doctrine routing to tracer-append). Both are small and independent, and each stops a loss that happens on every run.
2. **Allocator/resolver mission (one mission, three WPs, sequential in one file family):** B-11 (single_branch honoured), then B-13 (lane identity), then B-05 (stale lane refresh). #4889 and #4905 are already in flight in the same code, so coordinate with those owners.
3. **Placement mission:** re-verify B-01, then B-02 (after the #4632 decision), then B-03 (flatten command on the #2618 seam).
4. **Gate hardening:** B-12 (transactional claim) runs in parallel with B-20 (merge asserts acceptance, after #4891/#3894) and B-23 (safe-commit lifecycle awareness).
5. **Backlog (P3):** B-15/B-29 UX bundle, B-21, B-28, B-30, B-31.

## Honest limits

- **GitHub semantic search was heavily rate-limited.** It is shared with the parallel delegates (about 15 of roughly 30 attempts returned 403). About 12 semantic searches completed. The rest of the coverage check relied on multi-variant greps of `open_issues.tsv` (the complete open set) plus 20 `issue_read` body confirmations. Closed-issue coverage is therefore sampled, not exhaustive. An UNCOVERED verdict means nothing open was found, but a closed duplicate may still exist.
- **Some semantic queries returned zero results with no error** (for example, every Zeitgeist phrasing). I treated those as weak evidence. The B-26 verdict rests mainly on a direct code read of `status/zeitgeist_bridge.py`, which shows no review_result-to-evidence mapping.
- **Recency:** I dated missions by decoding the mid8 ULID prefix (granularity about 1 s). B-01, B-02, B-14 and B-18 evidence all predates the closing fixes (#3482/#2739, #3680/#3715, #2275), so I did not claim regressions for them. B-06 (#2980) and B-08 (#2549) do have post-close witnesses.
- **Code spot-checks** (read-only) back four verdicts: mark-status has no `--wp` and only done/pending (B-15); `src/specify_cli/sync/` is gone (B-14 likely resolved); one `_walk_wp_section` (B-32 resolved); the tracer procedure never mentions `tracer-append` (B-07).
- **Cluster count is 32**, above the 8-20 guideline, because group B carries 168 items (about 17% of the corpus). I kept distinct fixes separate rather than merging them under the big epics (#2160, #1619, #2017), which would hide actionable gaps.
- **Tracer cited_issues** include internal SK-NN ledger ids and one PR number (#3520) that cannot be checked against the tracker, and one cross-repo ref (`Priivacy-ai/spec-kitty#588`).
- **Unclustered items** (design notes, positive decisions, or already-resolved context): 0, 12, 20, 22, 27, 30, 31, 37, 56, 57, 59, 66, 110, 128, 130, 139, 143, 144, 150, 151. Examples: the lanes.json PRIMARY-partition decision; the coord/primary partition settlement (#2106/#2113/#2119); FR-011 queryable-event deferral; git-revert across merge commits deferred to #3897 (open epic); the #3884 re-enabled completion checks; the tail_reader core/shell split.
