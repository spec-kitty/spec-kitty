---
title: Cross-Repo Evidence-Based Completion
description: Required structured commit evidence before completion, closing the split-brain gap where the planning repository and the implementation repository disagreed.
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-02-09'
---

> Superseded by `2026-04-03-2-review-approval-and-integration-completion-are-distinct.md`.
> This ADR attached review approval evidence directly to `done`. The current
> lifecycle splits review evidence (`for_review -> approved`) from integration
> and acceptance evidence (`approved -> done`).

## Context and Problem Statement

Spec Kitty's planning repository and implementation target repositories are separate git repositories. A WP can be marked "done" in the planning repo while the target repo has no corresponding commits — or implementation may be complete in the target repo while the planning repo still shows `in_progress`. This "split-brain" failure mode exists because there is no automatic linkage between planning status and target-repo commits.

The current system allows marking a WP as "done" with no structured proof of what was actually implemented, tested, or reviewed. This makes `done` a trust-based assertion rather than a verifiable fact.

## Decision Drivers

* **Verifiable "done"** — Completion must include structured proof, not just assertion
* **Cross-repo drift detection** — Planning and implementation repos must be reconcilable
* **Dual execution mode support** — Both worktree-based and direct-repo workflows need evidence paths
* **Offline-first reconciliation** — Must work via git-native `status reconcile`, not a centralized service
* **Reviewer authority** — Evidence must satisfy guard conditions from ADR 2026-02-09-2

## Considered Options

* **Option 1:** Trust-based completion (mark done without evidence)
* **Option 2:** Automated verification only (CI gates, no human review evidence)
* **Option 3:** Structured evidence payloads with explicit reconciliation
* **Option 4:** Centralized service-based reconciliation

## Decision Outcome

**Chosen option:** "Option 3: Structured evidence payloads with explicit reconciliation", because it makes "done" verifiable, supports both execution modes, preserves offline capability, and integrates with the state machine's guard conditions.

### Implementation

**Evidence payload for `done` transitions:**

Every event transitioning a WP to `done` must include a structured `evidence` field:

```json
{
  "repos": [
    {
      "repo": "spec-kitty-saas",
      "branch": "feature/WP05-webhook-handler",
      "commit": "abc123f",
      "files_touched": ["apps/connectors/views.py"]
    }
  ],
  "verification": [
    {
      "command": "pytest apps/connectors/tests/",
      "result": "passed",
      "summary": "12 tests passed, 0 failed"
    }
  ],
  "review": {
    "reviewer": "architecture-team-review",
    "verdict": "approved",
    "reference": "WP05 review feedback"
  }
}
```

**Execution modes:** Feature metadata includes `execution_mode`:
1. `worktree` (default) — evidence gathered from worktree branch
2. `direct_repo` — evidence explicitly gathered via reconciliation

**Reconciliation command (`status reconcile`):**
1. **Scan**: Examine target repos for WP-linked commits and evidence
2. **Detect**: Identify drift between planning status and implementation reality
3. **Emit**: Generate reconciliation events (dry-run shows proposed; apply appends to canonical log)
4. **Never implicit**: Reconciliation never silently mutates state

**Guard integration:** Evidence satisfies ADR 2026-02-09-2 guards:
* Guard 3 (`in_progress → for_review`): Satisfied by `evidence.repos` and `evidence.verification`
* Guard 4 (`for_review → done`): Satisfied by `evidence.review`

### Consequences

#### Positive

* "Done" is verifiable — every completion includes structured proof
* Cross-repo drift is detectable via `status reconcile`
* Dual execution modes have first-class evidence paths
* Reconciliation is explicit — events always written to canonical log, no silent mutation
* Audit trail complete — evidence captures the full chain: code → tests → review → approval

#### Negative

* Evidence gathering adds friction to WP completion
* Reconciliation tooling (`status reconcile` with scan, detect, dry-run, apply) must be built
* Dry-run adds a manual review step before applying
* Evidence schema may need evolution for different WP types (code, research, documentation)

#### Neutral

* Auto-collection from git: `status emit` can auto-populate `repos[]` from branch commit log
* Evidence stored as JSON, so schema evolution is non-breaking
* `status doctor` provides automated detection of stale completions and unresolved drift

### Confirmation

* CI check: `done` events without evidence payload are flagged
* `status reconcile --dry-run` shows proposed events before applying
* `status doctor` detects orphaned workspaces and stale completions

## Pros and Cons of the Options

### Trust-based completion (mark done without evidence)

Allow WPs to be marked "done" based on the implementer's assertion.

**Pros:**

* Zero friction — fastest path to completion
* No tooling required
* Works for any execution mode without special handling

**Cons:**

* "Done" is a meaningless assertion — no way to verify what was implemented
* Enables split-brain between planning and target repos
* No audit trail for what was tested or reviewed
* Scales poorly to multi-agent work — cannot verify AI agent completions

### Automated verification only (CI gates, no human review)

Require CI pipeline results as evidence, but don't capture human review context.

**Pros:**

* Fully automated — no manual evidence gathering
* Objective — test results are binary (pass/fail)
* Integrates with existing CI infrastructure

**Cons:**

* Cannot capture human review context (architecture review, UX evaluation)
* State machine guard condition 4 requires reviewer identity — missing without review evidence
* Not all WPs have automated tests (documentation, research, planning WPs)
* Misses the "who approved and why" audit trail

### Centralized service-based reconciliation

Use the SaaS platform to continuously monitor target repos and auto-reconcile.

**Pros:**

* Real-time drift detection — no manual triggering
* Dashboard visibility
* Can integrate with GitHub/GitLab webhooks

**Cons:**

* Requires online centralized service — violates non-goal: "Not replacing git with an online control plane"
* Breaks offline workflow
* Single point of failure
* Canonical authority question: does the service or git own the truth?

## More Information

**Related ADRs:**
* ADR 2026-02-09-1 (Canonical WP Status Model) — evidence events appended to the same JSONL log
* ADR 2026-02-09-2 (WP Lifecycle State Machine) — evidence satisfies guard conditions
* ADR 2026-02-09-3 (Event-Log Merge Semantics) — reconciliation events participate in merge

**References:**
* The Twelve-Factor App: Admin Processes — https://12factor.net/admin-processes
* PRD: Feature Status State Model Remediation (Sections 2, 4, 8, 10, 11)
