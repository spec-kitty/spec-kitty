---
name: spec-kitty-orchestrator-api-operator
description: >-
  Teach agents and external systems how to use spec-kitty orchestrator-api to
  drive workflows from outside the host CLI.
  Triggers: "use orchestrator-api", "build a custom orchestrator",
  "automate externally", "integrate CI with spec-kitty",
  "call spec-kitty from another tool", "orchestrator contract",
  "external automation".
  Does NOT handle: host-internal lane mutation (use the host CLI directly),
  runtime loop advancement (use spec-kitty next), mission sequencing logic
  (the mission state machine owns that), or setup/repair diagnostics.
---

# spec-kitty-orchestrator-api-operator

Teach agents and external systems how to use `spec-kitty orchestrator-api` to
drive workflows from outside the host CLI. The orchestrator-api is the only
supported entry point for external automation -- direct frontmatter mutation,
git worktree manipulation, or internal CLI internals are not part of the
contract.

---

## When to Use This Skill

- Build an external orchestrator that drives spec-kitty workflows
- Integrate CI/CD pipelines with spec-kitty state transitions
- Query mission and work package state from an external tool
- Understand the boundary between host CLI and external API

Do NOT use when the caller is an agent inside the host CLI (use
`spec-kitty next`), wants setup/repair (use setup-doctor), or wants
mission sequencing (the state machine owns that).

---

## How the Orchestrator API Works

The orchestrator-api is a **stable JSON contract** — every command returns a
canonical JSON envelope. External systems parse `success` first, then
`error_code` for programmatic handling, then `data` for command-specific
results. No command returns prose or mixed text/JSON.

### JSON Envelope (All Commands)

```json
{
  "contract_version": "1.0.0",
  "command": "orchestrator-api.<subcommand>",
  "timestamp": "2026-03-22T10:00:00+00:00",
  "correlation_id": "corr-<uuid>",
  "success": true,
  "error_code": null,
  "data": { ... }
}
```

- `success=true` → `error_code` is always `null`
- `success=false` → `error_code` is a machine-readable string, exit code is 1
- `correlation_id` is unique per invocation — use for audit trails and log
  correlation

### The 9 Commands

| Command | Purpose | Mutates State |
|---|---|:---:|
| `contract-version` | Verify API compatibility | No |
| `mission-state` | Query full mission state | No |
| `list-ready` | List WPs ready to start | No |
| `start-implementation` | Claim + begin WP (atomic) | Yes |
| `start-review` | Claim a WP for review (for_review -> in_review) | Yes |
| `transition` | Explicit single lane change | Yes |
| `append-history` | Add note to WP activity log | Yes |
| `accept-mission` | Mark mission as accepted without closing approved WPs | Yes |
| `consolidate-mission` | Merge lane branches into the mission branch, then land the mission branch | Yes |

### Policy Metadata (Required for Run-Affecting Lanes)

Transitions to `claimed`, `in_progress`, `for_review`, or `in_review` require `--policy`
with a JSON object containing **7 required fields**:

```json
{
  "orchestrator_id": "my-ci-bot",
  "orchestrator_version": "1.0.0",
  "agent_family": "claude",
  "approval_mode": "manual",
  "sandbox_mode": "container",
  "network_mode": "restricted",
  "dangerous_flags": []
}
```

| Field | Purpose |
|---|---|
| `orchestrator_id` | Who is driving the workflow |
| `orchestrator_version` | Version of the orchestrator |
| `agent_family` | Agent type (claude, codex, gemini, cursor, etc.) |
| `approval_mode` | manual, auto, or supervised |
| `sandbox_mode` | container, none, vm, etc. |
| `network_mode` | restricted, full, none |
| `dangerous_flags` | Array of dangerous flags enabled (can be `[]`) |

Optional: `tool_restrictions` (string or null).

Policy is recorded in the append-only event log for every run-affecting
transition, enabling post-incident review of exactly what orchestrator drove
each state change.

**Validation:** Fields cannot contain secret-like values (pattern:
`token|secret|key|password|credential`). Invalid JSON or missing fields
returns `POLICY_VALIDATION_FAILED`.

### Error Codes

| Code | Cause |
|---|---|
| `CONTRACT_VERSION_MISMATCH` | Provider version below minimum |
| `MISSION_NOT_FOUND` | Mission slug doesn't resolve |
| `WP_NOT_FOUND` | WP ID doesn't exist in mission |
| `TRANSITION_REJECTED` | Invalid transition or guard failure |
| `WP_ALREADY_CLAIMED` | Another actor owns the WP |
| `POLICY_METADATA_REQUIRED` | Policy missing on run-affecting lane |
| `POLICY_VALIDATION_FAILED` | Policy JSON invalid or contains secrets |
| `USAGE_ERROR` | CLI usage or missing required arguments |
| `DEPENDENCIES_NOT_SATISFIED` | WP dependencies do not permit the requested transition |
| `MISSION_NOT_READY` | Not all WPs approved or done |
| `PREFLIGHT_FAILED` | Worktree dirty, target diverged, or missing WPs |
| `UNSUPPORTED_STRATEGY` | Merge strategy not in {merge, squash, rebase} |

---

## Step 1: Verify the API Contract

```bash
spec-kitty orchestrator-api contract-version --provider-version "1.0.0"
```

Check that `api_version` matches your orchestrator's expected version and
`min_supported_provider_version` is at or below your version. A
`CONTRACT_VERSION_MISMATCH` error means the orchestrator must be updated.

**Rule:** Always call `contract-version` at orchestrator startup.

---

## Step 2: Query Mission State

```bash
spec-kitty orchestrator-api mission-state --mission <slug>
```

Returns summary counts and per-WP details:

```json
{
  "mission_slug": "042-test-mission",
  "summary": {
    "planned": 2, "claimed": 0, "in_progress": 1,
    "for_review": 1, "approved": 0, "done": 3,
    "blocked": 0, "canceled": 0
  },
  "work_packages": [
    {"wp_id": "WP01", "lane": "done", "dependencies": [], "last_actor": "claude"},
    {"wp_id": "WP02", "lane": "in_progress", "dependencies": ["WP01"], "last_actor": "codex"}
  ]
}
```

```bash
spec-kitty orchestrator-api list-ready --mission <slug>
```

Returns only WPs whose dependencies are satisfied (in `planned` lane with all
deps in `done`). The host runtime computes the lane workspace; orchestrators do
not choose a base branch manually.

```json
{
  "mission_slug": "042-test-mission",
  "ready_work_packages": [
    {"wp_id": "WP03", "lane": "planned", "dependencies_satisfied": true}
  ]
}
```

Both commands are query-only and safe to poll.

---

## Step 3: Respect the Host Boundary

The orchestrator-api is the ONLY supported interface for external systems.

**Anti-patterns (do NOT do):**

- Edit frontmatter directly (`lane: in_progress` in WP files)
- Call internal CLI commands (`spec-kitty agent tasks move-task`)
- Create worktrees manually (`git worktree add`)
- Poll by reading files (`grep "lane:" kitty-specs/...`)
- Skip `contract-version` check
- Skip `--policy` on run-affecting transitions

See `references/host-boundary-rules.md` for the full boundary specification.

---

## Step 4: Start Implementation with Policy

```bash
spec-kitty orchestrator-api start-implementation \
  --mission <slug> --wp WP01 --actor "ci-bot" \
  --policy '{"orchestrator_id":"my-orch","orchestrator_version":"1.0.0","agent_family":"claude","approval_mode":"auto","sandbox_mode":"container","network_mode":"restricted","dangerous_flags":[]}'
```

This transitions `planned → claimed → in_progress` **atomically** (two events
in one call). The response includes:

- `workspace_path` — The computed worktree path. **The caller must create the
  worktree** — `start-implementation` does not create it.
- `prompt_path` — Path to the WP task file to present to the agent.
- `no_op` — `true` if the WP is already `in_progress` by the same actor
  (idempotent, no new events emitted).

**Idempotency behavior:**

| Current state | Same actor | Different actor |
|---|---|---|
| `planned` | Transitions to `in_progress` | Transitions to `in_progress` |
| `claimed` by this actor | Transitions to `in_progress` | `WP_ALREADY_CLAIMED` error |
| `in_progress` by this actor | `no_op=true`, success | `WP_ALREADY_CLAIMED` error |
| Other lane | `TRANSITION_REJECTED` | `TRANSITION_REJECTED` |

---

## Step 5: Transition Work Packages

```bash
spec-kitty orchestrator-api transition \
  --mission <slug> --wp WP01 --to for_review --actor "ci-bot" \
  --policy '{"orchestrator_id":"my-orch",...}'
```

**Valid target lanes:** `planned`, `claimed`, `in_progress`, `for_review`,
`in_review`,
`approved`, `done`, `blocked`, `canceled`.

**Rules:**

- Run-affecting lanes (`claimed`, `in_progress`, `for_review`, `in_review`) require `--policy`
- Use `--force` only when recovering from a known-bad state
- Use `--note` to record transition reasoning in the audit trail
- Use `--review-ref` when transitioning from `for_review` or `approved` back
  to `in_progress` or `planned` (required guard for these rollback transitions)

---

## Step 6: Start Review

For reviewer claim/start (not an implementation rollback):

```bash
spec-kitty orchestrator-api start-review \
  --mission <slug> --wp WP01 --actor "reviewer-bot" \
  --policy '{"orchestrator_id":"my-orch",...}'
```

This moves the WP from `for_review` to `in_review`. `--review-ref` is optional;
use it when there is an external review artifact to record.

---

## Step 7: Record History and Complete

```bash
# Append a history note
spec-kitty orchestrator-api append-history \
  --mission <slug> --wp WP01 --actor "ci-bot" --note "Tests passed"

# Accept mission (validates all WPs are approved or done via dependency graph)
spec-kitty orchestrator-api accept-mission --mission <slug> --actor "ci-bot"

# Merge mission
spec-kitty orchestrator-api consolidate-mission \
  --mission <slug> --target main --strategy squash --push
```

`accept-mission` returns `MISSION_NOT_READY` if any WP from the dependency
graph is not `approved` or `done`.

Once every WP is `approved`/`done`, `accept-mission` (contract >= 1.7.0) ALSO
applies the host readiness verdict — the same `collect_feature_summary(...,
strict_metadata=True)` check the `accept` CLI runs (a pending/failing
acceptance matrix, a missing/corrupt `lanes.json`, a dirty working tree,
etc.). A failing verdict refuses with `MISSION_NOT_READY` again, this time
carrying `outstanding` / `activity_issues` / `skipped_checks` /
`blocked_checks`, and records no acceptance (`meta.json` gains no
`accepted_at`, HEAD unchanged; the gate may still update judged matrix rows in
the working tree).
Acceptance is only ever recorded inside the same locked pre-stamp re-check
the host CLI uses, so a verdict committed between the check and the write is
still refused.

`accept-mission` reports `accepted_wps`, `approved_wps`, `done_wps`, and
`merge_pending_wps`. It does not move WPs from `approved` to `done`; merge owns
that transition.

`consolidate-mission` runs **4 preflight checks** before merging:
1. All expected WPs have worktrees
2. All worktrees are clean (no uncommitted changes)
3. Target branch is not behind origin
4. Missing WPs in done lane are handled (skipped with warnings)

On preflight failure, returns `PREFLIGHT_FAILED` with detailed error list.

Supports 3 merge strategies: `merge` (--no-ff), `squash` (default), `rebase`.
Use `--push` to push the target branch after merge.

---

## What This Skill Does NOT Cover

- **Mission sequencing** -- use `spec-kitty next` (the state machine owns that)
- **Host-internal mutations** -- agents inside the host CLI use
  `spec-kitty agent tasks move-task`, not orchestrator-api
- **Setup and repair** -- use the setup-doctor skill

---

## References

- `references/orchestrator-api-contract.md` -- Full command reference with all 9 commands, flags, output fields, and error codes
- `references/host-boundary-rules.md` -- When to use orchestrator-api vs host CLI, anti-patterns, boundary rules
