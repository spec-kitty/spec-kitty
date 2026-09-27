---
title: Spec Kitty Mission Workflow
description: 'End-to-end authority for a local autonomous mission: the nine phases from specify through retrospective, and the focused-PR path when the target branch is not synchronized.'
doc_status: active
updated: '2026-08-15'
type: explanation
audience: docs/context/audience/internal/lead-developer.md
---
# Spec Kitty Mission Workflow

Use this workflow for local autonomous missions that start from a normal
repository checkout and finish with a pull request to the mission's target
branch.

## Phase 1: Specify

Create the mission spec from the intake prompt:

```bash
/spec-kitty.specify @start-here.md
```

Confirm the mission slug, target branch, and requirement scope before planning.

If the brief carries YAML frontmatter with `handoff_packet: 1` — emitted by an
upstream requirements tool — `spec-kitty intake` picks it up automatically
(`intake --auto` also scans `.handoff/*.md` at the project root) and
`/spec-kitty.specify` adopts the packet's FR/AC ids verbatim instead of
re-minting them; the discovery-gate confirmation above still runs. This
overlay is optional and additive: a packet-less brief, an unrecognised
version, or malformed frontmatter all behave exactly like plain prose intake.
See [Handoff Packet v1](../contracts/handoff-packet-v1.md).

## Phase 2: Plan

Generate the plan from the approved spec:

```bash
/spec-kitty.plan @start-here.md
```

Keep branch intent explicit. If the mission should land somewhere other than
`main`, resolve that before tasks are generated.

## Phase 3: Tasks

Generate and finalize tasks:

```bash
/spec-kitty.tasks @start-here.md
spec-kitty agent mission finalize-tasks --mission <mission-slug>
```

Review lane assignments and owned files before implementation begins.

## Phase 4: Implement and Review

Run the implement-review loop until every WP is approved:

```bash
/spec-kitty-implement-review
```

Each implementer edits only the execution workspace printed by
`spec-kitty agent action implement`.

## Phase 5: Accept

Run acceptance after the final WP is approved:

```bash
/spec-kitty.accept
```

Acceptance checks mission readiness. Consolidation still performs its own pre-flight
validation.

## Phase 6: Consolidation Preview

Preview the consolidation before mutating the target branch:

```bash
spec-kitty consolidate --mission <mission-slug> --dry-run
```

Resolve dirty worktrees, missing worktrees, and dependency ordering issues
before continuing.

## Phase 7: Consolidate or Open a Focused PR

If the target branch is synchronized with its tracking branch, consolidate normally:

```bash
spec-kitty consolidate --mission <mission-slug> --push
```

If `spec-kitty consolidate` stops with this diagnostic, use the focused-PR path
instead of trying to make local `main` publishable:

```text
Error: Target branch is not synchronized with its tracking branch.
  diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
  branch_or_work_package: main
  violated_invariant: local_target_branch_must_match_tracking_branch
```

Autonomous local runs often leave `main` ahead of or diverged from
`origin/main` because planning, status, review, and orchestration commits are
created during the run. Do not reset, rebase, force-push, or push local `main`
as remediation for this diagnostic.

When the mission branch already contains the approved lane consolidation, open
the PR directly from the mission branch:

```bash
git push -u origin kitty/mission-<mission-slug>
gh pr create --base main --head kitty/mission-<mission-slug> --fill
```

If you want a dedicated PR branch, create it from the mission branch and open
the PR from there:

```bash
git switch -c kitty/pr/<mission-slug>-to-main kitty/mission-<mission-slug>
git push -u origin kitty/pr/<mission-slug>-to-main
gh pr create --base main --head kitty/pr/<mission-slug>-to-main --fill
```

Prefer a squash merge for autonomous runs that accumulated many orchestration
commits:

```bash
gh pr merge --squash --delete-branch
```

## Phase 8: Mission Review

After the PR lands, run mission review from a checkout containing the landed
changes:

```bash
spec-kitty agent mission review --mission <mission-slug>
```

Use the review to confirm spec-to-code fidelity and requirement coverage.

## Phase 9: Retrospective

Verify or create the retrospective, then inspect synthesis proposals:

```bash
spec-kitty retrospect create --mission <mission-slug>
spec-kitty agent retrospect synthesize --mission <mission-slug>
```

Apply only the proposals you intend to preserve:

```bash
spec-kitty agent retrospect synthesize --mission <mission-slug> --apply <proposal-id>
```
