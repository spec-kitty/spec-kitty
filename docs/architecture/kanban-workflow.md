---
title: Kanban Workflow Explained
description: "How Spec Kitty tracks work-package progress: the nine lanes, the 27 allowed transitions and their guards, the append-only event log, and who moves work between them."
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/ai-agent-architecture.md
- docs/architecture/execution-lanes.md
- docs/architecture/spec-driven-development.md
---
# Kanban Workflow Explained

Spec Kitty uses a kanban-style workflow to track work package progress. This document explains how lanes work, why we track status this way, and what happens when work moves between lanes.

## The Nine Lanes

Work packages move through nine lanes during their lifecycle. Seven lanes form the main progression, and two lanes handle exceptional states:

### Main progression

```
planned -> claimed -> in_progress -> for_review -> in_review -> approved -> done
```

### Exceptional states

```
blocked    (reachable from planned, claimed, in_progress, for_review, in_review, approved)
canceled   (reachable from planned, claimed, in_progress, for_review, in_review, approved, blocked)
```

### Lane definitions

#### planned

**Meaning**: work package is defined and ready to start.

**How it gets here**:
- `/spec-kitty.tasks` creates WPs in `planned` lane
- Returned from review with feedback (`for_review -> planned`, `approved -> planned`)
- Voluntarily un-claimed (`in_progress -> planned`, with reason required)

**What happens**:
- WP waits for an agent to claim it
- Dependencies are satisfied (or WP is independent)

#### claimed

**Meaning**: An agent has claimed this work package but has not yet started a workspace.

**How it gets here**:
- Agent claims WP with `spec-kitty agent tasks move-task WP01 --to doing --assignee claude`
- Guard: requires actor identity

**What happens**:
- WP is reserved for the claiming agent
- No workspace exists yet
- Next step: create a workspace and transition to `in_progress`

#### in_progress

**Meaning**: An agent is actively implementing this work package in a workspace.

**How it gets here**:
- From `claimed` when a workspace is created (`claimed -> in_progress`)
- Automatically when running `spec-kitty agent action implement WP01 --agent <name>`
- Returned from review/approval for rework (`for_review -> in_progress`, `approved -> in_progress`)
- Unblocked (`blocked -> in_progress`)
- Guard: `claimed -> in_progress` requires workspace context

**What happens**:
- Agent works in the WP's worktree
- Makes commits to the lane branch backing the current workspace
- Only ONE agent should have a WP in `in_progress` at a time

**Alias**: `doing` is accepted as input and resolved to `in_progress` at input boundaries. The alias is never persisted in events or frontmatter.

#### for_review

**Meaning**: Implementation is complete, waiting for review.

**How it gets here**:
- Agent moves WP with `spec-kitty agent tasks move-task WP01 --to for_review`
- Guard: requires completed subtasks and implementation evidence (or `--force`)

**What happens**:
- WP waits in the review queue
- A reviewer claims it by transitioning `for_review -> in_review`
- Can also be blocked (`-> blocked`) or canceled (`-> canceled`)

#### in_review

**Meaning**: A reviewer is actively examining this work package.

**How it gets here**:
- Reviewer claims WP from review queue: `for_review -> in_review`
- Guard: requires actor identity (conflict detection prevents two reviewers claiming the same WP)

**What happens**:
- Reviewer examines the implementation against spec and acceptance criteria
- All outbound transitions require a `ReviewResult` in the transition context
- Either approves (`-> approved`) or requests changes (`-> in_progress` or `-> planned` with feedback)
- Can also be blocked (`-> blocked`) or canceled (`-> canceled`)

#### approved

**Meaning**: work package has passed review and is merge-pending.

**How it gets here**:
- Reviewer approves: `spec-kitty agent tasks move-task WP01 --to approved --approval-ref PR#42`
- Can come from `for_review` or directly from `in_progress` (skipping explicit review)
- Guard: requires reviewer approval evidence (reviewer identity + approval reference)

**What happens**:
- WP is approved and ready for acceptance and merge
- Can still be sent back for rework if issues arise (`-> in_progress` or `-> planned`)

#### done

**Meaning**: work package has been merged/integrated into the mission target branch.

**How it gets here**:
- From `approved` after merge/integration, or via forced override with audit evidence
- Guard: requires merge/integration evidence or an explicit force reason

**What happens**:
- Lane branch content has already landed
- No further changes expected
- `approved` unblocks dependent WPs immediately
- `done` is recorded by merge bookkeeping after approved work lands
- Once all WPs are `approved` or `done`, run `/spec-kitty.accept` to validate
  the entire mission before merge

#### blocked

**Meaning**: work package cannot proceed due to an external dependency or issue.

**How it gets here**:
- Any non-terminal lane can transition to `blocked` (planned, claimed, in_progress, for_review, in_review, approved)

**What happens**:
- WP is parked until the blocker is resolved
- Can transition to `in_progress` when unblocked
- Can be canceled if the blocker is permanent

#### canceled

**Meaning**: work package has been abandoned and will not be completed.

**How it gets here**:
- Any non-done lane can transition to `canceled` (planned, claimed, in_progress, for_review, in_review, approved, blocked)

**What happens**:
- WP is removed from active work
- `canceled` is a terminal lane (force required to leave)
- Does not count toward feature completion

## Allowed Transitions (27 pairs)

The state machine enforces exactly 27 legal transitions. Any transition not in this list is rejected unless `--force` is used (which requires actor + reason for audit).

### Forward progression (8)

| From | To | Guard |
|------|----|-------|
| planned | claimed | Actor identity required |
| claimed | in_progress | Workspace context required |
| in_progress | for_review | Subtasks complete + evidence (or force) |
| for_review | in_review | Actor identity required (conflict detection) |
| in_review | approved | ReviewResult required |
| in_review | done | Legacy direct-completion path; prefer in_review -> approved, then merge records done |
| in_progress | approved | Reviewer approval evidence |
| approved | done | Merge/integration evidence |

### Rework / rollback (5)

| From | To | Guard |
|------|----|-------|
| in_review | in_progress | ReviewResult required |
| in_review | planned | ReviewResult required |
| approved | in_progress | Review reference required |
| approved | planned | Review reference required |
| in_progress | planned | Reason required |

### Blocking (7)

| From | To | Guard |
|------|----|-------|
| planned | blocked | (none) |
| claimed | blocked | (none) |
| in_progress | blocked | (none) |
| for_review | blocked | (none) |
| in_review | blocked | ReviewResult required |
| approved | blocked | (none) |
| blocked | in_progress | (none) |

### Cancellation (7)

| From | To | Guard |
|------|----|-------|
| planned | canceled | (none) |
| claimed | canceled | (none) |
| in_progress | canceled | (none) |
| for_review | canceled | (none) |
| in_review | canceled | ReviewResult required |
| approved | canceled | (none) |
| blocked | canceled | (none) |

### Force overrides

Any transition not in the 27 allowed pairs can still be performed with `--force`, which requires both `actor` and `reason`. Force also bypasses guard conditions on allowed transitions. This is designed for administrative recovery, not normal workflow.

### Terminal lanes

`done` and `canceled` are terminal. Transitioning out of a terminal lane requires `--force` with actor + reason.

## How Work Moves Between Lanes

### Normal Flow: planned -> claimed -> in_progress -> for_review -> in_review -> approved -> done

```
1. WP created by /spec-kitty.tasks
   lane: planned

2. Agent claims WP
   spec-kitty agent tasks move-task WP01 --to doing --assignee claude
   lane: claimed (resolved from "doing" alias at input, but actual transition is planned -> claimed)

3. Agent creates workspace
   spec-kitty agent action implement WP01 --agent <name>
   lane: in_progress

4. Agent completes implementation
   spec-kitty agent tasks move-task WP01 --to for_review
   lane: for_review

5. Reviewer claims WP for review
   spec-kitty agent tasks move-task WP01 --to in_review --assignee reviewer
   lane: in_review

6. Reviewer approves
   spec-kitty agent tasks move-task WP01 --to approved --approval-ref PR#42
   lane: approved

7. Continue until every WP is approved or done
   (Then /spec-kitty.accept validates the mission before merge)
```

### Review Feedback: in_review -> planned (with feedback)

When review finds issues:

```
1. WP in for_review, reviewer claims it
   spec-kitty agent tasks move-task WP01 --to in_review --assignee reviewer
   lane: in_review

2. Reviewer finds problems
   /spec-kitty.review WP01
   Writes feedback file and runs move-task with --review-feedback-file
   Feedback persisted to git common-dir as feedback://<feature>/<wp>/<artifact>.md
   lane: planned (reset)
   review_status: has_feedback
   review_feedback: feedback://<feature>/<wp>/<artifact>.md

3. Agent re-claims WP
   Reads review_feedback pointer from frontmatter
   Addresses issues
   lane: claimed -> in_progress -> for_review

4. Reviewer re-reviews (claims again: for_review -> in_review)
   If good: lane: in_review -> approved
   If issues remain: repeat
```

### Blocking and Unblocking

```
1. WP hits an external blocker
   spec-kitty agent tasks move-task WP01 --to blocked --note "Waiting for API key"
   lane: blocked

2. Blocker resolved
   spec-kitty agent tasks move-task WP01 --to in_progress
   lane: in_progress (resumes work)
```

## Event Log (Canonical Status Tracking)

Lane transitions are tracked in an append-only event log stored at `kitty-specs/<feature>/status.events.jsonl`. Each line is a JSON object representing one `StatusEvent`:

```json
{"actor":"claude","at":"2026-02-08T12:00:00+00:00","event_id":"01HXYZ...","evidence":null,"execution_mode":"worktree","feature_slug":"034-feature","force":false,"from_lane":"planned","reason":null,"review_ref":null,"to_lane":"claimed","wp_id":"WP01"}
```

### StatusEvent fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | ULID (globally unique, time-sortable) |
| `feature_slug` | string | Feature identifier (e.g., "034-feature-name") |
| `wp_id` | string | work package ID (e.g., "WP01") |
| `from_lane` | string | Lane before transition (canonical name) |
| `to_lane` | string | Lane after transition (canonical name) |
| `at` | string | ISO 8601 UTC timestamp |
| `actor` | string | Who made the transition (agent name or "system") |
| `force` | boolean | Whether force override was used |
| `execution_mode` | string | "worktree" or "direct_repo" |
| `reason` | string/null | Reason for forced or rollback transitions |
| `review_ref` | string/null | Review feedback reference |
| `evidence` | object/null | DoneEvidence payload (for done transitions) |

### Why an event log?

**Immutability**: Events are append-only. No event is ever modified or deleted.

**Deterministic replay**: The `reduce()` function replays all events to produce a `StatusSnapshot` (materialized as `status.json`). Same events always produce the same snapshot.

**Debugging**: If something goes wrong, you can trace the full history of transitions.

**Metrics**: Calculate time-in-lane, cycle time, throughput from the event stream.

**Audit trail**: Know who did what, when, and why.

**Coordination**: Multiple agents can see what others are doing.

### Materialization

The current state of all WPs is derived from the event log by the deterministic reducer:

```bash
spec-kitty agent status materialize
```

This produces `status.json` (the `StatusSnapshot`), which contains the current lane, actor, and timestamp for every WP.

## Lane Status in Frontmatter

Lane status is also reflected in each work package's YAML frontmatter for backward compatibility:

```yaml
---
work_package_id: "WP01"
title: "Database Schema"
lane: "in_progress"
assignee: "claude"
agent: "claude"
shell_pid: "12345"
review_status: ""
review_feedback: ""
---
```

### Key Fields

| Field | Purpose |
|-------|---------|
| `lane` | Current status (canonical lane name) |
| `assignee` | Who is working on this WP |
| `agent` | Which AI agent claimed this |
| `shell_pid` | Process ID of the agent (for tracking) |
| `review_status` | Empty or `has_feedback` if returned from review |
| `review_feedback` | Pointer to persisted feedback artifact (`feedback://...`) |

### Not Directories, Just a Field

In many kanban systems, you move cards between columns (directories). In Spec Kitty, the WP file stays in the same place -- only the `lane:` field changes.

```
kitty-specs/012-feature/tasks/
  WP01-database.md      # lane: done
  WP02-api.md           # lane: for_review
  WP03-frontend.md      # lane: in_progress
  WP04-tests.md         # lane: planned
```

This design keeps all WP files in one location for easier discovery.

## Kanban Board Display

### CLI board (`spec-kitty agent tasks status`)

The CLI status command displays a **5-column** kanban board:

```
Feature: 012-user-authentication
Kanban Board
  Planned       Doing         For Review    In Review     Approved      Done
  WP04-tests    WP03-front..  WP02-api      WP06-auth     WP05-docs     WP01-database
                (stale: 15m)

  1 WPs         1 WPs         1 WPs         1 WPs         1 WPs         1 WPs
Progress: 1/6 (16.7%)
```

The display maps the 9 internal lanes to 6 board columns:

| Display Column | Internal Lane(s) |
|----------------|------------------|
| Planned | `planned` |
| Doing | `claimed`, `in_progress` (`claimed` is active ownership; `in_progress` is active implementation) |
| For Review | `for_review` |
| In Review | `in_review` (active review in progress) |
| Approved | `approved` |
| Done | `done` |

`blocked` and `canceled` WPs are not shown in the main board columns. They appear in separate sections below the board when present.

### Python API board (`agent_utils/status.py`)

The Python API (`show_kanban_status()`) displays all 9 lanes as separate columns, giving full visibility into every state.

## Who Moves Work?

### Agents Move Work Forward

Agents are responsible for:
- `planned -> claimed` (or `doing` alias) - Claiming a WP to work on
- `claimed -> in_progress` - Starting work in a workspace
- `in_progress -> for_review` - Signaling completion

Commands:
```bash
# Claim a WP
spec-kitty agent tasks move-task WP01 --to doing --assignee claude

# Mark complete
spec-kitty agent tasks move-task WP01 --to for_review --note "Implementation complete"
```

### Reviewers Make Accept/Reject Decisions

Reviewers are responsible for:
- `for_review -> in_review` - Claiming a WP for active review
- `in_review -> approved` - Approving work (requires ReviewResult)
- `in_review -> planned` - Requesting changes with feedback (requires ReviewResult)
- `in_review -> in_progress` - Requesting minor changes, keeps workspace (requires ReviewResult)

Merge is responsible for `approved -> done` after integration.

Commands:
```bash
# Claim a WP for review (for_review -> in_review)
spec-kitty agent tasks move-task WP01 --to in_review --assignee reviewer

# Review a WP (opens review workflow)
/spec-kitty.review WP01

# Approve (in_review -> approved)
spec-kitty agent tasks move-task WP01 --to approved --approval-ref PR#42

# Request changes with feedback file (in_review -> planned)
spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file feedback.md

# Once ALL WPs are approved or done, validate the mission before merge
/spec-kitty.accept
```

### Rework After a Rejection Is Not an Override

An ordinary review loop (reject → rework → resubmit → approve) needs no `--force`.
Each actor passes its own `--agent` identity:

- **Implementer:** the WP's latest implementer can resume a rejected WP and resubmit it to
  `for_review`. This holds even while the agent slot still names the reviewer. The latest
  implementer is the most recent actor to move the WP into `claimed` or `in_progress`,
  excluding two kinds of move: a reviewer's rework verdict that carries review feedback,
  and one made under a generic identity such as `user`.
- **Reviewer:** any named agent whose tool differs from the latest implementer's can
  review straight from `for_review`: claim it into `in_review`, approve it, or reject it
  back to `planned` with feedback. A generic identity never counts as a reviewer.
- **`in_review` verdicts:** only the agent holding the review claim can issue them.

These moves are recorded as ordinary transitions, so the review history lists each
cycle as rejected or approved and never as `rejected → overridden`.

The ownership check compares agent *tools*, not full identities. It prevents a
different agent from moving your WP by accident, but it does not prove that review
was independent.

An **arbiter override** is recorded only when someone deliberately overrules a
rejection. That means forcing a rejected WP from `planned` straight to `approved` or
`done`, with a note. The override counts after a rejection from either `for_review`
or `in_review`.

### Users and External Orchestrators Can Override

Users can override lane transitions when needed:
```bash
# Force move (e.g., to un-block stuck work or leave a terminal lane)
spec-kitty agent tasks move-task WP01 --to planned --force --note "Reopening after hotfix"
```

External orchestrators should request equivalent transitions through `spec-kitty orchestrator-api transition ...`, including review-handoff evidence such as `--subtasks-complete`, `--implementation-evidence-present`, `--review-ref`, and `--evidence-json`, so host validation and audit history stay consistent.

## Rules and Constraints

### One Agent Per WP in Progress

When a WP is in `claimed` or `in_progress`:
- Only the assigned agent should work on it
- Other agents should work on different WPs
- This prevents conflicts and wasted work

### Dependencies Must Be Satisfied

Before moving a WP to `claimed` or `in_progress`:
- All dependencies must be in `done` lane (or at least `for_review`)
- If WP02 depends on WP01, WP01 should be complete first

The implement command enforces this:
```bash
spec-kitty agent action implement WP02 --agent <name>  # Ensures WP01 code is available
```

### Review Before Done

WPs cannot skip directly from `in_progress` to `done`:
- Must pass through `for_review`, `in_review`, and `approved` first
- Review approval records `approved`; merge/integration records `done`
- This ensures all work is validated before it lands

### Subtask Validation

Before moving to `for_review`:
- All subtasks in the WP must be marked `[x]`
- The system blocks moves if subtasks are unchecked (unless `--force` is used)
- Ensures nothing is forgotten

## Common Patterns

### Linear Workflow

```
WP01 -> WP02 -> WP03 -> WP04
```

Each WP moves through lanes sequentially. One agent handles everything.

### Parallel Workflow

```
        WP01 (done)
       /    \
WP02 (in_progress)  WP03 (in_progress)
```

Multiple WPs in `in_progress` simultaneously. Different agents work in parallel.

### Review Feedback Loop

```
planned -> claimed -> in_progress -> for_review -> in_review -> planned -> claimed -> in_progress -> for_review -> in_review -> approved -> done
                                                       ^                                                           ^
                                                  (feedback)                                                  (approved)
```

Work returned from review goes back to `planned` with feedback.

### Blocking Pattern

```
planned -> claimed -> in_progress -> blocked -> in_progress -> for_review -> approved -> done
                                        ^            ^
                                   (blocker)    (unblocked)
```

Work paused due to external dependency, then resumed.

## See Also

- [Spec-Driven Development](spec-driven-development.md) - The methodology that creates work packages
- [Execution Lanes](execution-lanes.md) - How parallel development works
- [AI Agent Architecture](ai-agent-architecture.md) - How agents claim and process work

---

*This document explains how lanes work. For practical steps on moving work, see the how-to guides.*

## Try It

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)

## How-To Guides

- [Sync Workspaces](../guides/how-to/collaboration/sync-workspaces.md)
- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)

## Reference

- [CLI Commands](../api/cli-commands.md)
- [Slash Commands](../api/slash-commands.md)
