---
title: 'Context: Planning & Tracking'
description: 'Glossary context for planning and tracking: how work is organized, classified, and dispatched across the tracker and execution tiers (companion to the seed).'
doc_status: active
updated: '2026-09-30'
related:
- docs/context/execution.md
- docs/context/orchestration.md
- docs/context/system-events.md
---
## Context: Planning & Tracking

Terms describing how work is organized, classified, and dispatched in the issue
tracker and across the execution tiers. Human-readable companion to the
`.kittify/glossaries/planning-and-tracking.yaml` seed (the machine-checkable
subset); when the two differ, the seed governs semantic-check resolution and this
page governs prose. Surfaces are lowercase to match the seed.

### functional epic

| | |
|---|---|
| **Definition** | An epic that represents a real domain of work — a subsystem, capability, or bug-class — and owns its tickets as native sub-issues. Contrasted with a meta-tracker. Functional epics, not meta-trackers, are the canonical parents of work. |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [meta-tracker](#meta-tracker), [issue type](#issue-type) |

---

### meta-tracker

| | |
|---|---|
| **Definition** | A tracking or convenience issue — release gate, go/no-go, or program rollup — that references work via checklist but must NOT own functional tickets as their canonical parent. Titles are prefixed `META-TRACKER:`. Release gating belongs in milestones or labels, not in issues-as-parents. |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [functional epic](#functional-epic) |

---

### issue type

| | |
|---|---|
| **Definition** | The GitHub issue-type classification (Task, Bug, or Feature) applied to every ticket, orthogonal to priority. Epics are typed Feature. The invariant `bug label <-> type Bug` holds. Type captures the kind of work; the legacy Px-description labels that conflated priority with type are retired. |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [priority scheme](#priority-scheme), [triage status](#triage-status) |

---

### priority scheme

| | |
|---|---|
| **Definition** | The canonical issue-priority labels `priority:P0` .. `priority:P3`. The legacy `Px-description` labels (P0-critical, P1-bug, P2-enhancement, P3-future, P4-wontfix) are retired in favor of `priority:Px` plus the orthogonal issue-type field. |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [issue type](#issue-type) |

---

### triage status

| | |
|---|---|
| **Definition** | A cross-priority label namespace marking a ticket's disposition pending triage: `triage:stale` (reproduce and close if no longer valid), `triage:needs-revision` (scope/spec needs rework), and `triage:maybe-duplicate` (suspected duplicate pending confirmation — distinct from the confirmed `duplicate` label). |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [issue type](#issue-type), [priority scheme](#priority-scheme) |

---

### usability (label)

| | |
|---|---|
| **Definition** | The `usability` label, marking operator/user-experience and ergonomics concerns (CLI surface, status display, command clarity). Narrows the UX overlap previously folded into the `workflow` label. |
| **Context** | Planning & Tracking |
| **Status** | canonical |
| **Applicable to** | `3.x` |

---

### op

| | |
|---|---|
| **Definition** | A bounded, doctrine-governed agent action dispatched immediately without mission overhead (the `ask` / `advise` / `do` commands) that still produces a durable, git-tracked record. The execution tier between a full Mission and untracked ad-hoc invocation. An Op is to ask/advise/do what a Mission is to the full planning loop. |
| **Context** | Planning & Tracking |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Related terms** | [Mission](./orchestration.md#mission), [Tool](./execution.md#tool) |

---

## Glossary Scope — Planning & Tracking subset (deferred runtime scope)

The terms above are tracker-organization vocabulary. They are **not** yet bound to
a runtime [Glossary Scope](./system-events.md#glossary-scope); the current scope
enum is `mission_local`, `team_domain`, `audience_domain`, `spec_kitty_core`
(see `src/glossary/scope.py`).

**Deferred (FR-011, tracked as [#1418]).** Promoting the planning-and-tracking
subset to a first-class runtime `GlossaryScope` enum value is intentionally
deferred. Rationale: mission runs are not yet wired into the issue-tracking
concepts (epics, triage labels, the Op tier), so a runtime scope would have no
resolution surface to bind against. Reassess under #1418 once mission runtime
consumes tracking vocabulary. Until then this subset lives as a seed file
(`.kittify/glossaries/planning-and-tracking.yaml`) and this human-readable page,
deliberately outside the runtime scope hierarchy.

[#1418]: https://github.com/Priivacy-ai/spec-kitty/issues/1418
