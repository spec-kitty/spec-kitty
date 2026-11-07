---
name: spec-kitty-program-orchestrate
description: >-
  Orchestrate a multi-repo, multi-mission Spec Kitty program end-to-end:
  run specify → plan → tasks → implement → review → merge → mission-review →
  post-merge fixes across several repositories in a defined dependency order,
  using background sub-agents for parallel work and a pulse-heartbeat safety
  net for long uninterrupted runs. Triggers: "ship this program across N
  repos", "orchestrate a cross-repo release", "run the full mission workflow on
  repos A/B/C in program order", "drive Decision Moment V1 across all
  repos", "multi-repo spec-kitty sprint". Does NOT handle: single-mission
  implement-review loop (use spec-kitty-implement-review), post-merge mission
  audit (use spec-kitty-mission-review), setup or repair (use
  spec-kitty-setup-doctor), per-WP review (use spec-kitty-runtime-review).
---

# spec-kitty-program-orchestrate

You are the program orchestrator for a multi-repo Spec Kitty effort. A single
"program" is a coordinated feature release that spans two or more repositories
in a specific sequence (often with cross-repo contract dependencies): e.g.
"Decision Moment V1" that touches an events repo, a SaaS backend, a CLI, a
web app, and two test-surface repos.

Your job is to drive the program from kickoff to "all repos merged + all
mission reviews cleared + all post-merge remediations landed" without
requiring the user to hand-hold each transition. You rely on
`spec-kitty-implement-review` to drive each individual mission, on
`spec-kitty-mission-review` to audit each merged mission, and on background
sub-agents to execute phases in parallel where dependencies allow.

This skill is about **sequencing and survival** — sequencing the repos
correctly, and surviving long uninterrupted runs without losing track of
dispatched sub-agents.

---

## When to Use This Skill

- The user has defined a program as an ordered list of repos + issues, where
  each repo is a distinct Spec Kitty mission and later repos may depend on
  earlier ones (merged commits, shipped APIs, contract artifacts).
- The user has authorized "uninterrupted" work — they want you to keep
  pushing without asking for input on every transition.
- Multiple concurrent background sub-agents are expected (typical: 3-6 in
  flight at peak; dispatch → review → chain pattern).
- Mission reviews and post-merge remediations are part of the deliverable,
  not optional follow-ups.

Do NOT use this skill when:

- There is only one mission — use `spec-kitty-implement-review` directly.
- The repos are independent (no ordering / contract dependency) — run each
  as a standalone mission.
- The user wants manual control over every dispatch — follow their lead
  instead.

---

## Program Inputs

Before you start, you need:

1. **Ordered repo list**: the sequence in which repos must ship. Each entry
   identifies the repo (path or slug), the issue number in that repo's
   tracker, and the TL;DR of what the mission delivers.
2. **Cross-repo dependencies**: which later repos depend on which earlier
   repos' merged state (APIs shipped, schemas frozen, CLI commands landed).
3. **Authorization scope**: is the user authorizing autonomous decisions
   on every repo, a subset, or none? Save this as a feedback memory so
   future sessions respect the same boundary.
4. **Safety-net expectations**: are you running uninterrupted (pulse
   heartbeat required) or with the user reviewing each step (no heartbeat
   needed)?

If any of these are missing, clarify once at the start. Do not keep asking
once the program is moving.

---

## The Mandatory Phase Pattern (Per Repo)

For each repo in the ordered list, run all of these phases. Each phase is
gated on the prior phase producing a clean artifact.

```
0. Discovery & decision interview     (optional — skip on autonomous repos)
1. /spec-kitty.specify                 → spec.md + checklists/requirements.md
2. /spec-kitty.plan                    → plan.md + research.md + data-model.md + contracts/ + quickstart.md
3. /spec-kitty.tasks                   → tasks.md + tasks/WPxx-*.md + finalize-tasks
4. Implement-review loop               (dispatch sub-agents per spec-kitty-implement-review)
5. spec-kitty accept + merge           → readiness nudge, then squash commit on main
6. Post-merge move WPs done           (handle invariant-check workarounds)
7. spec-kitty-mission-review skill     → structured report with verdict
8. Retrospective workflow              → capture learning while context is fresh
9. Post-merge remediation branch       (address any HIGH/MEDIUM findings)
```

Phase 0 is where user decisions are required for non-autonomous repos.
Phases 1–3 can be delegated to a single sub-agent per repo for autonomous
repos; keep them in the foreground when you need architectural judgment.
Phases 4–9 run via sub-agent dispatch once the phase-3 task contract is
finalized.

---

## Step 1: Program Orientation

Before dispatching any work, state the program shape back to the user (or
to your own memory if the user is silent and has authorized autonomy):

- Total repo count and ordering.
- Critical-path dependencies (e.g., "#110 must merge before #111 can dispatch
  its WP04").
- Autonomous vs user-gated repos.
- Expected program duration (rough estimate from the WP counts once
  `/spec-kitty.tasks` has run on each repo).

If the user has NOT authorized autonomy for a given repo, run phase 0
discovery interactively. If they HAVE authorized autonomy (see feedback
memory for the canonical phrasing, e.g., "You are 100% completely in
control"), skip discovery and synthesize the spec from the source
description + cross-repo contracts yourself.

---

## Step 2: Drive Each Repo Through the Workflow

For each repo, in dependency order:

### 2a. Capture the source description

Read the issue brief (usually at `issue-prompts/<N>-<repo>-<issue>.md` or
linked in the user's brief). Extract: goal, scope, cross-repo contract
references, locked architectural rules from prior repos.

### 2b. Phase 1 — Specify

Invoke `/spec-kitty.specify` with a prompt that includes the source
description AND any already-locked architectural decisions from earlier
repos in the program. For autonomous repos, skip discovery Q&A; go
straight to `mission create`.

Commit the spec + checklist. Read back the branch contract to the user
(current branch, planning base, merge target).

### 2c. Phase 2 — Plan

Invoke `/spec-kitty.plan --mission <slug>`. Self-answer any planning
questions the codebase can answer (via an Explore sub-agent or direct
grep) rather than asking the user — unless the architectural decision
is genuinely open and program-altering.

Commit plan.md + research.md + data-model.md + contracts/ + quickstart.md.

### 2d. Phase 3 — Tasks

Delegate `/spec-kitty.tasks` to a dedicated sub-agent. Tasks generation
is large and highly structured; a focused agent produces better WP prompts
than an orchestrator splitting attention. Reference the companion skill
for the task-generation workflow.

Verify the returned report: WP count, subtask tally per WP, requirement
coverage (`unmapped_functional` must be empty), finalize commit hash.

### 2e. Phase 4 — Implement-Review Loop

Use `spec-kitty-implement-review` as your loop engine. Per-WP pattern:

1. Dispatch implementer sub-agent with a prompt that includes the WP's
   dependencies, any cross-repo context (especially contracts from earlier
   repos), and explicit instructions to use the test-DB workaround for
   Django-backed projects (see issue #770 for why).
2. On `for_review` notification, dispatch reviewer sub-agent with a prompt
   that includes the adversarial checklist and any WP-specific risks
   surfaced during planning.
3. On `approved`, chain the next unblocked WP per the dependency DAG.
4. On `rejected`, read the review cycle file, dispatch a focused
   remediation agent with the exact blocker list, then re-review.

### 2f. Phase 5 — Accept and Consolidate

Run `spec-kitty accept --mission <slug>` after all WPs are approved. Treat it
as a pre-merge readiness nudge for the orchestrator and the human operator.
If it passes, run `spec-kitty consolidate --mission <slug>`. It auto-rebases a
stale lane (many WPs touched overlapping files) before consolidating it; when
the auto-rebase stops, run the command consolidate prints, resolve any
conflict in the lane checkout it names, and re-run consolidate. Consolidation
removes lane and coordination checkouts as its final step and prints a
`Removed` / `Kept` / `Retained` report.

### 2g. Phase 6 — Move WPs Done (workaround for the invariant check)

The post-merge bookkeeping often fails on `.worktrees/` being untracked.
Workaround:

```bash
mv .worktrees /tmp/<slug>-worktrees-parked
for wp in WP01 WP02 ...; do
  spec-kitty agent tasks move-task "$wp" --to done --mission <slug>
done
mv /tmp/<slug>-worktrees-parked .worktrees
```

This is tracked upstream as issue #772.

### 2h. Phase 7 — Mission Review

Dispatch a sub-agent that invokes the `spec-kitty-mission-review` skill
on the just-merged mission. Do not shortcut this step — the mission
review reliably catches real bugs that slipped past per-WP review
(FR-to-test coverage gaps, dead code, API whitelist misses, TOCTOU
races on external side effects).

### 2i. Phase 8 — Retrospective

The canonical post-merge sequence is: **mission review → author or verify retrospective
(`retrospect create`) → surface findings (`summary` aggregates; `synthesize` reviews proposals)**.

Under default 3.2.0 policy, the `retrospective.yaml` is authored during merge. Verify it:

```bash
cat .kittify/missions/$(jq -r .mission_id kitty-specs/<slug>/meta.json)/retrospective.yaml
```

If the record is absent (older mission or generation failed), author it now — context decays fast:

```bash
spec-kitty retrospect create --mission <slug>
```

Then surface findings:

```bash
spec-kitty retrospect summary                              # cross-mission aggregation (read-only)
spec-kitty agent retrospect synthesize --mission <slug>  # inspect proposals (dry-run by default)
spec-kitty agent retrospect synthesize --mission <slug> --apply  # apply proposals (mutates)
```

If `retrospective.yaml` is missing and `retrospect create` fails, escalate — check
`status.events.jsonl` for `RetrospectiveCaptureFailed` events and their `remediation_hint`.

### 2j. Phase 9 — Post-Merge Remediation

If the mission review verdict is `PASS WITH NOTES` with any HIGH or
MEDIUM findings, dispatch a remediation sub-agent to fix them on a
`post-merge/<slug>-mission-review-fixes` branch, then merge that branch
back to main with `--no-ff`. LOW findings can be deferred as follow-up
issues unless they are user-visible.

---

## Step 3: Parallel Dispatch Pattern

Do not drive the program serially. Within each repo and across repos,
dispatch work in parallel wherever the dependency graph allows.

### Within a repo

- After WP01 + WP02 approve, WPs 03, 04, 06, 08 may all be independently
  unblocked depending on the DAG. Dispatch them all in parallel, one
  sub-agent per WP.
- Reviewers and next-WP implementers can run simultaneously — a reviewer
  for WP05 does not conflict with an implementer for WP07 if they own
  different files.

### Across repos

- Once repo A reaches MVP (enough WPs merged for repo B to consume its
  APIs), begin repo B's phase 1 (specify) in parallel with repo A's
  remaining WPs.
- If the user has authorized autonomy on repo C, spawn the full-workflow
  sub-agent for repo C while repo A is still finishing. Nothing in phase
  1-3 depends on earlier repos being *merged* unless the spec explicitly
  requires consuming a merged API during planning (rare).

### Dispatch hygiene

- Cap concurrent sub-agents at ~6 to avoid overwhelming the task notification
  channel. More than that and you lose track of which agent owns which WP.
- Use distinctive descriptions in every `Agent` dispatch (`description`
  field). "Implement repo4 WP06 slack webhook" is readable; "Implement
  the thing" is not.
- Track dispatched IDs in a scratchpad you can grep. When you get a
  `<task-notification>`, you need to know which repo and which WP it
  corresponds to without re-reading your own prior turns.

---

## Step 4: Pulse Heartbeat (Mandatory for Uninterrupted Runs)

When the user has authorized uninterrupted work ("keep pushing",
"work without interruption", or equivalent), always keep a
`ScheduleWakeup` armed at all times as a pulse-monitor safety net.

### Why

Task notifications wake you on sub-agent completion, but:

- A sub-agent can die silently (sandbox kill, OOM, hung tool call).
- The notification can be delayed or lost (backend hiccup).
- You yourself can silently hang — the only thing that will unstick
  you is a scheduled wakeup.

Silence is not success. A scheduled heartbeat is the difference between
"I was working the whole time" and "I sat silent for two hours waiting
for a dead agent".

### How

- Delay: 1200–1800s (20–30 min). Shorter than ~270s burns cache without
  useful signal; longer than ~1800s risks the user noticing a stall
  before you do.
- Reason: one specific sentence (`"Checking in on repo 4 WP06 impl after
  dispatch + 2 parallel reviews; expect for_review or approved state"`).
- Prompt: pass the same `/loop ...` instruction verbatim each turn so
  the wakeup re-enters this skill and continues the loop.

On each heartbeat fire:

1. Run `TaskList` to find running agents.
2. For each running agent, peek output (via `TaskOutput` non-blocking).
3. For each repo, run `spec-kitty agent tasks status --mission <slug>`
   and check for stuck WPs (in_review >15min with no active reviewer,
   for_review with no reviewer dispatched).
4. If everything is green and still-working, report "all green" with the
   specific signal you saw (N tool calls in last 5min from each agent),
   then re-arm the wakeup.
5. If anything is stuck, dispatch a repair or chase agent.

Stop the pulse only when the entire program is closed (all repos merged,
all mission reviews cleared, all remediations landed).

---

## Step 5: Handle the Recurring Friction Points

These friction points are known and tracked upstream. Expect them; have
the workaround ready in your dispatch prompts.

| Friction | When it hits | Workaround | Upstream |
|---|---|---|---|
| Test-DB collisions across parallel lanes | Django-backed projects with ≥2 concurrent lane runs | `DJANGO_TEST_DATABASE_NAME=test_<proj>_lane_<letter> <project-test-command> --create-db` | #770 |
| Stale lane on consolidate | Missions where multiple WPs touched `pyproject.toml` / `urls.py` / shared `__init__.py` | Consolidate auto-rebases; when it stops, run the command consolidate prints, resolve, re-run consolidate | — |
| Post-merge invariant check on `.worktrees/` | Every successful merge | `mv .worktrees /tmp/park && move-task WP## --to done && mv back` | #772 |
| Silent repo fallback when target isn't initialized | Phase 1 on a repo without `.kittify/` scaffold | Detect via `ls <target>/kitty-specs/` after the status commit phase; if empty and another repo got the artifacts, relocate + `spec-kitty init --ai <agent>` in the real target | #773 |
| `spec-kitty decision` not found | Sub-agents referencing the `decision` command group | Use `spec-kitty agent decision ...` | #774 |
| `review-request` is not a real command | Sub-agents trying to submit a WP for review | Use `spec-kitty agent tasks move-task WP## --to for_review` | #775 |

---

## Step 6: Memory and Feedback Capture

At the start and throughout the program, persist specific feedback to the
memory system:

- **Autonomy scope**: the exact phrasing the user used to authorize
  autonomous operation on which repos.
- **Architectural decisions locked in by earlier repos**: these become
  constraints for later repos. Save as project memories so later repo
  phases can load them without re-asking.
- **Recurring user preferences**: the user's cadence preference ("never
  wait more than 5 min"), their preferred sub-agent model, their
  tolerance for parallelism.

At the end of the program:

- Capture the debrief patterns the user surfaces — which frictions cost
  the most time, which parts of the mission workflow they valued, what they
  would change. These inform future programs.

---

## Step 7: Final Report

At the end of the program, produce a concise shipping summary:

```
Decision Moment V1 — Program Complete

| # | Repo | Issue | Merge | Mission review | Post-merge fixes |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... |

Architecture locks in place:
- <repo A> owns <canonical responsibility>
- <repo B> owns <...>
- ...

Known follow-ups (non-blocking):
- <issue #NNN> — <description>
```

If the user asks for a debrief, be honest about what worked and what
didn't. The retrospective is worth more than the shipping report for
future programs.

---

## Key Rules

1. **Sequence the repos, don't serialize the work.** Many phases can
   run in parallel across repos; the serial constraint is on the
   dependency graph, not on your calendar.

2. **Pulse heartbeat or it didn't happen.** If you run uninterrupted
   without a ScheduleWakeup armed, you will eventually silently stall.

3. **Mission review catches real bugs.** Never skip it. Budget for
   remediation.

4. **Dispatch with context, not just a task ID.** Every sub-agent
   prompt should include the cross-repo contract references, the
   locked architectural rules from earlier repos, and the known
   friction workarounds (test-DB name, stale-lane pattern). Do not
   make them re-derive what you already know.

5. **When you discover a friction point not in Step 5 above**, file it
   as a GitHub issue against the tracker and add it to this skill in
   a follow-up PR. The program is also an opportunity to make the
   tool better.

6. **Be honest in the debrief.** The user is tracking whether the
   program landed AND whether it was worth running it this way. Give
   them real signal, not a success-narrative.
