---
doc_status: draft
updated: '2026-11-28'
---

# Needs and user journeys

Assessor N1, profile analyst-annie. The profile asks for Given/When/Then acceptance criteria; the envelope asks for a needs map of at most 3,000 words, so the envelope wins and scenarios are left to deliverable 8.

## Conclusion

1. The documented product promise is small. It is: agree intent, split it into bounded work, let agents do the work without interfering, review each piece independently, let a human accept, land only what was approved, and leave a trail in the repository. Twelve journeys and 32 needs cover everything the README, tutorials, how-tos and prompts promise.
2. No documented need names lanes, a coordination branch, a topology, a partition or an approval stamp. The documentation promises outcomes ("in parallel without branch chaos", `core:README.md:13` [read]). Worktrees are the one mechanism the README promises by name. The need is non-interference; the mechanism is a choice.
3. Nine needs are core to the promise. Each of the nine is served by more than one mechanism today (section 3). The spread is widest for "what should the agent do next", "isolate parallel work", "land approved work" and "state the rules once".
4. Three documented journeys depend on something that is not placed anywhere at head: read-only progress for an outsider, turning tracker issues into work, and publishing a landed Mission.
5. The user documentation describes three generations of the product at once (section 6). This matters for an architect: the documentation cannot be read as a statement of the intended target.

Method. Needs come from documentation and prompts, not from use inside Spec Kitty's own repositories (R5, R15). Mechanism names in section 3 are names only, from the component catalogue (K-ids) and the CLI command list. Counts are pointers, not evidence of excess (R15).

## 1. Actors

| Id | Actor | Source |
|---|---|---|
| A1 | Practitioner: one person with one agent tool, day to day | `core:docs/context/audience/external/practitioner.md:3` [read] |
| A2 | Team lead: several agents or developers on one Mission, or several Missions at once | `core:README.md:45-46` [read] |
| A3 | Human in Charge: the accountable human; decides, accepts, lands. Often the same person as A1 | `core:docs/context/identity.md:155-159` [read] |
| A4 | AI agent (implementer or reviewer) inside an agent tool | `core:docs/context/audience/internal/ai-collaboration-agent.md:3` [read] |
| A5 | External integrator: an orchestrator, an MCP client, a CI job | `core:docs/guides/tutorials/orchestrator-quickstart.md:16-19` [read] |
| A6 | Pack author: writes governance artefacts or a mission type for others | `core:docs/guides/how-to/governance/create-an-org-doctrine-pack.md:3,48` [read] |
| A7 | Organisation governance owner: sets rules across projects | same file, Step 3 (`:243`) [read] |
| A8 | Observer: client, leadership, a reporting tool; read-only | `core:docs/guides/how-to/scenarios/agency-client-demo.md:3` [read] |
| A9 | Install and upgrade operator | `core:docs/README.md:3` [read] |

Evaluator personas (architect, tech lead, product manager) exist in `docs/context/audience/external/` but run no journey; they judge the others.

## 2. Journeys

| Id | Journey | Steps, intent to verified result | Source |
|---|---|---|---|
| J1 | Bring a repository under Spec Kitty | install; `init` with the chosen agent tools; verify; commands appear in the tool | `core:README.md:86-116` [read] |
| J2 | Solo software Mission | state intent; answer the interview; agree spec; plan; split into work packages; loop "next" until done; each package reviewed; accept; land on the target branch; retrospective | `core:README.md:118-148`; `core:docs/guides/tutorials/your-first-mission.md` [read] |
| J3 | Parallel Mission with several agents | as J2; packages declare dependencies; independent packages run at the same time in isolation; dependent ones start from the predecessor's result; lead watches status; land once | `core:docs/guides/tutorials/multi-agent-workflow.md:26-40,74-90` [read] |
| J3b | Several Missions at once in one repository | three Missions progress in parallel without branch switching | `core:docs/guides/how-to/scenarios/worktree-parallel-missions.md:16` [read] |
| J4 | Non-software Mission | pick research, documentation or plan; the steps, artefacts and gates differ; result is evidence, a doc set or an approved plan | `core:docs/context/mission-types.md:27-36` [read] |
| J5 | Govern a project | charter interview; generate; choose what applies; every later step receives the rules | `core:docs/guides/tutorials/charter-governed-workflow.md:38-60` [read] |
| J6 | Short governed task | `dispatch` a request; get role and rules; do the work; close with an outcome; no Mission | `core:docs/context/ops-vs-missions.md:25-37` [read] |
| J7 | External or unattended run | a program asks what is ready, starts work, records transitions, reviews, accepts, lands, through a versioned contract; human returns at the decision point | `core:docs/guides/tutorials/orchestrator-quickstart.md:92-212`; `core:docs/context/execution.md:201-213` [read] |
| J8 | Author and distribute organisation rules | lay out a pack; write artefacts; validate; publish; a project adds it; required items cannot be switched off | `core:docs/guides/how-to/governance/create-an-org-doctrine-pack.md:53-430` [read] |
| J9 | Define a new kind of Mission | write a mission definition with steps and roles; it becomes selectable at specify | `core:docs/api/missions.md:224-232,310-331` [read] |
| J10 | Observe and report | see where every package stands, human and machine readable, without source access | `core:docs/guides/how-to/scenarios/agency-client-demo.md:18-27` [read] |
| J11 | Recover | resume after an agent crash; resume or abort an interrupted landing; act on a refusal | `core:docs/guides/how-to/recovery/` (3 guides) [read] |
| J12 | Upgrade | upgrade the CLI; upgrade the project; nothing in flight is lost | `core:README.md:28,160` [read] |

## 3. Capabilities as needs

Essentiality: core (the promise fails without it), important, optional, speculative. Documentation: stated, implied, not found. Full rows with quality attributes are in `capabilities.csv`.

| Id | Need | Journeys | Essentiality | Doc |
|---|---|---|---|---|
| C01 | A repository can be brought under Spec Kitty and the setup verified | J1 | core | stated |
| C02 | The same workflow is available inside the agent tool the user already has | J1 J2 | core | stated |
| C03 | Intent becomes an agreed specification through an interview; work does not start on unanswered questions | J2 J4 | core | stated |
| C04 | The specification becomes a plan and bounded units of work with declared dependencies | J2 J3 | core | stated |
| C05 | At any moment an agent can ask what to do next, and a new session can pick up where the last stopped | J2 J3 J4 J7 | core | stated |
| C06 | The state of each unit of work is recorded in the repository, with who, when and why | all | core | stated |
| C07 | Several agents work on one Mission at once without overwriting each other | J3 J7 | core | stated |
| C08 | Dependent work starts only when its predecessor is ready, and from its result | J3 | important | stated |
| C09 | Each unit of work is reviewed by someone other than its author, with reject and rework | J2 J3 J7 | core | stated |
| C10 | A human accepts the Mission as a whole before it lands | J2 J3 J4 | core | stated |
| C11 | Only reviewed work lands on the target branch; the landing can be previewed, resumed and undone | J2 J3 J7 J11 | core | stated |
| C12 | The integration branch stays clean while work is in flight; the target is chosen deliberately | J2 J3 | important | stated |
| C13 | Interrupted work is recoverable with a named remedy | J11 | important | stated |
| C14 | Kinds of work other than software have their own steps, artefacts and gates | J4 | important | stated |
| C15 | A new kind of work can be defined without changing the CLI | J9 | important | stated (reference only) |
| C16 | A project states its rules once and every step applies them | J5 J2 | core | stated |
| C17 | A project chooses which rules and roles apply, and related items follow | J5 | important | stated |
| C18 | An organisation sets rules for many projects, some of which a project cannot remove | J8 | important | stated |
| C19 | An agent can take a defined role with its boundaries | J5 J6 J9 | important | stated |
| C20 | Terms are kept consistent across specs, code and docs | J5 | optional | stated |
| C21 | A short task runs under the rules and leaves a trace, without a Mission | J6 | important | stated |
| C22 | An outside program drives a Mission through a stable, versioned contract | J7 | important | stated |
| C23 | A Mission runs unattended up to a human decision point | J7 | important | stated |
| C24 | Progress is visible, for a person and for a tool, without reading source | J10 J3 | core | stated |
| C25 | Other systems can consume Mission lifecycle events | J10 | speculative at head | stated as direction |
| C26 | Finished Missions feed proposals back into the rules, under human approval | J2 J5 | important | stated |
| C27 | CLI and project can be upgraded without losing work in flight | J12 | important | stated |
| C28 | A Mission can start from, and report to, an issue tracker | J2 | optional | implied |
| C29 | A broken setup can be diagnosed and repaired | J1 J11 J12 | important | stated |
| C30 | Several Missions are in flight in one repository without confusion of identity | J3b | important | stated |
| C31 | A landed Mission can be closed, reopened, followed up or archived | none | optional | not found in guides |
| C32 | Team members on different machines share Mission state through ordinary git | J3 J7 | important | implied |

Notes on essentiality, kept apart from present mechanisms (R14):

- C07 is core because the README makes it the headline. The need is "no overwriting, no branch chaos". It does not require more than one way to isolate.
- C11 states three properties: only approved work, preview, recoverable. The documentation gives users no finer rule than that (`core:docs/guides/how-to/missions/merge-mission.md` [read]); the fine-grained refusal codes are reference material, not a stated need.
- C14 and C15 are needs although the repositories rarely use them (R15). Four types are documented as first-class (`core:docs/guides/tutorials/missions-overview.md:32-73` [read]).
- C25 has a documented direction but no consumer at head: the produce seam registers no default handler (`core:CLAUDE.md`, Team Kitty section [read]).

### Mechanisms that claim each need

Names only. "n" is the count of distinct mechanisms I could name, a pointer for the mechanism assessors, not a finding.

| Need | Mechanisms that claim it today | n |
|---|---|---|
| C05 next action | `spec-kitty next` runtime (K10); mission-type step graph (K15); slash commands run directly; the implement-review skill; `orchestrator-api list-ready`; top-level `specify`, `plan`, `research`, `tasks` commands | 6 |
| C07 isolation | lanes; worktrees; topology (four kinds); coordination branch; write-checkout guards; owned-files declaration (K35) | 6 |
| C11 landing | `consolidate`; `orchestrator-api consolidate-mission`; approval-stamp bound; reconciliation gate; rollback authority; retention policy; origin-freshness gate | 7 |
| C16 rules once | Python charter (K03, K04); charter service (K06); activation ledger (K05); action-context resolver; rendered prompts carrying rules (K36); DRG | 6 |
| C06 state record | status event log (K12); work-package state machine in three places (K14); events package reducer (K16); write service (K20); derived views (`materialize`) | 5 |
| C24 visibility | `agent tasks status`; `orchestrator-api mission-state`; `events tail`; read service (K19, not launched by the CLI); dashboard (K40, removed) | 5 |
| C02 agent tools | command files for 12 tools; shared skills for 5; Claude Code plugin; session hooks; `agent config` (K36) | 5 |
| C09 review | review prompt; `agent action review`; `move-task`; review-cycle artefacts; independence check; verdict-capture skill | 6 |
| C14 kinds of work | mission types as pack data (K15); a second `mission.yaml` copy under `src/specify_cli/missions/` (`core:docs/context/mission-types.md:20-23` [read]); type-specific CLI commands; a built-ins-only role table (`core:docs/api/missions.md:370` [read]) | 4 |
| C15 new kind of work | project mission loader (`.kittify/missions/`); pack-shipped mission type; `spec-kitty workflow`; `mission run` | 4 |
| C22 external contract | orchestrator API (K28); `next --json`; `agent` subcommands; MCP adapter (K30) | 4 |
| C29 diagnose | `doctor` with about 30 subcommands; `verify-setup`; `validate-encoding`; `validate-tasks` (marked LEGACY) | 4 |
| C27 upgrade | `upgrade`; migration ledger (K37); `migrate` with 14 backfill subcommands; compatibility shims | 4 |
| C03 interview | specify prompt; Decision Moments (`agent decision`); intake brief | 3 |
| C18 org rules | org packs; open-packs (K25); pack logic in four readers (K26); pack composer (K41) | 4 |
| C12 clean target | topic branch default; protection policy; `--commit-to-target`; retarget | 4 |
| C01, C04, C08, C10, C13, C17, C19, C20, C21, C23, C26, C28, C30, C31, C32 | one or two each; see the CSV | 1-2 |

Subcommand counts: [executed] `spec-kitty --help` lists 49 top-level commands; `doctor` and `migrate` headings counted in `core:docs/api/cli-commands.md:2254-4415` [read].

## 4. Gaps in both directions

### Documented capability, no journey behind it

[executed] The README's "Everyday Commands" names 6 of the 49 top-level commands (`core:README.md:152-161`). These have reference text but no tutorial, how-to or scenario I could find under `docs/guides/` (92 files; `grep -rl` per term):

| Capability | Where documented | Journey |
|---|---|---|
| `mission close`, `reopen`, `follow-up`; `archive create/list/reclaim` | CLI reference only | none (C31) |
| `issue-matrix` | reference; one prompt heads-up (`specify/prompt.md:266`) | none |
| Decision Moments as a user-visible record | prompts (`specify/prompt.md:381`); no guide | hidden inside J2 |
| `spec-kitty workflow`, `mission run` | reference only | J9 has no how-to |
| `reconcile` (dossier), `cutover-guard`, `regen`, `plugin`, `docs query`, `lint`, `ops` | reference; one guide each for `lint` and `ops` | maintainer tasks, not user journeys |
| Topology choice (`--topology`) | one guide mentions it (`merge-mission.md:137,152`) | no guide tells a user how or why to choose |
| Glossary strictness | one how-to | no journey depends on it (C20) |

The topology row is the notable one. A user is never asked to want a topology. It is an internal answer to C07 and C12 that surfaced in the command line.

### Promised journey, nothing placed to serve it

| Promise | Source | State at head |
|---|---|---|
| A client sees progress "without exposing any source code" | `agency-client-demo.md:3` | the dashboard is removed; the read API is "planned" (`:27`) and the CLI does not launch it. What remains is pasting CLI output. Transitional, no stated end |
| "Turn GitHub issues ... into executable work packages" | `core:README.md:68` | [executed] `tracker bind` offers local trackers only (beads, fp); hosted connectors were removed (`README.md:183`). The README still says hosted tracker integrations are optional (`:203`) |
| Publish after landing (`/spec-kitty.merge --push`) | `core:README.md:140` | no `merge` command exists; `consolidate` lands locally only. Publishing is left to the user's own pull request |
| Multiplayer consumers over the read API | `core:docs/context/product-lines.md` | no consumer observed (K41) |
| Parity across "CLI, slash-command, and hosted surfaces" | `core:README.md:79-80` | hosted surfaces are not in this repository |
| A custom mission "appears as an option during specify" | `core:docs/api/missions.md:232` | reference only; the specify prompt and `mission-types.md:23` say there are exactly four types |

## 5. Principles as testable expectations (R8)

| Principle | What a user or the Human in Charge must be able to do or rely on |
|---|---|
| Human in Charge | Nothing lands on the target branch, and no rule changes, without an act of a named human or an explicit standing delegation by one. The human can stop, redirect or overrule at any step, and the overrule is recorded as theirs. Agents propose; the system never records an agent's proposal as a human decision. |
| Responsible delegation | The human can choose how much to attend: present throughout, present at checkpoints, or absent until the final decision (`core:docs/context/execution.md:177-213` [read]). Whatever the choice, what was delegated, to which role, under which rules, is visible afterwards. Delegating more never removes the final accept or decline. |
| Explicit responsibility ownership | For every unit of work the record answers: who implemented it, who reviewed it, who approved it, who landed it, and that author and reviewer differ. For every rule the record answers: which layer set it (product, organisation, project) and who may change it. No fact has two owners. |
| Independent evolvability | A user can change a rule, a role, a mission type or an agent tool without a CLI release. An integrator can upgrade the CLI without rewriting the integration, as long as the contract version holds. A part can be replaced without the user redoing Missions in flight. |
| Governed Mission coordination | Every step of a Mission runs with the project's rules in force and leaves evidence that it did. Parallel work cannot bypass review or acceptance. The same rules apply whether a human, a slash command or an external program drives the step. |

Test hints. The first three can be tested against a design by asking where a single authoritative answer is read from. The fourth is the one the architect's example violates: a mission type configured in a pack while the CLI branches on its name. The fifth fails wherever two entry paths (CLI and orchestrator API) enforce different checks.

## 6. Where the documentation reflects an older design

Labels follow R17. Counts are over `docs/guides`, `docs/api` and the README [executed, `grep -rl`].

| Remnant in the documentation | Example | Spread | Label |
|---|---|---|---|
| "merge" as the landing command; `/spec-kitty.merge --push` | `core:README.md:10,140`; `run-an-autonomous-mission.md:101` | 24 files with `spec-kitty.merge`; 9 with `spec-kitty~ merge`. [executed] no such command; the command is `consolidate` | legacy |
| "Spec Kitty 3.2" as the current product | `core:docs/README.md:2` | 40 files; the README says 4.0.0rc8 | legacy |
| One worktree per Mission (`.worktrees/001-auth/`), "restart the agent in the worktree" | `worktree-parallel-missions.md:16,110-116`; `claude-cursor-collaboration.md:19` | whole scenario guides | legacy; contradicts the lane model in `multi-agent-workflow.md:88-90` |
| Project-wide active mission: `mission switch`, "choose it during `init`" | `research-mission-example.md:29,42,220`; `missions-overview.md:30` | 2 files with `mission switch`. [executed] the CLI lists `switch` as removed in v0.8.0 | legacy |
| "Feature" as the domain object | `switch-missions.md:16-22`; [read] `src/specify_cli/cli/commands/init_help.py:58` "per-feature" | widespread in guides | legacy; forbidden by the project's own terminology rule |
| Numbered slugs (`###-`, `034-payment-retry-flow`) | `multi-agent-workflow.md:85`; `orchestrator-quickstart.md:136` | 21 guide files match a numbered-slug pattern | legacy; the mission number is now display-only and assigned at landing |
| One lifecycle for all types: "every mission type moves through this same loop" | `missions-overview.md:106-110` | contradicted by `mission-types.md` and the four different step sets under `packs/built-in/missions/mission-steps/` [read] | legacy |
| `/spec-kitty.research` as the way to start a research Mission | `missions-overview.md:90` | it is a software-dev step ("capture discovery findings") | legacy |
| "Kanban", dashboard, "lane" meaning status column | `claude-cursor-collaboration.md:3`; `use-dashboard.md:3` | "lane" names both a status column (`README.md:58`) and an isolation unit (`multi-agent-workflow.md:74`) | legacy for kanban and dashboard; the double sense of "lane" is current and unresolved |
| Hosted tracker, sync and auth as optional parts | `core:README.md:203` against `:183` | README | legacy |
| Mission type definitions "under `src/specify_cli/missions/`" with "an identical copy" in the pack | `mission-types.md:20-23` | one page; states the duplication as fact | transitional, no stated end |
| Built-in types listed as three, without `plan` | `core:docs/api/missions.md:370` | one page | legacy |
| `.kittify/missions/<key>/` holds custom mission definitions; `.kittify/missions/<mission_id>/` holds retrospective records | `api/missions.md:316`; `use-retrospective-learning.md:25` | two pages | current; two meanings for one directory |
| Retired tools kept as guides | `harnesses/roo.md`, `amazon-q.md` ("legacy") | 2 of 19 harness guides | legacy |
| The user-journey folder itself | `core:docs/plans/user_journey/README.md:28-31`: all journeys are "2.x-era vision", none re-validated | all | legacy; there is no current, owned statement of journeys |

Three generations are visible, each with a marker (R14):

1. Project-level mission, one worktree per numbered feature, kanban and dashboard. Markers: `mission switch`, `001-auth`, "feature", "kanban".
2. Per-Mission type, work-package lanes in worktrees, `merge`. Markers: "3.2", `spec-kitty~ merge`, `###-feature-lane-b`.
3. Topologies, coordination branch, `consolidate`, packs as the source of mission types. Markers: `--topology`, `consolidate`, "Charter Pack".

## Uncertainty

- Decision-relevant: whether C25 (event consumers) and C28 (tracker) are needs of the open product or only of the hosted line. The documentation points both ways. The architect should rule; it decides how much of the event and tracker machinery the open CLI must carry.
- Decision-relevant: whether J3b (several Missions at once) must be supported in one checkout, or only across checkouts. The documentation promises the outcome, not the place.
- Safe to settle by experiment: which of the 49 commands a user journey actually reaches. A walk through J2, J3, J4 and J7 in a disposable clone would list them.
- I did not read every guide in full. Journeys rest on about 30 of the 92 guide files plus the prompts' headings. A journey I missed would most likely be in `docs/operations/` or `docs/integrations/`.

What would change my mind on essentiality: a stated commitment to users (a release note, a published roadmap item) that names a mechanism, such as a topology, as something they may rely on.
