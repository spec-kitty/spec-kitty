---
title: Ops vs. Missions
description: 'What separates a lightweight, governed ad-hoc Op from a full spec-to-consolidate Mission, and a concrete rule for choosing between them.'
doc_status: active
updated: '2026-07-20'
type: explanation
related:
- docs/context/mission-types.md
- docs/api/profile-invocation.md
- docs/architecture/governed-profile-invocation.md
---
# Ops vs. Missions

Spec Kitty has two distinct units of governed work. Confusing them is the single
most common source of "why didn't this get tracked/reviewed/merged" confusion for
users past their first mission.

## The two units of work

**An Op** is a lightweight, governed ad-hoc invocation started with
`spec-kitty dispatch "<request>"`. It does **not** create a mission, a spec, a
plan, a work package, a branch, or a worktree. Concretely, `spec-kitty dispatch`
(`src/specify_cli/cli/commands/dispatch.py`):

1. Routes the request text to an agent profile via `ActionRouter` (or uses the
   profile you pass with `--profile`).
2. Loads governance/Charter context for that `(profile, action)` pair.
3. Opens an **Op record** — a single append-only JSONL file at
   `kitty-ops/<invocation_id>.jsonl` — and writes a `started` event with a fresh
   ULID invocation ID.
4. Returns synchronously with that context. It never spawns an LLM call itself;
   the calling agent does the actual work.

The Op stays **open** until you close it explicitly:

```bash
spec-kitty profile-invocation complete --invocation-id <id> --outcome <done|failed|abandoned>
```

That command appends a `completed` event to the same JSONL file (see
`src/specify_cli/invocation/executor.py`'s `ProfileInvocationExecutor.invoke()` /
`complete_invocation()`). Unclosed Ops are surfaced by `spec-kitty doctor ops` and
eventually swept to `abandoned`. There is no lane, no `for_review` state, and no
consolidation step — an Op is a single governed unit of work with a start event and an
end event, nothing else.

**A Mission** is the canonical product term for a full spec-to-consolidate workflow
unit: specify → plan → tasks → implement → review → consolidate (accept, for some
mission types). Starting one (`spec-kitty.specify` / `mission create`) creates a
persistent mission directory under `kitty-specs/<mission-slug>/` with `spec.md`,
`plan.md`, `tasks.md`, work-package files, and a `meta.json` carrying a durable
`mission_id`. Work packages move through the 9-lane status state machine
(`planned` → `claimed` → `in_progress` → `for_review` → `in_review` → `approved`
→ `done`, with `blocked`/`canceled` as side states), each transition is an
append-only event in `status.events.jsonl`, and `spec-kitty implement` creates
dedicated git worktrees/branches per work package. A Mission is designed to
survive across many sessions, multiple agents, and a review/consolidation gate; an Op is
designed to be opened and closed inside a single turn of work.

## Decision rule

Use this table to decide before you start:

| If your situation is... | Use |
|---|---|
| A one-off question, review, or piece of advice with no lasting spec/plan/code artifact to track | **Op** (`spec-kitty dispatch`) |
| A small fix or task that doesn't need a spec, a review gate, or multi-session tracking | **Op** (`spec-kitty dispatch`) |
| You want the governance context (Charter, doctrine) injected once, synchronously, without opening a multi-step workflow | **Op** (`spec-kitty dispatch`) |
| The work needs a written spec, an implementation plan, discrete reviewable work packages, or will span more than one sitting | **Mission** (`spec-kitty.specify` → `plan` → `tasks` → `implement` → `review` → `consolidate`) |
| The work needs to be resumable by name/slug across sessions or by a different agent | **Mission** |
| The work needs an explicit review/approval gate before it lands | **Mission** |

A useful heuristic: if you can describe the entire task in one sentence and
expect it done in one sitting, it's an Op. If you'd naturally want to write a
spec for it, or if "let's continue this tomorrow" makes sense, it's a Mission.

Ops and Missions are not mutually exclusive: a governed mission action (e.g.
`spec-kitty next --agent <name> --mission <slug>`) uses the same governed-context
model as `dispatch`. Both may write under `kitty-ops/`, but the record kind
differs. `dispatch` opens a standalone **per-invocation Op record** — its own
file at `kitty-ops/<invocation_id>.jsonl` (`src/specify_cli/invocation/writer.py`
/ `executor.py`) — that stays open until you explicitly close it with
`profile-invocation complete`. `spec-kitty next` never opens one of those. It
instead appends paired `started`/`completed` **lifecycle records** — a
different schema, `ProfileInvocationRecord`
(`src/specify_cli/invocation/lifecycle.py`) — to one shared, append-only
`kitty-ops/lifecycle.jsonl` log; there is no per-invocation file and no
explicit "close" command for it.

## Examples

**Op** — a quick governed question, no mission created:

```bash
spec-kitty dispatch "Review this implementation approach for the retry logic" --profile implementer-ivan
# ... agent does the review inline ...
spec-kitty profile-invocation complete --invocation-id 01J... --outcome done
```

**Mission** — a full lifecycle reference, spanning multiple commands and
sessions:

```bash
/spec-kitty.specify   # -> kitty-specs/<mission-slug>/spec.md
/spec-kitty.plan       # -> plan.md
/spec-kitty.tasks      # -> tasks.md + tasks/WP*.md
spec-kitty implement WP01   # creates a lane worktree, work begins
# ... review, approve, repeat per WP ...
spec-kitty consolidate   # lane consolidation into local main
```

For the mechanism behind governed dispatch in more depth, see
[Profile Invocation Reference](../api/profile-invocation.md) (CLI flags and
trail fields) and
[Understanding Governed Profile Invocation](../architecture/governed-profile-invocation.md)
(the `(profile, action, governance-context)` model). To choose which Mission
type to start, see [Mission Types](mission-types.md).
