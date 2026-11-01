---
title: 'Context: Lexical'
description: "Glossary context for the glossary's own data model: how terms are represented, resolved, and tracked, including the term-surface concept."
doc_status: active
updated: '2026-03-10'
related:
- context/execution
- context/identity
- context/system-events
---
## Context: Lexical

Terms describing the glossary's own internal data model — how terms are represented, resolved, and tracked.

### Term Surface

| | |
|---|---|
| **Definition** | The raw text of a domain term as it appears in mission inputs or outputs, before the system determines what it means. For example, the word "agent" is a term surface that could mean different things in different contexts. |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Sense](#term-sense), [Glossary Scope](./system-events.md#glossary-scope) |

---

### Term Sense

| | |
|---|---|
| **Definition** | The specific meaning of a term surface within a particular glossary scope. Carries the definition, where it came from (provenance), how confident the system is in it, and whether it's active or deprecated. |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Surface](#term-surface), [Provenance](#provenance), [Confidence Score](#confidence-score) |

---

### Provenance

| | |
|---|---|
| **Definition** | Metadata recording where a term sense or artifact originated — who created it, when, and how (e.g., entered by the Human-in-Charge during clarification, extracted automatically from a spec, or seeded from a YAML file). |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Sense](#term-sense), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### Confidence Score

| | |
|---|---|
| **Definition** | A value between 0.0 and 1.0 indicating how certain the system is about a term extraction or sense resolution. Higher values mean higher certainty. Used to prioritize which conflicts the Human-in-Charge should review first. |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Sense](#term-sense), [Semantic Check](./execution.md#semantic-check) |
