---
title: Feature Acceptance Runs on the Integrated Mission Branch
description: 'Mission acceptance and QA must run on the integrated mission branch, mapping every critical requirement to an automated test or a manual evidence item.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-03'
---

## Context and Problem Statement

WP review can prove that a branch diff is coherent. It cannot prove that the
integrated feature behaves correctly once multiple lanes are merged together.

Feature `028-saas-active-projects-shell` demonstrated the gap:

1. route cleanup was treated as evidence that the old mission page was gone,
2. the old fallback mission page still existed behind the new canonical route,
3. the integrated user journey was therefore broken even though WP review had
   passed.

This is not a planner or merge-topology problem alone. It is an acceptance
problem. Feature completion must be evaluated against the integrated mission
branch and against the actual user journey, including forbidden fallback paths.

## Decision Drivers

* **Product truth over branch folklore** — acceptance must validate what the
  user can actually do.
* **Integrated QA** — QA must run against the real integrated mission branch.
* **Negative invariant enforcement** — removed surfaces must be proven absent,
  not merely hidden from primary navigation.
* **Evidence discipline** — manual QA must leave durable proof, not just a
  checkbox.
* **Representative data** — acceptance must exercise realistic data paths, not
  only fixture-backed happy paths.

## Considered Options

* **Option 1:** Accept a feature by aggregating WP approvals
* **Option 2:** Allow QA and acceptance to run on any convenient branch
* **Option 3:** Require feature-level acceptance on the integrated mission branch with explicit evidence

## Decision Outcome

**Chosen option: Option 3**, because acceptance must judge the integrated
product, not isolated implementation slices.

### Core Decision

1. WP review may happen on a lane branch.
2. Feature QA and `accept` MUST happen on the mission integration branch.
3. A feature is not acceptable until its critical user journeys are validated on
   that integrated branch.

### Acceptance Contract

For each feature, acceptance MUST map every critical requirement to one of:

1. an automated test, or
2. a manual QA evidence item.

If neither exists for a requirement, acceptance is blocked.

### Negative Invariant Rule

When a spec says a legacy or unwanted surface is "gone", acceptance MUST verify
all relevant dimensions, not only one.

At minimum, the following must be checked where applicable:

1. no primary route remains,
2. no navigation entry remains,
3. no compatibility redirect lands on the removed surface itself,
4. no fallback code path or secondary entrypoint can still render the removed
   surface.

### Negative Invariant Verifier Model

Negative invariant evidence MUST distinguish absence from verifier failure.
`grep_absence` remains a cheap textual fallback, but only `grep` exit code 1
proves absence. Exit code 0 means the forbidden surface is still present. Exit
codes greater than 1 mean verifier failure and MUST produce a blocking
`verification_error`, not `confirmed_absent`.

Structured surfaces SHOULD use typed verifiers instead of grep:

1. command registry inspection for command absence,
2. route table inspection for route absence,
3. AST or import graph checks for code-level bans,
4. parsed config or manifest inspection for configuration invariants,
5. orchestrator/state APIs for workflow-state invariants.

Every verifier SHOULD declare the checked surface, absence semantics, evidence
shape, and blocking behavior. Its tests MUST prove both positive detection
(`still_present`) and negative absence (`confirmed_absent`), and SHOULD include
a verifier-failure case (`verification_error`) where the verifier depends on
parsing, external commands, or structured inputs.

### Manual QA Evidence Rule

Manual QA evidence MUST include, at minimum:

1. the exact URL or command exercised,
2. the scenario/data precondition,
3. the observed outcome,
4. a screenshot, DOM snapshot, or equivalent durable artifact.

### Representative Data Rule

For UI features, acceptance MUST cover representative cases that reflect real
product risk, not only ideal fixtures. At minimum:

1. the expected happy path,
2. a missing-data or degraded-data path,
3. one identity/uniqueness edge case if the feature depends on keyed lookups or
   routing,
4. real dev/staging data when such data exists and is materially different from
   fixtures.

## Consequences

### Positive

* Acceptance now evaluates the product the user actually sees.
* Hidden fallback paths become explicit acceptance targets.
* QA artifacts become durable evidence rather than unverifiable statements.
* Features like 028 can fail acceptance for the correct reason before merge.

### Negative

* Acceptance is more demanding and may take longer.
* Manual QA requires disciplined evidence capture.
* Some features will need better staging/dev datasets to be meaningfully tested.

### Neutral

* WP-level review remains valuable, but it is no longer treated as sufficient
  proof of integrated correctness.
* Compatibility redirects may still exist, but they must be validated against
  the negative invariant rule.

### Confirmation

This decision is validated when:

1. acceptance artifacts consistently reference the mission integration branch,
2. critical user journeys are provably exercised before a feature is merged,
3. removed legacy surfaces cannot survive through fallback code paths without
   failing acceptance,
4. QA evidence is attached for any requirement not covered by automation.

## Pros and Cons of the Options

### Option 1: Aggregate WP approvals

Treat the feature as done when all WPs are approved.

**Pros:**

* Simple accounting model.
* Minimal extra process after WP review.

**Cons:**

* Misses integrated failures and overlap regressions.
* Cannot prove that deleted surfaces are truly unreachable.
* Encourages "all boxes green" without validating the user journey.

### Option 2: Allow QA on any convenient branch

Run QA on whichever branch is easiest to access.

**Pros:**

* Flexible and cheap in the short term.
* Easy to parallelize.

**Cons:**

* Results are not authoritative for the final integrated product.
* Makes acceptance outcomes branch-dependent and non-reproducible.

### Option 3: Require integrated mission-branch acceptance

Run feature QA and acceptance only on the mission integration branch.

**Pros:**

* Acceptance measures the real assembled feature.
* Negative invariants become enforceable.
* QA evidence becomes reviewable and reproducible.

**Cons:**

* Requires stronger orchestration and evidence capture.
* Exposes more failures late unless teams integrate lanes continuously.

## More Information

**Related ADRs:**
* `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`
* `2026-04-03-2-review-approval-and-integration-completion-are-distinct.md`
* `2026-02-17-1-canonical-next-command-runtime-loop.md`

**Related Product Document:**
* Companion planning artifact: `prd-lane-based-execution-and-feature-acceptance-gates-v1.md` in the planning repo
