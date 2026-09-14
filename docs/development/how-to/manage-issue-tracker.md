---
title: Managing the Issue Tracker
description: 'Conventions for the Spec Kitty issue tracker: epics vs meta-trackers, sub-issue parenting, blocked_by dependencies, triage (type, severity, blockers), and the label taxonomy.'
doc_status: active
updated: '2026-09-07'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/agent-fleet.md
- docs/development/contributing.md
- docs/guides/how-to/missions/keep-main-clean.md
- docs/development/how-to/pr-landing.md
- docs/development/reference/red-main-and-release-readiness.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---

# Managing the Issue Tracker

This guide describes how Spec Kitty structures its GitHub issue tracker so the
work graph stays honest, machine-navigable, and free of the drift that
hand-maintained checklists cause. It is aimed at maintainers and agents doing
tracker hygiene — parenting issues, wiring dependencies, and pruning stale
rollups.

The rules exist because a misleading work graph is expensive: a real defect
parented under a release rollup is hidden when that rollup is closed, and a
dependency captured only as prose is invisible to every tool that reads the
tracker.

## Functional epics versus meta-trackers

The tracker has two distinct kinds of parent issue. Telling them apart is the
first decision in any hygiene pass.

- A **functional epic** is a real domain or slice of work. It owns
  **native GitHub sub-issue children**, carries the `epic` label, and has a
  body that describes the work (see [Epic bodies](#epic-bodies-describe-work-not-children)).
- A **meta-tracker** is a convenience rollup — a release go/no-go list, a
  stabilization checklist, or a dashboard view. It carries the `meta-tracker`
  label, its body is a checklist that *references* issues owned elsewhere, and
  it has **no native children of its own**.

**The distinguishing test is native children, not the title.** An issue titled
`Umbrella: …` that owns native sub-issues is a functional epic; an issue that
holds only a body checklist of items homed under other epics is a
meta-tracker. Judge by the sub-issue graph, never by the name.

Parent functional issues under functional epics only. Never parent a real
work item under a meta-tracker.

## Parent and child are native sub-issue links

Express the parent/child relationship as a **native GitHub sub-issue link**, not
as a `## Children` checklist in the parent's body. Body checklists duplicate the
relationship and silently drift out of sync.

Create a link (REST — `sub_issue_id` is the child's numeric **database** id, not
its issue number):

```bash
CID=$(gh api repos/OWNER/REPO/issues/<CHILD> --jq .id)
gh api --method POST repos/OWNER/REPO/issues/<PARENT>/sub_issues -F sub_issue_id="$CID"
```

Or via GraphQL (node ids, not numbers):

```bash
PID=$(gh api repos/OWNER/REPO/issues/<PARENT> --jq .node_id)
CID=$(gh api repos/OWNER/REPO/issues/<CHILD> --jq .node_id)
gh api graphql -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}' -f p="$PID" -f c="$CID"
```

List a parent's children with `gh api repos/OWNER/REPO/issues/<PARENT>/sub_issues`.

**Single-parent constraint.** GitHub allows an issue only one parent; a second
link attempt returns HTTP 422. To **reparent**, remove the old link first, then
add the new one:

```bash
gh api graphql -f query='mutation($p:ID!,$c:ID!){removeSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}' -f p="$OLD_PARENT_NODE" -f c="$CHILD_NODE"
gh api graphql -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}' -f p="$NEW_PARENT_NODE" -f c="$CHILD_NODE"
```

## Execution order is blocked_by, not prose

Encode sequencing as native `blocks` / `blocked_by` dependencies **between
children**, not as a `#A → #B → #C` sequence in the epic body. An epic body
should carry no ordering prose that a tool cannot read.

```bash
# REST — issue_id is the BLOCKING issue's numeric database id
gh api --method POST repos/OWNER/REPO/issues/<BLOCKED>/dependencies/blocked_by -F issue_id=<BLOCKER_DB_ID>

# GraphQL — issueId is the BLOCKED issue's node id
gh api graphql -f query='mutation($b:ID!,$k:ID!){addBlockedBy(input:{issueId:$b,blockingIssueId:$k}){issue{number}}}' -f b="$BLOCKED_NODE" -f k="$BLOCKER_NODE"
```

For a strangler sequence of children, wire each step `blocked_by` its
predecessor so the ready-to-start item is always unambiguous.

## Epic bodies describe work, not children

An epic body is a functional description, not a child enumeration. Every epic
body must convey:

- **Why** — the problem or motivation.
- **For whom** — which users or roles benefit.
- **Intended effect** — the outcome once the epic is done.

Preserve substantive rationale; drop mechanical checklists (the sub-issue graph
already records the children).

## Meta-tracker lifecycle

- Label a meta-tracker `meta-tracker`, never `epic`.
- Its body checklist is by design. Do **not** audit a meta-tracker for
  "no in-body children" and do **not** native-link its checklist entries — the
  real issues live under their own epics.
- **Close a meta-tracker once it holds zero native sub-issues.** Its purpose is
  spent when the work it references is tracked under proper epics. Close it with
  an audit comment, and explicitly note any residual free-text checklist items
  so nothing silently vanishes.

## Filing children from an epic

When you decompose an epic into issues:

- **Match the epic's own stated breakdown** — file exactly the slices the body
  names, in the order it names them. Do not invent scope the epic did not
  specify; flag anything too vague to file cleanly instead of guessing.
- **Ground each slice in the real code first.** If a named slice already shipped,
  record that with evidence rather than filing a phantom "to-do" ticket that
  misrepresents completed work as pending.

## Triaging issues: type, severity, and release-blocking bugs

Every open issue carries two orthogonal classifications a triage pass must get
right: **what kind of thing it is** (native type) and **how urgent it is**
(priority). They are set independently and mean different things.

### Native type is the kind carrier

Set the GitHub **native issue type** — `Task`, `Bug`, or `Feature` (the tokens
are case-sensitive: `gh issue edit <N> --type Bug`). The type is the *sole* kind
carrier; the old `bug` label was retired repo-wide and must not be reintroduced.
A capability request wearing a bug title is a `Feature` (retype it, don't leave
it as a `Bug`). `enhancement` is a Feature, not a separate kind.

### Priority, and what makes a P0

Priority is a label (`priority:P0` … `priority:P3`). **`priority:P0` on a `Bug`
means a release-blocking defect** — and, per
[ADR 2026-07-17-1](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md),
that has teeth: **an open P0 bug is expected to red mainline**, mainline CI is the
authoritative release gate, and **red CI means no release**.

Because a P0 bug halts the release train, calibrate it deliberately. A bug is P0
if it trips any of:

- **Data/state corruption or loss** — overwrites recorded results, poisons/drops
  events, wrong-authority or split-brain committed writes.
- **Silent wrong result / false success** — a command reports success but skips or
  loses work (especially damning under the honesty ADR).
- **Core workflow broken with no workaround** — cannot implement / review / merge /
  accept / commit a mission; a deadlock or hang with no escape hatch.
- **Blocks release** directly, or a **security** exposure (credentials/secrets).

Downgrade below P0 when a clear workaround exists, the fault is edge-case-only,
cosmetic/UX, or confined to a dev-assist command. **Do not inflate P0** —
crying wolf devalues the red-mainline signal; and **do not under-call** a genuine
corruption or hang. Escalation to P0 is an operator decision.

Priority on a **non-bug** means something else: a `priority:P0` `Feature`/`Task`
is the priority of *planned work*, not a release-blocking defect — it does not
imply a red mainline.

### A P0 bug should carry a failing reproduction test

Per the ADR, when you file or accept a P0 bug, land an **issue-pinned red-first
reproduction test** so mainline honestly reflects the blocker rather than merely
asserting it. Mark it `@pytest.mark.regression` (the issue-pinned
exact-reproduction marker — **not** `quarantine`, which is built to *never* red
main), reproduce the defect through the pre-existing entry point, and note in the
test that it is an intentional red-first P0 reproduction referencing its tracking
issue. It must fail because of the product defect, not a test error — a
false red corrupts the signal it exists to give. Expensive QA and manual testing
wait for green; maintainers prioritize red recovery. See the
[red-main policy](../reference/red-main-and-release-readiness.md).

### What "good first issue" means here

`good first issue` is **not** a difficulty or seniority signal — this project's
contributor base is senior by default. It marks a **good entry point into the
codebase**: a self-contained issue that teaches a subsystem while carrying **low
customer and blast-radius impact**, so someone new to the repo can land it
without first absorbing deep cross-cutting context.

Reach for it when an issue is well-scoped, has a clear deliverable, and touches a
peripheral or tooling surface rather than a load-bearing one. One guardrail: if a
`good first issue` could still alter a **blocking or shared gate** (or otherwise
carry real blast radius despite being a good entry point), require maintainer
concurrence on the chosen approach **before** implementation — normal PR review
then covers the rest.

## Label taxonomy

Two orthogonal axes carry the load and are documented above: the **native type**
(`Bug` / `Feature` / `Task` — the sole kind carrier) and **priority**
(`priority:P0`…`priority:P3`). Labels never encode kind — the retired `bug`
label must not return. Beyond type and priority, labels fall into the families
below. Apply as many as genuinely apply; a `catfooding` `reliability` `Bug` at
`priority:P2` is a normal, well-triaged issue.

### Classification labels — what *kind of work* it is

These describe the nature of the work independently of the subsystem. They are
orthogonal to native type (a `catfooding` issue is still a Bug, Feature, or Task).

- `catfooding` — **Doctrine Catfooding**: dogfooding Spec Kitty's own
  quality/doctrine practices. Applied to defects and frictions surfaced by
  *running Spec Kitty on Spec Kitty* — a live mission session that exercises the
  specify → plan → tasks → implement → review → merge loop and reports where the
  tool fought its own operator. This is the dominant classifier for the
  post-convergence dogfooding backlog; expect clusters of `catfooding`
  `workflow`/`git`/`usability` issues that circle a single root cause.
- `tidy-up` — Campsite / declutter / degodding cleanup surfaced *during other
  work* (the boy-scout residue a mission couldn't fold in-line).
- `tech-debt` — Accumulated lint, type-checking, static-analysis, and
  code-quality debt.
- `design-spike` — Foundational design work.
- `research` — Research / experiment validation work.

### Subsystem / domain labels — *where* the work lives

Route an issue to its owning surface. Apply every domain that genuinely applies.

- `reliability` — Runtime reliability, resiliency, observability, incident
  prevention.
- `usability` — Operator/user experience and ergonomics.
- `workflow` — Workflow / UX improvements.
- `git` — How Spec Kitty uses git.
- `doctrine` — Doctrine system.
- `agent-profiles` — Agent-profile system.
- `schema-versioning` — Schema-versioning infrastructure.
- `sync` — Local event sync, sync daemon, offline queue, projection delivery.
- `saas` — Hosted SaaS projection, `saas_client`, auth, hosted teamspace.
- `dashboard` — Dashboard features.
- `windows` — Windows-specific issues.

### Triage-state labels — transient hygiene state, not classification

These record *where an issue sits in triage*. Remove them once resolved; they are
working state, not a permanent property.

- `triage:maybe-duplicate` — Suspected duplicate pending confirmation (as opposed
  to the confirmed `duplicate`).
- `triage:needs-revision` — Scope/spec needs rework before action.
- `triage:stale` — Reproduce and close if no longer valid.
- `triage:repro-needed` — Reported against behavior that may already be fixed;
  needs live re-reproduction before implementing.

### PR-workflow labels — for pull requests, not issues

These live on pull requests, not issues. The first is the fleet-coordination
handshake; the rest are workflow state.

- `ready-for-squad` — **fleet handshake**: the implementer has run the required tests
  and self-review and hands the PR to the review squad and CI. The
  [SkyKitty agent fleet](../agent-fleet.md) owns CI and squad review from this point;
  the operator still performs the mainline merge. Do **not** apply it to a still-draft
  scope or to work whose tests have not run — the label is the fleet's contract that the
  PR is finished and independently testable. See
  [The `ready-for-squad` handshake](../agent-fleet.md#the-ready-for-squad-handshake).
- `pr:needs-refresh` — PR branch drifted from `main`; rebase/refresh before review
  or merge.
- `pr:needs-revision` — PR has unresolved review findings that must be addressed
  before it can merge.
- `pr:kept-for-reference` — Kept open for reference/history; not intended to merge
  as-is.
- `pr:deferred` — Held under the 3.2.x doctrine-surface freeze; CI is skipped
  until unblocked.
- `pr:skip-ci` — Intentionally skip CI for this PR (docs / manual review only).
- `ci:full` — Run the full CI suite on a draft PR (overrides `ci-quality`'s draft
  exemption).

### Lifecycle & community labels

- `deferred` — Work paused pending an activation trigger.
- `feedback-welcome` — Community feedback & brainstorming welcome; comment
  ideas/objections, no code needed.
- `good first issue` — a good *entry point* (see
  [What "good first issue" means here](#what-good-first-issue-means-here)); not a
  difficulty signal.
- `help wanted` — Extra attention is needed.
- `mvp` — Required for the current Private Teamspace MVP.
- `release` — Release tracking and coordination.
- `documentation` — Improvements or additions to documentation.
- `enhancement` — GitHub's built-in label; treat it as a `Feature` synonym only.
  Kind lives in the **native type** — prefer setting `--type Feature` over relying
  on this label.
- The stock GitHub defaults `duplicate`, `invalid`, `question`, and `wontfix`
  keep their conventional meanings.

### Grouping labels (documented above)

`epic` and `meta-tracker` are covered in
[Functional epics versus meta-trackers](#functional-epics-versus-meta-trackers) —
they are not free-floating classification labels and carry structural obligations
(native children vs. a body checklist).

## See also

- [The SkyKitty agent fleet](../agent-fleet.md) — the fleet that acts on this repo, its
  roles, and the `ready-for-squad` handshake these labels feed.
- [Contributing to Spec Kitty](../contributing.md) — pull-request and maintainer workflow.
- [Keep main clean](../../guides/how-to/missions/keep-main-clean.md) — branch and merge discipline.
- [PR landing](pr-landing.md) — the fork-PR landing runbook, incl. red classification.
- [Red main and release readiness](../reference/red-main-and-release-readiness.md) — what a red main means and the release gate.
- [ADR 2026-07-17-1 — Red main is honest signal; CI is the release authority](../../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md).
