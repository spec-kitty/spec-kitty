---
title: 'Context: Lexical'
description: "Glossary context for the glossary's own data model: how terms are represented, resolved, and tracked, including the term-surface concept."
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to know how the glossary code models a term, its senses, provenance and confidence.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before reporting a glossary conflict, so you describe sense status and confidence as the code records them.
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
| **Definition** | The specific meaning of a term surface within a particular glossary scope. Carries the definition, where it came from (provenance), how confident the system is in it, and its status: `draft` (auto-extracted), `active` or `deprecated` (`TermSense` and `SenseStatus` in `src/glossary/models.py`). |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Surface](#term-surface), [Provenance](#provenance), [Confidence Score](#confidence-score) |

---

### Provenance

| | |
|---|---|
| **Definition** | Metadata recording where a term sense or artifact originated — who created it, when, and how (e.g., entered by the Human-in-Charge during clarification, extracted automatically from a spec, or seeded from a YAML file). The `source` field records values such as `user_clarification`, `seed_file` and the extraction heuristics (`metadata_hint`, `quoted_phrase`, `acronym`, `casing_pattern`, `repeated_noun`). |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Sense](#term-sense), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### Confidence Score

| | |
|---|---|
| **Definition** | A value between 0.0 and 1.0 indicating how certain the system is about a term extraction or sense resolution. Higher values mean higher certainty. It feeds conflict severity scoring (`score_severity` in `src/glossary/conflict.py`): an unknown term with confidence below 0.5 at a critical step scores high severity, which blocks generation under `medium` strictness. |
| **Context** | Lexical |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Term Sense](#term-sense), [Semantic Check](./execution.md#semantic-check) |
