---
title: 'ADR: Auto-Merge Gates on the Terminal CI Aggregators — main Required Status Checks'
description: 'main now requires the router and CI Modules terminal gates as status checks, plus repo auto-merge, so GitHub auto-merge waits for real green instead of merging on one fast check.'
status: Accepted
date: '2026-09-23'
updated: '2026-09-23'
---

## Context and Problem Statement

> **Ratified by the operator (agentic-framework-core-team) on 2026-09-23** and applied to
> `spec-kitty/spec-kitty` `main` the same day. This ADR records a branch-protection
> configuration decision; it changes no code. It is a sibling of
> [`2026-09-15-1-ci-main-verdict-topology`](2026-09-15-1-ci-main-verdict-topology.md)
> under epic [#4437](https://github.com/spec-kitty/spec-kitty/issues/4437) ("CI pipeline
> honesty"): that ADR made a landed main tip *prove itself* green honestly; this one makes
> the *merge gate* honour that proof before a PR lands.

`main`'s protected-branch `required_status_checks` listed exactly one context:
**`Clean install verification`** (a ~24s job). Because it was the only *required* check,
GitHub treated a PR as mergeable the moment that one fast job passed — while the
architectural battery, the module-test shards, and coverage aggregation were still
running.

The failure surfaced concretely when landing PR
[#4953](https://github.com/spec-kitty/spec-kitty/pull/4953): `gh pr merge --rebase --auto`
was expected to hold the PR until CI was green, but it **merged immediately** with ~11
checks still pending (0 failed at the time). The merge came out clean, but only by luck of
the pending jobs subsequently passing — "merge on green" was not actually gating on green.
The same gap would let a genuinely red heavy shard land on `main` if auto-merge fired
before that shard reported.

## Decision

Two settings together, both applied to `spec-kitty/spec-kitty`:

1. **`main`'s `required_status_checks`** is expanded from one context to **three**, and
   `strict` stays `false`:

   | Required context | Producing workflow | Role |
   | --- | --- | --- |
   | `Clean install verification` | (kept) | wheel installs from a clean env |
   | `router gate` | `ci-router.yml` (`router-gate`, `if: always() && !cancelled()`) | the single `gate_selection.py` path/gate authority |
   | `CI Modules gate` | `ci-modules.yml` (`modules-gate`, `if: always() && !cancelled()`) | the per-module test-matrix verdict |

2. **`allow_auto_merge: true`** at the repository level. Without it `gh pr merge --auto`
   cannot queue and silently **degrades to an immediate merge** the moment a PR is nominally
   mergeable — which is how a PR once merged with the heavy shards still pending.

`strict: false` is deliberate: this repo **rebase-merges**, and requiring branches to be
up to date with `main` before merging would force a re-sync churn on every PR without
adding safety the gates do not already give.

## Rationale — why these three gates, and no others

The two added contexts are the CI's **skipped-tolerant terminal aggregator** jobs. Each
runs `if: always()` and always posts a definitive success/failure verdict *even when its
downstream shards path-skip* (`ci-modules.yml` states outright that "the required check is
the terminal `modules-gate`"), **and both post their check onto the PR head.** That
combination — always-posted *and* posted on the PR head — is what makes them safe to
*require*.

**Do not require an individual shard or a path-scoped job** (for example
`architectural battery (heavy, code-scoped)`). Those jobs are *skipped* — never posted — on
a PR whose diff does not match their trigger paths, and a required check that is never
posted blocks the PR from merging forever.

### Why `CI Aggregate gate` is deliberately NOT required (learned by testing this)

`ci-aggregate.yml` is `workflow_run`-triggered off `CI Modules` and therefore executes in
the **default-branch context**; empirically its `CI Aggregate gate` check posts only onto
`main` heads, **never onto a PR head** (verified: 5 runs on the `main` tip, 0 on every head
of the PR that shipped this ADR, and no `Aggregate` context in that PR's status rollup).
Requiring a check that never posts on a PR head puts every PR into a permanent `BLOCKED`
merge state — auto-merge can never satisfy it. It is a `main`-side coverage/diff-cover gate
(enforced after merge, honouring the `2026-07-17-1` "CI is the release authority on main"
model), not a pre-merge required check. This was caught by exercising `--auto` on a live PR
during the change itself; the four-gate first cut deadlocked, and the required set was
corrected to the three PR-posting gates.

## Consequences

- `gh pr merge <N> --rebase --auto` now holds a PR until the three required gates report
  success and refuses on any red — genuine on-green merging. The maintainer landing runbook
  can rely on `--auto` for the hand-off-to-merge step instead of polling the shards by hand.
  Always confirm it **armed and did not immediate-merge** (`state: OPEN` with a non-null
  `autoMergeRequest` while checks pend).
- No contributor-facing change: this only makes the merge gate behave the way the workflow
  design already intended.
- **Rollback reference:** the prior state was `required_status_checks.contexts:
  ["Clean install verification"]`, `strict: false`, and `allow_auto_merge: false`.
- This does not alter the [`2026-07-17-1`](2026-07-17-1-red-main-is-honest-ci-is-release-authority.md)
  invariant that mainline CI is the release authority; it strengthens the *pre-merge*
  application of the same honesty principle.
