---
title: 'Context: Practices and Principles'
description: 'Glossary context for practices and principles: the operating principles guiding glossary-semantic-integrity execution, such as the mostly-invisible process.'
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: external/tech-lead-evaluator
  guidance_text: Read this to see the working principles behind the glossary checks and who owns each decision.
- profile: internal/lead-developer
  guidance_text: Read this before changing glossary gating, so a change keeps the block rule and the append-only history.
related:
- context/identity
---
## Context: Practices and Principles

Terms describing operating principles for glossary-semantic-integrity execution.

### Mostly Invisible Process

| | |
|---|---|
| **Definition** | Glossary checks should run by default with minimal interruption during normal flow. |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### Highly Visible Outcomes

| | |
|---|---|
| **Definition** | Conflict results, block reasons, and clarification decisions must be visible in artifacts/logs. |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### Append-Only Semantic History

| | |
|---|---|
| **Definition** | Term/sense changes and conflict decisions are recorded as immutable events, not rewritten in place. |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### Deterministic Gate, Human Clarification

| | |
|---|---|
| **Definition** | Conflict detection/gating is deterministic; only ambiguity resolution requires human input. |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### High-Severity Block Rule

| | |
|---|---|
| **Definition** | Under the default `medium` glossary strictness, generation is blocked only when high-severity semantic conflicts remain unresolved. `max` strictness blocks on any unresolved conflict and `off` never blocks (`should_block` in `src/glossary/strictness.py`). |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |

---

### Human-in-Charge (Cross-Reference)

| | |
|---|---|
| **Definition** | The principle that the human remains responsible and accountable for all decisions. Agents assist and propose; the HiC owns the final call. See full definition in Identity context. |
| **Context** | Practices & Principles |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Canonical entry** | [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |
