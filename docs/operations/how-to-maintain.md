---
title: How to Maintain — Spec Kitty Issue Tracker
description: 'Maintainer runbook for Spec Kitty tracker hygiene: issue-tracker structure, priority levels, issue types, and milestone/release-goal conventions grounded in live repo data.'
doc_status: active
type: how-to
audience: docs/context/audience/internal/maintainer.md
updated: '2026-06-16'
related:
- docs/operations/index.md
- docs/changelog/release-goals.md
- docs/changelog/3.2.x.md
---
# HOW TO MAINTAIN — Spec Kitty Issue Tracker

> Maintainer entry-point for tracker hygiene. Authored 2026-06-16 (planner-priti, governance op).
> Grounded in **live repo data** (`spec-kitty/spec-kitty`) and the operator conventions in
> `work/TRACKER_DOCTRINE_NOTES.md`. Items marked **(inferred)**
> are derived from observed usage, not an explicit written rule; everything else is **confirmed**
> from the label taxonomy, native GitHub Types, or an existing convention doc.
>
> Decision rationale for the milestone / release-goal recommendations lives in
> [§5 Recommended additions](#5-recommended-additions) (per Directive 003 — Decision Documentation).

---

## 1. Issue tracker structure

Three structural roles. Keep them distinct — conflating them is the most common drift.

| Role | What it is | Parenting rule |
|------|-----------|----------------|
| **Functional epic** | A *domain that produces code/behaviour* — a subsystem, capability, or bug-class. Labelled `epic`, native Type `Feature`. | **Owns** work. Functional tickets are parented here via native sub-issues. |
| **Functional ticket** | A single Bug / Task / enhancement that changes the product. | Lives under exactly one functional epic (single-parent constraint). |
| **Meta-tracker** | A release / go-no-go / stabilization rollup (e.g. *3.2.0 release tracker*). **Not** a domain of work. | **NEVER the canonical parent** of functional tickets. Prefix `META-TRACKER:`. References work via a body checklist only. |

**The cardinal rule (confirmed — CLAUDE.md "Meta vs functional epics" + TRACKER_DOCTRINE_NOTES §1):**
> Functional epics own work; meta-trackers only *reference* it. Never make a meta-tracker the parent
> of a functional ticket — use a checklist in the meta-tracker body, and parent the ticket under its
> functional epic.

Live example of the pattern done right: **#1929** (`Tracking: post-#1908 adversarial-panel findings`)
is a checklist-only meta view; each of its four findings (#1915–#1918) is canonically parented under
its *functional* epic (#1795/#1868/#1666/#1914), and #1929 explicitly states it is **not** their parent.

### Native sub-issues are the source of truth

- Parent/child is the **native GitHub sub-issue graph**, *not* body checklists (checklists are invisible
  to tooling). **Confirmed:** 29 of 35 open epics already use native sub-issues; e.g. **#1619** carries 10
  native children. Backfill native links wherever a body checklist implies a parent.
- REST: `POST/DELETE /repos/{owner}/{repo}/issues/{n}/sub_issues`; `sub_issue_id` is the integer
  **database id** (use `gh api -F`, not `-f`). Single-parent → `DELETE` from the old parent before `POST`.
- `.parent` is reliable only via **GraphQL** (`issue.parent`), not REST.

### Hygiene invariants (every open ticket)

1. Resolves to a **functional epic** — not an orphan, not meta-rooted, not under a closed/superseded epic.
2. Has an **issue Type** (`Task` / `Bug` / `Feature`; epics = `Feature`). See [§3](#3-issue-types).
3. Has a **priority** label (`priority:P0..P3`). See [§2](#2-priority-levels).

Sweep closed epics for *open* children and rehome them — open tickets under a closed parent look
tracked but are invisible.

### How a mission maps to issues

A mission's **issue-matrix** (in the mission spec) lists every tracker issue the mission addresses.
At spec time:

- Every addressed issue → a row in the issue-matrix **and** a tracker comment naming the mission.
- The issue is **claimed** (assigned to the operator) per the claim discipline below.

**Claim discipline (operator rule, 2026-06-16):**

- **Claim before WORKING** a ticket — assign it to yourself/operator *before* starting implementation,
  so concurrent agents/contributors don't collide.
- **Closing / cleanup is exempt.** You may close a provably-done ticket **without claiming it first** —
  attach an evidence comment (the PR/commit/test proving it's done). No claim needed to close.

---

## 2. Priority levels

Priority is a **tracker-state label** (`priority:P0..P3`), distinct from the MoSCoW planning lens
(MoSCoW = a scoping discipline at mission-negotiation time; `priority:Px` = backlog state). Both
coexist; do not collapse one into the other.

Operational meaning is **confirmed** from the label descriptions and **(inferred)** from observed
application across the current 3.2.x stabilization lane:

| Label | Label description (confirmed) | Operational meaning (inferred from usage) | Open count | Example |
|-------|-------------------------------|-------------------------------------------|-----------:|---------|
| `priority:P0` | *Release blocker / must decide before final 3.2.0* | **Release/merge blocker.** Must be resolved or explicitly decided before the targeted release ships. | 7 | #1844 (rc verify blocked), #1619 (exec-context epic) |
| `priority:P1` | *High-value stabilization / bug or release confidence* | **Important** — high-value stabilization or release-confidence work; not a hard ship-gate but strongly targeted for the cycle. | 63 | #1978 (naming split-brain), #1945 (ToolSurfaceContract epic) |
| `priority:P2` | *Planned enhancement / post-blocker work* | **Normal** — planned enhancements / cleanup scheduled after blockers clear. | 83 | #1979, #1928 (lint/strict debt epic) |
| `priority:P3` | *Backlog / future / needs reconfirmation* | **Low** — backlog; future or needs reconfirmation before it's actionable. | 55 | #1973 (experiment), #1911 |

Triage rule: assign a **provisional priority and flag it** rather than silently guessing. The
`p1-decision:*` and `triage:*` labels (see §3) record in-flight triage decisions on top of the base level.

---

## 3. Issue Types

**Confirmed:** the repo uses GitHub's **native org-level issue Types** (not type-via-label). Three
types are enabled: `Task`, `Bug`, `Feature` (GitHub's built-in default set — note this `Feature` is
GitHub's generic Type and is *unrelated to* the prohibited domain term "feature/Mission"; do not
rename it).

| Type | Use for |
|------|---------|
| `Bug` | An unexpected problem or incorrect behaviour to fix. |
| `Task` | A specific, scoped piece of work (refactor, chore, doc, tech-debt item). |
| `Feature` | A request / new capability **and all epics** (epic = `Feature` + `epic` label). |

Set Type via GraphQL `updateIssue(input:{id, issueTypeId})` (type ids are per-repo). Derive Type
objectively — from the conventional-commit prefix + labels — not by guesswork.

**Adoption gap (inferred — action item):** Type coverage is incomplete. In an 80-issue recent-open
sample, ~24% (19/80) had **no** Type set (e.g. #1929, #1978 at time of audit). Backfilling Type on
untyped open issues is a standing hygiene task.

### Type-flavour labels (label-based, complement the native Type)

These labels add a *flavour* the three native Types don't capture:

- `tech-debt` — accumulated lint / type-check / static-analysis / code-quality debt.
- `reliability` — runtime reliability, resiliency, observability, incident-prevention.
- `usability` — operator/user experience and ergonomics.
- `documentation` — docs additions/improvements.
- `research-mission` — research-mission related.
- `deferred` / `future` — paused pending an activation trigger / out-of-cycle vision work.

### `triage:*` and `p1-decision:*` workflow labels

These record **in-flight triage state**, not the final classification:

- `triage:maybe-duplicate` — suspected dup pending confirmation (vs confirmed `duplicate`).
- `triage:needs-revision` — scope/spec needs rework before action.
- `triage:stale` — reproduce and close if no longer valid.
- `p1-decision:keep | split | close-if-stale | defer` — the disposition reached for a P1 during a
  triage sweep (keep as-is / split into children / reproduce-and-close / defer out of the lane).
- `p1:verified`, `ddd-audit:reviewed` — audit provenance stamps.

Clear `triage:*` labels once the decision is executed.

---

## 4. Labels (area / component taxonomy)

Beyond priority and type-flavour labels, the area/component taxonomy (confirmed from `gh label list`):

- **Subsystem / area:** `dashboard`, `doctrine`, `agent_profiles`, `schema-versioning`, `git`,
  `workflow`, `windows`, `oauth-ddd-refactor`.
- **Release / coordination:** `release` (tracking & coordination), `launch-blocker`
  (must resolve before broad launch), `mvp` (current Private Teamspace MVP), `design-spike`.
- **Version tag labels (current release-scoping mechanism):** `3.2.0` (43 issues), `3.3.0` (17),
  and historically `0.15.0`. **(inferred)** These version labels are how releases are scoped today —
  see §5, because GitHub *milestones* are not currently used for this.
- **Stock GitHub labels:** `bug`, `enhancement`, `documentation`, `duplicate`, `invalid`, `question`,
  `wontfix`, `help wanted`, `good first issue`.

Keep area labels few and orthogonal; prefer native sub-issue parenting over inventing a new area label.

---

<a id="5-recommended-additions"></a>

## 5. Release scoping: emergent milestones + declarations of intent (IMPLEMENTED)

Adopted 2026-06-16. Milestones were previously **abandoned** (2 historical, no due-dates, zero open
issues; release scoping rode on version labels `3.2.0`/`3.3.0`). The model below is now live.

### 5a. Emergent milestones (per minor cycle, not per patch)

Scope by **minor cycle**: milestones are `3.2.x`, `3.3.x` (+ a retroactive point-in-time `3.2.0` for
what shipped). A minor cycle has **one goal**; multiple **emergent patches** (`3.2.1`, `3.2.2`, …) each
advance that same goal, and the milestone stays **open until the goal is structurally met**. This lets
us split a minor cycle into as many patches as the work needs without re-litigating scope.

- **Current milestones:** `3.2.0` (#3, closed — 7 shipped issues) · `3.2.x` (#4, open — the active
  stabilization cycle) · `3.3.x` (#5, open — next cycle, #1878 write-side + forward).
- **What it buys:** a real "what's left this cycle" burndown for free; one stable target across patches.
- **Gotcha (record this):** `gh issue edit --milestone "<title>"` only resolves **open** milestones by
  title. To attach issues to a **closed** (retroactive) milestone, use the API by **number**:
  ```bash
  unset GITHUB_TOKEN
  gh api repos/spec-kitty/spec-kitty/milestones -X POST -f title="3.2.x" -f state="open" -f description="<one-line goal + link to docs/changelog/3.2.x.md>"
  gh issue edit <num> --repo spec-kitty/spec-kitty --milestone "3.2.x"        # open milestone, by title
  gh api repos/spec-kitty/spec-kitty/issues/<num> -X PATCH -F milestone=<N>   # any/closed milestone, by number
  ```

### 5b. Declarations of intent (the canonical goal home)

The **release goal lives in a version-controlled doc**, not (only) the milestone description:
**`docs/changelog/<minor>.md`** — the durable, PR-reviewed declaration of intent (goal · rationale
· scope · non-goals · success criteria · emergent-patch plan · links). The **milestone description is a
short pointer** back to it (it is ephemeral, char-limited, unreviewable, and can't link to research).

- Why a doc over the milestone description: a "declaration of intent" deserves git history + review and
  must link to the research/missions; the milestone is the burndown surface, the doc is the intent.
- **Connection to mission practice:** a cycle goal maps to a driving mission (or small named set); the
  mission's `issue-matrix.md` is the per-patch closure ledger that rolls up into the milestone burndown.
- See [`docs/changelog/release-goals.md`](../changelog/release-goals.md) for the convention and
  [`docs/changelog/3.2.x.md`](../changelog/3.2.x.md) for the live example
  (**3.2.x — "Strangle the naming/identity/read-path split-brain toward a consistent SSOT."**).

---

### Quick maintainer checklist

- [ ] Every open issue: functional-epic parented (native sub-issue), Typed, prioritized.
- [ ] No functional ticket parented under a `META-TRACKER:` issue.
- [ ] Backfill native sub-issue links where a body checklist implies a parent.
- [ ] Backfill issue **Type** on the ~24% currently untyped.
- [ ] Claim before working; close-with-evidence is claim-exempt.
- [ ] (Proposal) Stand up a `v3.2.1` milestone + one-line release goal in its description.
