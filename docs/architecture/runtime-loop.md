---
title: The Runtime Loop Explained
description: "How spec-kitty next inverts control so the runtime picks the next action: query versus advancing mode and the four decisions, step, decision_required, blocked, and terminal."
doc_status: active
kind: Explanation
updated: '2026-11-12T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Written for the Lead Developer reader.
related:
- architecture/kanban-workflow
- architecture/mission-system
- architecture/mission-type-resolution
- architecture/multi-agent-orchestration
---
# The Runtime Loop Explained

Spec Kitty offers two ways to advance work through a mission: slash commands and the runtime loop. This document explains the runtime loop -- what it is, when to use it, and how to interpret what it tells you.

**Terminology note**
- Canonical 2.x model: `Mission Type -> Mission -> Mission Run`
- `spec-kitty next` uses `--mission` as the canonical tracked-mission selector

## What Is `spec-kitty next`?

In a typical workflow, a human decides what to do next. They look at the kanban board, pick a work package, and run the appropriate slash command (`/spec-kitty.implement`, `/spec-kitty.review`, and so on). The human is the decision-maker.

`spec-kitty next` inverts that relationship. Instead of the human choosing the next action, the **runtime decides** and tells the agent what to do. The agent calls `spec-kitty next`, receives a decision, executes it, reports the result, and asks again. This is the runtime loop.

```
Agent asks: "What should I do next?"
    |
    v
Runtime evaluates mission state, WP status, guards, priorities
    |
    v
Runtime returns a decision: "Implement WP03 -- here is the prompt file"
    |
    v
Agent executes the work, reports the result
    |
    v
Agent asks again: "What should I do next?"
```

The runtime considers several factors when making its decision:

- **Mission phase** -- Which step in the mission workflow is active (specify, plan, tasks, implement, review, accept)
- **work package status** -- Which WPs are planned, in progress, done, or blocked
- **Guard conditions** -- Whether required artifacts exist, whether prerequisites are met
- **Priority ordering** -- Reviews before new implementations, dependency-free WPs before dependent ones

## When to Use the Runtime Loop

**Use `spec-kitty next` when:**

- You are running multi-agent orchestration (multiple agents working on the same mission in parallel)
- You want autonomous mission execution where agents run in a loop without human intervention
- You want the runtime to determine ordering and priority rather than choosing manually

**Use slash commands directly when:**

- You are working manually on a single mission
- You are a single developer working through one work package at a time
- You want explicit control over which action to take next

The two approaches are complementary. Slash commands give you direct control. The runtime loop gives you automation.

### Concurrent advances are serialised

When several agents advance the same mission run in parallel (or one agent retries a slow call), advancing a run is **serialised**: at most one `next` mutates a given run's cursor at a time, and an advance that was evaluated against a step the run has since moved past is **refused** with a `blocked` decision and a named reason — never silently completed or re-planned as `success`. A per-run-directory lock guards the cursor's read-modify-write and a caller-evaluated-step compare-and-swap detects a run that moved between the caller's read and the commit. See ADR [2026-10-08-1](../adr/4.x/2026-10-08-1-serialise-run-dir-advance.md). A refused advance returns the ordinary `blocked` shape (reason + exit 1); a retrying loop should treat `blocked` as "re-query, do not hammer".

## Query Mode vs Advancing Mode

`spec-kitty next` has two distinct modes:

- **Query mode** is the read-only form: `spec-kitty next --mission <slug> --json`
- **Advancing mode** is the runtime loop form: `spec-kitty next --agent <name> --mission <slug> ...`

Use query mode when you want to inspect the current run state without changing it. On a fresh run, the canonical query JSON returns `mission_state: "not_started"` and a non-null `preview_step` telling you which step would be issued first. `unknown` is a legacy transitional value and is no longer the primary contract to teach or consume.

### What a query envelope tells you

Every query envelope keeps `kind: "query"`, and `mission_state` keeps its values. Two fields tell you how to proceed:

- **`next_command`** names the command to run next. It is additive: it appears only when set. A query sets it on every envelope except two:
  - a pending decision on a run that has already started, which you answer with `--answer` (see `decision_required` below);
  - a landed Mission, which has nothing left to run.

  | What the query sees | `next_command` |
  |---|---|
  | A fresh Mission (`not_started`), a first decision, an in-flight or blocked run, a board previewing `implement` or `review`, a `blocked:*` board, an unreadable WP task file | `spec-kitty next --agent <agent> --mission <slug> --result success` |
  | A finished software-dev board, not accepted, or accepted before the board's latest WP transition | `spec-kitty accept --mission <slug>` |
  | A finished software-dev board, accepted after the board's latest WP transition | `spec-kitty consolidate --mission <slug>` |
  | A run that completed (`mission_state: "done"`) with no finished board, for example a Mission with no work packages | `accept`, or `consolidate` once accepted |

  A query without `--agent` never invents an identity: the command carries the literal placeholder `<agent>`. A finished board of another Mission type (documentation, research, plan, custom) names the advance command, because its runtime still has steps after the work packages.
- **`question` and `decision_id`** come together or not at all. When they are set, `options` or `input_key` is set too, so the decision can be answered. This holds by construction: an envelope that breaks it cannot be built.

**The start handshake.** A fresh Mission has no run yet. Its query previews the first step (`mission_state: "not_started"`, `preview_step`) and names the advance command. When the first step needs input, the query also shows that decision's `decision_id`, `question` and `input_key`. The decision is not pending yet, so `--answer` would be refused: run the advance command (`--result success`) first. It starts the run and returns the decision as `decision_required`, which you can then answer.

Use advancing mode when an agent is actively executing the loop. In this mode, `--result` reports the outcome of the previous issued step and the runtime may advance mission state.

Planning-artifact work packages follow the same runtime loop, but they execute in repository root outside the lane graph. Their workspace is the main checkout rather than a lane worktree.

## What the Runtime Consumes: a Single Resolved Mission Type

The runtime is a finite-state machine that consumes a mission type it does not
itself define. Per-mission-type behaviour is resolved **once**, upstream, into a
single `ResolvedMissionType` bundle, and the FSM reads that bundle rather than
reaching into any mission-type catalogue directly.

The bundle is keyed off the canonical `mission_type` field in `meta.json` that
the FSM already uses to read a mission's action sequence. The legacy `mission`
field remains readable for metadata compatibility; issue #2660 separately owns
removal of the meta-less software-development template fallback.
Governance rides alongside the action sequence as a **sibling field of the same
resolved bundle — not a property of any individual state or transition**. When
"states & transitions as config" fully lands, the state loader and the governance
slot both read the same `ResolvedMissionType`, but they stay distinct fields so the
two configuration axes remain separable.

This also closes the **software-dev-default leak**. Previously the action-scoped
context path inferred a mission's type from `template_set`, defaulting to
`software-dev` when it was unset — so a documentation, research, or plan mission
that never set `template_set` silently loaded software-dev's test-first,
implementation, and code-review doctrine. The runtime now keys governance off the
real `mission_type` from `meta.json`; a missing or unknown type is a hard error,
never a software-dev fallback. Governance, templates, expected artifacts, and
step contracts are current consumers of this bundle. Template readers select a
semantic artefact kind from the immutable doctrine-backed `template_set`, then
apply the existing project/user/package path precedence to its configured
filename. See
[Mission-Type Resolution](mission-type-resolution.md) and
[ADR 2026-07-14-2](../adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md).

## The Four Advancing Decisions

In advancing mode, every call to `spec-kitty next` returns exactly one of four decision kinds. Each tells the agent something different about what to do.

### `step` -- An action is available

The runtime has identified work to do. The decision includes an `action` (such as "implement" or "review"), a `wp_id` (which work package), and a `prompt_file` containing the full instructions.

**What to do:** Read the prompt file and execute the work described in it.

**Example output:**

```json
{
  "kind": "step",
  "agent": "claude",
  "mission_slug": "042-test-feature",
  "mission": "software-dev",
  "action": "implement",
  "wp_id": "WP02",
  "workspace_path": ".worktrees/042-test-feature-lane-b",
  "prompt_file": "/tmp/spec-kitty-next-claude-042-test-feature-implement-WP02.md",
  "reason": null,
  "guard_failures": [],
  "progress": {
    "total_wps": 5,
    "done_wps": 1,
    "in_progress_wps": 1,
    "planned_wps": 3,
    "for_review_wps": 0
  },
  "step_id": "implement"
}
```

### `decision_required` -- The runtime needs input

The runtime has reached a point where it cannot proceed without a choice. It provides a question, a set of options, and a `decision_id` that you use to send back your answer.

**What to do:** Read the question and options. Answer with:

```bash
spec-kitty next --agent <agent> --mission <slug> \
  --answer "<your choice>" --decision-id "<decision_id>" --json
```

If the agent cannot determine the answer, escalate to the user.

### `blocked` -- Cannot proceed

Something is preventing the mission from advancing. The `reason` field explains the high-level problem, and `guard_failures` lists the specific conditions that are not met.

**What to do:** Read the reason and guard failures. Common blockers include:

| Blocker | Typical Resolution |
|---|---|
| Missing artifacts (spec.md, plan.md) | Run the planning workflow first |
| Upstream WP not done | Implement or review the upstream WP |
| Review feedback not addressed | Re-implement, address feedback, move back to for_review |
| Stale agent (WP stuck in doing) | Move WP to planned with `--force`, then re-dispatch |
| Circular dependencies | Edit WP frontmatter to break the cycle, re-run finalize-tasks |

### `terminal` -- Mission complete

There are no more steps to execute. What `terminal` means depends on the Mission:

- **A software-dev Mission with a finalized work-package board, whose run is not authoritative**
  (see the next section): the Mission is accepted, with an acceptance newer than the board's latest
  work-package transition, or it has landed. An unaccepted finished board returns `blocked` with
  `MISSION_AWAITING_ACCEPTANCE` instead.
- **Every other Mission** (documentation, research, plan and custom Missions, a software-dev
  Mission with no work packages, or a run that reached the end of its runtime path): the run
  completed. Nothing has checked acceptance.

**What to do:** If the Mission is not accepted yet, run `spec-kitty accept --mission <slug>`. Then,
if it has not landed, run `spec-kitty consolidate --mission <slug>`. `consolidate` does not check
acceptance itself, so do not skip `accept`. Then run `/spec-kitty-mission-review` and the
retrospective workflow. A read-only query (`spec-kitty next --mission <slug> --json`) names the
command to run next in `next_command` (`accept`, then `consolidate` once accepted). Treat that field
as the authoritative hint.

## A Finalized Board Is Never Rewound

These rules apply to **software-dev Missions with a finalized work-package board** only.
Documentation, research, plan and custom Missions keep their runtime path unchanged, because their
runtime has steps after the work packages.

They also depend on whether the run is **authoritative**. A run at `analyze`, `implement`, `review`
or `accept` is authoritative and keeps the runtime path unchanged. For example, a run at `review`
whose last work package is approved gets the runtime `accept` step. A run that is absent, untouched,
or issued at a planning step (`discovery`, `research`, `specify`, `plan` or `tasks`) is not
authoritative, because the board is further along than the run. For such a run, an advancing
`next` never sends the Mission back to an earlier step such as `discovery`. Two rules apply:

- **The board's own answers.** These apply for every `--result` value (`success`, `failed` and
  `blocked`), when the run is absent, untouched, or issued at `discovery`, `research`, `specify`,
  `plan` or `tasks`:
  - **A finished board** (every work package approved, done or canceled) that is not accepted
    returns `kind: "blocked"` with `error_code: "MISSION_AWAITING_ACCEPTANCE"` and a
    `next_command` of `spec-kitty accept --mission <slug>`. Once you accept, the next advance
    returns `kind: "terminal"`.
  - **Acceptance must be newer than the board.** The acceptance recorded in `meta.json`
    (`accepted_at`) counts only when it is later than the board's latest work-package transition.
    If a work package is reopened and approved again after acceptance, the Mission is blocked on
    acceptance again.
  - **A board step that cannot be dispatched** (for example a work package that is claimed or in
    progress) returns `kind: "blocked"` with `error_code: "BOARD_STEP_NOT_DISPATCHABLE"`, naming
    the work package, and a `next_command` that resumes it:
    `spec-kitty agent action <implement|review> <WP> --agent <agent> --mission <slug>`. When no
    work package can be named, `next_command` is `spec-kitty agent tasks status --mission <slug>`,
    so you can inspect the board.
  - **A board step whose work package needs `lanes.json`, when `lanes.json` is missing**, returns
    `kind: "blocked"` with `error_code: "LANES_MANIFEST_MISSING"`. The `reason` is the error's own
    message. `next_command` is `spec-kitty agent mission finalize-tasks --mission <slug>` while
    every work package is still `planned`, and
    `spec-kitty doctor mission-state --fix --mission <slug>` once any work package has left
    `planned` (finalize-tasks refuses then; the doctor rebuilds `lanes.json` from the event log).
    The same answer is returned when the board dispatch below meets a missing `lanes.json`.
  - These answers start no run and record no step as completed. A `terminal` answer carries no
    `next_command` in advancing mode; a read-only query names `consolidate` for it.
- **Board dispatch.** A claimable work package is dispatched from the board when the run is absent,
  untouched, or issued at `discovery`, `research`, `specify` or `plan`. A run at `tasks` is not
  overridden: it advances through the runtime to `analyze`, its next step.

Read-only `next` uses the same finished-board verdict, so the two modes agree on a finished board: a
query names `accept`, and names `consolidate` once the acceptance is fresh.

**Residuals.**

- `MissionRunCompleted` and the retrospective gate are not reached through `next` for a
  software-dev Mission whose run is not authoritative (its work packages were driven from the
  board or outside `next`).
- A run that an earlier release already replayed to `analyze` or beyond cannot be told apart
  from a legitimate run, so it keeps the runtime path.

## The Agent Loop Pattern

At a conceptual level, an agent running the runtime loop follows this pattern:

1. Call `spec-kitty next --agent <name> --mission <slug> --json`
2. Read the decision kind
3. If **step**: read the prompt file, do the work, report the result
4. If **decision_required**: answer the question (or escalate to the user)
5. If **blocked**: diagnose the blocker, attempt to resolve it
6. If **terminal**: run `accept` if the Mission is not accepted, then `consolidate` if it has not landed, and exit
7. Report the result of the previous step with `--result success` (or `failed` or `blocked`)
8. Go back to step 1

The loop continues until the runtime returns `terminal` or the agent hits a blocker it cannot resolve.

### WP iteration within a single step

During the implementation phase, multiple calls to `spec-kitty next` will return different `wp_id` values but the **same `step_id`** ("implement"). The runtime stays on the "implement" step while cycling through work packages. It only advances to the next mission step (such as "review") when all WPs have reached a terminal or handoff lane (`done`, `approved`, `for_review`, or `canceled` **with operator provenance** — an operator-recorded cancellation is an acceptable ending, mirroring `is_acceptable_ending`; a synthetic cancellation still blocks advancement, fail-closed — #3780).

This means that in a mission with WP01 through WP09, successive calls might return:

- `step_id: "implement"`, `wp_id: "WP01"`
- `step_id: "implement"`, `wp_id: "WP02"`
- `step_id: "implement"`, `wp_id: "WP03"`
- ...and so on until all WPs are accepted-ready

The same behavior applies to the review step.

### Reporting results

After completing a step, tell the runtime what happened:

```bash
# After successful work
spec-kitty next --agent <name> --mission <slug> --result success --json

# After a failure
spec-kitty next --agent <name> --mission <slug> --result failed --json

# After hitting a blocker
spec-kitty next --agent <name> --mission <slug> --result blocked --json
```

If `--result` is omitted, the command stays in read-only query mode. Query mode may still accept `--agent` as a compatibility form, but it does not advance mission state.

## Things to Be Aware Of

### Merged missions are recognized as terminal (#2947, was #335)

**Fixed (#2947).** `spec-kitty next` now resolves mission state from the
**committed status authority** before it selects a coordination workspace. When a
Mission has landed — its PRIMARY `meta.json` records `merged_at`, which
`mission_has_landed` (`src/mission_runtime/landing.py`) reads — the loop recognizes it
from that committed record instead of a stale coordination worktree checkout:
advancing mode (`--result success`) returns `kind: "terminal"` and creates **no**
runtime run; read-only query mode returns `kind: "query"` with
`mission_state: "done"` (query mode is structurally `kind: query`). If the
committed record has landed but its status is not all-accepted
(a merge/status conflict), or an actionable step needs a coordination workspace
whose checkout is missing the mission's artifacts, the loop fails closed with a
structured `kind: "blocked"` — never a fabricated "unstarted" step. A landed
Mission's query envelope carries no `next_command`. The former
`progress`-field workaround is no longer required.

Historically this class was tracked as #335; the committed-authority resolution
in mission `next-committed-state-authority` closes it via #2947.

### Some steps may return a null prompt file (#336)

Certain mission steps (such as `discovery`) do not have command templates. When the runtime reaches one of these steps, it returns a `step` decision with `prompt_file: null`. An agent that tries to read a null prompt file will fail.

**Workaround:** Always check that `prompt_file` is not null before attempting to read it. If it is null, treat the decision as blocked -- do not attempt to execute without a prompt.

## See Also

- [Multi-Agent Orchestration](multi-agent-orchestration.md) -- The coordination model for running multiple agents
- [Mission System](mission-system.md) -- How missions define the workflow that the runtime follows
- [Mission-Type Resolution](mission-type-resolution.md) -- The doctrine → charter → core seam that resolves the bundle the runtime consumes
- [Kanban Workflow](kanban-workflow.md) -- The lane-based status model that the runtime reads

---

*This document explains the concepts behind the runtime loop. For step-by-step instructions on running agents, see the how-to guides. For the full decision output schema, see the reference documentation.*
