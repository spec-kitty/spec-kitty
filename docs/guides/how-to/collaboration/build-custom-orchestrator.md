---
title: Build a Custom Orchestrator
description: Implement your own external orchestration runtime against spec-kitty orchestrator-api.
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/architect-evaluator.md
related:
- docs/guides/how-to/collaboration/run-external-orchestrator.md
---
# Build a Custom Orchestrator

Use this guide to implement your own orchestration strategy while keeping `spec-kitty` as the workflow host.

## Contract Rules

Your orchestrator must:

- Call only `spec-kitty orchestrator-api ...` subcommands for workflow state (output is always JSON).
- Treat `spec-kitty` as source of truth for lane state and dependencies.
- Never write `kitty-specs/<feature>/tasks/*.md` lanes directly.

## Required Flow

1. Check API compatibility.
2. Poll for ready WPs.
3. Start implementation for selected WPs.
4. Transition WPs through implementation, review, approval, and rework loops.
5. Accept when all WPs are terminal/accepted, then merge through your normal landing process.

### 1. Check compatibility

```bash
spec-kitty orchestrator-api contract-version
```

### 2. Discover work

```bash
spec-kitty orchestrator-api mission-state --mission <slug>
spec-kitty orchestrator-api list-ready --mission <slug>
```

### 3. Start implementation

```bash
spec-kitty orchestrator-api start-implementation \
  --mission <slug> \
  --wp WP01 \
  --actor my-orchestrator \
  --policy '<json>' \
```

Use returned `workspace_path` and `prompt_path` to run your agent process.

### 4. Drive transitions

```bash
# implementation complete
spec-kitty orchestrator-api transition \
  --mission <slug> --wp WP01 --to for_review \
  --actor my-orchestrator --policy '<json>' \
  --subtasks-complete --implementation-evidence-present
# reviewer claims active review
spec-kitty orchestrator-api start-review \
  --mission <slug> --wp WP01 --actor my-orchestrator \
  --policy '<json>' --review-ref review/WP01/attempt-1

# review approved
spec-kitty orchestrator-api transition \
  --mission <slug> --wp WP01 --to done \
  --actor my-orchestrator \
  --policy '<json>' \
  --review-ref review/WP01/attempt-1 \
  --review-result-json '{"reviewer":"reviewer-bot","verdict":"approved","reference":"review/WP01/attempt-1"}' \
  --evidence-json '{"review":{"reviewer":"reviewer-bot","verdict":"approved","reference":"review/WP01/attempt-1"}}' \
  --note "Approved by reviewer-bot"

# review rejected -> rework
spec-kitty orchestrator-api transition \
  --mission <slug> --wp WP01 --to in_progress \
  --actor my-orchestrator \
  --policy '<json>' \
  --review-ref review/WP01/attempt-1 \
  --review-result-json '{"reviewer":"reviewer-bot","verdict":"changes_requested","reference":"review/WP01/attempt-1"}' \
  --note "Rejected by reviewer-bot; rework required"
```

### 5. Finalize

```bash
spec-kitty orchestrator-api accept-mission --mission <slug> --actor my-orchestrator
spec-kitty orchestrator-api merge-mission --mission <slug> --target main --strategy merge
```

## Policy JSON Template

Run-affecting operations require `--policy` with these keys:

```json
{
  "orchestrator_id": "my-orchestrator",
  "orchestrator_version": "0.1.0",
  "agent_family": "claude",
  "approval_mode": "supervised",
  "sandbox_mode": "workspace_write",
  "network_mode": "none",
  "dangerous_flags": []
}
```

## Lane and Error Semantics

- Use API lane `in_progress`; host maps it to internal `doing`.
- Expect deterministic `error_code` on failures.
- Build retry/backoff logic based on `error_code`, not message text.

Common retry-relevant failures:

- `WP_ALREADY_CLAIMED`
- `TRANSITION_REJECTED`
- `POLICY_VALIDATION_FAILED`

## Minimal Loop Skeleton

```text
while true:
  ready = list-ready(feature)
  if no ready and all accepted-ready: break
  for wp in ready up to concurrency limit:
    start-implementation(wp)
    run implementation agent
    transition(wp, for_review)
    run reviewer
    start-review(wp, review_ref)
    if approved: transition(wp, done, review_result, done_evidence)
    else: transition(wp, in_progress, review_result)
accept-mission(mission)
merge-mission(mission)
```

## Reference Implementation

Use [`spec-kitty-orchestrator`](https://github.com/spec-kitty/spec-kitty-orchestrator) as a concrete provider example.

## See Also

- [Run the External Orchestrator](run-external-orchestrator.md)
- [Orchestrator API Reference](../../../api/orchestrator-api.md)
