---
title: 'Cut-over guard: fail-closed pre-merge gate for runtime-state cut-over'
description: What `spec-kitty cutover-guard` checks, how it is wired into CI so it cannot be silently skipped, and how to register it as a required status check.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
type: how-to
---
# Cut-over guard: fail-closed pre-merge gate for runtime-state cut-over

> **Status**: stable
>
> **Authority**:
> - [`kitty-specs/runtime-state-birth-cutover-all-paths-01KYH654/contracts/pre-merge-guard.md`](../../../kitty-specs/runtime-state-birth-cutover-all-paths-01KYH654/contracts/pre-merge-guard.md)
>   (IC-03 / IC-04; FR-002, FR-003, FR-008, FR-009, NFR-002, NFR-003)
> - Mission `runtime-state-birth-cutover-all-paths-01KYH654`, WP03 (guard CLI)
>   and WP04 (CI wiring, this document)

## What the guard does

`spec-kitty cutover-guard` is a diff-scoped, fail-closed check that blocks a
pull request unless every `kitty-specs/<mission>/` corpus touched by that PR's
diff has been **cut over** to event-log-authoritative runtime state, or is a
[pre-accept Mission](#pre-accept-missions), which is exempt from the stamp check.

"Cut over" is decided using the same event-log-evidence authority the
dogfood corpus lock uses
(`specify_cli.status.cutover_eligibility.is_cut_over`) — a mission carries a
runtime-state event log
(`_mission_carries_event_log_runtime`) AND satisfies the non-empty-snapshot
birth invariant (`_assert_birth_invariant_holds`). `verify_backfill.ok` is
checked but is **not sufficient on its own** — it is vacuous for
natively-born missions (they never ran a backfill and can still report
`ok`), so the guard never keys solely on it.

The guard is a second, independent caller of that same authority; it is not a
fork of the decision logic.

### Exit behavior

- **Exit 0** — every mission touched by the diff is cut over or pre-accept
  (including the
  vacuous case where the diff touches no `kitty-specs/` mission at all).
- **Exit 1** — one or more touched missions are un-cut-over, OR the diff
  itself could not be determined (unknown base ref, unreadable
  `--paths-from` file, missing project root). The guard **never** passes on
  uncertainty (NFR-003) — any verify error, ambiguous corpus, missing
  `mission_id`, or missing mission directory is treated as a failure, not a
  skip.

On failure the guard prints the un-cut-over mission slug(s) and a remedy
specific to the reason (see [Remedies](#remedies)). The default remedy is:

```
spec-kitty migrate backfill-runtime-state --mission <slug>
```

## Pre-accept Missions

A Mission driven only by the canonical commands carries event-log runtime
evidence from its first claim, but the `status_phase` stamp is written only at
accept/consolidate, by design (#2917). Before this exemption, every in-flight
Mission failed the guard on its first push (#5835, #5300).

A Mission is exempt, and passes with the note
`pre-accept: status_phase stamp deferred to accept/consolidate`, when all of
these hold:

- it has event-log evidence of runtime state;
- `meta.json` has no `status_phase`, or a well-formed one below `1`;
- it has no terminal evidence: no `accepted_at`, `merged_at` or `mission_number`;
- no work package carries legacy WP-frontmatter runtime state;
- it has a `mission_id`.

The guard lists exempt Missions in a separate section of the report and in the
`exempt` key of `--json`. It does not call them cut over.

The exemption fails closed. A malformed `status_phase`, an unreadable
`meta.json`, or a WP file the guard cannot read to rule out legacy runtime makes
the Mission fail, never pass.

### Remedies

| Reason | Remedy |
|---|---|
| Accepted or merged, but no stamp; or legacy WP frontmatter | `spec-kitty migrate backfill-runtime-state --mission <slug>` |
| `status_phase` malformed | fix `status_phase` in `kitty-specs/<slug>/meta.json` (expected an integer, for example `"1"`), then rerun |
| `meta.json` or a WP file unreadable | repair `kitty-specs/<slug>/meta.json` or the unreadable WP file, then rerun |
| Absent `mission_id` | `spec-kitty migrate backfill-identity` |

### Known limits

- A Mission merged mid-flight without accept, and with no legacy runtime state,
  is not caught: nothing marks it terminal.
- A coordination-topology Mission's event log may be absent from a PR head.
  This is pre-existing; a follow-up tracks it.

## How it is invoked

```bash
# CI usage — diff against the PR's base ref
spec-kitty cutover-guard --base-ref origin/main

# CI usage — host already has the changed-file list (e.g. a PR file listing)
spec-kitty cutover-guard --paths-from changed-files.txt

# Either form, machine-readable
spec-kitty cutover-guard --base-ref origin/main --json
```

Exactly one of `--base-ref` / `--paths-from` is required.

## How it triggers in CI (the corpus-only-PR requirement)

The guard runs as the `cutover-guard` job in
`.github/workflows/release-readiness.yml`, **not** in `ci-quality.yml` or the
modular CI. This placement is deliberate:

- The test workflows decide which jobs run from a paths filter over the
  *source* areas a diff touches (today `ci-router.yml`'s `changes` job). A
  diff that touches **only** `kitty-specs/**` does not set the `src`-family
  outputs, so a guard job hosted there and gated the same way would never
  execute on a corpus-only PR — exactly the leak this WP exists to close (risk R1, and
  the general "a required check that is `if:`-skipped reports neutral and
  does not block merge" footgun).
- `release-readiness.yml` is a small, `pull_request`-scoped workflow with no
  such gate on its own trigger. Its `on.pull_request.paths` filter has been
  extended to include `kitty-specs/**` specifically so that a corpus-only
  PR triggers this workflow (and therefore the `cutover-guard` job) at all.
  **If `kitty-specs/**` is ever removed from that `paths` list, the guard
  stops firing on corpus-only PRs with no other symptom** — treat that path
  entry as load-bearing.
- The `cutover-guard` job itself carries **no** `changes`/`dorny` step gate.
  It has exactly one conditional: the standard repo-wide
  `pr:deferred` / `pr:skip-ci` label skip (the same explicit,
  operator-visible opt-out also used in `ci-windows.yml` and
  `check-spec-kitty-events-alignment.yml`). Beyond that label check, the job runs unconditionally whenever
  the workflow runs — it does not sit behind any src-changes-shaped filter
  that a corpus-only diff could fail to satisfy.

## Registering it as a required check (operator action)

Wiring the job into the workflow is necessary but **not sufficient**. GitHub
branch protection only blocks a merge on checks that are explicitly
registered as required. The operator must:

1. Open the repository's branch protection settings for the target branch
   (`main`; the workflow's `pull_request.branches` list also still names the
   legacy `2.x` branch).
2. Under "Require status checks to pass before merging", add
   **`cutover-guard`** (the job name from `release-readiness.yml`) to the
   required-checks list.
3. Confirm the setting was saved — GitHub's UI only offers checks that have
   run at least once on that branch, so the job must have executed on some
   PR before it appears in the picker.

### The skipped-required-check footgun

A required check whose job is `if:`-skipped for a given run reports a
**neutral/"skipped"** conclusion in GitHub's UI, not a failure — and GitHub
treats a skipped required check as satisfied, letting the PR merge. This is
exactly why the job above avoids any conditional beyond the label skip: a
required check that *can* legitimately be skipped for reasons unrelated to
the label opt-out is a required check that can silently fail open.

If this job is ever refactored, re-verify — with a live scratch PR touching
only `kitty-specs/**` — that it still executes (not skips) on a corpus-only
diff. Do not trust a reading of the `paths:`/`if:` YAML alone; the mission
that produced this guard (`runtime-state-birth-cutover-all-paths-01KYH654`)
was itself created to close a gap that a path-filter reading alone had
missed (see `#2968`).

## Local verification (CI-equivalent simulation)

Because a real GitHub Actions run only happens once a PR is opened, the
job's behavior can be simulated locally with `--paths-from`, which accepts
exactly the changed-path list the CI job would otherwise obtain from a real
diff:

```bash
# 1. A synthetic corpus-only changed-path list (as if only this file changed)
echo "kitty-specs/<mission-slug>/status.events.jsonl" > /tmp/changed-paths.txt

# 2. Run the guard exactly as CI would
spec-kitty cutover-guard --paths-from /tmp/changed-paths.txt
```

This proves, without needing a live GitHub run:

- the guard triggers (evaluates the mission) on a changed-path set that
  touches only `kitty-specs/**`;
- it exits non-zero and names the mission plus the remedy command when that
  mission is un-cut-over;
- it exits `0` when the named mission is cut over.

The true end-to-end verification — that GitHub itself schedules and runs
the `cutover-guard` job for a real corpus-only PR — is recorded as a
separate, mandatory piece of evidence (subtask T019) gathered against a real
scratch PR, since it cannot be produced from a local git checkout.
