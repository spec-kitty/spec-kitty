---
doc_status: active
updated: '2026-09-26'
---

# Recon — slice1 (17 most recent missions)

**Profile applied:** `retrospective-facilitator` (the builtin profile; `agent profile show` resolved it). I applied it like this:
- Every finding is captured with provenance: a `file:line` evidence pointer, all validated against the checkout.
- Proposals are recorded as data. Nothing was auto-applied (FR-010 boundary), and the repo is untouched.
- The directives it carries are 003 (decision documentation), 010 (specification fidelity: I report what the tracers say and do not re-derive it) and 018.
- I also loaded the review-action charter context (`charter context --action review --json`). From it I took the Terminology Canon, the Pre-existing Failure Reporting Rule, and Standing Order #3 (tracer files).

Deliverable: `recon-slice1.jsonl` has 243 items: 104 friction, 65 note, 35 concern, 39 recommendation. All 17 missions are covered, and every tracer file listed in `slice1.txt` was read in full, including the WP02 tracer, its review-cycle file, and the WP04 close-out prompt.

Mission path prefix below: `kitty-specs/<mission>/`.

## Per-mission digest

### accept-fail-closed-missing-lanes-01M3CC1V (#4891)
- [NOTE] `AcceptanceSummary.ok` consults `activity_issues` only, never `skipped_checks`/`blocked_checks`. This is the root cause of the silent accept pass (`tracer-design-decisions.md:15`).
- [NOTE] An existing characterization test (`test_missing_lanes_manifest_is_a_silent_noop`) encoded the bug and had to be inverted to serve as the red anchor (`tracer-approach.md:9`).
- [CONCERN] `merge` never re-verifies acceptance, so `accept` is the only chokepoint. Defense-in-depth is recorded only in the PR body and is not ticketed (`tracer-design-decisions.md:40`).
- [FRICTION] `mission create --pr-bound` requires `--branch-strategy already-confirmed`, and that flag is truncated off the first page of `--help` (`tracer-tooling-friction.md:9`).
- [NOTE] The tooling-friction tracer is still at its seed placeholder (`tracer-tooling-friction.md:13`).

### upgrade-idempotent-worktree-metadata-01M38X2Y (#4972)
- [FRICTION] Lane worktrees have no `.venv`. As a result:
  - 46 tests in `tests/upgrade` false-red on `Missing executable: <worktree>/.venv/bin/spec-kitty`.
  - `make test-fast` cannot run in the worktree because it calls `uv run`, so its flags had to be replayed by hand (`traces/tracer-blast-radius.md:24`, `:53`).
- [FRICTION] Three charter JSON-contract tests always fail inside a linked worktree, because the charter-write refusal fires (`traces/tracer-blast-radius.md:66`).
- [FRICTION] Single-file mypy reports `no-any-return` false positives because pyproject sets `follow_imports=skip` (#3719) (`traces/tracer-blast-radius.md:96`).
- [NOTE] The fix belongs at the single shared mint site in `runner.py`, which has three callers. A CLI-only fix would have missed two of them (`traces/tracer-root-cause.md:6`).
- [CONCERN] The `lanes/merge.py` and `stale_check.py` consumers still refuse on a metadata.yaml conflict. The fix was prevention-only by operator choice (`traces/tracer-root-cause.md:21`).

### coord-read-fail-closed-01M38VVH (#4959, #4966)
- [FRICTION] The bug under repair (#4966) blocked this mission's own `agent decision open` with `MISSION_NOT_FOUND`, because `meta.json` was resolved via the coord husk. The decision was recorded inline in `research.md` instead (`tracer-tooling-friction.md:10`).
- [NOTE] Root cause: tracer-append's exception tuple swallowed an unmaterialised-coord read into `""`, and the writer then produced a fresh header that clobbered the file (`tasks/WP02-tracer-fail-closed.md:49`).
- [CONCERN] #4979 (`_coord_branch_exists` / `doctor coordination --fix`) was left explicitly out of scope (`tracer-design-decisions.md:7`).
- [FRICTION] #5007 (issue-matrix per-WP gate plus review-cycle commit friction) was carried in (`tracer-tooling-friction.md:3`).
- [CONCERN] Two process gaps:
  - The review-cycle record is a bare "Approved by claude" with empty `affected_files`.
  - All three tracers stop at "(planning) seeded" (`review-cycle-1.md:11`; `tracer-approach.md:11`).

### charter-epic-golden-path-nfr-budget-01M35H35 (#4213, #4211)
- [FRICTION] The `plan --json` scaffold was stale (a `src/doctrine` path and "Constitution Check"). Root cause: the stale `.kittify/overrides` template, SK-248 (`tracer-tooling-friction.md:41`, `:156`).
- [FRICTION] `finalize-tasks` raised `LANE_DEPENDENCY_CYCLE` because every `planning_artifact` WP collapses into one `lane-planning` (`tracer-design-decisions.md:733`).
- [FRICTION] A dispatch premise was wrong: the lanes had already been auto-merged into the `lane-planning` workspace, so the manual `git apply` failed for every lane (`tracer-tooling-friction.md:89`).
- [FRICTION] Other recurring friction:
  - SK-250: status files left dirty after auto-commit.
  - #4017: the global-asset race.
  - The issue-matrix gate blocks every approval.
  - A rejection resets all subtasks.
  - The ruff-format-exclude ratchet went red on a file the WP did not own (`tracer-tooling-friction.md:141-171`).
- [NOTE] Root cause of the "hang": `ensure_global_agent_commands` renders 104 templates on every CLI call, accounting for about 55-65% of per-call cost (`tracer-design-decisions.md:376`).
- [CONCERN] The run passed at 102.56s against a hard 110s bar, a margin of only 7.44s. Setup time is dominated by the `test_venv` `pip install -e`, which no fix touched (`tracer-approach.md:191`).
- [CONCERN] Governance overhead:
  - Six spec review rounds, two HALTs and six operator rulings, mostly over attribution and wording.
  - Phase agents twice self-authorized a decision fork (PLAN-GOV-001) (`tracer-design-decisions.md:73`, `:597`).
- [CONCERN] Remediation passes regressed on citation accuracy: a wrong raise site, and `research.md` not mirrored (`tracer-design-decisions.md:552`).

### coordination-doctor-branch-safety-01M35EN8
- [FRICTION] `charter context --action specify` reported unresolved configured directive IDs (`tracer-tooling-friction.md:5`).
- [FRICTION] The `spec-kitty next` specify-to-plan handoff exceeded the command wait window, and lifecycle state had to be recovered by hand (`tracer-tooling-friction.md:10`).
- [FRICTION] Team Kitty publication was unavailable because the session was logged out (`tracer-tooling-friction.md:8`).
- [NOTE] Success is treated as a postcondition: "Fast-forwarded" prints only after the ref is re-read (`tracer-design-decisions.md:14`).

### windows-upgrade-mode-fidelity-01M35C25 (#4923, #4927; #4925 deferred)
- [FRICTION] The defects are Windows-only but CI runs on Linux. The risk is mocking too coarsely, so a test passes for the wrong reason (`tracer-tooling-friction.md:6`).
- [FRICTION] `record-analysis` fails with `DIRTY_WORKTREE` on pre-existing untracked evidence and kitty-ops files. The trap is that `mv kitty-ops/*.jsonl` mass-deletes tracked files (`tracer-tooling-friction.md:8`).
- [FRICTION] The remote is named `skupstream`, not `upstream` (`tracer-tooling-friction.md:5`).
- [FRICTION] New helpers must go through the no-follow re-export shim (`tracer-tooling-friction.md:9`).
- [NOTE] The post-spec squad retargeted the #4927 driver (the original targets were wrong) and added a missed crash site (`tracer-design-decisions.md:12`).
- [CONCERN] #4925 is untraced and needs a real Windows run (`tracer-approach.md:5`).

### user-content-preservation-01M3549Q (#4888, #4907, #2691, #4895, #4910, #4896, #4890)
- [NOTE] `safe_commit`'s stash push/pop dance failed deterministically on partially staged files. It was replaced with `git commit --only` (`tracer/approach.md:12`).
- [CONCERN] The whole-index backstop is no longer called from `safe_commit` (`tracer/approach.md:24`).
- [NOTE] `_remove_project_agent_surface` reported "Removed" while it was actually preserving content (`tracer/design-decisions.md:13`).
- [NOTE] Other silent-success findings:
  - The `SafeCommitRecoveryFailed` flattening exited 0 (`tracer/approach.md:30`).
  - Two backup-naming authorities existed (`tracer/design-decisions.md:16`).
- [FRICTION] The auto-mode classifier blocked `git push origin main` (`tracer/tooling-friction.md:5`).
- [NOTE] The tooling-friction tracer has only one entry for a seven-issue mission (`tracer/tooling-friction.md:5`).

### interpreter-matrix-3-13-env-and-divergence-01M34HVD (#4866, #4922, #3189)
- [FRICTION] Nested `uv run --frozen` calls in two tests rebuild and downgrade the venv mid-run.
  - Pinning `UV_PROJECT_ENVIRONMENT` is necessary but not sufficient; the fix is `--no-sync` (`tracer-tooling-friction.md:729`).
- [FRICTION] Three `finalize-tasks` defects:
  - `build_wp_manifests` drops a WP with `owned_files: []` (`:139`).
  - SK-25 false lane cycle, second recurrence (`:367`).
  - `_detect_dependency_conflicts` blocks adding a genuine dependency edge (`:460`).
- [FRICTION] `mark-status` has no WP scope. Subtask IDs collide (T001 in every WP), writes silently land on WP01, and the command reports false success (`tracer-tooling-friction.md:684`).
- [FRICTION] SK-99: the harness backgrounds any foreground call at about 600s regardless of the `timeout` value, and subagents strand (`tracer-tooling-friction.md:615`).
- [FRICTION] The stale plan scaffold was first misdiagnosed as a CLI defect. The real cause is the stale `.kittify/overrides` template dated 2026-04-17 (`tracer-tooling-friction.md:197`).
- [FRICTION] Doc/CI drift:
  - The docs claim Bandit and pip-audit are blocking, but neither is wired into CI (`:95`).
  - mypy is run by no workflow (`tracer-approach.md:184`).
- [FRICTION] SK-64: the commitlint ignore regex misses the scaffold commit (`:8`).
- [FRICTION] SK-237: the `tasks-packages` verb does not exist (`:120`).
- [CONCERN] The 3.12 CI floor was already exposed to the `dir_fd` defect. Residual divergence was filed on #3189 (`tracer-tooling-friction.md:664`; `tracer-design-decisions.md:277`).

### reconcile-flake-family-01M34HR7 (#4882)
- [FRICTION] SK-240: `requirement_refs` lives in three unsynced places, which cost 3 of 5 analyze rounds (#3221) (`tracer-tooling-friction.md:36`).
- [FRICTION] SK-241: the generated WP prompt shows raw `git commit` instead of safe-commit, omits `--mission`, and leaves the `status emit` flag shape undocumented. This template ships to consumers (`tracer-tooling-friction.md:63-84`).
- [FRICTION] The spec's "34 pre-existing failures" were a stale-venv false red. Three design phases believed part of the suite was red (`tracer-tooling-friction.md:104`).
- [FRICTION] SK-64 fired three times in one mission (`tracer-tooling-friction.md:131`).
- [FRICTION] Lane worktrees have no `.venv`, and `radon` is missing (`:85-94`).
- [CONCERN] `workflow_run` executes main's copy of the workflow, so the PR cannot exercise its own fix and verification happens only after merge (`tracer-design-decisions.md:92`).
- [CONCERN] `plan.md` was amended twice after the squad passed it, and the squad never re-ran (`tracer-design-decisions.md:53`).
- [NOTE] The plan-time retry design was vacuous and was reversed. The real diff was about 3x the estimate (`tracer-design-decisions.md:40`; `tracer-approach.md:109`).

### ci-nightly-wallclock-budget-01M34HNZ (#4865, #4864)
- [FRICTION] SK-91/SK-199: `implement` silently created a lane branch and worktree for a `single_branch` mission.
  - Code was stranded on the undeclared branch, and commits had to be duplicated (`tracer-tooling-friction.md:211`).
  - Later a phantom `lane-planning` auto-merge and SK-69 blocked WP07 (`tracer-tooling-friction.md:662`).
- [FRICTION] `finalize-tasks` defects:
  - The requirement-ref regex does not recognize `SC-###` (`:5`).
  - A wrapped refs line is silently truncated (`:33`).
  - The lane cycle recurs (`:57`).
  - A `lanes.json` was written for a `single_branch` mission, with a nonexistent branch and bogus surfaces (`:99`).
- [FRICTION] The `--review-result-json` field (`review_result`) does not match the payload validator (`evidence`). The Zeitgeist moment is dropped on every approved/done transition, with a WARNING printed next to OK (`tracer-tooling-friction.md:338`).
- [FRICTION] "Global asset input changed" surfaces as a raw RuntimeError from every subcommand. It is a transient race, likely between concurrent missions writing `~/.agent/workflows`, and a retry clears it (`tracer-tooling-friction.md:462`).
- [FRICTION] Lane-state gaps:
  - SK-175: safe-commit accepted a commit for a WP still in `planned`.
  - `mark-status` has no `skipped` value.
  - The verdict vocabulary disagrees (`rejected` vs `changes_requested`).
  - `--reason` never reaches notes (`:421`, `:516`, `:599`, `:621`).
- [NOTE] Root cause of #4864: the committed durations list had the wrong length, so the consumer silently fell back to uniform weights. This comes from drift plus a producer/consumer marker mismatch (`tracer-tooling-friction.md:541`).
- [NOTE] Orchestration lessons:
  - A dispatch that was silent on sub-delegation led to two writers on one WP.
  - Concurrent mutating lenses produced a false failure (`tracer-tooling-friction.md:823`, `:832`).
- [CONCERN] AC4 was not met: the long pole got 2m16s worse. Twenty of 21 modules remain allowlisted as mismatched, and no follow-up was filed (`tracer-approach.md:224`, `:57`).

### verdict-matrix-rmw-preservation-01M32M9G (#4858, #4868)
- [FRICTION] Two concurrent missions ran in one clone. Planning runs in the root checkout, so HEAD was switched and a stray commit landed on the other mission's branch (`tracer-tooling-friction.md:5`).
- [FRICTION] The claim step auto-commits `base_commit` into kitty-specs on the lane branch, and the review gate then refuses it. The suggested directory-wide `git restore` would delete the matrices (`tracer-tooling-friction.md:26`).
- [FRICTION] Worktrees have no `.venv`, so tests silently import the unfixed main source (`tracer-tooling-friction.md:35`).
- [FRICTION] Opus subagents hit HTTP 429 mid-wave and were re-dispatched on sonnet (`tracer-tooling-friction.md:21`).
- [FRICTION] The shipped specify checklist template emits "Feature" (`tracer-squad-findings.md:48`).
- [NOTE] Squads caught that the deterministic harness could not gate the lock, and found a fail-open on lock timeout (`tracer-squad-findings.md:22`, `:84`).
- [CONCERN] The lock covers verdict-vs-verdict only. #2482 is still unfolded (`tracer-design-decisions.md:46`, `:50`).

### finalize-repin-orphaned-planning-commit-01M31TAT (#4827)
- [FRICTION] The lane-branch hygiene gate refused move-task because the implement bootstrap auto-commits kitty-specs onto the lane branch (field report L1). The mission pivoted to implementing on the mission branch (L2) (`tracer-tooling-friction.md:10-11`).
- [FRICTION] The editable install cannot rebuild because the artifactory has no hatchling (`tracer-tooling-friction.md:5`).
- [FRICTION] The blast radius lies outside `make test-fast`, and the golden and doc-freshness gates only run in CI (`tracer-tooling-friction.md:6-7`).
- [CONCERN] A fifth pin reader (`detached_base`) was left non-orphan-aware (#3571) (`tracer-design-decisions.md:20`).
- [NOTE] The #4178 preserve-WARN false positive fired on the tool's own bookkeeping commit and was folded in (`tracer-design-decisions.md:11`).

### mission-type-canonical-source-01M302V9 (#3831, #4088)
- [NOTE] The planning premise was wrong: the charter tier lacks path and artifact data. The mission was re-scoped, WP04 and WP05 were dropped, and full convergence was deferred to #2652 (`tracer-design-decisions.md:36`).
- [CONCERN] The legacy `mission.py` resolver remains. The new `path_conventions` slot is null for every built-in (`tracer-design-decisions.md:41`).
- [FRICTION] There is no `agent mission issue-matrix` CLI, so the matrix is hand-authored (`tracer-tooling-friction.md:10`).
- [FRICTION] `CharterCatalogMissWarning` noise appears in charter context output (`tracer-tooling-friction.md:7`).
- [NOTE] The implement-phase tracer sections are empty (`tracer-approach.md:24`).

### move-task-approval-ergonomics-01M302R0 (#3469)
- [FRICTION] Live dogfood: the gate demanded verdicts for context-only refs. No truthful value existed, so a false `deferred-with-followup` had to be recorded (`tracer-tooling-friction.md:18`).
- [NOTE] The gating computation was forked across the approval blocker, `merge_gates` and doctor. It was unified into one helper (`tracer-design-decisions.md:24`).
- [NOTE] The WP09 `not_applicable` intent was documented but never implemented (`tracer-design-decisions.md:35`).
- [FRICTION] Issue text drifts from current behaviour, so reproduce-before-fix was essential (`tracer-tooling-friction.md:13`).
- [NOTE] The squads caught a vacuously green red-first framing (`tracer-design-decisions.md:44`).

### charter-catalog-coherence-01M2XQQF (#4785)
- [NOTE] The integration suite on the merged tree caught three real cross-WP regressions that per-WP and pre-PR reviews missed (`tracer-tooling-friction.md:33`).
- [FRICTION] The #2627 global-asset race hit `activate`, `move-task` and `merge`; a retry heals it (`tracer-tooling-friction.md:11`, `:21`).
- [FRICTION] Folding squad findings after `finalize-tasks` left `planning_commit_sha` stale (`tracer-tooling-friction.md:17`).
- [FRICTION] A dependent lane went stale during consolidation and needed a manual merge plus `--resume` (`tracer-tooling-friction.md:23`).
- [FRICTION] Charter writes are not isolated by worktrees, so repro needed separate clones (`tracer-tooling-friction.md:7`).
- [FRICTION] Ratchets:
  - The format-exclude ratchet tripped.
  - The dead-module allowlist ratchets in both directions (`tracer-approach.md:26`).

### merge-destructive-op-safety-01M2XQF8 (#4752, #4753, #4754)
- [NOTE] There were about nine forked dirty-check predicates with no owner, so one guard was unified (`tracer-approach.md:7`).
- [NOTE] The planned chokepoint `remove_workspace` is dead code with zero callers, and the plan was re-scoped (`tracer-design-decisions.md:33`).
- [NOTE] The hand-written gate allowlist was wrong, so the baseline has to come from a live census (`tracer-design-decisions.md:40`).
- [FRICTION] The clone was 353 commits behind, and its `upstream` remote pointed at the pre-move org (`tracer-tooling-friction.md:9`).
- [CONCERN] `branch -D` was deferred (`tracer-design-decisions.md:15`).

### terminus-safety-invariant-01M2XFT7 (#4764, #4765, #4474, #2745)
- [NOTE] The pre-PR aggregate squad caught a HIGH cross-WP defect (rollback x bake) that both WP reviews missed, because the test mocked the seam (`tracers/tooling-friction.md:33`).
- [FRICTION] The global-asset race broke `charter context`, and subagents fell back (`tracers/tooling-friction.md:23`).
- [FRICTION] Doctrine and packs:
  - A worktree is not an install; `regenerate-graph` needs `PYTHONPATH` plus `SPEC_KITTY_PACKS_ROOT`.
  - Stale-binary false reds.
  - `charter context` is not a valid activation check (`tracers/tooling-friction.md:9`).
- [FRICTION] `spec-commit` silently skips non-spec artifacts, and `issue-verdict` writes are not visible in the checkout (`tracers/tooling-friction.md:5-6`).
- [FRICTION] A local-vs-pinned ruff version skew produced format drift (`tracers/tooling-friction.md:19`).
- [NOTE] `SPEC_KITTY_ENABLE_SAAS_SYNC=1` was still needed to bypass the daemon boundary for completion regeneration, so sync residue still gates behaviour (`tracers/tooling-friction.md:31`).
- [CONCERN] `git revert` cannot cross a consolidation merge commit, so direct-on-target rollback was deferred to #3897 (`tracers/tooling-friction.md:18`).

## Cross-mission themes in this slice (ranked by mission count)

1. **cli-ergonomics** — 12 missions, 15 items. The strongest sub-signal is the **"Global asset input changed" RuntimeError race**, which appears in 4 missions (golden-path #4017, ci-nightly, charter-catalog #2627, terminus):
   - Stated root cause (ci-nightly `tracer-tooling-friction.md:505-514`, labelled a hypothesis): concurrent missions regenerate the shared `~/.agent/workflows` assets inside `ensure_global_agent_commands`.
   - It surfaces as an unenveloped traceback, and a retry clears it.
   - Recommendation: envelope the error and make global asset regeneration concurrency-safe.

   Other items in this theme: undocumented required flags (SK-241), `spec-commit` silently skipping artifacts, no issue-matrix CLI, and the `record-analysis` carrier-key collision.

2. **coord-branch-worktree** — 8 missions, 18 items.
   - Implement bootstrap commits kitty-specs onto the lane branch, and the review gate then refuses it. This hit finalize-repin (L1) and verdict-matrix, and the gate's remediation is unsafe.
   - `single_branch` missions get phantom lanes: silent lane creation, a phantom `lane-planning` merge, and SK-69 (ci-nightly).
   - The coord husk breaks `meta.json` resolution (#4966).
   - `issue-verdict` writes are invisible in the checkout.
   - Stated root causes: the workspace resolver and implementation-commit guard ignore the `meta.json` topology, and the bootstrap writes planning files onto lanes.
   - Recommendations: resolve guards against the resolved write branch, skip lane machinery for lane-less topologies, and scope `git restore` remediation to single files. Two missions pivoted to implementing directly on the mission branch.

3. **test-env-venv-install** — 8 missions, 17 items.
   - Worktrees have no `.venv`. Tests silently import the main checkout's unfixed source, fixtures that need `<worktree>/.venv/bin/spec-kitty` false-red, and `make test-fast` is unusable in a worktree.
   - Stale-venv false reds cost reconcile-flake three design phases.
   - Nested `uv run` calls downgrade the venv mid-run (interpreter-matrix, fixed with `--no-sync`).
   - Installed/pyproject version skew; hatchling missing from the artifactory.
   - Recommendations: re-sync before recording a failure as pre-existing, run nested uv calls with `--no-sync`, and provide a fast-tier target that takes an explicit interpreter.

4. **finalize-tasks-planning** — 6 missions, 22 items (the highest item density).
   - **The `LANE_DEPENDENCY_CYCLE` from single `lane-planning` bundling hit 3 missions** (golden-path, interpreter-matrix as SK-25's second recurrence, ci-nightly).
   - Other defects:
     - `owned_files: []` is dropped.
     - The dependency-conflict gate blocks adding edges.
     - `requirement_refs` has three unsynced copies (SK-240/#3221).
     - The SC-### prefix is ignored, and wrapped lines are silently truncated.
     - `lanes.json` is written for `single_branch` missions.
     - Folding findings after finalize leaves a stale `planning_commit_sha`.
   - Stated root cause: `PLANNING_LANE_ID` bundles every planning WP regardless of its position in the graph.
   - Recommendations: ordering constraints stay out of `dependencies:`, detect the shape early and suggest a fold, and use a single write path for refs.

5. **ci-gates-routing** — 6 missions, 18 items.
   - SK-64: the commitlint scaffold-commit gap hit 3 missions, three times in one of them.
   - `workflow_run` and schedule-only workflows cannot validate their own PR.
   - Vacuous or unwired gates: commit-msg `|| true`, mypy in no workflow, Bandit and pip-audit documented as blocking but not wired.
   - The e2e shard is path-scoped, so CLI-only pushes skip the golden path.
   - #4864: a silent uniform fallback on wrong-length timing lists; a length-agreement gate was added.
   - Golden-contract and doc-freshness gates only run in CI.

6. **review-loop-verdicts** — 6 missions. The issue-matrix gate demands verdicts for every cited #NNN, including context-only references. Related problems:
   - A rejection resets subtasks.
   - Doctrine says `rejected`, the CLI says `changes_requested`.
   - Review-cycle records are thin.
   - move-task-ergonomics added a `not-applicable` verdict and classification as the fix.

7. **squad-review-value** — 6 missions. Adversarial and integration squads repeatedly caught HIGH defects that per-WP review missed:
   - Cross-WP regressions on the merged tree (charter-catalog, 3 of them; terminus, 1).
   - Vacuous red-first tests (move-task, verdict-matrix).
   - Wrong fix targets (windows).
   - Recommendation: always run the integration gate on the consolidated tree, and do not mock the partner seam.

8. **agent-harness-sandbox** — 6 missions.
   - SK-99: auto-backgrounding at about 600s regardless of `timeout`, with strand-on-turn-end (interpreter-matrix, ci-nightly).
   - Bash cwd resets; the auto-mode push block; the `next` wait window.
   - Recommendation: `run_in_background` plus an in-turn `kill -0` or `tail --pid` loop.

9. **dead-code-legacy-residue / duplicate-authorities** — 6 and 4 missions.
   - A dead `remove_workspace`.
   - About nine forked dirty predicates.
   - Gating logic forked three ways.
   - Two backup authorities.
   - Legacy `mission.py` alongside an unpopulated `path_conventions`.
   - The `SPEC_KITTY_ENABLE_SAAS_SYNC` residue still gates the completion regen.

10. **arch-gate-allowlists** — 6 missions. Ratchets (the format-exclude list and the dead-module allowlist) go red when a WP incidentally cleans a file it does not own (pyproject.toml). Hand-written allowlists were wrong, so baselines must come from a live census.

11. **templates-prompts** — 5 missions.
    - The stale `.kittify/overrides` plan template won resolution (golden-path, interpreter-matrix, SK-248; misdiagnosed at first).
    - "Feature" wording in the canonical `plan-template.md:4` and in the checklist template.
    - The WP prompt suggests raw git and assigns PR creation to the WP agent.

12. **docs-drift** — 5 missions. Mis-cited lines and raise sites in remediation passes, `depends_on_lanes` mischaracterized, the lint-policy doc wrong, and no canonical location for contracts.

13. **tracer-process-itself** — 6 missions. Tracers were left at seed placeholders with no implement-phase entries: accept-fail-closed, coord-read, mission-type, move-task, merge-destructive, and a single entry in user-content. By contrast, ci-nightly, interpreter-matrix and golden-path produced very rich, self-correcting, append-only logs.

14. **subagent-orchestration / multi-clone-environment** — 4 missions each.
    - Dispatches that are silent on sub-delegation, and concurrent mutating lenses in one checkout.
    - Opus 429s mid-wave.
    - Two missions in one clone; remotes named differently per clone; clones hundreds of commits behind.
    - CPU contention on a shared host inflated wall-clock by about 10x.

15. **Lower frequency:**
    - status-lanes-move-task (4 missions): SK-175 unclaimed commits; mark-status ID collision; SK-250 dirty status; the SK-125 actor 'user' label.
    - charter-context-activation (5 missions): the linked-worktree charter-write refusal red-flags tests; version bumps in `synthesis-manifest`.
    - zeitgeist-moment-publication (2 missions): the `review_result` vs `evidence` mismatch drops moments.
    - plan-premise-errors (3 missions).
    - governance-overhead (2 missions).

## Honest limits

- **Thin tracers.** Several tracers (accept-fail-closed, coord-read, mission-type, move-task, merge-destructive, user-content) hold only planning seeds, so implement-phase friction for those missions is almost certainly under-captured. I did not mine `retrospective.yaml` or WP activity logs to back-fill it.
- **Ledger references not resolved.** Many items cite SPEC-KITTY-LEDGER IDs (SK-06/25/64/69/91/94/99/125/175/199/218/234/237/240/241/248/250/251). That ledger lives outside this checkout, so I could not verify their current status.
- **Issue state not checked.** GitHub issue numbers are recorded as cited. I did not check whether they are open or closed.
- **Some root causes are hypotheses.** For example, the global-asset race was attributed to concurrent missions writing `~/.agent/workflows`, and the tracer labels this a hypothesis. Where a tracer later appended a correction (interpreter-matrix's SK-06 misdiagnosis, the stale-template cause, `depends_on_lanes`; ci-nightly's hand-edit accusation and the "no sanctioned command" claim), I recorded the corrected version.
- **Some counts cannot be separated.** Items that repeat across missions are counted once per mission, but items inside one mission can overlap. For example, ci-nightly's SK-64 appears in both its approach and friction tracers.
- **Theme slugs I coined.** These are not in the vocabulary: `squad-review-value`, `multi-clone-environment`, `duplicate-authorities`, `plan-premise-errors`, `zeitgeist-moment-publication`, `atdd-red-first`, `safe-commit-git-plumbing`, `destructive-op-safety`, `upgrade-migrations`.
