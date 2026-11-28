---
doc_status: draft
updated: '2026-11-28'
---

# The case for what exists

Assessor ST, profile reviewer-renata (its "approve/reject" verbs yield to the envelope: I assess, the architect decides). Sources read: M1 to M8, the duplication catalogue, the needs analysis. `candidates/` was not read. References are `repo:path` at head with a tag; ADR references name the section read. Item ids (S1 ...) match `steelman.csv`.

## 1. Conclusion

Thirty-six proposals were examined. For most the assessors are right: the reason is gone, or it survives the proposal by a simpler means. Seven are different. In each, a recorded failure that a user can meet would return, and the assessor either did not see the reason or named it as an open question without finding the record that answers it.

| Verdict | Count |
|---|---|
| The reason holds and the proposal loses it | 7 |
| The reason holds and the proposal keeps it by other means (often on a condition) | 15 |
| The reason no longer holds | 9 |
| No reason found | 5 |

The single most important finding: three assessors (M1, M3, M4) each move the status record out of the git-tracked tree, and each treats "several clones write one Mission's status" as a hypothetical. It is a recorded scenario with three issue numbers (S1). Together they remove the only sharing mechanism the documented journeys have.

The second: M1's recommended target keeps lanes that hold several work packages; M7's recommended target assumes one branch per reviewed unit. Both cannot be chosen (S3).

## 2. The reason holds and the proposal loses it

### S1. Ordering rules and the event-log merge driver (M4 alternative A; M3 alternative B; M1 "status leaves the tree")

- **Proposal.** One writer per repository, order is append order; delete the wall-clock sort, the approved-departure lift, continuity arbitration and the merge driver "not ported" (M4 §5.4, §8 A).
- **Reason found.** "Two people work on one Mission from two clones of one remote. The reviewer in clone B rejects a work package and pushes the status change. The integrator in clone A has not pulled" (`core:docs/adr/4.x/2026-10-06-3-evidence-gates-check-origin-freshness.md`, Context [read]; #5780, #5758, #5759). The lift answers #4941, where a rejection minted on a clock behind its approval was ordered before it and the rejected implementation landed on `main` (`core:CLAUDE.md`, Status Model Patterns [read]).
- **Failure scenario.** Reviewer and implementer work in two clones. Each appends rows. Git joins the two files. Without an ordering rule that is independent of file position, the fold can read the stale approval after the rejection, and consolidation lands rejected work with exit 0.
- **Does it survive the proposal?** Yes. A resident service per repository is one writer per clone, not one writer per Mission. Two clones still produce two histories that something must join. A git ref with compare-and-swap does not change this: the swap is local, and a fetched ref that diverged still needs a merge rule. Only a single shared store (hosted, or one always-reachable server) removes the cause, and that gives up need C32 ("share Mission state through ordinary git", `A:needs/capabilities.csv` C32 [read]) and the repo-native record of C06.
- **Simpler means?** Yes, but not deletion: one ordering rule that needs no wall clock (for example a per-work-package sequence number). It still needs a join step at merge.
- M4 §11 says such a documented need would change its disposition.
- **Verdict:** reason holds; proposal loses it. **Confidence:** high.

### S2. A local landing that needs no forge (M7 alternative A)

- **Proposal.** Spec Kitty stops moving the target; the pull request is the landing.
- **Reason found.** M7 states that landing without a pull request is not documented as a need. One documented journey ends exactly there: "Consolidate the mission into your local primary branch ... Result: Mission complete" with no publish step (`core:docs/guides/how-to/scenarios/solo-developer-workflow.md:131-136` [read]). The README loop ends in "merge" (M7 §2).
- **Failure scenario.** A solo developer, or a team on a host without required reviews, finishes a Mission. Under A there is no reviewer on the host, and a protected branch with a required review cannot be satisfied by one person. The per-work-package verdicts (approved, rejected, canceled) are not visible to the host: it sees one diff. Canceled or rejected work lands unless the human rereads everything.
- **Verdict:** reason holds for the solo and forge-free journeys; A loses it. A is sound for teams whose host enforces review. M7's recommended B keeps it. **Confidence:** medium-high.

### S3. Mixed-lane protection, when M1 A and M7 B are combined

- **Proposals.** M1 A keeps "lane = group of work packages sharing a worktree". M7 B deletes work-package windows, attribution and the canceled axes because "one branch carries one unit of review".
- **Reason found.** "Lanes integrate whole, so until #5046 the canceled WP's committed content shipped at exit 0" (`core:docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md`, Context [read]). #5668: commits added after approval landed under "Reconciliation verified" in four of four combinations (`core:docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`, Context [read]).
- **Failure scenario.** WP01 and WP02 share a lane. WP01 is approved, WP02 is canceled after committing. Under B the branch has one approved commit; whose approval is it? If WP01's, the tip moved and the landing refuses for ever. If "the branch's", no reviewer looked at the whole.
- **Does it survive?** Only if several work packages share a branch. M7 says so in its §8 B "Needs". M1 recommends A, not C.
- **Verdict:** each proposal alone is coherent; the pair loses the rule. The architect must choose: lanes with one work package each (M1 C or a restricted A), or keep per-work-package bounds. **Confidence:** high.

### S4. The lane test-origin probe (M1 alternative B)

- **Proposal.** Delete `lane_invocation.py` with tool-owned worktrees.
- **Reason found.** The probe reports whether a lane's tests load packages from the lane or "elsewhere: the #1907 case" (`core:src/specify_cli/lanes/lane_invocation.py:8-12` [read]; Mission lane-code-verification, #7547).
- **Failure scenario.** A Python project has an editable install pointing at the root checkout. The reviewer runs the tests in the lane worktree. They pass against the root's code, not the lane's. The reviewer approves untested work.
- **Does it survive?** Yes, in any design with more than one checkout, whoever creates the worktree. Host-provided worktrees make it more likely, since the host knows nothing of the project's environment.
- **Simpler means?** One check at review time. That is what the probe is; 476 lines may be too many, but the check is not accidental.
- **Verdict:** reason holds; B loses it. **Confidence:** medium-high.

### S5. Native command files for twelve tools (M6 alternative B)

- **Proposal.** Two open formats only (`.agents/skills/`, one `AGENTS.md` block); per-tool adapters become optional.
- **Reason found.** C02, rated core and stated: "the same workflow is available inside the agent tool the user already has" (`A:needs/capabilities.csv` C02 [read]); twelve tools are served by command files today (`core:CLAUDE.md`, Supported AI Agents [read]).
- **Failure scenario.** A user of a tool that reads neither format upgrades and finds no commands.
- **Does it survive?** Unknown per tool. M6 calls the check "a desk exercise" and did not do it. Until it is done this is a removal of a core capability on an assumption.
- **Verdict:** reason holds; proposal loses it for every tool that fails the check. **Confidence:** medium (the check could clear most tools).

### S6. Narrowing the rule set by allow list (M5 alternative B)

- **Proposal.** Activation is an ordered pack list plus exclusions; no allow lists, no per-kind absent defaults.
- **Reason found.** Two rules, both recorded. (a) `--only` and `--narrow-activation` are "the explicit choice to write a list" (`core:docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md:501-520` [read]). (b) For skills an absent key means the org-required set only, because every pack skill in force is projected as files into the project (`core:CLAUDE.md`, Pack skills [read]; `core:src/charter/offering/artifact_kinds.py:263-271` [read]: "registering a pack must not silently add N commands to every tool").
- **Failure scenario.** (a) A project narrowed to five directives bumps a pack pin; ten new rules come into force with no human act. That contradicts the needs analysis' reading of Human in Charge: "no rule changes without an act of a named human" (`A:needs/needs-and-journeys.md:149` [read]). (b) Every skill of every activated pack is written into the user's tool directories.
- **Simpler means?** Keep one allow-list form at pack level (activate a pack "pinned to these ids") and a per-kind "opt in" marker for kinds that project files. Much smaller than five flags per kind.
- **Verdict:** reason holds; B as written loses it. **Confidence:** medium.

### S7. The frozen step definition (M6 alternative A; partly M3 C)

- **Proposal.** No persisted run state; position is computed from the current definition, artefacts and events.
- **Reason found.** The engine freezes the mission template into the run directory with a hash (`core:src/runtime/next/_internal_runtime/engine.py:150-165` [read]). M2 lists it as essential item 6 and keeps it by a recorded digest (M2 §8 B). M6 does not mention it.
- **Failure scenario.** A user upgrades the CLI or bumps a pack pin mid-Mission. The step list changes. `next` reports a different position, or a new guard blocks a step already passed.
- **Verdict:** the cursor's reason no longer holds for work-package steps; the freeze's reason holds and M6 A loses it. M2 B keeps it. **Confidence:** medium.

## 3. The reason holds and the proposal keeps it by other means

| Id | Mechanism (proposal) | Reason and source | Kept how, on what condition |
|---|---|---|---|
| S8 | Lane work tips and hooks (M1 A simplify, B give up) | A destroyed lane's commits stay detectable after branch, worktree and context record are gone (`core:src/specify_cli/lanes/lane_tip.py:1-11` [read]; #5115, #4889) | "Never delete an unabsorbed branch." `git branch -d` does this only if landing is not a squash; under squash every lane looks unmerged, which is why the absorption probe exists. Condition: drop squash, or keep one absorption check |
| S9 | Operator attestations (M7 B deletes) | "Attribution refusals could never clear ... the event log is append-only" (`ADR 2026-09-29-1`, Context [read]); one of three points where M6 finds Human in Charge carried by mechanism (M6 §11) | M3 C's `Override` event with actor and reason. Condition: M3 C is adopted with M7 B; otherwise pre-4.0 approvals without a recorded commit refuse for ever |
| S10 | First-load context state (M5 removes) | 184 activated artefacts against a 32,000-token budget; delivery cannot mean inlining at every step (`core:docs/adr/3.x/2026-07-28-1-progressive-disclosure-of-doctrine-context.md`, Context [read]) | A depth argument chosen by the caller instead of a stored timestamp. M5's defect (a second agent gets ids only) is real; the budget reason is too |
| S11 | Surface keyword heuristic (M1 removes from CLI) | Two work packages go to one lane when "ownership is not provably disjoint" (`core:src/specify_cli/lanes/compute.py:8,1019` [read]); prevents two agents editing the same files | A conservative rule: no disjoint `owned_files`, same lane. No vocabulary needed |
| S12 | PRIMARY/COORD partition (M1 removes) | #2101 deadlock on protected `main` (`core:docs/adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md`, Context [read]) | All artefacts on the Mission branch, as the default path already does. Caveat: "a ref no worktree checks out" is not fetched or pushed by default refspecs; for C32 it must be a branch or a configured refspec. M1 does not say this |
| S13 | `RESERVED_BUILTIN_KEYS` (M2 removes) | A custom mission may not take a built-in key (`core:src/runtime/next/_internal_runtime/discovery.py:34-42` [read], R-002) | Layer precedence, as for every other artifact. Condition: replacing `software-dev` is an explicit, visible act (an org pack already needs a sanction to override built-ins, ADR `2026-10-05-3`), since it changes the gates of every Mission |
| S14 | Python step guards (M2, M6: declarative checks) | Parity fixtures marked "do not weaken" (M2 §10) | A closed check vocabulary. Condition: M2's experiment passes. The research guards with no producer have no defence (S26) |
| S15 | `genesis`, `uninitialized` lanes (M3 removes) | #1589: "two readers, two truths" when a missing work package read as `planned` (`core:docs/adr/3.x/2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md`, Context [read]) | One source of work-package existence. Condition: task files stop being a second source; while `tasks/WP*.md` can exist without a record the sentinel is still needed |
| S16 | `claimed` lane (M3 questions) | Exclusive claim before work starts; the window opener for approval evidence (`core:CLAUDE.md`, Work-package windows [read]) | An assignment on `in_progress`. The stale-claim check and the window stamp move with it |
| S17 | Produce seam `status/adapters.py` (M4 removes) | "The produce seam stays" (`core:CLAUDE.md`, Team Kitty section [read]); registrants live in `event-router/relocated` (M4 §5.5) | A subscriber that tails the ledger (ADR `2026-10-13-2`). Condition: that read surface exists before the seam goes |
| S18 | Rollback authority and run record (M7 B: one ref) | C11 "previewed, resumed and undone", C13 (`A:needs/capabilities.csv` [read]); ADR `2026-09-19-1` | B still moves the Mission branch and then the target; an interruption between leaves merged lanes, which a re-run tolerates. Dry run kept as "the real check" |
| S19 | Merge-attribute guard (M7 B removes) | Local `merge.renormalize` or a custom driver can change a merge result (`core:CLAUDE.md`, #5604 [read]) | B's integrated approval covers the merged tree. Condition: `accept` really judges the integrated tree; today it is documented as a nudge |
| S20 | Clone-local migration partition (M8: declarative reconcile) | "A teammate's fresh clone never receives the per-clone merge-driver settings, so its first pull ... leaves conflict markers that wedge every command" (#5759, ADR `2026-10-06-3`, Context [read]) | Reconcile on `upgrade`, `init`, `implement`. Gap: the failure occurs at the first `git pull`, before any of those. It must run at CLI start-up, or the merge driver must go (which S1 forbids) |
| S21 | Live org floor (M5 C: compile to files) | C18: rules "a project cannot remove"; `RequiredArtifactDeactivationError` | Enforced at compile and by a check. No weaker than today, where the agent also only reads text |
| S22 | Owned checkout as a mode (M1) | An agent already placed in a linked worktree by its host (ADR `2026-09-03-1`) | "The checkout I run in" as the general case |

## 4. The reason no longer holds

| Id | Mechanism | Why the reason has gone |
|---|---|---|
| S23 | Coordination worktree, seed and restore (M1) | The project's own Proposed ADRs `2026-11-06-4` to `-6` retire it; the size default already avoids it (`ADR 2026-11-06-3`, Context [read]: "build nothing that may have to be torn down") |
| S24 | Sparse exclusion of status, lane-checkout write guard, planning-commit pin (M1) | They exist only because status is a tracked file in the tree lanes are cut from; gone once it is not (subject to S1 and S12) |
| S25 | Squash as default (M7) | The one stated reason is "many orchestration commits" (`core:docs/guides/how-to/missions/accept-and-merge.md:304` [read]). If status and bookkeeping leave the code branches, those commits do not exist. No ADR for the default was found |
| S26 | Research guards counting events nobody writes (M2 §5.4) | A defect. A user of the research type is blocked today |
| S27 | G0 `mission.yaml`, frontmatter lane mirror, `selected_*`, legacy activation keys, G0 lane routes (M2, M3, M5, M1) | Superseded generations; each is marked legacy or transitional in its own text |
| S28 | Committed `status.json` (M3, M4) | Its recorded consumer wanted "to reduce `status.events.jsonl` itself instead of trusting the committed `status.json`" (`fleet-kitty:infra/DEFERRED.md:33` [read]); the reducer has since moved to the shared package (M4 §5.3). Confirm with the hosted consumer before removal |
| S29 | Migrations below 3.0 and their supersession apparatus (M8) | No documented need to upgrade from them; the stepping stone through 3.2.6 is named |
| S30 | Five-source directive activation, identity index (M5) | They reconcile generations and stem-versus-id drift; fix in content |
| S31 | Second consolidation executor in the orchestrator API (catalogue 3.1, M7) | Weaker guarantees for the same act; no reason for the difference was found |

## 5. No reason found

| Id | Mechanism | Note |
|---|---|---|
| S32 | Topology `lanes` straight onto a target; `coord` without lanes (M1) | Explicit-only, refused on protected targets; no journey found |
| S33 | Workflows (`*.workflow.yaml`, M2) | Documented (`docs/api/missions.md:410-510`, per M2) but no need distinct from a mission type; R16 migration named |
| S34 | Dispatch keyword router (M6) | A profile can be named or asked for |
| S35 | Empty shim registry with doctor and gates (M8) | Guards nothing |
| S36 | RACI and significance scoring in the engine (M2, M6) | No built-in use. If "the type declares which steps a person decides" is wanted, this is the only R8 hook that exists for it; deleting it closes that door. Decide the intent first |

## 6. What the assessors did not look at

**Joint effects.** Three joint effects were examined by no one:

1. M1 + M3 B + M4 A together remove git as the sharing channel for status (S1). No assessor names how a second clone obtains state afterwards.
2. M1 A + M7 B disagree on what a lane is (S3).
3. M6 finds Human in Charge carried by mechanism at three points only: protected-branch refusals, the independence comparison, operator attestations. M7 B deletes the third and calls the second advisory; M7 A hands the first to the host. No assessor proposes what replaces them. The honest missing piece is a human identity; without it the simplification removes the recorded acts and leaves instructions.

**Consumers in other repositories.**

| Consumer | Depends on | Named by an assessor? |
|---|---|---|
| `fleet-kitty` playbook, tests and agent prompts | `status.events.jsonl` rows, topology outcomes, worktrees (`fleet-kitty:tests/test_spike88_corpus_facts.py:39`, `docs/CONTROLLER-PLAYBOOK.md:274` [read]) | M3 yes; M1 no |
| `spec-kitty-planning` | 18 files name `status.events.jsonl`, 3 name `lanes.json` [executed: `grep -rIl`] | no |
| Every initialised project's `.gitattributes` | merge-driver lines (`spec-kitty-container:.gitattributes:1-5` [read]) | no; harmless if the driver goes (git falls back to text merge), but then S20's failure returns for old logs |
| `spec-kitty-orchestrator` | `workspace_path` must be a lane worktree on the lane branch (`spec-kitty-orchestrator:src/spec_kitty_orchestrator/executor.py:74` [read]); calls `transition` without command-level guards | M1 yes for the path. M3 C ("guards in one place, behind every door") would make its transitions start refusing, including the pre-review gate that runs tests; not named |
| Hosted dossier | on-disk row shape at pushed commits | M4 yes |
| User home directories | global commands shared by all of a user's projects (ADR `2026-04-08-6`, Context [read]: the double-prompt problem) | M6 B removes the global installers; a user's other projects on an older CLI lose commands. Not named |

## 7. Breaking changes and migration (R16)

| Change | Affected | Migration named by the assessor? |
|---|---|---|
| Topology keys removed, coordination Missions converted (M1) | every project with open Missions; Java services | yes, three options |
| Status out of the tree (M1, M3 B, M4 A) | every clone of every project; teams sharing by git | partly: log conversion is named; the loss of sharing by git is posed as a question, not costed |
| Lane reduction, one row envelope (M3) | old logs, orchestrator, prompts | yes |
| Guards behind every door (M3 C) | orchestrator API clients | no |
| One mission-type format (M2) | custom missions under `.kittify/missions/`, org packs | yes (converter) |
| Activation as pack list plus exclusions (M5 B) | every `charter.yaml` and `activation.yaml`; narrowed projects | converter named; loss of narrowing named as "long exclusion lists", which understates it (S6) |
| Two open formats (M6 B) | users of tools that read neither; user-home installs | optional pack named; per-tool check and other-project effect not |
| Pull request as landing (M7 A) | solo and forge-free users; both API clients | API yes; solo users no |
| Tree-equality landing (M7 B) | in-flight Missions on shared lanes | yes (flatten command) |
| Baseline cut (M8) | projects below 3.2; depends on 3.2.6 staying installable | yes |

## 8. Limits of this review

- I read the Context sections of nine ADRs and module docstrings, not the issues themselves; issue numbers are quoted from those texts.
- I did not test which tools read the two open formats (S5), nor run any reproduction.
- The hosted consumers of `status.json` and of the produce seam are outside the clones; S17 and S28 need their owner's word.

What would change my mind on the seven: a ruling that Mission state is shared through a service and not through git (S1); that the pull request is the only supported landing (S2); one work package per branch (S3); evidence that hosts isolate the test environment (S4); a completed per-tool check (S5); a ruling that exclusion is the only narrowing (S6); a definition digest in M6's design (S7).
