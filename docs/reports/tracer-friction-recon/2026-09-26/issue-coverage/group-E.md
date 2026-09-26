# Planner Priti — Group E issue-coverage check

Themes: cli-ergonomics (51), review-loop-verdicts (54), squad-review-value (9), subagent-orchestration (33), agent-harness-sandbox (22), spec-kitty-dispatch-ops (7): **176 tracer items from 57 missions -> 31 clusters**.

**Profile applied:** planner-priti (loaded via `spec-kitty agent profile show planner-priti`, plan-action charter context loaded). I used its decomposition, dependency-mapping and Eisenhower prioritisation (P0-P3) modes and stayed inside its avoidance boundary: no implementation or architectural decisions, and read-only on GitHub and the repo. Directives and tactics used: 003 decision documentation (each verdict states its reasoning), 028 search-tool discipline, 045 read-intent (read-only), 044 canonical sources, analysis-extract-before-interpret, eisenhower-prioritisation, problem-decomposition and avoid-gold-plating.

**Verdicts:** COVERED 8 · PARTIAL 15 · CLOSED-ONLY 3 · UNCOVERED 5

## Clusters -> verdict -> issues

| ID | Kind | Cluster | Missions / items / max sev | Verdict | Issues (state, fit) |
|---|---|---|---|---|---|
| E-01 | cause | 'Global asset input changed' race in ensure_runtime/global asset sync crashes arbitrary verbs (activate, move-task, merge, charter context, implement) as an unenveloped traceback under concurrent sessions; retry self-heals. | 5 / 6 / high | **COVERED** | #4885 (open, exact); #3998 (open, exact); #2627 (open, partial); #4017 (open, partial) |
| E-02 | cause | record-analysis DIRTY_WORKTREE preflight checks the whole repo (untracked scratch dirs, other missions' status files, kitty-ops debris) though it commits one file; operators resort to mv-aside/stash. | 5 / 5 / medium | **COVERED** | #4228 (open, exact); #2251 (closed, partial) |
| E-03 | cause | record-analysis input-carrier contract is fragile: wrong/absent carrier, missing '---' fence or input key 'schema' vs output 'schema_version' silently yields verdict: unknown; stdin default fails when backgrounded. | 5 / 5 / medium | **COVERED** | #3133 (open, exact) |
| E-04 | both | safe-commit --to-branch semantics mislead in lane worktrees: refusal suggests checking out the mission branch, dispatch templates say --to-branch <merge_target_branch> though the guard asserts current HEAD, bare safe-commit rea… | 6 / 8 / high | **PARTIAL** | #1820 (closed, partial); #4625 (open, adjacent); #4632 (open, adjacent) |
| E-05 | cause | Command outcome reporting is dishonest around side effects: implement --base exits 1 after creating the workspace (and leaves uncommitted writes that block the next command); finalize-tasks --json reports only the last of 7 com… | 6 / 6 / high | **PARTIAL** | #4722 (open, partial); #3930 (open, adjacent); #2549 (closed, partial); #4807 (open, adjacent) |
| E-06 | cause | --json does not mean pure JSON on finalize-tasks / record-analysis (Rich-wrapped), so agents grep fields instead of parsing. | 1 / 1 / medium | **PARTIAL** | #2605 (open, partial); #4533 (closed, adjacent) |
| E-07 | cause | Mutating verbs (agent action implement, move-task, next handoff) block for minutes after their useful work lands (SK-93/SK-65 tail stall); exit codes/printed output are weak evidence and backgrounded transcripts are empty, so a… | 5 / 7 / high | **CLOSED-ONLY** | #3680 (closed, exact); #3046 (open, adjacent) |
| E-08 | improvement | --mission is required on nearly every verb (433 missions in-tree) even inside a lane worktree or right after next resolved it; WP prompt footers and --help examples omit it. | 4 / 4 / medium | **UNCOVERED** | #4677 (closed, partial); #4682 (closed, adjacent) |
| E-09 | cause | `next` and the implement entry points disagree: next --json reports guard_failures [] (or discovery/not_started for a tasked mission) while agent action implement refuses (stale_analysis_report after fixer passes touch tasks.md). | 3 / 3 / medium | **PARTIAL** | #3932 (open, exact); #4161 (open, partial); #2493 (open, partial) |
| E-10 | cause | CLI surface naming/discoverability: two 'mission create' commands with different semantics, dispatches conflating mission-step IDs with CLI verbs (agent tasks tasks-packages), required flags below the fold of --help, overloaded… | 4 / 4 / medium | **PARTIAL** | #3577 (closed, partial); #2728 (open, adjacent); #4441 (open, adjacent); #2653 (open, exact) |
| E-11 | cause | Commit helpers under-commit or over-mutate: spec-commit silently commits only recognized artifact kinds (decision records, status.events.jsonl need plain git), refuses directory args with a destructive `git checkout HEAD --` re… | 3 / 4 / medium | **PARTIAL** | #2739 (closed, partial); #2570 (open, adjacent); #3471 (open, adjacent); #4722 (open, adjacent) |
| E-12 | cause | Bulk-edit gates are too coarse: claim-time keyword inference false-positives (spec discusses a migration) force --acknowledge-not-bulk-edit on every lane allocation; the diff-compliance gate classifies by a file's dominant cate… | 2 / 3 / medium | **COVERED** | #2229 (open, exact); #2555 (open, partial) |
| E-13 | cause | mission branch-context reported a stale per-clone primary_branch pin, so current_is_primary read false on main. | 1 / 1 / medium | **CLOSED-ONLY** | #3777 (closed, adjacent) |
| E-14 | cause | CLI verbs are slow (repository scan / doctrine load on every invocation, 20-60s; slow move-task gate exceeds subagent turn limits). | 2 / 2 / medium | **COVERED** | #4514 (open, exact); #4620 (open, exact); #4517 (open, partial); #3046 (open, partial) |
| E-15 | both | Per-WP approval is gated by the mission-wide issue-matrix: every cited #NNN (incl. context-only refs) needs a terminal verdict before any WP can go approved; agents fabricate 'deferred'/'in-mission' placeholders; no sanctioned … | 7 / 10 / high | **COVERED** | #5007 (open, exact); #3469 (closed, partial); #5011 (open, adjacent) |
| E-16 | cause | Review-verdict ergonomics: CLI vocabulary (approved/changes_requested) differs from doctrine (approved/rejected) so 'rejected' is refused; a rejection silently resets all subtasks which must be re-marked. | 2 / 3 / medium | **PARTIAL** | #3578 (open, exact) |
| E-17 | cause | Pre-review regression gate is unreliable as a signal: a fixed 300s cap times out on ~2-min scoped suites and refuses the transition; for WPs whose work landed on the mission branch (no lane diff) it prints 'no_coverage — skippi… | 1 / 2 / high | **PARTIAL** | #3046 (open, exact); #2741 (closed, partial); #3958 (open, adjacent); #3260 (open, adjacent) |
| E-18 | both | Review evidence is thin or not durable: review-cycle records like a bare 'Approved by claude' with empty affected_files; squad PASS verdicts exist only as prose; squad lens artifacts ignore the overlay filename contract; self-a… | 5 / 6 / high | **PARTIAL** | #3235 (closed, exact); #3044 (open, adjacent); #3158 (open, adjacent) |
| E-19 | improvement | Acceptance criteria and red-first tests pass vacuously: 13/29 requirements passable by a no-op, refusal probes without positive controls, flag-threaded strict paths never exercised by production, compound fixes not proven half-… | 11 / 13 / high | **UNCOVERED** | #3264 (closed, adjacent) |
| E-20 | cause | Specs, operator rulings and dispatch briefs are issued from summaries or stale citations rather than first-hand source: line citations drift within a round, truncated quotes hide contradictions, rulings contain factual errors, … | 11 / 15 / high | **UNCOVERED** | #4067 (open, adjacent) |
| E-21 | improvement | Adversarial point-cut squads repeatedly earned their cost (wrong fix targets, inert gates, critical scope gaps, 4x REJECT convergence, 5 BLOCKERs before implementation) — keep them on architecturally loaded missions. | 11 / 12 / high | **COVERED** | — (doctrine) |
| E-22 | both | Cross-WP composition defects escape per-WP review (tests mock the partner seam; partition-moving commits defeat same-partition rollback guards); the integration/arch suite on the consolidated tree caught 3 regressions — run it … | 3 / 5 / high | **COVERED** | #3943 (open, exact); #1979 (open, partial) |
| E-23 | cause | Concurrent agents share one working tree: parallel ops revert each other's edits, `git add -A` swallows another agent's source into a dossier commit, `git stash` steals a reviewer's edit, reviewers write during implementation o… | 8 / 10 / high | **PARTIAL** | #3129 (open, partial); #4228 (open, adjacent); #2017 (open, adjacent); #4227 (open, partial) |
| E-24 | both | A shared machine/tree is not a measurement substrate: 20+ concurrent pytest runs across agents give false reds (port band, leaked daemons, 7-min runs), fill tmpfs (EDQUOT/ENOSPC) and take tools offline; killed/piped runs are mi… | 2 / 6 / high | **UNCOVERED** | #1071 (closed, adjacent); #3283 (closed, adjacent); #3943 (open, adjacent) |
| E-25 | improvement | WP dispatch briefs omit load-bearing facts: whether sub-delegation is allowed (two writers committed to one WP), that dependency lanes are already merged into the lane-planning workspace (manual git apply failed), env overrides… | 4 / 7 / high | **UNCOVERED** | #1840 (closed, adjacent) |
| E-26 | cause | Fan-out ignores model routing and budget: implementers dispatched on opus instead of sonnet (--agent model string cosmetic); opus subagents die on 429/session limits and org spend caps, discarding partial work; transient crashe… | 5 / 6 / high | **PARTIAL** | #2364 (closed, exact); #1049 (open, partial); #4205 (open, partial); #2640 (open, adjacent) |
| E-27 | both | Harness long-run handling strands agents: foreground Bash is capped at ~600s regardless of timeout, `cmd & wait`/nohup is killed with the process group, repo-scale pytest auto-backgrounds and agents end the turn waiting for a n… | 4 / 6 / high | **PARTIAL** | #2555 (open, partial); #1707 (open, adjacent) |
| E-28 | cause | Harness sandbox/isolation conflicts with dispatch: worktree-isolation resets cwd to an unrelated branch, refuses git after cd into the shared checkout, blocks Write/Edit there and 'complex' heredocs; auto-mode blocks combined p… | 6 / 6 / high | **PARTIAL** | #4122 (open, adjacent); #1907 (open, adjacent); #2746 (open, adjacent) |
| E-29 | cause | The git pre-commit hook pins the absolute interpreter of whichever venv installed it (an ephemeral agent-worktree venv), so every later commit fails once that venv is gone. | 2 / 2 / high | **PARTIAL** | #669 (closed, partial); #3448 (open, partial) |
| E-30 | cause | Implementers bypass `agent action implement` (work directly in the primary checkout / plain git + safe-commit), so no lane worktree or status transitions happen and orchestrators do not notice; one prompt even authorized hand-b… | 3 / 3 / medium | **CLOSED-ONLY** | #571 (closed, partial); #2745 (closed, adjacent) |
| E-31 | cause | Dispatch router/op plumbing is unstable: the SK-08 rerank can select a different profile per call (in-flight missions route differently before/after merge; tk-watch pins --profile as a workaround); overlapping WP edits in route… | 2 / 5 / medium | **PARTIAL** | #4676 (open, partial); #3840 (closed, exact); #2685 (open, adjacent); #1781 (closed, adjacent) |

### Gaps per cluster (non-null)

- **E-01**: Minor: none of the four asks that the error be enveloped (structured error code + retry hint) rather than a raw traceback while the gate still exists.
- **E-03**: Small residual not in #3133: document the input-carrier key contract and refuse (not block on) empty stdin when non-interactive.
- **E-04**: No open issue for: (a) the lane-worktree refusal remedy text, (b) dispatch/implement templates naming the merge target for --to-branch, (c) bare safe-commit resolving the destination from stale meta.json (tracer SK-15).
- **E-05**: Uncovered: implement --base mutate-before-fail + failure reported after successful side effects; safe_commit git-commit stderr / identity preflight; finalize-tasks multi-commit reporting (residual after #2549).
- **E-06**: Evidence is from 2026-06-27 (one mission); finalize-tasks/record-analysis may already be clean. Gap = a repo-wide --json purity guard at the typer boundary, which #2605 suggests but does not own.
- **E-07**: Only post-close witness is hx1 (2026-09-22: specify->plan `next` handoff exceeded the wait window). Improvement 'print the result before any slow tail work' is not filed anywhere.
- **E-08**: Searched: 'infer mission from branch/worktree/cwd', '--mission required', 'mission context' (semantic + full-text over 3,187 issues) — no open issue proposes worktree/branch-derived mission inference.
- **E-09**: No issue asks for next's readiness verdict to run the same preflight gates (analysis freshness) as agent action implement.
- **E-10**: No guard validates CLI invocations named in shipped prompts/skills against the live typer registry (the #3577 class recurs).
- **E-11**: Uncovered: spec-commit reporting skipped (unrecognized) paths; mission create --pr-bound leaving meta.json dirty (tracer cited #2795, which is closed and about a different mechanism); map-requirements frontmatter reformat.
- **E-12**: Small residual: persist the not-bulk acknowledgement once per mission (not per lane).
- **E-13**: No post-fix witness; treat as fixed unless it recurs.
- **E-15**: rev9 (dedupe keeps first occurrence, may downgrade a dual-cited implementation target) and rev12 (ADR for not-applicable) are not tracked; minor.
- **E-16**: Searched 'rejected alias', 'changes_requested vocabulary', 'review-result-json' (semantic + full-text): nothing for the verdict-vocabulary mismatch.
- **E-17**: Uncovered: owned_files-vs-merge-base fallback when there is no lane diff, and a rule that no_coverage must never render like a pass.
- **E-18**: Uncovered: persisting adversarial-squad lens reports as named artifacts validated against the overlay contract; minimum-content floor for approval review-cycle records (affected_files, evidence).
- **E-19**: Searched 'positive control', 'vacuous', 'no-op requirement', '[build]/[ratchet]' over all 3,187 issues and packs/built-in: no issue or spec-template rule; only the arch-gate non-vacuity tactic exists.
- **E-20**: Searched 'citation drift', 'ruling ... verify', 'brief ... reproduce', 'line-number stale': only PR-scoped squad MINORs. This is a process/doctrine gap (in-house orchestration practice -> packs/internal, not built-in).
- **E-21**: Covered by doctrine, not an issue: charter Standing Order 'adversarial squad cadence' + the adversarial-squad skill. Nothing to file; useful as evidence if squad cadence is ever questioned.
- **E-22**: rev14 (two open PRs with opposite raise-vs-degrade policy on one exception) is a cross-PR variant not covered; minor.
- **E-23**: Uncovered near-term: an orchestration rule/guard 'one writer per checkout' (per-agent worktree for concurrent implementers AND reviewers incl. single_branch; no `git add -A`/`git stash` in shared checkouts; tree-mutating squad lenses serialized or isolated). adversarial-squad SKILL already says read-only unless isolated worktree.
- **E-24**: No issue. Doctrine partly covers it: tactic no-parallel-duplicate-test-runs (same suite, one agent) and the CLAUDE.md baseline-red gotcha; neither covers cross-agent fan-out, tmpfs quotas, PIPESTATUS, or pinning the mission base for attribution.
- **E-25**: Searched 'sub-delegation', 'dispatch brief', 'final-integration WP lanes merged', 'hunk overlap parallel': nothing open.
- **E-26**: Uncovered: budget-aware fan-out (stagger waves, detect rate-limit/spend-cap terminations, checkpoint partial work, disclose unfinished subagents).
- **E-27**: Uncovered: the concrete in-turn bounded-wait recipe (run_in_background + `while kill -0 <pid>` / `tail --pid`) in the implement-review and review skills.
- **E-28**: Uncovered: guidance for single_branch/shared-checkout dispatch under Claude Code worktree isolation (scratchpad-script pattern, `git -C` instead of cd). Mostly harness behaviour; spec-kitty can only document and avoid contradicting it.
- **E-29**: No dedicated open bug for pinning an ephemeral/worktree venv interpreter.
- **E-30**: Uncovered: an orchestrator-side check that each dispatched WP actually drove claim->in_progress->for_review transitions before accepting the hand-back.
- **E-31**: Uncovered: routing stability across a mission (record the first resolved profile per mission/WP) and removing the tk-watch --profile pin; op-record persistence reliability.

## Draft issues (NOT filed)

Ordered by priority (Eisenhower: urgent+important first). Dependencies are on other clusters (E-NN) or open issues.

### E-23 · P1 · One writer per checkout: concurrent implementers/reviewers get their own worktree (incl. single_branch); forbid git add -A / git stash in shared checkouts
- **Scope:** implement-review + adversarial-squad skills mandate per-agent worktrees and serialized mutating lenses; add a lightweight guard that refuses review claim in a checkout with another agent's live lease. Interim step toward #3129.
- **Labels:** workflow, reliability, domain:git
- **Depends on:** #3129, #4227
- **Verdict basis:** PARTIAL. Evidence: `journal-project-consent-3030-01KYKWQS: tracer-tooling-friction.md:47`; `common-docs-consolidation-01KW3Q6M: tracers/tooling-friction.md:7`

### E-04 · P2 · safe-commit in a lane worktree: remedy text and dispatch templates name the wrong --to-branch; bare form resolves from stale meta.json
- **Scope:** Make the refusal remedy name --to-branch <current lane branch>, fix implement/dispatch templates that pass merge_target_branch, and make bare safe-commit infer from the worktree HEAD (or refuse with that hint) instead of stale meta.json. Regression tests from a lane worktree.
- **Labels:** domain:git, domain:cli, usability, type:bug
- **Depends on:** #4625
- **Verdict basis:** PARTIAL. Evidence: `event-push-watch-channel-01M1K6W2: tracer-tooling-friction.md:55`; `spdd-reasons-activation-split-brain-01M1K6VN: tracer-tooling-friction.md:168`

### E-05 · P2 · Report side-effect outcome separately from bookkeeping-commit outcome (implement --base, finalize-tasks) and surface git's stderr on safe_commit failure
- **Scope:** implement --base must not exit 1 after the workspace exists, nor leave uncommitted meta/frontmatter writes; finalize-tasks --json lists every commit; safe_commit includes git stderr and preflights user.name/email.
- **Labels:** domain:cli, domain:git, reliability, type:bug
- **Depends on:** #4807, #4722
- **Verdict basis:** PARTIAL. Evidence: `org-pack-authoring-diagnostics-01KZY463: tracer-tooling-friction.md:183`; `org-activation-scan-dirs-01KZY1PT: tracer-tooling-friction.md:42`

### E-09 · P2 · next must evaluate the same implement preflight gates (analysis-report freshness) it predicts
- **Scope:** When next routes to implement, run the implement preflight (incl. stale_analysis_report) and report it in guard_failures so next's verdict predicts the entry point.
- **Labels:** domain:runtime, domain:cli, workflow
- **Depends on:** #3932, #4161
- **Verdict basis:** PARTIAL. Evidence: `mission-type-guard-registry-01KZY2FG: tracer-tooling-friction.md:457`; `common-docs-consolidation-01KW3Q6M: tracers/tooling-friction.md:13`

### E-17 · P2 · Pre-review gate: fall back to owned_files vs merge base when a WP has no lane diff; never present no_coverage as a pass
- **Scope:** Scope source uses the WP's owned_files diffed against the mission base when no lane worktree exists; no_coverage output is labelled UNVERIFIED and surfaced in the review prompt.
- **Labels:** domain:status, reliability, workflow
- **Depends on:** #3260, #3958
- **Verdict basis:** PARTIAL. Evidence: `journal-project-consent-3030-01KYKWQS: tracer-tooling-friction.md:35`; `journal-project-consent-3030-01KYKWQS: tracer-tooling-friction.md:153`

### E-19 · P2 · Spec template + review doctrine: label criteria [build]/[ratchet] and require positive controls for refusal/absence criteria
- **Scope:** Spec template adds a per-criterion [build]/[ratchet]/[folded] label and a 'no-op passable?' check; review tactic requires a positive control bound to the same fixture and half-by-half proof for compound fixes.
- **Labels:** domain:charter, workflow, enhancement
- **Depends on:** none
- **Verdict basis:** UNCOVERED. Evidence: `egress-refusal-consolidation-3110-01KYW895: tracer-squad-findings.md:482`; `egress-refusal-consolidation-3110-01KYW895: tracer-squad-findings.md:1612`

### E-24 · P2 · Tactic: measurement discipline for multi-agent missions (serialized sweeps, pinned worktree per claim, mission-base attribution)
- **Scope:** Extend no-parallel-duplicate-test-runs (or add a sibling tactic): cap concurrent heavy suites per machine, route pytest tmp/cache off tmpfs, check PIPESTATUS / treat killed runs as no measurement, attribute reds against the mission's recorded base commit.
- **Labels:** domain:charter, workflow, testing
- **Depends on:** E-23
- **Verdict basis:** UNCOVERED. Evidence: `journal-project-consent-3030-01KYKWQS: tracer-tooling-friction.md:315`; `spdd-reasons-activation-split-brain-01M1K6VN: tracer-tooling-friction.md:262`

### E-25 · P2 · implement-review dispatch template: required fields (sub-delegation policy, lane-merge state, env/venv constraints)
- **Scope:** Canonical WP dispatch block states sub-delegation permitted/forbidden, what is already merged into the workspace, and environment constraints; tasks finalize warns on same-hunk overlap between WPs labelled parallel.
- **Labels:** workflow, domain:charter, enhancement
- **Depends on:** E-23
- **Verdict basis:** UNCOVERED. Evidence: `ci-nightly-wallclock-budget-01M34HNZ: tracer-tooling-friction.md:823`; `charter-epic-golden-path-nfr-budget-01M35H35: tracer-tooling-friction.md:89`

### E-27 · P2 · implement-review/review skills: bounded in-turn wait recipe for long gates; never end a turn while your own gate runs
- **Scope:** Document run_in_background + repeated bounded waits as the standard for suites >10 min; orchestrator detects a delegate that yielded with a live gate and resumes it.
- **Labels:** workflow, documentation, domain:agent-profiles
- **Depends on:** #2555
- **Verdict basis:** PARTIAL. Evidence: `interpreter-matrix-3-13-env-and-divergence-01M34HVD: tracer-tooling-friction.md:615`; `ci-nightly-wallclock-budget-01M34HNZ: tracer-tooling-friction.md:395`

### E-29 · P2 · Hook installer must not pin an ephemeral worktree venv interpreter
- **Scope:** Resolve the interpreter at hook run time (repo .venv, then spec-kitty tool env) or refuse to install from a linked worktree venv; doctor detects a dangling pinned interpreter.
- **Labels:** domain:git, reliability, type:bug
- **Depends on:** none
- **Verdict basis:** PARTIAL. Evidence: `verdict-seam-boundary-hardening-01KZG179: tracers/tooling-friction.md:8`; `reliability-papercut-sweep-01KWD0V5: tracers/tooling-friction.md:22`

### E-06 · P3 · Enforce the --json pure-stdout contract once at the typer boundary (cover finalize-tasks, record-analysis)
- **Scope:** Add a CLI-wide guard/test that every --json command emits exactly one JSON document on stdout (Rich to stderr); fold #2605's allocator case into it.
- **Labels:** domain:cli, reliability, tech-debt
- **Depends on:** #2605
- **Verdict basis:** PARTIAL. Evidence: `common-docs-consolidation-01KW3Q6M: tracers/tooling-friction.md:11`

### E-07 · P3 · Mutating verbs print their outcome (and flush) before any slow tail work; bound every post-write tail
- **Scope:** implement/move-task/next emit the result line + JSON before telemetry/bookkeeping tails and cap the tail with a timeout. Re-check the 2026-09-22 next-handoff overrun first (may be a new instance).
- **Labels:** domain:cli, reliability, usability
- **Depends on:** #3046
- **Verdict basis:** CLOSED-ONLY. Evidence: `dossier-guard-reexport-analyze-cleanup-01M0NHRT: tracer-tooling-friction.md:320`; `custom-mission-guard-failure-blocking-inert-01M0STY0: tracer-tooling-friction.md:135`

### E-08 · P3 · Infer --mission from the lane/coord worktree or mission branch when unambiguous
- **Scope:** When cwd is a mission-owned worktree (or HEAD is a kitty/mission-<slug>-<mid8>-* branch) resolve the mission via the canonical selector; keep MISSION_AMBIGUOUS_SELECTOR fail-closed. Fix WP prompt footers/help examples that omit --mission.
- **Labels:** domain:cli, usability, enhancement
- **Depends on:** none
- **Verdict basis:** UNCOVERED. Evidence: `reconcile-flake-family-01M34HR7: tracer-tooling-friction.md:63`; `charter-authority-flip-01M14RB3: tracer-tooling-friction.md:4`

### E-10 · P3 · Guard: every `spec-kitty …` invocation in shipped prompts/skills must resolve in the live CLI registry
- **Scope:** Architectural test that parses command snippets in packs/built-in + skills and resolves them against the typer app (verb + flags).
- **Labels:** domain:cli, tech-debt, documentation
- **Depends on:** #4441, #2728
- **Verdict basis:** PARTIAL. Evidence: `accept-fail-closed-missing-lanes-01M3CC1V: tracer-tooling-friction.md:9`; `interpreter-matrix-3-13-env-and-divergence-01M34HVD: tracer-tooling-friction.md:120`

### E-11 · P3 · spec-commit: name the paths it skipped instead of silently committing a subset; tool-written meta (pr_bound) must be committed atomically
- **Scope:** spec-commit returns skipped_paths with reasons (non-zero or warning when any requested path is skipped); mission create --pr-bound commits its meta.json write.
- **Labels:** domain:git, domain:cli, type:bug
- **Depends on:** #2739
- **Verdict basis:** PARTIAL. Evidence: `terminus-safety-invariant-01M2XFT7: tracers/tooling-friction.md:5`; `lifecycle-gate-execution-context-01KY72GQ: tracers/tooling-friction.md:37`

### E-16 · P3 · status emit --review-result-json: accept doctrine's 'rejected' as an alias of changes_requested (or align doctrine)
- **Scope:** Pick one canonical verdict vocabulary across CLI and doctrine/skills; accept the other as an input alias at the boundary (like doing->in_progress).
- **Labels:** domain:status, domain:cli, usability
- **Depends on:** none
- **Verdict basis:** PARTIAL. Evidence: `ci-nightly-wallclock-budget-01M34HNZ: tracer-tooling-friction.md:599`; `charter-epic-golden-path-nfr-budget-01M35H35: tracer-tooling-friction.md:152`

### E-18 · P3 · adversarial-squad: persist each lens report as a contract-named artifact and validate names; approval review-cycle records need an evidence floor
- **Scope:** Squad runs write reviews/<phase>.<lens>.findings.yaml (validated); approval review-cycle records require non-empty affected_files + evidence refs (pasted run output, not self-attested counts).
- **Labels:** domain:charter, workflow, reliability
- **Depends on:** #3044
- **Verdict basis:** PARTIAL. Evidence: `assertive-test-suite-sanitation-01KZME3P: tracer-tooling-friction.md:14`; `mission-type-guard-registry-01KZY2FG: tracer-tooling-friction.md:55`

### E-20 · P3 · Internal doctrine: rulings and briefs must re-verify claims against live source and the issue's own repro before issue
- **Scope:** Add an in-house tactic (packs/internal): content-anchored citations (symbol + quote, not bare line ranges), 'reproduce before declaring resolved', 'verify each named acceptance test's reachability before ruling', record overturned rulings with the measurement.
- **Labels:** domain:charter, workflow
- **Depends on:** none
- **Verdict basis:** UNCOVERED. Evidence: `bare-prose-requirements-uncounted-01KZYV3C: tracer-approach.md:5`; `custom-mission-type-second-class-citizens-01M1FQXD: tracer-design-decisions.md:151`

### E-26 · P3 · Budget-aware fan-out in implement-review: stagger waves, detect rate-limit/spend-cap deaths, checkpoint partial work
- **Scope:** Skill + orchestrator guidance: cap parallel expensive-tier agents, treat 429/spend-cap termination as a recoverable state (commit WIP, re-dispatch on cheaper tier), always list unfinished delegates in the hand-back.
- **Labels:** workflow, domain:agent-profiles, enhancement
- **Depends on:** #1049, #4205
- **Verdict basis:** PARTIAL. Evidence: `coord-primary-partition-lock-01KWZ46V: tracer-tooling-friction.md:9`; `verdict-matrix-rmw-preservation-01M32M9G: tracer-tooling-friction.md:21`

### E-28 · P3 · spk-start-agent-surface: document Claude Code worktree-isolation constraints and the scratchpad-script / git -C pattern
- **Scope:** Explain harness cwd reset and isolation refusals; single_branch dispatches must not instruct 'work in the exact shared checkout' under isolation; recommend lane worktrees instead.
- **Labels:** documentation, domain:agent-profiles, workflow
- **Depends on:** E-23
- **Verdict basis:** PARTIAL. Evidence: `dispatch-dry-run-route-only-01M1HKV2: tracer-tooling-friction.md:7`; `legacy-cleanup-split-dossier-queue-migration-01M0MGHB: tracer-tooling-friction.md:158`

### E-30 · P3 · Orchestrator verifies a dispatched WP drove the canonical implement transitions before accepting the hand-back
- **Scope:** implement-review skill: after a delegate returns, assert status.events.jsonl shows claimed/in_progress/for_review by that actor and a lane worktree exists; otherwise reject the hand-back.
- **Labels:** workflow, domain:status
- **Depends on:** none
- **Verdict basis:** CLOSED-ONLY. Evidence: `cascade-asset-silent-drop-01M0RME0: tracer-tooling-friction.md:372`; `legacy-cleanup-split-dossier-queue-migration-01M0MGHB: tracer-tooling-friction.md:332`

### E-31 · P3 · Pin the routed profile per mission/WP so auto-routing is stable across router changes; drop tk-watch's --profile workaround
- **Scope:** Record the first dispatch resolution in the Op/mission and reuse it unless --profile overrides; follow-up removes the tk-watch pin (dsp4). Separately verify op-record persistence on every dispatch path.
- **Labels:** domain:agent-profiles, reliability
- **Depends on:** #4676
- **Verdict basis:** PARTIAL. Evidence: `dispatch-dry-run-route-only-01M1HKV2: tracer-design-decisions.md:44`; `dispatch-dry-run-route-only-01M1HKV2: tracer-approach.md:7`

## Sequencing note (planner lens)

- **E-23 (one writer per checkout)** is the root for E-24, E-25 and E-28. Do it first: it removes the largest class of silent cross-agent corruption (high severity in 8 missions). E-24, E-25 and E-28 are mostly doctrine and skill text and can be done in parallel once E-23's rule is fixed.
- **E-19 (vacuous criteria)** and **E-20 (unverified rulings)** have the most evidence and no issue at all (24 missions combined). E-19 governs consumers, so it belongs in packs/built-in (spec template + review tactic). E-20 is in-house orchestration practice, so it belongs in packs/internal.
- The CLI-honesty drafts (E-04, E-05, E-11, E-16, E-17) are independent small fixes that can run in parallel. E-17 and E-09 feed the open epics #3260 and #2720.
- The COVERED clusters need no new issues. The strongest open owners are #5007 (issue-matrix gate, P1), #4228 (record-analysis dirty scope, P1), #3133, #4885/#3998 (global asset race), #3943 (merged-tree gates) and #2229 (diff-compliance).

## Honest limits

- **Search quota:** semantic `search_issues` was rate-limited for most of the run because other delegates shared the quota. I made about 8 semantic searches. To compensate, I downloaded all 3,187 issues (818 open, 2,367 closed; titles and bodies) read-only through the REST list endpoint and ran regex full-text searches locally (`all_issues_E.jsonl`, `fts.py`). That catches literal wording but misses paraphrases that semantic search would find.
- **Bodies read in full:** #5007, #3469, #4228, #3133, #4885, #2627, #2493, #3932, #2605, #2555, #1907, #3046, #2229, #3129 (partial), #3943, #1979, #3680, #1820, #2739, #2741, #669, #2364 and #4116. I also skimmed about 12 more. Other matches rest on the title plus the matched context snippet.
- **Dates:** mission dates come from the ULID prefix (mid8), accurate to about a day. The residual/regression calls in CLOSED-ONLY and PARTIAL compare that date with `closed_at`. A later witness suggests the problem persists but does not prove a regression, because it could be the same issue on an older install (stale-install, CLAUDE.md category 3).
- **E-21 is marked COVERED because doctrine covers it, not an issue** (charter standing order on adversarial-squad cadence plus the adversarial-squad skill). It is positive evidence and has nothing to file. Excluding it gives 7 issue-backed COVERED clusters.
- Several clusters (E-24, E-25, E-27, E-28) are mostly behaviour of the harness or the orchestrating agent. Spec Kitty can only change its doctrine and skills for these, and the drafts are scoped that way. E-20 is in-house practice and should go to packs/internal per the pack-tier rule.
- **Singleton or old evidence:** E-06 (one mission, 2026-06-27) and E-13 (2026-06-30) may already be fixed. They are listed for completeness only.
- I did not reproduce any finding. All claims come from the tracer items and issue text.
