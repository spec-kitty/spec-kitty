---
title: 'ADR: Auto-Merge Gates on the Terminal CI Aggregators — main Required Status Checks'
description: 'main now requires the router and CI Modules terminal gates as status checks, plus repo auto-merge, so GitHub auto-merge waits for real green instead of merging on one fast check.'
status: Accepted
date: '2026-09-23'
updated: '2026-10-01'
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

## Amendment (2026-10-01) — skip-if-green on ready-for-review (mission ci-runtime-stabilisation, #5510)

This amendment appends to the accepted text above and does not edit it. The set of required
contexts is unchanged: `Clean install verification`, `router gate` and `CI Modules gate`.
`CI Aggregate gate` stays deliberately not required. Details are in the contracts
[green match](../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/green-match.md)
and [router two-authority amendment](../../../kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md)
(amendment A4).

### Decision

A required gate may now pass on matched prior-run evidence, under exactly one condition: a
`pull_request` run with the action `ready_for_review` for which a completed, successful run of
the **same workflow** exists, with a non-expired marker for the identical **tested key**.

- **The tested key** is `(workflow file, PR number, head SHA, base SHA)`, where the base SHA is
  the first parent of the merge commit the run actually tested. It is bound through the commits
  API, and the second parent must equal the PR head. The `base.sha` the Actions API reports on a
  run is not used, because it shows the PR's current base, not the tested one.
- **Markers.** Every executing `pull_request` run uploads an artifact named
  `ci-tested-key-pr<N>-base-<sha>`. A run that skipped uploads
  `ci-green-match-run-<id>-attempt-<n>` and is never itself a match candidate, so skips do not
  chain. Both artifacts carry the same small JSON body written by
  `scripts/ci/green_match.py` (`pr`, `head`, `base`, `merge_sha`, `workflow`, `run_id`,
  `run_attempt` and `decision`, which is `run` or `skip`).
- **Effect.** The selection jobs of the router (`changes`), CI Modules (`generate-matrix`) and
  Packs (`changes`) suppress their path-filter step. Every path-gated job then skips, and
  `router gate` and `CI Modules gate` still post success on the PR head. This is event-level
  selection-step suppression, not a third CI path routing authority: no job `if:`, `needs:` or
  `changes` output expression mentions it, and `scripts/ci/gate_selection.py` does not model it.
- **CI Aggregate.** `collect` runs `scripts/ci/green_match.py effective-source` first. When the
  source run carries a skip marker, it re-points to the matched CI Modules run after re-verifying
  head SHA, workflow, event, success and tested identity, and fails closed otherwise
  ("re-run CI Modules to execute"). Fleet Verdict still binds by the skip run's display title.

### Never suppressed

Push, `workflow_dispatch`, `workflow_call` and schedule events; any other `pull_request` action;
any attempt after the first; a prior run that failed, was cancelled or is still in progress; a
moved base (a different tested key); a merge ref that cannot be bound to a tested key; and any
lookup error (HTTP, network, JSON or a missing key). A lookup error runs normally and emits a
`::warning::`. A skip marker from an earlier attempt of the same run is ignored, because markers
bind to their attempt.

### Escape hatch

Re-run the workflow. Attempt 2 always executes in full and Aggregate does not re-point.

### Consequences and recorded limits

- **Fail-safe direction.** The selection step never skips on doubt, and Aggregate never passes on
  doubt.
- **Trust surface.** The tested-key artifact name is written by a PR-controlled run, so on its
  own it proves nothing about which PR produced it. `decide` binds a match in two steps, and
  only the pair is trusted.
  - *Run identity.* The candidate run must be the same workflow file, `pull_request` event,
    success, head SHA and repository, with the same head branch and head repository as the event
    payload, and its `pull_requests` must list this PR. That list is not proof of authorship:
    GitHub fills it live with every open PR whose head matches. A second PR from the same
    branch, with a different base and a modified workflow, runs the same head SHA, head branch
    and head repository and lists both PR numbers (and only this one again once it closes).
  - *Head uniqueness.* Once a candidate matches, `decide` calls
    `GET pulls?head=<owner>:<ref>&state=all&per_page=100` and skips only when that returns
    exactly one PR, numbered this PR, with the event's base ref and head SHA. `state=all` makes a
    closed second PR still count. Zero, two or more, a full page (a possible second page), a
    malformed entry, an unknown event base ref and any API error all run normally.
  - Any other doubt also runs normally: empty or missing `pull_requests` (for example a fork
    PR, which therefore always executes in full), a missing head branch or head repository, or
    an unknown event-side identity.
  - *Residual.* The listing is a point-in-time read. A forged candidate run must already be
    completed and green to be matched, so its PR exists well before the read; the only gap is
    GitHub's own propagation delay in listing a just-opened PR. The marker JSON body is still
    not read: it is self-reported and proves nothing about what the run executed. CI Modules
    is stronger, because Aggregate re-verifies the matched run's identity from its immutable
    merge ref.
  - *Event guard and token.* The `green` step has a step-level `if:` for `pull_request` with
    action `ready_for_review`, so a PR that only edits the helper to print `skip=true` cannot skip
    on any other action: the step does not run. A sibling `green-key` step runs the same helper on
    every other `pull_request` action solely to record the tested-key marker; nothing reads its
    skip answer. The selection-job checkout also sets `persist-credentials: false` while PR code
    runs (on push, the router keeps it because `dorny/paths-filter` fetches over git there).
    This is not a boundary against a PR that edits the workflow file itself.
  - The `green` step carries `timeout-minutes: 3` in all three workflows, so a stalled `gh`
    cannot delay the run; a timeout runs normally.
- **Recorded residuals.** On a skip run the always-on lanes and `prose-scan` still run, and
  `tests (docs)` still runs on a prose-only skip run, because `prose-scan` is not suppressed.
  Sonar's informational per-change upload may repeat on a skip run. All three are accepted.
- **Evidence caveat.** The Aggregate half was verified offline against recorded API fixtures
  inside the mission, and live verification follows the merge, because `workflow_run` executes
  `main`'s copy of the workflow file.
