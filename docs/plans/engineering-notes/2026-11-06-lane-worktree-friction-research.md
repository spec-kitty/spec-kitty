---
title: Lane and worktree friction research
description: How much recent friction the lane and worktree execution model causes, why, and which direction to take.
doc_status: point_in_time
updated: '2026-11-06'
audience:
- profile: internal/maintainer
  guidance_text: For the operator and maintainers deciding the direction of the lane and worktree execution model.
related:
- architecture/execution-lanes
- architecture/git-worktrees
- context/topology
---
# Lane and worktree friction research

**Reader:** the operator and the core maintainers. You already know the topologies, the
consolidation gates and the status model; this note does not explain them.

**Bottom line.** Counted as one family, the lane, worktree and coordination machinery is the
largest source of friction in the last three months. It is also the dominant source of
consolidation and git defects. It is not "most of the friction": it accounts for about a quarter
to a third of it, and that is an upper estimate. The persistent per-lane checkout on its own
accounts for less than a tenth. The bigger share comes from the
coordination topology and the consolidation transaction around it. Recommended direction, in order:

1. **Tighten the current model now:**
   - one status read contract;
   - an owner for cleanup after a pull request lands;
   - pruning by proof.
2. **Stop lane branches carrying status.**
3. **Write coordination status through the Java write service without a coordination worktree.**
4. **Make lane checkouts short-lived.**

The operator ruled on the decisions on 2026-11-06 (section 5.4). Two rulings go further than
this note recommends. The default topology becomes size-based, which reverses #5100. Short-lived
lane checkouts start now, in parallel with the tighten slice. Do not drop lanes.

Research mission: `kitty-specs/lane-worktree-friction-research-01M6QS30/`. Every number below
comes from an evidence file there, and each file records the commands that reproduce it.

## 1. Sources and method

Window: 2026-08-06 to 2026-11-06.

| Source | Population | Evidence file |
|---|---|---|
| Tooling-friction tracers (`kitty-specs/*/traces/`) | 1,169 entries from 239 files | `research/tracer-entries.part{1,2,3}.csv`, `research/tracer-summary.md` |
| GitHub issues with a reliability, bug, priority, git, consolidation or status label | 1,365 of 2,550 opened in the window | `research/issue-classification.part{1,2}.csv`, `research/issue-summary.md` |
| Named example issues and their linked PRs | 16 issues plus 7 related | `research/named-examples.md` |
| Merged PRs and git churn on `main` | see section 2.4 | `research/pr-classification.csv`, `research/pr-churn-summary.md` |
| Code, architecture docs and ADRs | lanes, coordination, workspace, consolidation, status | `research/mechanisms-and-options.md` |
| Doctrine in `spec-kitty-open-packs` (`23686fb`) | built-in and internal packs, command skills | `research/doctrine-scan.md` |

Each tracer entry and issue got one primary cause code, a model attribution and a severity:

| Code | Cause |
|---|---|
| CT | coordination topology and teardown windows |
| WL | worktree lifecycle and cleanup |
| WC | dirty, occupied or wrong-branch write checkouts |
| CG | consolidation gate verdicts on lane content |
| SD | status-surface divergence (a lane checkout's status copy versus the resolved surface) |
| HC | harness or agent confusion about which checkout to use |
| UF | upgrade and migration fan-out across worktrees |
| HT | hooks and lane tips |
| DP | disk and performance |
| NL | not lane or worktree related |

Model attribution says what the friction depends on:

- `worktree`: a persistent per-lane checkout;
- `lane-branch`: a branch per lane;
- `coord`: the coordination topology;
- `single_branch`;
- `none`.

Severity is one of data loss, wrong verdict, forced override or wasted time.

**How accurate the classification is:**

- **Tracers.** Classified by ordered rules. The analyst reported 85-90% agreement on lane versus
  not lane, but did not record that sample. An independent re-check found 14 of 16 rows correct,
  and both errors counted an entry as lane-related when it was not.
- **Issues.** Classified by a keyword and label heuristic. On a recorded fresh holdout of 45
  issues it agreed on lane versus not lane for 42 of 45 and on cause code for 40 of 45. The
  independent re-check found 16 of 16 correct on lane versus not lane, but only about 75%
  correct on cause code, mostly because status-surface reads were coded CT instead of SD.
- **Severity.** The weakest column, at 23 of 45 on the holdout. Treat severity counts as
  indicative only.
- **Validation artifacts.** See `research/validation/README.md`.

## 2. Cause taxonomy and numbers

### 2.1 Share of friction

| Measure | Tracers | Issues |
|---|---|---|
| Lane, worktree or coordination related (any code but NL) | 376 / 1,169 = **32%** | 328 / 1,365 = **24%** |
| Within `catfooding` issues | n/a | 123 / 330 = 37% |
| Depends on a persistent per-lane checkout (`worktree` model) | 111 = **9.5%** | 94 = **6.9%** |
| Depends on the coordination topology (`coord` model) | 166 = 14% | 137 = 10% |
| Share of data-loss records | 12 / 22 = 55% | 41 / 129 = 32% |
| Share of data-loss or wrong-verdict records | 24 / 48 = 50% | 164 / 462 = 35.5% |
| Share of `domain:consolidation` / `domain:git` issues | n/a | 72% / 63% |

By cause code (tracers / issues):

| Code | Tracers | Issues | Typical shape |
|---|---|---|---|
| CT | 177 | 119 | coordination chosen by default and removed by hand; teardown races; projection before teardown |
| WL | 96 | 48 | lane worktree missing `.venv` or `packs/`; stale or stranded worktrees; unsafe removal |
| WC | 56 | 52 | shared write checkout dirty or occupied; hard resets of the root checkout |
| CG | 8 | 48 | approval bound, lane moved after approval, mixed lanes, evidence windows |
| HC | 36 | 9 | wrong checkout imported through a shared editable venv; commits racing across checkouts |
| SD | 1 | 23 | lane checkout's fork-time status copy read as truth |
| UF | 0 | 12 | upgrade commits into every checkout |
| DP | 0 | 13 | disk use of many checkouts |
| HT | 2 | 4 | lane-tip recorder hooks |
| NL | 793 | 1,037 | tests and CI, planning and tasks tooling, charter and doctrine, review process, upgrade, status model |

**Trend.** The issue share rises from 15.7% in August to 25.9% in October; within catfooding it
goes from 31% to 46%. The first six days of November show 37.7% (61 issues). The tracer share
falls over the same months, from 38% to 26%. Coordination teardown windows lead the issues from
August to October. Consolidation gate verdicts lead in early November.

**Most severe issues** (most are P0 or P1; #7198 is P2 and #6791 has no priority label):

- **#4753:** merge cleanup force-removes lane worktrees with no dirty check.
- **#4752:** an ungated hard reset of the root checkout.
- **#4981, its regression #5570, and #6791:** coordination teardown destroys later commits,
  some at exit 0.
- **#5666:** a rollback resets the target past a teammate's commit.
- **#7198:** the late window reads the coordination worktree's working tree, not the branch.
- **#7173:** 48 landed worktrees, about 36 GB, were never cleaned up, and an upgrade would have
  committed across 53 extra checkouts.

### 2.2 Verdict on the operator's observation

The observation is **qualified, not confirmed**. Three findings support it:

- **Largest family.** Counted as one family of nine cause codes, lane, worktree and coordination
  friction is the largest in both sources.
- **Dominant in git and consolidation.** It accounts for 72% of `domain:consolidation` issues and
  63% of `domain:git` issues. Within catfooding its share of issues is rising.
- **Costly cases, with a caveat.** It accounts for half of tracer data-loss and wrong-verdict
  entries and 35.5% of such issues. Both counts rest on the weak severity column. The more
  reliable priority labels do not show the skew: the lane share of P0 or P1 issues is 22.4%,
  slightly below its 24.0% share of all labelled issues. Treat "over-represented in the costly
  cases" as unproven for issues.

Four findings go against "most":

- **Minority share.** It is 24-32% of all friction, not a majority, and both figures are upper
  estimates.
- **Aggregation effect.** "Largest" depends on that grouping. Taken one cause code at a time, the
  biggest lane code (CT: 177 tracer entries, 119 issues) is smaller than tests and CI (238 tracer
  entries, 290 issues).
- **Persistent checkouts are rare.** Persistent lane checkouts, which "the worktree system"
  suggests, are under 10%.
- **Label selection.** Across all 2,550 issues, not just the labelled 1,365, the lane share is at
  most about 13%.

Most of what operators feel as worktree pain is the coordination topology and the consolidation
transaction. The coordination worktree, the coordination branch's projection before teardown and
the resume and rollback windows all touch checkouts, so they are easy to read as worktree
problems.

Three biases push the measured share in opposite directions:

- **Tracer coverage.** 25 of 70 Missions in an earlier recon never wrote past their seed entry
  (`docs/reports/tracer-friction-recon/2026-09-26/README.md`). This hides friction of every kind.
- **Issue authorship.** Issues come largely from QA and squad rounds by two authors, and
  regression chains such as #4981, #5570, #6871 and #7121 count one defect class several times.
  This inflates the lane share.
- **Subject matter.** Missions whose own subject was lanes or coordination contribute a large
  block of the tracer entries. Without them the tracer share is about 28-30%. Two counts of those
  Missions differ (42 and 29), and neither is recorded as an artifact.
- **Classifier errors.** The independent tracer re-check found only false positives, so 32% is
  an upper estimate.

### 2.3 Where the operator's ruling bites

The status-surface divergence class (SD) looks small in count: 1 tracer entry and 23 issues.
It is undercounted, because the issue heuristic coded several status-surface reads as CT
(#4970, #4975 and #6299 in the re-check sample).
Its records are severe, though: wrong verdicts, forced `--force` moves (#6466) and data loss at
exit 0 (#7198). The ruling that a lane checkout's own status files never count is right, but
today it is a convention, not a structure. Section 3.1 explains why.

### 2.4 Engineering effort spent

Effort follows the same pattern: a large, concentrated share that is still a minority. The
sources are `research/pr-churn-summary.md` and `research/pr-classification.csv`.

**Merged PRs.**

| Population | Lane, worktree or coordination share |
|---|---|
| All 1,305 merged PRs | 166 PRs (12.7%), 11.7% of churn (14.3% with each PR capped at the 95th percentile). 27 of these carry `NL:*` codes (lane allocation, refactors); without them the count is 139 |
| The 748 PRs that touch `src/` | 18.4% of PRs, 19.9% of churn |

Lane PRs are about three times larger than the rest (median 1,869 lines against 621).

By cause code:

| Cause | PRs | Churn (lines) |
|---|---|---|
| CG | 40 | 117k |
| SD | 33 | 133k |
| CT | 18 | 61k |
| WC | 16 | 117k |

By model:

| Model | PRs |
|---|---|
| lane-branch | 73 |
| coord | 46 |
| worktree | 23 |
| single_branch | 21 |

**Commits on `main`.** 546 of 3,514 `src/` commits (15.5%) touch the lane-model areas: `lanes/`,
`coordination/`, `workspace/`, `consolidation/`, the lane-tip recorder and `mission_runtime/`.
Their fix share is 67.8%, against a 65.3% baseline for all of `src/`. Only `consolidation/` is
clearly above the baseline, at 70.5%. `consolidation/executor.py` has the highest fix density
of any hot file: 54 of its 69 commits are fixes.

**Release notes.** 228 of 525 Fixed entries in `CHANGELOG.md` for 4.0.0rc1 to rc8 (43%)
mention lane, worktree or coordination terms, peaking at rc5 with 96 of 175. This keyword count
overcounts, but it shows where users met the fixes.

## 3. Mechanisms

The mechanisms below come from the named examples (`research/named-examples.md`) and the code
reading (`research/mechanisms-and-options.md`, which carries file and line citations).

### 3.1 Copies of shared state in N checkouts, read from a working tree

A `lanes_with_coord` Mission with N lanes keeps its state in several places:

- the repository root checkout;
- the coordination worktree;
- N lane worktrees, each with a committed fork-time copy of `status.events.jsonl` (hidden by
  sparse checkout only in coordination topologies);
- temporary merge, bake and review worktrees.

Readers split into two kinds:

- **Working-tree readers:** `status/aggregate.py:291` (`MissionStatus._resolve_read_dir`),
  `coordination/surface_resolver.py:1209-1300`, and `runtime/next/committed_authority.py`,
  which reads the repository root's working tree on purpose.
- **Git-ref readers:** `done_bookkeeping.py` and the status-surface guard.

There is one resolver body (`resolve_status_surface_with_anchor`,
`coordination/surface_resolver.py:1256`). At least eight wrappers sit around it, and they return
different directories when a coordination branch is declared but its worktree is empty or not
yet created. In numbers:

- `resolve_status_surface*` is named in 26 files: 62 call sites by the analyst's count, 93
  non-definition lines including imports by a plain grep;
- 12 call sites build `coord_feature_dir(` paths by hand.

This is how #6466 happened: a lane checkout's single-event fork-time log was read as truth, and
the seam "documented its `repo_root` as 'the primary checkout' but never enforced it" (#6884).
It is also how #7198 happened: "the union stage merges the coordination worktree's working-tree
event log, not branch commits". Lane auto-rebase even carries a dedicated merger for
`status.events.jsonl` conflicts (`lanes/auto_rebase.py:357`). Under the operator's ruling those
lane copies are pure carrying cost.

### 3.2 The coordination branch is a second home that must be projected before teardown

Coordination topologies write lifecycle state to the coordination branch. Consolidation must then
project it onto the target before it tears the triple down, which opens a late window:

- #4981, its regression #5570, and #6791 with its first-run twin #6871: data loss or a wrong
  verdict at exit 0;
- #7198 and #7199: open.

#7265 asks for one design pass on "what the late window must prove and on which tip, covering
resume" before more patches land. The tracers show the cheaper end of the same cost: 62 entries
describe `specify` choosing the coordination topology on a protected branch, followed by the
scaffold being removed by hand.

### 3.3 Checkouts outlive the session and the merge, and removal needs ever more proofs

A Mission that lands through a pull request merge leaves its lane and coordination worktrees, its
branches, the `.kittify/workspaces` records and the lane-tip refs with no owner:

- `accept --mode pr` does not tear down.
- The new landed-worktree prune reports Mission branches as `mission_owned` and leaves them alone
  (`workspace/landed_worktrees.py:20-21` and `:375`).

#7173 states it directly: "No step owns removal" and "The merge outlives the session". Each safe
removal then needed another proof:

- #7211: reflogs are lost on removal;
- #7212: check-then-act branch deletes;
- #7214: the landing proof is bound to `origin/<primary>`;
- #7196: "a Mission lane mid-rebase was judged `landed` and pruned (reproduced)".

#7264 collects these into one list of proof obligations for any destructive git operation.
Hand deletion then trips `DESTROYED_LANE` or `LANE_WORK_TIP_UNKNOWN` on a later `implement`.

### 3.4 Operations fan out into every checkout

`spec-kitty upgrade` wrote and committed `.kittify/metadata.yaml` separately in the root checkout
and in every lane worktree (#5457), and #7173 found that an upgrade would have committed across 53 extra checkouts, including open
pull request branches. The
current upgrade skips Mission worktrees (`upgrade/worktree_selection.py:164`). That stops the
fan-out but leaves long-lived lanes on stale `.kittify/` content.

Tracer friction has the same shape:

- 47 WL entries are lane worktrees with no `.venv` or `packs/` tree (`BuiltInPackMissing` after
  about 95 seconds).
- A shared editable venv makes a lane worktree import the root checkout's `src/`, for example
  `kitty-specs/pack-shipped-builtin-override-sanction-01M45WB7/traces/tooling-friction.md:10`.

### 3.5 Anchors and records outlive the attempt that wrote them

The consolidation record outlived its attempt and forced `--release-branch` (#6770). A resume's
captured coordination tip went stale (#7199). Recovery machinery exists only because branches and
checkouts can disappear or be rewritten while a checkout lives:

- lane-tip refs and their recorder hooks (`lanes/lane_tip.py`, `policy/lane_tip_recorder.py`);
- the destroyed-lane decision table (`lanes/worktree_allocator.py:417-520`);
- the `CRASH_RECOVERY` route;
- workspace tombstones;
- `git reset --hard` on resume across four checkout roles;
- `resync_checkouts_to_tip`;
- `COORD_STATUS_SURFACE_DIVERGED`.

### 3.6 Each topology has its own guard copy, and `single_branch` has its own locks

#6715 found a guard that "returns early for any topology other than `single_branch`".
`single_branch` turns the one write checkout into a lock across Missions:

- #5550: "the occupant is a WP that no supported command can move".
- #5676: still open.

### 3.7 Doctrine does not tell agents where status lives

The packs tell implementers to do "ALL file operations" inside the lane worktree (implement
guidelines). The internal glossary routes status, notes and the issue matrix to the coordination
branch. No pack doctrine says which checkout to read status from. The doctrine also uses three
different worktree concepts:

- spec-kitty lane worktrees;
- harness `isolation: "worktree"`;
- manual PR-landing worktrees.

"Lane" has two meanings as well: a WP lifecycle state and an execution workspace. Agents get
contradictory checkout rules too: never write to the root checkout, yet `single_branch` WPs run
there. The command skills still teach manual stale-lane refreshes (`git merge
kitty/mission-<slug>` inside a lane worktree). See `research/doctrine-scan.md`.

### 3.8 The structural fact: attribution and approval gates read refs; a few readers still need checkouts

The consolidation attribution and approval gates read lane **branches** and refs, not lane
checkouts:

- the approval bound `check_lane` (`consolidation/approved_bound.py:465`);
- the `lane_head` probe (`status/lane_head.py:103`, under `refs/heads/`);
- the lane re-check at the gate;
- the claim build;
- closed-world, blob and line attribution;
- the work package evidence check (`wp_evidence`).

Lane consolidation already runs in temporary detached worktrees.

Five readers still depend on a checkout:

- **The for_review gate.** It requires the lane checkout to exist (`lanes/for_review_gate.py:280`)
  and counts commits with `git rev-list <base>..HEAD` run inside it (`lanes/_git.py`). Without a
  live checkout, an `in_progress -> for_review` move fails, which invites `--force`.
- **The late projection window.** It reads the coordination worktree's working-tree log
  (#7198).
- **The dirty-checkout preflight.** It reads lane checkouts.
- **Resume and rollback resync.** They reset and resync checkouts.
- **Auto-rebase and folding dependency lanes in at allocation.** Both run in the lane checkout.

Auto-rebase and the dependency fold-in could run in a temporary worktree. The other three need
reworking first.

So **lanes can stay branches while their checkouts become short-lived**, provided the for_review
gate moves onto `refs/heads/<lane>` first.

**Size of the surface.**

| Package | Source lines | Commits in window | Fix share |
|---|---|---|---|
| `lanes/`, `coordination/`, `workspace/`, `consolidation/` (with `policy/lane_tip_recorder.py`) | 57,263 | see section 2.4 | see section 2.4 |

- Section 2.4 gives the commit counts from the deeper history fetch.
- About 45 named codes tie to lanes, worktrees, the coordination worktree or the status surface.
- The tests for these packages run to about 122,000 lines.

## 4. Options

Topology use today (`meta.json` of the 440 Missions created since 2026-08-06):

| Topology | Missions |
|---|---|
| `single_branch` | 176 |
| `lanes` | 74 |
| `coord` | 53 |
| `lanes_with_coord` | 5 |
| none recorded | 132 |

Reproduce this table with the command in `kitty-specs/lane-worktree-friction-research-01M6QS30/research.md`.

### 4.1 How the Java write service changes the picture

ADR `2026-10-22-1` makes one resident write service per repository (D-2). Every lane worktree,
the coordination worktree and the root checkout talk to it, so writer races go. Divergence on the
read side does not:

- The service resolves "which partition, worktree and branch" (D-3).
- During the strangler the CLI still sends the resolved write location.
- Only the file adapter ships (D-6). A non-file adapter needs its own ADR, because the gates rely
  on git ancestry and on `lane_head` stamps.

So the service is the natural owner of a single status surface. On its own it does not stop a
command from reading a checkout's stale copy.

### 4.2 Options compared

| Option | Removes | Keeps or breaks | Effort | Java service |
|---|---|---|---|---|
| **(a) Tighten the current model** | the SD class (by gate); the stranded-worktree part of WL; part of CT (after the #7265 design pass) | nothing structural; new refusals in the window before the coordination worktree exists; keeps the 57,000-line surface | small per slice | complementary: the read contract becomes the service's request context (open question 2) |
| **(g) Lane branches stop carrying `status.events.jsonl`** | the lane status copies that #6466 read as truth; the lane auto-rebase merger for that file | nothing a gate needs, since lane copies never count under the ruling | small | independent of the service |
| **(b) Lanes as branches, short-lived checkouts** | most of WL and HC; the after-merge stranding for lanes; most lane-checkout recovery code | keeps the attribution and approval gates, `lane_head` stamps, lane-tip refs and parallelism; breaks long-lived IDE and agent sessions (harnesses keep a cwd across turns); amends ADR `2026-04-03-1` decision 3 ("one long-lived branch and one worktree" per lane) | medium | status writes need no lane path |
| **(c) Default `single_branch`, lanes opt-in** | the coordination default on the primary branch (62 tracer entries); lane and coordination worktrees on the common path | reverses the binding operator decision on #5100; on a protected target, the root checkout leaves the primary branch on every create; serializes concurrent Missions on one write checkout (#5550, #5676); widens the population without an approval bound | medium | simplest case |
| **(d) Drop lane worktrees and code lanes** | most of `lanes/`; the mixed-lane machinery | parallel multi-agent execution, the reason lanes exist (ADR `2026-04-03-1`); per-lane attribution gates lose their subject; test churn (about 57,000 lines in `tests/consolidation`) | large | no gain over (b) plus (e) |
| **(e) Status written to the coordination branch by git plumbing; no coordination worktree** | the coordination worktree's codes (`COORD_STATUS_SURFACE_*`, `COORDINATION_WORKTREE_*`, most `COORD_SEED_*`); the "declared but not created" wrapper rules; the #7198 class | keeps the coordination branch as the lifecycle home (#7266 favours keeping it); applies only to coordination topologies; breaks `events tail` | medium to large | must go through the service (see below) |

**Option (a): tighten the current model.**
- One status read contract, defined per topology.
- An owner for cleanup after a PR landing.
- Prune by proof (#7264).
- The for_review gate moved onto the lane ref.

**Option (g): lane branches stop carrying `status.events.jsonl`.** Apply the sparse exclusion
that coordination topologies already use (`coordination/workspace.py:416`) to `lanes` too, or
filter the tree when a lane is cut. The lane auto-rebase merger stays while existing lane
branches still carry the file.

**Option (b): lanes as branches, short-lived checkouts.** A lease is held per command or per
session, and releasing it commits or refuses.
- **Effort.** Reshape `worktree_allocator.py` (about 2,180 lines) into a lease. Move auto-rebase
  and dependency merges to temporary worktrees. Move the for_review gate onto refs. Update the
  prompts and skills in `spec-kitty-open-packs`.
- **Hidden costs.** The lane-tip hook exits on a detached HEAD (`policy/lane_tip_recorder.py:67`),
  so temporary-worktree merges need explicit record points or they feed
  `LANE_WORK_TIP_UNKNOWN`. Every re-entry takes the crash-recovery route. Review worktree
  creation and review's lane fast-forward assume a live checkout (`agent/workflow.py:2298`).
- **Main new risk.** Uncommitted work at release.

**Option (c): default `single_branch`, lanes opt-in.**
- **Today's code.** The non-pr-bound default is `coord` whenever the current branch is the
  primary branch, protected or not. Protection is read only on the `--pr-bound` arm
  (`cli/commands/agent/mission_create.py:441-449`).
- **The decision it reverses.** The binding operator decision on #5100 makes `single_branch`
  explicit-only (`mission_create.py:386-392`).
- **The approval bound.** Closing the `single_branch` approval-bound residual is not small. On
  one shared write branch, later work packages' commits sit past an earlier approval stamp, so
  the bound needs per-WP windows (the #5046 machinery) or an amendment to ADR `2026-10-04-5`.
- **Effort.** The default logic, the `specify` help text that mirrors it, docs and tests.

**Option (e): status written to the coordination branch by git plumbing.** There is no
coordination worktree; reads use `git show <ref>:<path>`.
- **Through the service only.** It must go through the service, because ADR `2026-10-22-1` D-5
  forbids a Python writer.
- **A step of its own.** Make it a step after migration step 4, framed as a change to the git
  port and write location (open question 2), not a storage adapter. Step 4 already moves every
  row family in one cut, and the migration gates each step on the previous one.
- **Coordination branches only.** A compare-and-swap plumbing write to a branch that is checked
  out (the primary or Mission branch in `single_branch` or `lanes`) would desync that checkout.
- **The four premises.** D-6 names four premises that each need their own ADR before storage
  changes: ADR `2026-10-13-2` D-2, ADR `2026-10-01-2` D-6, ADR `2026-02-09-3` merge semantics,
  and the gates' reliance on git ancestry and `lane_head`. Check (e) against each.
- **Tail reader.** `events tail` reads the log with a byte-offset cursor over a file
  (`status/tail_reader.py:70`).

No option removes everything. Compare-and-swap branch deletes (#7212) and the landing proof
against the right remote (#7214) are needed under every model. Removing a branch always needs
the #7264 proofs.

## 5. Recommendation

Ranked:

1. **(a) Tighten, now.**
   - Every other option depends on it.
   - It targets the classes with the worst severity per record: SD, the after-merge part of WL,
     and the CT late window.
2. **(g) Stop carrying status on lane branches.** It is cheap, it removes the copies the
   operator's ruling already disowns, and it needs no new authority.
3. **(e) Write status to the coordination branch through the Java write service, with no
   coordination worktree.**
   - It addresses most of the coordination-topology friction (the largest lane cause) without
     reversing #5100.
   - It keeps protected-primary Missions working.
   - It is sequenced after migration step 4.
4. **(b) Short-lived lane checkouts** for Missions that use lanes. Do this after the for_review
   gate moves onto refs and ADR `2026-04-03-1` is amended.
5. **(c) Only as an explicit operator decision.**
   - The evidence favours it on friction (62 tracer entries).
   - It reverses #5100, moves the root checkout off the primary branch, and widens the
     unbounded population.
   - It is not recommended before the `single_branch` approval bound has per-WP windows.
6. **(d) Reject.** It costs parallelism for no benefit that (b) plus (e) do not give.

### 5.1 Phased path

| Phase | Content | Exit evidence |
|---|---|---|
| 0. Contain | Land the open safety fixes under the #7264 proof-obligation ADR, in the order the triage issues set: #7239, #7237, #7240. Do the #7265 design pass, then land #7228 absorbing #7226. Land #6884. | the #7264 ADR accepted; #7198, #7199, #7211, #7212 and #7214 closed |
| 1. One read contract | See the list below the table | gate green with an empty allowlist; wrappers collapsed; the for_review gate passes with the lane checkout absent |
| 2. Ownership and copies | Give Mission worktrees an owner after a PR landing: `accept --mode pr`, or the prune with a merge-commit proof. Apply (g). Fix the pack doctrine upstream in `spec-kitty-open-packs`: add a status rule and use one worktree vocabulary. | no stranded Mission worktrees after a PR landing; no lane branch carries `status.events.jsonl` |
| 3. Status off the coordination checkout | Write the ADR set that D-6 requires. Deliver (e) as a step after write-service migration step 4. | coordination worktree removed; `COORD_STATUS_SURFACE_*` codes retired |
| 4. Short-lived lane checkouts | Amend ADR `2026-04-03-1`. Introduce lease-based lane checkouts with explicit lane-tip record points. Run auto-rebase and dependency merges in temporary worktrees. Migrate by dropping clean, recorded lane worktrees. | no lane worktrees left between sessions |

Phase 1 covers four changes:
- One read contract, defined per topology. Read status from the ref only where the write path
  commits in the same unit of work. Otherwise read one named working-tree surface. The flat
  status shell appends without committing, which is why `runtime/next/committed_authority.py`
  reads the working tree.
- No wrapper-local fallback.
- No read of a lane checkout's status copy.
- The for_review gate moved onto `refs/heads/<lane>`, plus an empty-allowlist architectural
  gate.

### 5.2 First slice

**Phase 1: one status read contract.** It turns the operator's ruling of 2026-11-06 into
structure:
- It finishes what #6884 starts.
- It collapses the wrappers onto `resolve_status_surface_with_anchor`.
- It defines the read semantics per topology.
- It moves the for_review gate onto the lane ref.
- It gates the call sites.

It also settles the Java service's open question 2, which needs one location rule before
resolution can move into the service. Run it as its own software-dev Mission; this note does not
start it.

Phase 0's #7264 ADR is the parallel priority for the data-loss cases (#4753, #4752).

### 5.3 Decisions the operator needs to make

1. **Default topology (#5100).** Keep the binding decision that `single_branch` is explicit-only
   (recommended for now), or reverse it? If you reverse it, `single_branch` needs per-WP
   approval windows first, and you must accept that the root checkout leaves the primary branch
   on create.
2. **Coordination branch.** Keep it as the lifecycle home, with the #7266 artefact-placement
   decision? (e) removes only its worktree.
3. **Status by plumbing.** Approve the ADR set D-6 requires, and the step after migration step 4
   that writes the coordination branch without a worktree?
4. **Lane status copies.** Approve (g): lane branches stop carrying `status.events.jsonl`.
5. **Short-lived checkouts.** Amend ADR `2026-04-03-1` decision 3? Accept that releasing a lane
   checkout commits or refuses, which changes behaviour for agents and IDE sessions?
6. **Cleanup owner after a PR landing.** `accept --mode pr`, or the landed-worktree prune with a
   merge-commit proof?
7. **Destructive operations.** Adopt the #7264 proof-obligation ADR as the single authority for
   prune, lane teardown and consolidation cleanup?

### 5.4 Operator rulings (2026-11-06)

These rulings are stijn-dejongh's of 2026-11-06. The dispatcher session relayed them into the
research session; they are recorded here as received.

| # | Decision | Ruling |
|---|---|---|
| 1 | Default topology (#5100) | **Reverse explicit-only.** The default is chosen by Mission size: `single_branch` when the finalized tasks have at most 2 WPs, or when lane computation yields a single lane; lanes otherwise. An explicit `--topology` always wins. |
| 2 | Coordination branch | **Keep** it as the lifecycle home for coordination topologies. |
| 3 | Lane status copies | **Approved:** lane branches stop carrying `status.events.jsonl`. |
| 4 | Status by plumbing | **Approved:** write the ADR set for the Java write service writing coordination status without a coordination worktree. This follows migration step 4 (ADR `2026-10-22-1` D-6). |
| 5 | Short-lived checkouts | **Approved, start now:** amend ADR `2026-04-03-1` for short-lived per-command lane checkouts, where releasing a checkout commits or refuses. This runs in parallel with the tighten slice. The for_review gate must move onto the lane branch. |
| 6 | Cleanup after landing | **Both `accept` and prune, without waiting for the PR merge,** which is asynchronous. Worktree and branch cleanup is the final step of the consolidation phase, under the destructive-operation proofs. `doctor workspaces --prune` stays the proof-based backstop for anything left. |
| 7 | Destructive operations | **Adopted:** the #7264 proof list is the single authority for every destructive git operation (prune, lane teardown, consolidation cleanup), enforced through `git/destructive_guard.py`. |

What the rulings change in this note:

- **Recommendation order.** Ruling 5 moves (b) up beside (a). Ruling 1 replaces "(c) only as an
  operator decision" with a size-based default.
- **Design point for the ruling 1 ADR.** Topology is chosen at `mission create`, before any WP
  exists. The size rule therefore has to apply at `finalize-tasks`, either by deciding there or by
  re-stamping a provisional topology. The re-stamp must not strand a coordination branch or a
  lane allocation made in between.
- **Risks that grow with ruling 1.** More Missions become `single_branch`, so more of them are
  neither stamped nor approval-bounded (section 4.2). Per-WP approval windows should land with
  the size-based default, or before it. #5550 and #5676 (the shared write checkout as a lock
  across Missions) matter more as well.
- **Effect of ruling 6.** Cleanup moves out of "after the PR merge" and into consolidation.
  Section 3.3's no-owner gap closes for Missions that consolidate through the CLI. The prune
  remains for checkouts that never reach that step.

### 5.5 Proposed slices (for the operator to approve; none filed or started)

| Slice | Ruling | Content | Depends on |
|---|---|---|---|
| S1. One status read contract | (a) | One read contract per topology: read from a ref only where the write commits in the same unit of work. Collapse the wrappers onto `resolve_status_surface_with_anchor`. Add an empty-allowlist call-site gate. Finish #6884. | none |
| S2. For_review gate on the lane branch | 5 | Count lane commits with `git rev-list <base>..refs/heads/<lane>` instead of `HEAD` in the lane checkout (`lanes/for_review_gate.py:280`, `lanes/_git.py`). Exit: the gate passes with the lane checkout absent. | none |
| S3. ADR `2026-04-03-1` amendment: short-lived lane checkouts | 5 | Lease per command, release commits or refuses. Explicit lane-tip record points for temporary detached worktrees (the hook exits on a detached HEAD, `policy/lane_tip_recorder.py:67`). Re-entry without the crash-recovery route. Harness cwd across turns. Review worktree and fast-forward. Migration of existing lane worktrees. | S2 for the implementation, not the ADR |
| S4. Destructive-operation authority | 7 | Accept the #7264 ADR. Enforce it through `git/destructive_guard.py`. Land #7239, #7237 and #7240 under it, in that order. | none |
| S5. Cleanup as the final consolidation step | 6 | Worktree and branch teardown becomes the last consolidation step, also on the `accept --mode pr` route, without waiting for the PR merge. `doctor workspaces --prune` is the backstop. | S4 |
| S6. Lane branches without status copies | 3 | Sparse exclusion or a tree filter at lane cut for `lanes` as well as coordination topologies (`coordination/workspace.py:416`). A migration for existing lane branches. Retire the lane auto-rebase merger for the file once no lane carries it. | S1 |
| S7. Size-based default topology | 1 | ADR reversing #5100: the size rule, its home (`finalize-tasks`, decide or re-stamp), the explicit `--topology` override, the `specify` help text, docs and tests. | per-WP approval windows for `single_branch` (S8) |
| S8. `single_branch` approval bound | 1 (risk) | Per-WP approval windows on a shared write branch (the #5046 machinery) or an amendment to ADR `2026-10-04-5`. | none |
| S9. Coordination status without a coordination worktree: the ADR set | 2, 4 | The ADRs D-6 requires: committed-ledger publication (ADR `2026-10-13-2` D-2), the read API pull (ADR `2026-10-01-2` D-6), event-log merge semantics (ADR `2026-02-09-3`), and the gates' reliance on ancestry and `lane_head`. Also covers the `events tail` cursor. Delivered after write-service migration step 4. | write-service step 4 |
| S10. Late-window design pass | (a), phase 0 | The #7265 design pass, then #7228 absorbing #7226. | none |
| S11. Doctrine upstream | (a) | In `spec-kitty-open-packs` and the command skills: a status-surface rule, one worktree vocabulary, current `consolidate` wording, cleanup and recovery guidance for `DESTROYED_LANE` and `LANE_WORK_TIP_UNKNOWN`. | S1, S3 |

## 6. Limitations

- Classification is rule-based with sampled hand checks. Read the cause shares within a few
  points, and treat severity counts as indicative only.
- Tracer coverage is uneven. Op records, retrospectives and design-decision tracers were not
  mined for friction.
- The issue population is label-selected. Across all 2,550 issues opened in the window, the lane
  share is at most about 13%.
- The CT code is broad. It includes resume, abort and rollback windows that are only partly
  caused by the coordination topology.
- "Lane" is overloaded (WP lifecycle lane versus execution lane), so the keyword counts
  overstate the topic. The classifications corrected this by hand where sampled.
