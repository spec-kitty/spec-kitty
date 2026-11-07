# F: doctrine upstream (S11, #7285) and the write-service ADR set (S9, #7284)

Discovery agent: doctrine-daphne lens (curator: classify, audit overlap, never promote without approval).
Read-only. Pack trees read from the fetched core copies `packs/built-in` (pin `a79c3631`) and
`packs/internal` (pin `ecda7b00`); paths below are relative to the pack root, so `built-in/X`
maps to `spec-kitty-open-packs:packs/built-in/X`. The research doctrine scan was taken at
open-packs `23686fb`; its paths differ from the pinned tree (for example the toolguide is
`toolguides/GIT_WORKTREE_PR_WORKFLOW.md`, the implement prompt is
`missions/mission-steps/software-dev/implement/prompt.md`). Line numbers are the pinned tree's.

## Summary

- **Pack doctrine: 31 edits in 17 pack files** (14 built-in, 3 internal), plus a glossary block of
  8 new or rewritten terms. The core command skills under `src/charter/offering/skills/` (source,
  not generated) need 9 more edits in 6 skills; they are core files, not open-packs files.
- **No status-surface rule exists anywhere in the packs.** The best homes are the three
  task-prompt templates' "Progress & Status" section (all WPs see it), the implement and review
  prompts' "Working Directory" sections, and a new glossary term `resolved status surface`.
- **The glossary actively contradicts ruling 3:** `status commit` says "Status commits target lane
  branches" (`built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml:608-612`).
- **"lane" has one glossary entry and it is the WP state** (`:259-265`). No entry exists for
  execution lane, lane worktree, lane branch, coordination worktree, harness isolation worktree or
  PR-landing worktree. "merge" is still the verb for consolidation in 6 glossary definitions and a
  dead artefact (`.kittify/merge-state.json`, `:344-349`).
- **The manual stale-lane refresh lives in core, not in the packs:** the CLI prints it
  (`src/specify_cli/lanes/stale_check.py:143,152`) and three core skills repeat it. Doctrine cannot
  drop it until the CLI message changes; that is a code change S11 must pair with (or hand to S3).
- **No consolidate prompt exists** (`consolidate` is a thin CLI wrapper,
  `src/specify_cli/skills/command_installer.py:116-139`). Ruling 6 ("cleanup is the final
  consolidation step") can only be taught in the accept prompt, the wrap-up procedure and the
  skills, unless a consolidate prompt is added (scope growth; open question).
- **S9 needs 5 records, not 4:** three core ADRs (placement, gates, publication/cursor) and two
  `spec-kitty-events` ADRs (plumbing commit with CAS, read service over git objects), plus a short
  amendment to ADR 2026-10-22-1 D-6 that points at them. Writing to the object store is a new
  `EventLogPort` adapter in D-6's sense, so D-6's "own ADR before such an adapter" applies.
- **The mission-write contract must change before its 1.0.0 release:** `WriteSurface` knows only
  `checkout_append` and `coordination_transaction_append` ("in the coordination worktree"), and
  five refusal codes presuppose a coordination worktree. ADR 2026-10-27-1 says any closed-response
  change after 1.0.0 is a major version. This is the most time-sensitive S9 finding.
- **The coordination transaction writes more than events:** `BookkeepingTransaction.write_artifact`
  and `enroll_subprocess_byproducts` (`src/specify_cli/coordination/transaction.py:1067,1110`) write
  notes, trace, issue-matrix and decision artefacts into the coordination worktree. A worktree-less
  coordination branch needs a rule for every coordination-partition kind, not only the event log.

## Call sites / code shapes

### Part 1: pack doctrine (S11). Tier B = `packs/built-in` (ships to consumers), I = `packs/internal`.

Depends-on column: the slice whose behaviour the new text describes. Text that teaches behaviour
not yet built must land with or after that slice, never before (else doctrine lies).

#### Status-surface rule (ruling 8)

| # | Path (pack root) : line | Tier | Current text | Proposed text | Depends |
|---|---|---|---|---|---|
| 1 | `built-in/missions/software-dev/templates/task-prompt-template.md:119-128` (also `research/templates/task-prompt-template.md:~122-131`, `documentation/templates/task-prompt-template.md:~114-123`) | B | "Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in this prompt file." | Keep, then add: "**Read status only through the CLI** (`spec-kitty agent tasks status --mission <handle>`), which reads the resolved status surface. Never read `status.events.jsonl` or `status.json` from a lane worktree, a coordination worktree or any other checkout's files: a lane's copy is stale by design and never counts." | S1 (rule holds today; wording of "lane copy" holds fully after S6) |
| 2 | `built-in/missions/mission-steps/software-dev/implement/prompt.md:161-164` | B | "Confirm all dependency WPs are in `approved` or `done` status before proceeding." | "Confirm all dependency WPs are `approved` or `done` with `spec-kitty agent tasks status --mission <handle>`. Do not read the event log from your checkout; the CLI reads the resolved status surface." | none |
| 3 | `built-in/missions/mission-steps/software-dev/review/prompt.md:300-301` | B | "check the history field or `status.events.jsonl` to find the last `in_progress` actor" | "run `spec-kitty agent tasks status --mission <handle>` to find the last `in_progress` actor" (the frontmatter history field is retired; the template says so) | none |
| 4 | `built-in/missions/mission-steps/software-dev/review/guidelines.md:9-10` | B | "confirm each WP listed in its `dependencies` ... is `approved` or `done` ... note their current lanes" | "...is `approved` or `done` according to `spec-kitty agent tasks status` ... note each dependent's current WP state" | none |
| 5 | `built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml:608-612` (`status commit`) | B | "Status commits target lane branches, not protected branches." | "A status commit lands on the Mission's resolved status surface: the coordination branch for coordination topologies, the write branch otherwise. It never lands on a lane branch, and never on a protected branch." | S6 (ruling 3); today lanes still carry copies but status commits already do not target them for coordination topologies |
| 6 | glossary, new term `resolved status surface` | B | absent | "The one place a Mission's status is read from and written to, as the CLI resolves it per topology: the coordination branch for `coord`/`lanes_with_coord`, the write branch (repository root checkout or owned checkout) for `single_branch` and `lanes`. A lane worktree's own status files are never a status surface. Read it with `spec-kitty agent tasks status`." | S1 |
| 7 | `internal/glossary_packs/spk-internal.glossary-pack.yaml:106-113` (`coord/primary partition`) | I | "...routing lifecycle surfaces ... to the coord branch ..." | add: "Read lifecycle state through the CLI, never from a checkout's files; see `resolved status surface`." | S1 |

#### One worktree vocabulary; "lane" WP state vs execution lane

| # | Path : line | Tier | Current | Proposed | Depends |
|---|---|---|---|---|---|
| 8 | glossary `:259-265` (`lane`) | B | "Work package lifecycle state. Canonical lanes are planned, ..." | Rename the surface to `WP state` with `lane` as a legacy alias (`synonyms_to_avoid: lane (when meaning WP state)`), and add a separate `execution lane` entry: "A group of WPs that `finalize-tasks` computes to run in sequence on one lane branch. Not a WP state." Status vocabulary stays (`to_lane` in events is a field name, not prose). | none; glossary-only |
| 9 | glossary, new terms | B | absent | `lane branch` (`kitty/mission-<slug>-lane-<id>`; the durable carrier of an execution lane's commits); `lane worktree` (a spec-kitty checkout of a lane branch under `.worktrees/`, created by `spec-kitty implement`; short-lived after S3); `coordination worktree` (checkout of the coordination branch; retired after S9); `write checkout` (single_branch: repository root or owned checkout); `harness isolation worktree` (a checkout an agent harness creates, e.g. `isolation: "worktree"`; spec-kitty neither creates nor tracks it, and it is never a status surface); `PR-landing worktree` (a maintainer's checkout of a PR branch for a landing pass). | S3 for the "short-lived" clause |
| 10 | glossary `:701-703` (`workspace`) | B | "Git worktree directory created for implementing a work package" | "The checkout a WP is implemented in: its lane worktree for lane topologies, the write checkout for `single_branch`. Resolve it with `spec-kitty implement`; never construct the path." | none |
| 11 | glossary `:850-857` (`integrating worktree`) | B | "...For a per-work-package execution checkout in general, say lane worktree." | keep; link to the new `lane worktree` entry | none |
| 12 | `built-in/paradigms/execution-lanes.paradigm.yaml:4-10` | B | "Each work package runs in an isolated execution-lane worktree ... Execution lanes keep task status, branch state, prompt files ... aligned" | "Each execution lane is a lane branch; WPs in a lane run in sequence on it, in a lane worktree the CLI provides per command. Status is not kept in the lane: it lives on the resolved status surface. Small Missions (at most 2 WPs or one lane) use `single_branch` and need no lane." | S3, S6, S7 |
| 13 | `built-in/missions/built_in_step_contracts/implement.step-contract.yaml:19-21` | B | "Execution lanes are the default and only supported git worktree paradigm." | "Spec Kitty chooses the topology at `finalize-tasks` by Mission size; lane topologies use execution-lane worktrees provided by `spec-kitty implement`. Do not create or reuse a lane worktree by hand." | S7, S3 |
| 14 | `.../software-dev/implement/prompt.md:41-47` | B | "works inside the execution workspace (worktree) allocated by `spec-kitty agent action implement` ... (a lane worktree, or a harness-isolated worktree)" | Name the three kinds once: "Work in the checkout `spec-kitty agent action implement` prints: a lane worktree, or for `single_branch` the write checkout. A harness isolation worktree is yours to use for reading or scratch work, but WP deliverables are committed in the printed checkout." | none (vocabulary); S3 for "per command" |
| 15 | `.../software-dev/implement/guidelines.md:9-11` | B | "NEVER write deliverable files to the repository root checkout" | "Write deliverables only in the checkout `spec-kitty implement` printed. For lane topologies that is the lane worktree, never the repository root checkout; for `single_branch` it is the write checkout, which may be the repository root checkout." (resolves the contradiction with implement/prompt.md:42) | none |
| 16 | `.../software-dev/review/prompt.md:23-26` and `review/guidelines.md:21` | B | "Review from your own checkout (a lane worktree, or a harness-isolated worktree)"; "Verify that no deliverable files were written to the repository root checkout instead of the worktree." | Same three-kind vocabulary; guideline becomes "...were written outside the WP's workspace (for lane topologies, the repository root checkout is outside it)." | none |
| 17 | `built-in/tactics/pr-agent-worktree-isolation.tactic.yaml:12-24,69-73` | B | "must execute in an isolated worktree ... `isolation: "worktree"`" | Say "harness isolation worktree" and add: "It is not a spec-kitty lane worktree: never run `spec-kitty implement` or status writes from it, and never treat its files as status." | none |
| 18 | `built-in/missions/mission-steps/documentation/generate/prompt.md:20` | B | "repository root checkout (or your lane worktree, if `spec-kitty implement` allocated one ...)" | "...the checkout `spec-kitty implement` printed (a lane worktree, or the write checkout for `single_branch`)" | none |
| 19 | `internal/procedures/landing-contributor-prs.procedure.yaml:86-96` | I | "check the PR branch out into its own dedicated worktree ... If a worktree is stale or points at a missing gitdir, create a fresh standalone checkout" | Call it a "PR-landing worktree"; on failure: "run `git worktree prune` to drop the broken registration, then create a fresh PR-landing worktree" (no stray standalone clone) | none |
| 20 | `internal/glossary_packs/spk-internal.glossary-pack.yaml:98-104` (`cutover-guard`) | I | "Reads the primary checkout, which is a footgun in shared worktrees." | "Reads the repository root checkout's working tree, so a run from a lane worktree or PR-landing worktree checks the wrong tree." (name the sense of "primary") | none |

#### Current `consolidate` wording (not merge)

| # | Path : line | Tier | Current | Proposed |
|---|---|---|---|---|
| 21 | glossary `:262-263, 267-269, 273-275, 279-281, 285-287, 293-298` | B | "merge pending", "ready to merge", "The merge workflow owns the approved -> done transition", "merged/integrated", "whole-mission merge", "merge dependency gate" | "consolidation pending", "ready to consolidate", "`spec-kitty consolidate` owns the approved -> done transition", "consolidated into the target", "consolidation"; keep `merge dependency gate` as a code name only if `policy/merge_gates.py` keeps it, else rename with the code |
| 22 | glossary `:344-349` (`merge state`) | B | "The persistent JSON artifact (.kittify/merge-state.json) ..." | Replace with `consolidation state`: "`.kittify/runtime/merge/<mission_id>/state.json` (`ConsolidationState`), which lets `spec-kitty consolidate --resume` continue an interrupted consolidation." Deprecate `merge state`. |
| 23 | glossary `:478-482` (`preflight validation`) | B | "Pre-merge checks ... before a merge operation begins" | "Checks `spec-kitty consolidate` runs before it moves any branch (git state, target branch, review artefacts, origin freshness)." |
| 24 | `.../software-dev/accept/prompt.md:2, 76` | B | "Validate an approved mission before merge"; "what still blocks merge" | "...before consolidation"; "...still blocks consolidation" |
| 25 | `.../software-dev/review/guidelines.md:28` | B | "Merge later records `done`." | "Consolidation later records `done`." (the step contract `review.step-contract.yaml:71` already says this) |
| 26 | `.../software-dev/tasks/prompt.md:398` | B | "...and merge all lanes when done." | "...and consolidate the Mission when every WP is approved." |
| 27 | `.../software-dev/specify/prompt.md:37,498,507,595,681-682` | B | "assigned at merge time", "inside the merge-state lock" | "assigned at consolidation" (mission_number is assigned by `consolidation/mission_number/`) |
| 28 | `built-in/procedures/post-merge-arch-gate-adjudication.procedure.yaml:4-14` | B | "After merging one or more lane branches ... merged coordination or target branch" | "After consolidating lanes ..." (keep the id; rename the title only if open-packs accepts an id-stable rename) |

#### Cleanup as the final consolidation step (ruling 6) and short-lived checkouts (ruling 5)

| # | Path : line | Tier | Current | Proposed | Depends |
|---|---|---|---|---|---|
| 29 | `.../software-dev/accept/prompt.md:102-111` | B | "Follow the consolidate instructions printed by the acceptance command (and any cleanup steps it lists)." | "`spec-kitty consolidate` removes the Mission's lane worktrees, lane branches and coordination triple as its final step, under the destructive-operation proofs, unless the Mission declared `--retain-branches`/`--retain-worktrees`. Do not remove them by hand and do not wait for a pull request to merge. Anything left behind is cleaned by `spec-kitty doctor workspaces --prune`." | S5, S4 |
| 30 | `built-in/procedures/mission-wrap-up-sequence.procedure.yaml:67-74` | B | "Consolidate the approved lanes ... Resolve any stale-lane conflicts on shared files." | "...`spec-kitty consolidate --mission <slug>` lands locally and, as its last step, removes the Mission's lane and coordination checkouts and branches. If it reports a stale lane, follow the command it prints; never `git merge` inside a lane worktree by hand." Also: compaction (step at :75) must come after consolidation, which it already does; say the mission branch is not a removed branch. | S5, plus the CLI message change (see risks) |
| 31 | `.../mission-wrap-up-sequence.procedure.yaml:27-33` | B | "Verify all work packages are in the approved lane" | "...are in the `approved` state (`spec-kitty agent tasks status`)" | none |
| 32 | `internal/procedures/issue-to-mission-delivery.procedure.yaml:196-203` | I | "If you are asked to follow up after the PR has merged, confirm the commits are on ... `main` and remove the worktrees and branches." | "Consolidation already removed the Mission's lane and coordination checkouts. After the PR merges, remove only your PR-landing or harness isolation worktree and the PR branch; run `spec-kitty doctor workspaces --prune` for anything left." | S5 |
| 33 | `internal/procedures/landing-contributor-prs.procedure.yaml:349-353` | I | "Then remove the worktree, the local branch and the merged PR branch" | add "(or `spec-kitty doctor workspaces --prune --remote <canonical>`, which proves the landing first)" | S4 (#7275/#7240 introduce `--remote`) |
| 34 | `.../software-dev/specify/prompt.md:502` and `tasks/prompt.md:56` | B | "Each lane gets exactly one worktree, for example `.worktrees/<human-slug>-<mid8>-lane-a/`" | "Missions with at most 2 WPs, or one lane, run `single_branch` in the write checkout. Larger Missions get one lane branch per lane; `spec-kitty agent action implement` provides its checkout for the length of a command. Never build a `.worktrees/` path yourself." | S7, S3 |
| 35 | `.../software-dev/implement/guidelines.md:9` and `implement/prompt.md:41-42` | B | "After running `spec-kitty implement WP##`, change into the worktree directory shown" | add: "Commit before the command or turn ends. A lane checkout is released at the end of the command: releasing commits your work or refuses, so uncommitted edits block the release. Re-run `spec-kitty agent action implement WP## --mission <handle>` to get a checkout again; do not keep a shell parked in `.worktrees/`." | S3 (behaviour not built; ADR amendment pending) |
| 36 | `built-in/procedures/post-merge-arch-gate-adjudication.procedure.yaml:51-69` | B | "`git stash  # or use a worktree`... `git checkout "$MISSION_BASE"` ... `git worktree add /tmp/base-check "$MISSION_BASE"`" | Use one short-lived detached worktree and remove it: `tmp=$(mktemp -d) && git worktree add --detach "$tmp" "$MISSION_BASE" && (cd "$tmp" && <runner> <paths>); git worktree remove "$tmp"`. Drop `git stash` (contradicts `toolguides/GIT_WORKTREE_PR_WORKFLOW.md:8-22`) and drop `git checkout` of the base in the active checkout (fails when the base is checked out elsewhere). | none |
| 37 | `.../software-dev/tasks/prompt.md:160` | B | "Too small (<3 subtasks, <150 lines): Overhead of worktree creation not worth it" | "...overhead of a separate WP (review cycle, status transitions) is not worth it" (worktree cost stops being the argument under S3/S7) | S7 |
| 38 | `.../software-dev/tasks-finalize/prompt.md:68-74, 100-117` | B | "execute sequentially in one lane and share a single worktree (or run direct-to-branch)"; output list has no topology | "...execute sequentially in one execution lane (or, for `single_branch`, in the write checkout)". Output list adds: "`topology`: the topology finalize-tasks chose (`single_branch` when at most 2 WPs or one lane, `lanes` otherwise; an explicit `--topology` at create wins)". | S7 |
| 39 | `.../software-dev/review/guidelines.md:11` | B | "warn those agents to rebase and provide a concrete rebase command" | "tell them to re-run `spec-kitty agent action implement <WP> --mission <handle>`, which refreshes the lane from the Mission branch (auto-rebase); give a manual command only if the CLI reports a conflict" | verify the re-entry refresh path (`lanes/implement_support.py:619`) |

#### DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN recovery

No pack file mentions either code. Proposed home: a new built-in **tactic**
`lane-recovery` (technique, not a rule) referenced from `implement/prompt.md` "Working Directory"
and from `spk-run-blocked-recovery`. Content, taken from CLAUDE.md "Lane work tips":
- `DESTROYED_LANE`: the lane worktree or branch was deleted with unabsorbed work. Restore with the
  printed `git branch <b> refs/spec-kitty/lane-tip/<b>`; to abandon it, `git update-ref -d
  refs/spec-kitty/lane-tip/<b>` then `spec-kitty context cleanup` (operator decision; never by an
  agent alone).
- `LANE_WORK_TIP_UNKNOWN`: no tip was recorded. Look for stranded commits (`git reflog <b>`,
  `git fsck --lost-found`); if found, `git update-ref refs/spec-kitty/lane-tip/<b> <sha>` and
  re-run `implement`; if certain nothing was committed, `spec-kitty context cleanup`.
- Never delete a lane worktree or lane branch by hand: that is what produces these codes; use
  `spec-kitty consolidate` or `spec-kitty doctor workspaces --prune`.
Tier B (consumers hit these codes). Depends: none for the text; S3 may add a lease-based re-entry
that changes the abandon path, so re-check after S3. Needs DRG registration
(`spec-kitty charter pack regenerate-graph`) in open-packs.

#### Core command skills (core tier: `src/charter/offering/skills/`, edit in core, not open-packs)

| # | File : line | Current | Proposed |
|---|---|---|---|
| K1 | `spec-kitty-implement-review/SKILL.md:841-877` | "Handling Stale Lane Conflicts ... `cd .worktrees/<mission>-lane-<X>` ... `git merge kitty/mission-<mission-slug> --no-edit` ... `spec-kitty merge`" | Delete the manual recipe; "If `spec-kitty consolidate` reports a stale lane, run the command it prints." (after the CLI message changes) |
| K2 | `spec-kitty-implement-review/SKILL.md:1040-1048` | "Parallel review commit batching: commit all status changes from main in one batch"; "Stale git index after merge ... `git checkout HEAD -- src/ tests/`" | Delete both: status is written by the CLI to the resolved surface, never hand-committed; the `checkout HEAD --` advice can discard real work |
| K3 | `spec-kitty-implement-review/SKILL.md:1069-1076` | "Lane staleness on merge ... `cd .worktrees/<slug>-lane-X && git merge ...` ... #771" | Replace with auto-rebase reality; drop #771 pointer if closed |
| K4 | `spec-kitty-implement-review/SKILL.md:187, 743, 808, 832` | `spec-kitty merge --mission <slug>` | `spec-kitty consolidate --mission <slug>` |
| K5 | `spec-kitty-git-workflow/SKILL.md:28-40, 112-125, 162-171, 186-191, 233, 263` | ownership table rows "`git commit` (lane transitions)", "`spec-kitty merge`", "`--push`", "`git worktree remove` After successful merge"; section "Refreshing a Stale Lane Workspace"; "spec-kitty merge --push" | Rows: status commits go to the resolved status surface (never a lane branch); `consolidate` (no `--push`, CLAUDE.md forbids it); `git worktree remove` is consolidation's final step under `git/destructive_guard.py`. Keep "Refreshing" but say the CLI does it; add DESTROYED_LANE / LANE_WORK_TIP_UNKNOWN pointer |
| K6 | `spec-kitty-git-workflow/SKILL.md:155-160` | "spec-kitty checks that the worktree has commits ahead of the base branch (`git rev-list --count <base>..HEAD`)" | "...that the lane branch has commits ahead of its base (`git rev-list --count <base>..refs/heads/<lane>`), so the check works with no lane checkout" | after S2 |
| K7 | `spec-kitty-program-orchestrate/SKILL.md:185-188, 343` | `spec-kitty merge`; manual `git merge kitty/mission-<slug>` | consolidate; "run the command consolidate prints" |
| K8 | `spec-kitty-mission-review/SKILL.md:35, 73` | "After `spec-kitty merge`"; `cat kitty-specs/<slug>/status.events.jsonl` | consolidate; read the event log from the target branch (`git show <target>:kitty-specs/<slug>/status.events.jsonl`) or `spec-kitty agent tasks status --mission <slug> --json`, never from a checkout's working tree |
| K9 | `spk-gate-consolidate/SKILL.md:13-17`, `spk-run-blocked-recovery/SKILL.md:8-17` | consolidate flow without cleanup; recovery lists "sync issue", "team sync", "merge" | add "Consolidation removes lane and coordination checkouts as its final step; `doctor workspaces --prune` is the backstop"; recovery: drop "sync"/"team sync" (retired), add `lane-recovery` tactic pointer |

Do **not** edit `.claude/commands/`, `.agents/skills/` or other generated agent copies; they regenerate
from the sources above via `spec-kitty upgrade`.

### Part 2: code shapes the S9 ADRs must account for

- Write path today: `BookkeepingTransaction` (`src/specify_cli/coordination/transaction.py:447`),
  `append_events` `:984`, `write_artifact` `:1067`, `enroll_subprocess_byproducts` `:1110`,
  `commit` `:1226`, `_cut_event_log` `:1351`, `_rollback` `:1376`; coordination worktree root
  `_resolve_coord_worktree_root_for_transaction` `:209`. Non-event writers through the transaction:
  `decisions/service.py` (4), `coordination/status_transition.py` (4), `coordination/outbound.py`,
  `cli/commands/agent/tasks_move_task_gates.py`, `cli/commands/agent/workflow.py`,
  `cli/commands/implement_planning_commit.py`.
- Divergence guard that disappears: `coordination/status_surface_guard.py`
  (`COORD_STATUS_SURFACE_DIVERGED` / `_UNREADABLE`): with no working tree, committed is the only state.
- Event tail cursor: `status/tail_reader.py:60` `TailCursor(offset, content_invariant)`, a byte
  offset into one file; `ResumeRefused` reasons `negative|out_of_range|misaligned|content_mismatch`.
- Read side: `status/aggregate.py:291` `_resolve_read_dir`, `coordination/surface_resolver.py:1256`
  (one resolver, about eight wrappers; S1). Java read service:
  `spec-kitty-events/service/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/ReadDirResolver.java:139`
  (reads the coordination Mission directory from the filesystem, DD-105).
- Contract: `spec-kitty-events/contracts/mission-write/schemas/WriteSurface.yaml` (2 values, the
  second "in the coordination worktree"), `RequestContext.yaml` (`checkout` required),
  `DurabilityAck.yaml:44-56` (`statusCommit` provisional "until migration step 4"),
  `WriteRefusalCode.yaml:24,33-44` (`COORD_STATUS_SURFACE_DIVERGED`, `BOOKKEEPING_WORKTREE_MISSING`,
  `FALLBACK_COORD_WORKTREE_UNRESOLVED`, `COORDINATION_WORKTREE_UNMATERIALIZED`, unreadable). Version
  `1.0.0-SNAPSHOT`, unreleased.
- Gates that already read refs (unchanged by S9): `consolidation/approved_bound.py:465`
  `check_lane`, `status/lane_head.py:103`, claim build, closed-world/blob/line attribution,
  `wp_evidence`. Gates that read the coordination worktree (changed): the late projection window
  (#7198), `resync_checkouts_to_tip`, the four-role resume `reset --hard`, `ProjectionTeardownGate`
  (`coordination/teardown.py`, already CAS on the ref).

### Part 2: the ADR set D-6 requires (S9, ADRs only)

Conventions checked: core ADRs are `docs/adr/4.x/YYYY-MM-DD-N-title-with-dashes.md`, YAML front
matter (`title`, `description`, `status`, `doc_status`, `kind: ADR`, `date`), body per
`docs/architecture/adr-template.md` (Status / Date / Deciders / Technical Story, Context, Drivers,
Options, Decision Outcome with D-n, Consequences, Confirmation, Pros and Cons, More Information);
do not add the era index row (the `ci/regen-docs-index` bot does). `2026-11-06-1` is already taken
by the #7264 ADR (PR #7275), and S3/S7 ADRs may land the same day, so pick `N` at landing.
`spec-kitty-events` ADRs are `docs/adr/NNNN-title.md` with no date, `**Status:**`/`**Date:**`
lines, next free number **0007**. Placement rule (ADR 2026-10-29-1 D-1, D-7): Java service
internals and the `mission-write` / `mission-status` contracts are decided in spec-kitty-events;
the CLI's placement, topology, gates, `events tail` and launcher stay core decisions.

**C-1 (core, 4.x). "A coordination branch is written by commit, not through a coordination worktree"**
- D: The coordination branch stays the lifecycle home (ruling 2); no coordination worktree is
  created for new Missions after migration step 4; the write service commits each unit of work
  straight to `refs/heads/<coord>`.
- D: Coordination-partition kinds covered: status events, plus notes, trace, issue-matrix and the
  decision artefacts the transaction writes today. Either the service gains an artefact-write
  operation, or those kinds move partition (ties to #7266 artefact placement). One of the two must
  be ruled; nothing may keep needing a worktree.
- D: `status.json` is not committed on the coordination branch (derived; rebuilt on read), or the
  service recomputes it in the same commit. Pick one.
- D: Read contract for coordination topologies is "read the ref" (S1's rule: read from a ref where
  the write commits in the same unit of work). Readers never read a coordination working tree.
- D: Retired codes: `COORD_STATUS_SURFACE_DIVERGED`/`_UNREADABLE`, `COORDINATION_WORKTREE_UNMATERIALIZED`,
  `FALLBACK_COORD_WORKTREE_UNRESOLVED`, coordination half of `BOOKKEEPING_WORKTREE_MISSING`.
- D: Migration: an existing coordination worktree is drained (clean and committed, or refused),
  then removed under `git/destructive_guard.py` (ruling 7); the service refuses to write a
  coordination ref that is checked out in any worktree (a ref moved under a checkout looks dirty).
- Amends: ADR 2026-10-22-1 D-3/open question 2 (resolution moves into the service at step 4),
  D-6 (names this set); the coordination-worktree parts of ADR 2026-04-03-1 (coordinate with S3).
- Open: which partition the decision ledger uses (ADR 2026-10-01-3 says PRIMARY; check why
  `decisions/service.py` uses the transaction); does `lanes_with_coord` need its own rule; the
  owned-checkout (`--owned-checkout`) interplay.

**C-2 (core, 4.x). "Consolidation gates over a worktree-less coordination branch"**
- D: Gates that read lane refs and `lane_head` stamps (approval bound, claim, attribution,
  evidence) are unchanged; record that they never needed a checkout.
- D: The service stamps `policy_metadata.lane_head` from `refs/heads/<lane>` (command form,
  2026-10-27-1 D-3 at step 4); the stamp's meaning (lane head when the approval was recorded) is
  unchanged.
- D: The late projection window and the union step of ADR 2026-02-09-3 read the coordination log
  from the ref at a pinned tip, never from a working tree (closes the #7198 class by
  construction). Merge semantics (concat, dedupe, wall-clock reduce, #4990/#4941 rules) are
  unchanged; only their inputs change, so 2026-02-09-3 needs at most a factual amendment.
- D: Exclusion between service writes and consolidation: CAS on both sides (service
  `update-ref <coord> <new> <old>`; teardown CAS delete, `CoordMovedAfterLanding`), plus a
  write fence: the service refuses a coordination write while a consolidation record holds the
  Mission (new code, e.g. `CONSOLIDATION_IN_PROGRESS`), or consolidation writes its own
  bookkeeping through the service. Pick one.
- D: Resume/rollback no longer resync or `reset --hard` a coordination checkout (one of the four
  roles goes away); `pre_mutation_coord_sha` stays a ref anchor.
- Overlap: S10 (#7265 design pass, PR #7274/#7228/#7226) decides "what the late window must prove
  and on which tip"; C-2 must cite it, not re-decide it.
- Open: does `--dry-run` forecast read the same pinned tip; does the orchestrator-api path (no
  rollback door) need the fence too.

**C-3 (core, 4.x). "The committed ledger of a coordination Mission is the blob on its coordination branch"**
- D: Amends 2026-10-13-2 D-2: for coordination topologies the publication seam is the
  `status.events.jsonl` blob at `refs/heads/<coord>` (and, after consolidation, on the target);
  "committed" means reachable from that ref, never a working-tree file.
- D: Amends 2026-10-01-2 D-3/D-6: the read API's pull reads git objects for coordination Missions;
  still read-only, no lock, independent of drain.
- D: `events tail` cursor gains a source: `TailCursor(offset, content_invariant, source_ref,
  commit)`; a resume whose ref moved by append resumes by offset; a resume after the coordination
  branch was consolidated onto the target (union may reorder or dedupe bytes) refuses with a new
  `ResumeRefused` reason (e.g. `source_moved`) or remaps by event id. Pick one.
- D: Retention (2026-10-13-2 D-3) unchanged: the coordination branch's history is git's to keep
  until consolidation; branch deletion at teardown is the only removal, under ruling 7.
- Open: does the overview cursor of the read API become a commit id; does `events tail` poll the
  ref (cheap `rev-parse`) or watch the reflog.

**E-0007 (spec-kitty-events). "The write service commits a unit to a branch ref with compare-and-swap"**
- D: Mechanism: read tip `T` of `refs/heads/<coord>`; build the new tree from `T`'s tree with the
  appended blob (temporary index `GIT_INDEX_FILE` + `read-tree`/`update-index`/`write-tree`, or a
  path-rewrite of nested trees); `commit-tree -p T`; `update-ref -m <msg> <ref> <new> T`. No hooks
  run, no index or working tree is touched, a reflog entry is written.
- D: Byte contract: the appended bytes are exactly 2026-10-22-1 D-7 / 2026-10-27-1 D-5 rows; the
  "one O_APPEND write + fsync" rule is restated for the object store (objects and ref durable,
  e.g. `core.fsync`, before the 201); `DurabilityAck.statusCommit` is the new commit.
- D: CAS failure: the service is the only writer, so a moved ref means a foreign writer: refuse
  with a new 409 code (e.g. `COORDINATION_REF_MOVED`) and write nothing; no blind retry. (Or a
  bounded re-read-and-retry when the move is an append by the same service; decide.)
- D: Contract changes before `mission-write` 1.0.0: `WriteSurface` gains a value (e.g.
  `coordination_ref_commit`); `RequestContext.checkout` becomes optional for it; the new refusal
  code(s); the coordination-worktree codes become never-emitted for this surface.
- D: Protected-branch policy (`PROTECTED_BRANCH_REFUSED`) and commit identity (author/committer
  for status commits) are evaluated inside the service.
- D: Git implementation in a native image: JGit vs a `git` subprocess (the existing `GitPort`);
  minimum git version (the core already needs 2.38 for `merge-tree --write-tree`).
- Open: Windows ref-lock semantics (#6193 lock-interop spike); whether a batch of units is one
  commit or one commit per unit; commit message format; signing (DIRECTIVE_029 / signing toolguide).

**E-0008 (spec-kitty-events). "The read service reads the coordination ledger from git objects"**
- D: A `MissionEventSource` adapter over git objects beside the filesystem one; `ReadDirResolver`'s
  coordination case (DD-105) reads the ref, not a directory.
- D: Conformance: the Python oracle and corpus compare (2026-10-29-1 D-6/D-7) gain a fixture with a
  coordination ref and no worktree.
- Open: whether this is an amendment of ADR-0002 rather than a new record.

**Amendment to core ADR 2026-10-22-1** (short, after C-1..E-0008 are Accepted): D-6 lists the
records that discharge "each of those needs its own ADR" for the git-object adapter; migration
order gains step 4a "coordination writes by commit; coordination worktree retired" after step 4.

## Overlap with in-flight PRs

- **#6884 `issue-6466-lane-status-shadow`**: the code half of ruling 8 ("lane worktree root is never
  a status surface"). Doctrine rows 1-7 describe what #6884 enforces; land doctrine after it, cite
  it. Its diff touches no pack or skill text.
- **S4: #7275 `issue-7211-safe-landed-prune`** carries `docs/adr/4.x/2026-11-06-1-a-destructive-git-operation-discharges-named-proof-obligations.md`
  (Proposed) and rewrites `docs/development/how-to/pr-landing.md` (adds `--remote`). Rows 29, 32,
  33 and the `lane-recovery` tactic must point at the guard and that ADR, not restate proofs.
  Date slot `2026-11-06-1` is taken.
- **S10: #7274 `issue-7198-late-window-one-pass`** amends ADR 2026-09-19-1 and the
  interrupted-merge recovery how-to. C-2's late-window decision must build on #7265's pass, and
  C-2 makes the "coordination worktree's working-tree log" input disappear rather than patch it.
- **#7255 finalize-tasks pin / #7248 flat fixture single_branch**: S7's topology field in the
  finalize output (row 38) should match whatever #7255 freezes in finalize-tasks JSON.
- No open branch edits `src/charter/offering/skills/` text for the stale-lane recipe or
  `lanes/stale_check.py` (checked by name only; not exhaustive).

## Tidy-first prep

1. Change the CLI's stale-lane remediation (`src/specify_cli/lanes/stale_check.py:117-153`) to
   print a CLI command instead of `cd .worktrees/*-<lane> && git merge <mission>` (that path will
   not exist under S3). Without this, K1/K3/K7/row 30 would contradict the CLI. Behaviour-preserving
   if it keeps the planning-lane text and only replaces the `cd` form with the re-entry command.
2. Vocabulary-only pack edits that need no new behaviour (rows 2-4, 8-11, 14-18, 20-28, 31, 36):
   one open-packs PR, then `spec-kitty charter pack vendor --pack built-in --ref <sha>` and
   `make sync-packs` in core. Rows that teach S3/S5/S6/S7 behaviour wait for those slices.
3. Core skill `spec-kitty merge` -> `consolidate` renames (K4, K5 table, K7, K8): pure text.
4. For S9: freeze the `mission-write` `WriteSurface` and refusal enums as "open until S9 rules" in
   the contract CHANGELOG, so 1.0.0 is not cut without the coordination-ref surface.

## Proposed WP shape

S11 (doctrine), a documentation Mission across two repos:
- WP-a (open-packs, B+I): vocabulary and consolidate wording, rows 2-4, 8-11, 14-28, 31, 36.
  Red-first: a terminology check in open-packs (or core `test_no_legacy_terminology.py`-style
  grep) that fails on "merge workflow", "merge-state.json", "Status commits target lane branches",
  "git merge kitty/mission" in pack text. Size S-M.
- WP-b (open-packs, B): status-surface rule (rows 1, 5-7) + `lane-recovery` tactic + DRG regen.
  Red-first: a pack lint that every task-prompt template contains the status-surface sentence.
  Size S.
- WP-c (core): skills K1-K9 + `stale_check.py` message (tidy step 1). Red-first: a test that the
  stale remediation string contains no `git merge` and no `.worktrees/` (`tests/lanes/`), and a
  grep test over `src/charter/offering/skills/` for `spec-kitty merge`. Size S.
- WP-d (open-packs, after S3/S5/S7): rows 12, 13, 29, 30, 32-35, 37-38. Size S.
- WP-e: vendor pin bump + `make sync-packs` + `spec-kitty charter pack regenerate-graph` in core.

S9 (ADRs only): one Mission, five records + one amendment. WP-1 C-1, WP-2 C-2 (after S10's pass),
WP-3 C-3, WP-4 E-0007 (+ contract CHANGELOG note), WP-5 E-0008, WP-6 the 2026-10-22-1 amendment.
Acceptance per ADR: a reviewer can map each D-6 bullet to one Accepted record; each record names
its Confirmation tests. Size M (writing), gated on operator rulings for the "pick one" bullets.

## Risks / open questions

1. **Doctrine ahead of code is a lie.** Rows that describe short-lived checkouts (S3), cleanup in
   consolidation (S5), no status on lanes (S6) and size-based topology (S7) must not ship before
   those slices; the pack pin bump is the release gate. S11 "depends on S1, S3" in the research
   note understates it: S5, S6, S7 too.
2. **The CLI teaches the manual refresh.** `lanes/stale_check.py:152` prints `cd .worktrees/*-<lane>
   && git merge <mission>`. Removing it from doctrine alone leaves agents following the CLI.
3. **Ruling 6 has no prompt home.** `consolidate` is a CLI wrapper with no mission-step prompt.
   Adding one grows scope (a new prompt-backed command touches `command_installer.py`, 12 agent
   dirs and a migration). Default proposal: teach it in accept + wrap-up + skills only.
4. **Wrap-up compaction vs cleanup.** `mission-wrap-up-sequence` compacts and rebases the mission
   branch after consolidation. If consolidation's final cleanup ever deleted the mission branch
   (it should not: it is the PR head), the procedure breaks. S5 must state that the mission branch
   survives consolidation cleanup for PR-bound Missions.
5. **Glossary rename of `lane`.** `to_lane`/`from_lane` are event field names and the 9-lane state
   machine is documented as "lanes" in core docs and CLAUDE.md. Renaming the prose term to "WP
   state" without touching field names is safe; touching field names is a contract change.
6. **S9 contract timing.** `mission-write` is `1.0.0-SNAPSHOT`; ADR 2026-10-27-1 makes a closed
   response change after 1.0.0 a major. If 1.0.0 is cut first, E-0007 forces mission-write 2.0.0.
7. **S9 scope is wider than status.** The coordination transaction writes notes, trace,
   issue-matrix and decision artefacts and runs subprocesses that write into the coordination
   worktree. Ruling 4 says "coordination status"; without a rule for the rest, the coordination
   worktree cannot be retired. Needs an operator ruling or #7266.
8. **Concurrency with consolidation.** Service writes (Java, one process) and consolidation (Python)
   both move/delete `refs/heads/<coord>`. CAS alone prevents silent loss, but a status write that
   lands after projection and before teardown triggers `CoordMovedAfterLanding` (exit 75) on every
   race. A fence is needed (C-2).
9. **`events tail` cursor across consolidation.** The union at projection can reorder or dedupe
   lines, so a byte-offset cursor taken on the coordination blob is invalid on the target blob.
   A cursor contract change is a consumer-visible change (event-router).
10. **D-6 reading.** One could argue the object store is still "the local file ledger", so D-6 does
    not apply. The safer reading (and the research note's) is that it does; C-1 should say so.

## Friction

- The research doctrine scan's paths (open-packs `23686fb`) do not match the pinned fetched tree
  (`a79c3631`): the toolguide file is `GIT_WORKTREE_PR_WORKFLOW.md`, prompts live under
  `mission-steps/<type>/<step>/prompt.md`. Every line number had to be re-derived.
- `packs/built-in/skills/` is empty; the command skills live in core `src/charter/offering/skills/`,
  so "doctrine upstream" is really two repositories and two release paths (pin bump vs core PR).
- ADR 2026-10-01-2 has no `### D-6` heading: decisions are list items (`- **D-6 (Proposed)...**`),
  so grepping for headings misses them; 2026-10-22-1 and 2026-10-13-2 use `### D-n`.
- `spec-kitty-events` ADR naming (`NNNN-`, no date) differs from core (`YYYY-MM-DD-N-`); a
  cross-repo ADR set needs both conventions and cross-links.
- `spec-kitty profiles show doctrine-daphne` worked; codegraph was not needed for this text-heavy area.
