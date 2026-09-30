---
title: 'Context: Identity'
description: 'Glossary context for identity: who performs work and who owns semantic decisions, defining the agent and related workflow-coordination roles.'
doc_status: active
updated: '2026-09-30'
related:
- docs/context/execution.md
- docs/context/practices-principles.md
- docs/adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md
- docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
---
## Context: Identity

Terms describing who performs work and who owns semantic decisions.

### Agent

| | |
|---|---|
| **Definition** | Logical collaborator identity used in workflow coordination (for example implementer, reviewer). |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Tool](./execution.md#tool), [Role](#role) |

---

### Role

| | |
|---|---|
| **Definition** | Responsibility assignment for a step or work package (implementer, reviewer, planner, etc.). |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Agent](#agent), [Agent Profile](#agent-profile), [Authored Intent](#authored-intent), [Resolved Binding](#resolved-binding) |

---

### Agent Profile

| | |
|---|---|
| **Definition** | Structured logical collaborator identity and behavior guidance, identified by a stable profile ID, that can govern assignment, handoff, role-scoped behavior, and tool-native custom-agent/subagent projection. |
| **Context** | Identity |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Examples** | `architect-alphonso`, `researcher-robbie`, `implementer-ivan`, `reviewer-renata` |
| **Use when** | Describing who the collaborator is, what role boundaries it follows, and how it should be selected or handed off to. |
| **Do NOT use when** | Describing the generated file or host configuration that exposes the profile to Claude Code, Codex, Copilot, Cursor, Windsurf, or another tool; use [Tool Surface](./execution.md#tool-surface) instead. |
| **Related terms** | [Agent](#agent), [Role](#role), [Tool](./execution.md#tool), [Authored Intent](#authored-intent), [Resolved Binding](#resolved-binding) |

---

### Authored Intent

| | |
|---|---|
| **Definition** | Who or what a work package was *designed* to be run by — the authored/recommended `role`, `agent_profile`, and `model`. Authored once at tasks-finalize; **frontmatter-canonical** and static for the life of the WP; never mirrored into events. |
| **Context** | Identity |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Use when** | Describing the *recommended* assignment a WP was planned with — the design-intent for who should run it. |
| **Do NOT use when** | Describing who or what *actually* resolved and ran the WP; that is the [Resolved Binding](#resolved-binding), which is event-sourced. Never treat authored intent as "what ran". |
| **Canonical authority** | Exactly one source per datum — **static → frontmatter**. (Umbrella rule shared with [Resolved Binding](#resolved-binding).) |
| **Related terms** | [Resolved Binding](#resolved-binding), [Agent Profile](#agent-profile), [Role](#role), [Field-authority ADR](../adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md) |

---

### Resolved Binding

| | |
|---|---|
| **Definition** | Who or what **actually** resolved and ran a work package at a given lifecycle transition — the resolved `role`, `agent_profile` (+`agent_profile_version`), `model`, and `provider`. **Event-log / snapshot-authoritative**, folded latest-wins; it **shifts** across the lifecycle (implementer→reviewer, model swap). Produced by `resolve_profile` / `resolved_agent()` / the dispatch resolution — **never** a re-read of the frontmatter string. |
| **Context** | Identity |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Use when** | Describing who or what is *actually* running a WP at a lifecycle transition, or the latest-wins reduced value across pick-up/claim/reassign. |
| **Do NOT use when** | Describing the planned/recommended assignment; that is the [Authored Intent](#authored-intent), which is frontmatter-canonical. A WP with no resolved-binding events has an *empty* resolved binding — never the authored value masquerading as resolved. |
| **Canonical authority** | Exactly one source per datum — **dynamic → event log** (reduced snapshot). (Umbrella rule shared with [Authored Intent](#authored-intent).) |
| **Related terms** | [Authored Intent](#authored-intent), [Agent Profile](#agent-profile), [Role](#role), [Field-authority ADR](../adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md) |

See the [Agent Profiles reference](../api/agent_profiles/index.md) for the full built-in roster.

---

### Audience Persona

| | |
|---|---|
| **Definition** | Architecture-level stakeholder persona used to model needs, constraints, and success criteria for Spec Kitty usage and adoption. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Location** | `docs/context/audience/` |
| **Related terms** | [Mission Participant](#mission-participant), [Human-in-Charge (HiC)](#human-in-charge-hic), [Internal Audience Persona](#internal-audience-persona), [External Audience Persona](#external-audience-persona) |

---

### Internal Audience Persona

| | |
|---|---|
| **Definition** | Persona representing contributors or runtime actors who directly shape or operate Spec Kitty from inside the delivery boundary. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Persona catalog** | [Internal Audience Index](../../docs/context/audience/internal/index.md), [Lead Developer](../../docs/context/audience/internal/lead-developer.md), [Maintainer](../../docs/context/audience/internal/maintainer.md), [System Architect](../../docs/context/audience/internal/system-architect.md), [Spec Kitty CLI Runtime](../../docs/context/audience/internal/spec-kitty-cli-runtime.md), [AI Collaboration Agent](../../docs/context/audience/internal/ai-collaboration-agent.md), [Project Codebase](../../docs/context/audience/internal/project-codebase.md) |
| **Related terms** | [Audience Persona](#audience-persona), [Mission Participant](#mission-participant) |

---

### External Audience Persona

| | |
|---|---|
| **Definition** | Persona representing evaluators and decision-makers outside the runtime boundary who assess Spec Kitty value, fit, and adoption risk. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Persona catalog** | [External Audience Index](../../docs/context/audience/external/index.md), [Project Owner](../../docs/context/audience/external/project-owner.md), [External Tech Lead Evaluator](../../docs/context/audience/external/tech-lead-evaluator.md), [External Architect Evaluator](../../docs/context/audience/external/architect-evaluator.md), [External Product Manager Evaluator](../../docs/context/audience/external/product-manager-evaluator.md) |
| **Related terms** | [Audience Persona](#audience-persona), [Mission Owner](#mission-owner) |

---

### Mission Participant

| | |
|---|---|
| **Definition** | Human or tool-backed collaborator participating in a mission and, when execution is active, in one or more mission runs. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### Mission Owner

| | |
|---|---|
| **Definition** | Participant responsible for tie-breaking unresolved semantic conflicts when collaborators disagree. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Rule** | Tie-break only after normal participant resolution fails |

---

### Human-in-Charge (HiC)

| | |
|---|---|
| **Definition** | The human who remains responsible and accountable for decisions made during a mission. Agents assist and propose, but the HiC owns the final call. This principle ensures that automation supports human judgment rather than replacing it. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Mission Owner](#mission-owner), [Collaboration Mode](./execution.md#collaboration-mode), [HiC cross-reference](./practices-principles.md#human-in-charge-cross-reference) |

---

### engagement

| | |
|---|---|
| **Definition** | The client relationship a [Mission](./orchestration.md#mission) is carried out under — the real-world party whose work the Mission delivers. Because Missions are named after the work, **a mission slug is a client engagement name**, and so are the issue titles derived from it. The term therefore names a *third party*, not a unit of work: disclosing a mission identifier discloses who the client is. This is the whole ground of the project-egress consent boundary — only the project that owns a record may consent to that record leaving the machine, and inability to determine which project owns it is never consent. |
| **Context** | Identity |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Examples** | The operator-facing hosted-sync refusal names the term verbatim: *"the project at `<root>` has not consented to hosted sync, so its **mission and engagement identifiers** must not be transmitted"* (`TRACKER_EGRESS_IDENTIFIER_KINDS`, `specify_cli/tracker/saas_client.py`, rendered through `specify_cli/egress.py`). Four of the five widen-mode SaaS endpoints carry `mission_id` — documented as "ULID **or** slug" — in the *request path*, so an engagement name can reach the wire in a URL as readily as in a body. |
| **Use when** | Explaining *why* a mission identifier is confidential, or naming the party that a slug, branch name, worktree name or issue title discloses. |
| **Do NOT use when** | Referring to the unit of work itself — that is a [Mission](./orchestration.md#mission). Or to the SaaS collaboration binding a repository may have — that is [`project_uuid`](./identity-fields.md#project_uuid), a SaaS-assigned identity that names no client. |
| **Related terms** | [Mission](./orchestration.md#mission), [Mission Owner](#mission-owner), [Mission Participant](#mission-participant), [`project_uuid`](./identity-fields.md#project_uuid), [`repository_label`](./identity-fields.md#repository_label) |
