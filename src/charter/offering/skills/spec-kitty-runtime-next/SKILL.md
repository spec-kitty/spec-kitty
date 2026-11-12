---
name: spec-kitty-runtime-next
description: >-
  Drive the canonical spec-kitty next --mission <handle> control loop for mission
  advancement. Load agent profiles at init, apply action-scoped doctrine
  context at each step boundary, and pull specific tactics/directives on demand.
  Triggers: "run the next step", "what should runtime do next", "advance the
  mission", "what is the next task", "continue the workflow", "what step comes
  next".
  Does NOT handle: setup or repair requests, purely editorial glossary or
  doctrine maintenance, or direct code review.
---

# spec-kitty-runtime-next

This skill teaches agents how to advance a Spec Kitty mission through the
canonical runtime control loop, including doctrine-aware context loading at
each step boundary.

## When to Use This Skill

Use this skill when the user wants to:

- Advance a mission to its next step
- Understand what the runtime will do next
- Unblock a stalled mission
- Interpret runtime outcomes (step, blocked, decision_required, terminal)

---

## How the Runtime-Next System Works

The `spec-kitty next` command is the single entry point for agent-driven mission
execution. Each call returns a deterministic decision about what action the
agent should take next.

### Decision Algorithm

The runtime evaluates state in this order:

1. **Mission state machine** — Current phase and available transitions (from
   `mission-runtime.yaml` DAG)
2. **WP iteration check** — For `implement` and `review` steps, the CLI bridge
   manages WP-level iteration WITHOUT advancing the runtime. The runtime only
   advances when ALL WPs reach terminal/handoff lanes.
3. **Guard conditions** — Required artifacts, prerequisites, dependency graph
4. **Priority ordering** — Reviews before implementations, higher-priority WPs
   first, dependency-free WPs before dependent ones

### WP Iteration Logic (Critical)

The CLI bridge (not the runtime) manages WP-level iteration:

- If current step is `implement` or `review`
- AND there are WPs in `planned` or `in_progress` lanes
- THEN return a WP-level decision **without advancing the runtime step**
- The runtime step only advances when ALL WPs are in terminal/handoff lanes
  (`done`, `approved`, or `for_review`)

This means multiple calls to `spec-kitty next` during implementation will
return different WP IDs but the same `step_id` (e.g., "implement") until all
WPs are done.

### Mission Runtime YAML Schema

Missions define steps as a DAG (directed acyclic graph) with dependencies:

```yaml
mission:
  key: software-dev
  name: Software Dev Kitty
  version: "2.1.0"

steps:
  - id: discovery
    title: Discovery & Research
    depends_on: []
    prompt_template: research.md

  - id: specify
    depends_on: [discovery]
    prompt_template: specify.md

  - id: plan
    depends_on: [specify]
    prompt_template: plan.md

  - id: tasks
    depends_on: [plan]

  - id: implement
    depends_on: [tasks]
    prompt_template: implement.md

  - id: review
    depends_on: [implement]
    prompt_template: review.md

  - id: accept
    depends_on: [review]
    prompt_template: accept.md
```

### Decision Kinds

Every call to `spec-kitty next` returns exactly one decision kind:

| Kind | Meaning | Agent Action |
|---|---|---|
| `step` | Normal action available | Read `prompt_file` and execute |
| `query` | Read-only current-state preview | Inspect state; run `next_command` when it is set; do not execute a prompt or mark a result |
| `decision_required` | Runtime needs input | Answer with `--answer` and `--decision-id` |
| `blocked` | Guards failing, cannot proceed | Read `reason` + `guard_failures`; when `next_command` is set, run it (for example `MISSION_AWAITING_ACCEPTANCE` names `spec-kitty accept`) |
| `terminal` | No more steps. Software-dev Mission with a finalized board and a run that is not authoritative: accepted or landed. Any other Mission: the run completed, with no acceptance check | If not accepted, run `spec-kitty accept --mission <handle>`; if not landed, run `spec-kitty consolidate --mission <handle>` (a query's `next_command` names which); then: mission review → author or verify retrospective (`retrospect create`) → surface findings (`summary` aggregates; `synthesize` reviews proposals) |

### Decision Output Fields

```json
{
  "kind": "step",
  "agent": "claude",
  "mission_slug": "042-test-mission",
  "mission": "software-dev",
  "mission_state": "implementing",
  "action": "implement",
  "wp_id": "WP02",
  "workspace_path": ".worktrees/042-test-mission-lane-b",
  "prompt_file": "/tmp/spec-kitty-next-claude-042-test-mission-implement-WP02.md",
  "reason": null,
  "guard_failures": [],
  "progress": {
    "total_wps": 5,
    "done_wps": 1,
    "approved_wps": 0,
    "in_progress_wps": 1,
    "planned_wps": 3,
    "for_review_wps": 0
  },
  "run_id": "abc123",
  "step_id": "implement",
  "decision_id": null,
  "question": null,
  "options": null
}
```

**Additive fields and codes (next-lifecycle-integrity).** These appear only when set, so
other envelopes are unchanged:

| Field or code | Where | Meaning |
|---|---|---|
| `next_command` | every `query` envelope, except a pending decision on a started run and a landed Mission | The command to run next: the advance command (`spec-kitty next --agent <agent> --mission <handle> --result success`), `spec-kitty accept --mission <handle>`, or `spec-kitty consolidate --mission <handle>` |
| `next_command` | `blocked` with one of the three codes below | The command that unblocks the Mission |
| `error_code: MISSION_AWAITING_ACCEPTANCE` | advancing `next`, software-dev Mission with a finalized board and a run that is not authoritative | Every WP is approved, done or canceled, and the Mission is not accepted, or was accepted before the board's latest WP transition. Run `next_command` (`accept`) |
| `error_code: BOARD_STEP_NOT_DISPATCHABLE` | advancing `next`, software-dev Mission with a finalized board and a run that is not authoritative | The finalized board's step cannot be dispatched (for example a WP claimed or in progress). The reason names the WP; `next_command` resumes it (`spec-kitty agent action <implement\|review> <WP> --agent <agent> --mission <handle>`), or is `spec-kitty agent tasks status --mission <handle>` when no WP can be named |
| `error_code: LANES_MANIFEST_MISSING` | advancing `next`, software-dev Mission with a finalized board and a run that is not authoritative | The board's WP step needs `lanes.json`, which is missing. `reason` is the error's own message. `next_command` is `spec-kitty agent mission finalize-tasks --mission <handle>` while every WP is `planned`, else `spec-kitty doctor mission-state --fix --mission <handle>` |

A query without `--agent` puts the literal `<agent>` placeholder in the advance command;
substitute your agent name. `question` is set exactly when `decision_id` is set, and then
`options` or `input_key` is set too.

### 6 Guard Primitives

Guards block step transitions by returning failure descriptions:

| Guard | Syntax | Checks |
|---|---|---|
| `artifact_exists` | `artifact_exists("spec.md")` | File exists relative to mission dir |
| `gate_passed` | `gate_passed("review_gate")` | Gate event in mission-events.jsonl |
| `all_wp_status` | `all_wp_status("approved_or_done")` | All WPs in a specific lane or named accepted-ready set |
| `any_wp_status` | `any_wp_status("for_review")` | At least one WP in lane |
| `input_provided` | `input_provided("architecture")` | Input exists in runtime model |
| `event_count` | `event_count("review", 1)` | Minimum event count threshold |

Guards never raise exceptions — they return `false` on missing context.

### Prompt File Generation

The runtime generates a temp file at:
`/tmp/spec-kitty-next-{agent}-{mission_slug}-{action}[-{wp_id}].md`

**Template actions** (specify, plan, tasks): Mission context header + governance
context + action-specific template content.

**WP actions** (implement, review): Full isolation-aware prompt containing:
1. WP header with workspace path
2. Governance context (paradigms, directives, tools)
3. **WP Isolation Rules** — DO only modify this WP's status, DO NOT change
   other WPs or react to their status changes
4. Working directory and review commands
5. WP file content (from `tasks/WP##.md`)
6. Completion instructions

**Decision prompts**: Question text, options, and the `--answer` command to run.

### Run Persistence

Runtime state is persisted between calls:

```
.kittify/runtime/
├── feature-runs.json       # Index: {"mission-slug": {"run_id": "...", "run_dir": "..."}}
└── runs/
    └── <run_id>/
        └── state.json      # Runtime snapshot (current step, inputs, etc.)
```

### Mission Detection

When `--mission` is omitted, the runtime detects the mission via (in order):
1. `SPECIFY_MISSION` environment variable
2. Git branch name (mission and lane branches both encode the mission slug)
3. Current directory path (walks up looking for `###-mission-name`)
4. Single mission auto-detect (only if exactly one mission exists)
5. Error with guidance if ambiguous

**NOTE:** Always use `--mission <slug>` in multi-mission repositories.

---

## Doctrine-Aware Step Execution

The runtime-next loop should load doctrine context **iteratively** — not all
at once. Each step boundary is a context loading opportunity.

### Agent Profile at Init

At the start of a session, resolve the active agent profile. This scopes
your role, boundaries, and initialization context.

**Load the profile using the Python API — do NOT read YAML files directly:**

```python
from charter.activation.active_charter_service_builder import build_active_charter_service

service = build_active_charter_service(project_root)

# resolve_profile()'s specializes_from lineage traversal is a repository
# operation, not available on the filtered `agent_profiles` dict — reach it
# through the pinned lineage/mutation accessor:
repo = service.agent_profile_repository
profile = repo.resolve_profile("<profile-id>")  # e.g. "implementer"

# Internalize identity — acknowledge this at session start
print(profile.initialization_declaration)

# Respect scope boundaries
profile.specialization.primary_focus       # What you actively do
profile.specialization.avoidance_boundary  # What you must NOT do
profile.collaboration.handoff_to           # Roles to defer to when out of scope

# Load only the directives this profile references (same `service`, gated dict)
for ref in profile.directive_references:
    directive = service.directives.get(f"DIRECTIVE_{ref.code}")
```

**Discovery (if you don't know your profile-id):**

```bash
spec-kitty agent profile list
spec-kitty agent profile show <profile-id>
```

### Action-Scoped Context at Each Step

At each step boundary (when `spec-kitty next` returns a `step` decision),
load governance context scoped to the current action — not the full doctrine:

```bash
# Load only what's relevant to this action (compact after first load)
spec-kitty charter context --action implement --json
```

The context system uses two depth levels:

| Depth | When | Content |
|---|---|---|
| `bootstrap` (depth-2) | First load for this action | Full policy summary + reference list |
| `compact` (depth-1) | Subsequent loads | Resolved paradigms, directives, tools only |

First-load state is tracked per action in
`.kittify/charter/context-state.json`. This means `implement` and
`review` each get their own first-load bootstrap independently.

### Pull Specific Doctrine On Demand

When you need governance guidance mid-step (e.g., how to structure tests,
which review criteria apply), pull the specific tactic or directive by ID
rather than re-loading the full context:

```python
from charter.activation.active_charter_service_builder import build_active_charter_service

service = build_active_charter_service(project_root)

# Pull a specific tactic when it becomes relevant
tactic = service.tactics.get("tdd-red-green-refactor")

# Pull a specific directive
directive = service.directives.get("TEST_FIRST")
```

The action index (`actions/<action>/index.yaml`) tells you which doctrine
artifacts are relevant to the current step. Load the index to discover what
to pull:

```python
from charter.offering.missions.action_index import load_action_index

index = load_action_index(missions_root, "software-dev", "implement")
# index.directives → ["TEST_FIRST", ...]
# index.tactics → ["tdd-red-green-refactor", ...]
# index.procedures → [...]
```

### Anti-Pattern: Upfront Context Dump

Do NOT load all doctrine into context at session start. This wastes tokens
and dilutes relevance. Instead:

1. **At init**: Load agent profile + initialization declaration.
2. **At each step boundary**: Call `charter context --action <action>`.
3. **When stuck or need guidance**: Pull specific tactic/directive by ID.
4. **When reviewing**: Pull review-scoped doctrine, not implement-scoped.

---

## Step 1: Load Runtime Context

Before invoking the runtime, gather the current state.

**Commands:**

```bash
# Check WP status for a mission
spec-kitty agent tasks status --mission <mission-slug>

# Check current context for an action
spec-kitty agent context resolve --action implement --mission <mission-slug> --json
```

**What to look for:**

- Active mission slug and mission type
- Current WP lane status (planned, claimed, in_progress, for_review, in_review, approved, done, blocked, canceled)
- Whether there are WPs ready for implementation or review
- Any blocked WPs that need attention first

---

## Step 2: Run the Next Command

```bash
# Run the next step
spec-kitty next --agent <agent> --mission <mission-slug> --json

# After completing a step successfully
spec-kitty next --agent <agent> --mission <mission-slug> --result success --json

# After a step failed
spec-kitty next --agent <agent> --mission <mission-slug> --result failed --json

# After a step was blocked
spec-kitty next --agent <agent> --mission <mission-slug> --result blocked --json
```

> **Note:** `--mission` is the sole selector. The legacy `--feature` alias has
> been removed (#1060); passing `--feature` now exits with `No such option`.

The `--result` flag tells the runtime the outcome of the previous step.
If omitted, `spec-kitty next` returns current state without advancing (query mode).
It does not report success for the previous step.

---

## Step 3: Interpret the Result

See `references/runtime-result-taxonomy.md` for the complete taxonomy.

| Kind | Next Action |
|------|-------------|
| `step` | Read and execute `prompt_file` (always non-empty and resolvable on disk) |
| `query` | Read-only: run `next_command` when it is set |
| `decision_required` | Answer with `--answer` and `--decision-id` |
| `blocked` | Run `next_command` when it is set; otherwise read `reason` + `guard_failures` and resolve blockers |
| `terminal` | Accept if not accepted, then consolidate if not landed (a query's `next_command` names which), then mission review and retrospective |

**Always check `guard_failures`** — this field may appear on any decision kind,
not just `blocked`.

**The `kind="step"` prompt-file contract is a hard runtime invariant (C1/C2).**
A `kind="step"` envelope MUST carry a `prompt_file` (or its consumer-side
`prompt_path` alias) that is non-null, non-empty, and resolves on disk. If
the runtime cannot produce an actionable step (no composed action, guard
failure, blocked dependency, prompt build error, etc.), it returns
`kind="blocked"` with a non-empty `reason` (and optional machine-readable
code such as `no_prompt_template`). There is no third state: an agent loop
should never observe a `kind="step"` decision with `prompt_file == null`.

**A finalized software-dev board is never rewound when the run is not
authoritative.** This applies only to software-dev Missions with a finalized
board. Other Mission types are unchanged.
- **Authoritative runs keep the runtime path.** A run at `analyze`,
  `implement`, `review` or `accept` keeps it. For example, a run at `review`
  whose last WP is approved gets the runtime `accept` step.
- **The board's own answers**, for any `--result`, when the run is absent,
  untouched, or issued at `discovery`, `research`, `specify`, `plan` or `tasks`:
  - Every WP approved, done or canceled: `kind: blocked` with
    `MISSION_AWAITING_ACCEPTANCE` and a `next_command` naming `spec-kitty accept`.
    After an acceptance newer than the board's latest WP transition, the answer
    is `kind: terminal`; then consolidate. A reopened and re-approved WP needs a
    new acceptance.
  - A board step that cannot be dispatched (a WP claimed or in progress):
    `kind: blocked` with `BOARD_STEP_NOT_DISPATCHABLE` and a resume `next_command`
    (`spec-kitty agent action <implement|review> <WP> --agent <agent> --mission <handle>`;
    `spec-kitty agent tasks status --mission <handle>` when no WP can be named).
  - A board step whose WP needs a missing `lanes.json`: `kind: blocked` with
    `LANES_MANIFEST_MISSING`; `next_command` is `finalize-tasks` while every WP
    is `planned`, else `spec-kitty doctor mission-state --fix --mission <handle>`.
  - These answers start no run. An advancing `terminal` carries no `next_command`.
- **Board dispatch of a claimable WP** takes over only a run that is absent,
  untouched, or at `discovery`, `research`, `specify` or `plan`. A run at
  `tasks` advances through the runtime to `analyze`.

**Starting a Mission.** A fresh Mission's query previews the first step
(`mission_state: "not_started"`) and names the advance command. When that first
step needs input, the query shows its `decision_id` and `question`, but the
decision is not pending until the run starts: run the advance command first,
then answer the `decision_required` it returns.

---

## Step 4: Handle decision_required

When the runtime needs input:

```bash
# The decision includes question, options, and decision_id
# Answer using:
spec-kitty next --agent <agent> --mission <mission-slug> \
  --result success --answer "<choice>" --decision-id "<decision_id>" --json
```

If the agent cannot determine the answer, escalate to the user with the
question and options.

---

## Step 5: Handle Blocked States

See `references/blocked-state-recovery.md` for detailed recovery patterns.

**Quick diagnostic:**

```bash
# Check WP status and dependency graph
spec-kitty agent tasks status --mission <mission-slug>

# Check specific WP dependencies
spec-kitty agent tasks list-dependents WP## --mission <mission-slug>
```

**Common blockers:**

| Blocker | Recovery |
|---|---|
| Missing artifacts (spec.md, plan.md) | Run the planning workflow first |
| Upstream WP not done | Implement or review the upstream WP |
| Review feedback not addressed | Re-implement, address feedback, move to for_review |
| Stale agent (WP in doing, no activity) | Move WP to planned with `--force` |
| Circular dependencies | Break cycle in WP frontmatter, re-run finalize-tasks |

---

## Step 6: The Agent Loop

The complete agent loop pattern:

```bash
# 1. Start the loop
DECISION=$(spec-kitty next --agent claude --mission 042-mission --json)
KIND=$(echo "$DECISION" | jq -r '.kind')

# 2. Loop until terminal or unresolvable block
while [ "$KIND" = "step" ] || [ "$KIND" = "decision_required" ]; do

  if [ "$KIND" = "step" ]; then
    PROMPT=$(echo "$DECISION" | jq -r '.prompt_file')

    # Contract (C1/C2, post-#336 fix): kind=step always carries a
    # non-empty prompt_file resolvable on disk. If a prompt cannot be
    # resolved, the runtime emits kind=blocked with a populated reason.

    # Read and execute the prompt...
    RESULT="success"  # or "failed" or "blocked"
  elif [ "$KIND" = "decision_required" ]; then
    # Answer the question...
    RESULT="success"
  fi

  DECISION=$(spec-kitty next --agent claude --mission 042-mission --result "$RESULT" --json)
  KIND=$(echo "$DECISION" | jq -r '.kind')
done

# 3. A finished board blocks on acceptance: run the command it names, then ask again
if [ "$KIND" = "blocked" ] && [ "$(echo "$DECISION" | jq -r '.error_code')" = "MISSION_AWAITING_ACCEPTANCE" ]; then
  # next_command is "spec-kitty accept --mission 042-mission"; run it, then call next again
  # (it returns kind=terminal once the acceptance is newer than the board).
  :
fi

# 4. Handle terminal state — accept, consolidate, then the post-consolidation sequence
if [ "$KIND" = "terminal" ]; then
  # terminal does not always mean accepted: documentation/research/plan/custom Missions and
  # software-dev Missions without WPs reach it when the run completes, without acceptance.
  # A read-only query names the next command:
  #   spec-kitty next --mission 042-mission --json | jq -r '.next_command'
  # If not accepted: spec-kitty accept --mission 042-mission
  # If not landed:   spec-kitty consolidate --mission 042-mission
  # Then follow the canonical post-consolidation sequence:
  #   a. Mission review: /spec-kitty-mission-review
  #   b. Author or verify retrospective:
  #      spec-kitty retrospect create --mission 042-mission  # if record absent
  #      OR verify: cat .kittify/missions/<mission_id>/retrospective.yaml
  #   c. Surface findings:
  #      spec-kitty retrospect summary                                   # read-only aggregation
  #      spec-kitty agent retrospect synthesize --mission 042-mission  # dry-run by default; --apply to mutate
  # Note: summary aggregates; synthesize applies proposals — neither authors records.
fi
```

**The loop continues until:**

- `terminal` — mission complete, exit loop
- `query` — read-only preview, no state mutation
- `blocked` — cannot proceed without external resolution
- `decision_required` — only if the agent cannot answer (escalate to user)

---

## Important: Runtime Precedence Rules

1. **Always use `spec-kitty next`** rather than manually sequencing phases
2. **Always pass `--mission`** in multi-mission repositories
3. **Respect mission state machine transitions** — do not skip steps
4. **Read the `prompt_file`** — it contains the full context the agent needs
5. **Check `guard_failures`** on every decision, not just blocked ones
6. **Reviews before implementations** — the runtime prioritizes unblocking
   downstream work
7. **WP isolation** — only modify the WP you were assigned, ignore other WPs

---

## Known Issues

**#335 — fixed for software-dev Missions whose run is not authoritative.** A
software-dev Mission with a finished board and a run that is absent, untouched,
or issued at `discovery`, `research`, `specify`, `plan` or `tasks` is no longer
sent back to `discovery`. Instead, an advancing `next` returns `blocked` with
`MISSION_AWAITING_ACCEPTANCE` until the Mission is accepted, then `terminal`. A
run at `analyze`, `implement`, `review` or `accept` keeps the runtime path; for
example, the runtime issues its `accept` step. The
`progress.done_wps == progress.total_wps` workaround is no longer needed. Residuals: `MissionRunCompleted` and the retrospective
gate are not reached through `next` when the run is not authoritative, and a
run that an earlier release already replayed to `analyze` or beyond keeps the
runtime path.

**#336 — fixed.** `prompt_file` is always non-empty and resolvable on disk
on `kind: step` decisions. When no prompt is available, the runtime now emits
a structured `kind: blocked` decision with a non-empty `reason` (and optional
machine-readable code such as `no_prompt_template`). Agent loops no longer
need to defensively null-check `prompt_file`; a `kind: step` decision with a
null prompt is a runtime bug.

---

## Standalone Invocations (Outside Missions)

Not all governed work happens inside an active mission. When a user asks for
help with a task that has no active `spec-kitty next` loop — a code review, a
quick implementation, an ad-hoc analysis — you should still invoke Spec Kitty's
governance layer with standalone dispatch.

Spec Kitty never spawns a parallel LLM call. You are the host; Spec Kitty routes, assembles governance context, and records the trail.

### When to use standalone dispatch

If the user says anything like "use spec kitty to ...", "hey spec kitty ...",
or "spec kitty <anything>", run standalone dispatch unless they are clearly
asking for a full mission.

### The governance injection loop

1. **Get context**:
   ```bash
   spec-kitty dispatch "implement the login handler" --json
   spec-kitty dispatch "review WP05" --profile reviewer --json
   ```
   Response includes `invocation_id`, `governance_context_text`, and `governance_context_available`.

2. **Inject governance**:
   Read `governance_context_text` and treat it as binding governance context for your task. Follow any directives and constraints it contains.
   If `governance_context_available` is `false`, note this to the user but proceed with the task.

3. **Execute**:
   Do the work. Generate the code, analysis, or plan.

4. **Close the Op** (mandatory — `dispatch` leaves it open):
   ```bash
   spec-kitty profile-invocation complete \
     --invocation-id <invocation_id> \
     --outcome <done|failed|abandoned>
   ```
   Use the real outcome: `done` for completed work, `failed` for work that did
   not succeed, `abandoned` for dropped work. Never leave an Op open
   deliberately — `spec-kitty doctor ops` reports and sweeps orphans.

### Trail produced

Every standalone invocation writes a Tier 1 JSONL file to:
```
kitty-ops/<invocation_id>.jsonl
```

Viewable at any time with `spec-kitty invocations list --json`. No SaaS connection required.

For full CLI surface documentation, see `src/charter/offering/skills/spec-kitty/SKILL.md`.

---

## References

- `references/runtime-result-taxonomy.md` -- Decision kinds, output fields, and precedence rules
- `references/blocked-state-recovery.md` -- 6 blocked state patterns with diagnosis and recovery
