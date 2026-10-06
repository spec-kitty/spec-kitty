---
title: 'Context: Governance'
description: 'Glossary context for governance: rule ownership, precedence, and policy controls in Spec Kitty, including the charter and doctrine-selection terms.'
doc_status: active
updated: '2026-10-06'
related:
- docs/context/configuration-project-structure.md
- docs/context/charter.md
- docs/context/identity.md
---
## Context: Governance

Terms describing rule ownership, precedence, and policy controls in Spec Kitty.

### Charter

| | |
|---|---|
| **Definition** | Project-level policy document that captures the HiC's operating constraints, quality rules, and doctrine selections for a repository. Compiled from interview answers and doctrine catalog choices. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Project Charter](./configuration-project-structure.md#project-charter), [Charter Interview](#charter-interview), [Charter Compiler](#charter-compiler), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### Governed AI Delivery

| | |
|---|---|
| **Definition** | Delivering software with AI agents under explicit human governance: work moves from agreed intent to a verified, useful result, while humans keep decision-making and accountability. Every change needs a clear purpose, verification proportionate to its risk, and evidence that the result was useful. Spec Kitty describes itself as the operating system for Governed AI Delivery. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `4.x` |
| **Related terms** | [Charter](#charter), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic), [Precedence Rule](#precedence-rule) |

---

### ADR (Architectural Decision Record)

| | |
|---|---|
| **Definition** | Immutable record of a significant technical/domain decision, with context and consequences. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Location** | `docs/adr/1.x/` and `docs/adr/2.x/` |

---

### Glossary Strictness Policy

| | |
|---|---|
| **Definition** | Governance rule for how semantic conflicts are treated (`warn` vs `block`) under each strictness mode. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Default** | `medium` |

---

### Clarification Burst Policy

| | |
|---|---|
| **Definition** | Rule that limits clarification interruption by prioritizing highest-impact conflicts first and capping prompt count per burst. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Cap** | 3 prompts per burst |

---

### Precedence Rule

| | |
|---|---|
| **Definition** | Ordering used when policy settings conflict. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Operational order (strictness)** | CLI override > step metadata > mission config > global default |

---

### Charter Interview

| | |
|---|---|
| **Definition** | A guided question-and-answer process that walks the HiC through their project's preferences, constraints, and doctrine selections. Answers are saved to `answers.yaml` and used to compile the charter. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Charter](#charter), [Charter Compiler](#charter-compiler), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### Charter Compiler

| | |
|---|---|
| **Definition** | The processor that takes the HiC's interview answers and their selected doctrine artifacts, and combines them into a finalized charter document and supporting governance files. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Charter](#charter), [Charter Interview](#charter-interview), [Doctrine Catalog](./charter.md#doctrine-catalog) |

---

### Governance Resolution

| | |
|---|---|
| **Definition** | The result of checking the HiC's charter selections against available doctrine catalogs — confirming that the referenced paradigms, directives, and tools actually exist and are compatible with each other. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Charter Compiler](#charter-compiler), [Doctrine Catalog](./charter.md#doctrine-catalog) |

---

### Activation Chokepoint

| | |
|---|---|
| **Definition** | The single activation filter applied by `charter.activation.resolver.DoctrineService` (the activation-aware wrapper). It enforces the project charter's per-kind activation state on a doctrine service's `paradigms`, `procedures`, and `agent_profiles` surfaces, so every profile-resolving path passes through one consistent filter rather than re-implementing activation logic. The factory `specify_cli.doctrine_service_factory.build_activation_aware_doctrine_service` is the single construction seam that routes callers through this chokepoint. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [Activated vs Available Profile](#activated-vs-available-profile), [Abstract Base Profile](#abstract-base-profile) |

---

### Activated vs Available Profile

| | |
|---|---|
| **Definition** | An **available** profile is any agent profile present in a doctrine layer (built-in, org pack, or project). An **activated** profile is an available profile that the project charter has explicitly turned on via `activated_agent_profiles`. Three-state semantics: when the key is absent, every available profile is activated; an explicit empty set activates none; an explicit set activates only the listed IDs. Only activated profiles are directly selectable by default surfaces; available-but-not-activated profiles surface only under `--all`/`--show-available`. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [Activation Chokepoint](#activation-chokepoint), [Abstract Base Profile](#abstract-base-profile) |

---

### Abstract Base Profile

| | |
|---|---|
| **Definition** | An agent profile that is referenced via a `specializes_from` lineage edge but is **not itself activated** in the project charter. It acts as a shared-element store that concrete profiles inherit from; it is not directly selectable as a runtime persona. Resolving a profile whose lineage traverses an abstract base (an ancestor not in the activated set) yields a lineage warning rather than an error. |
| **Context** | Governance |
| **Status** | canonical |
| **Applicable to** | `3.x` |
| **Related terms** | [Activated vs Available Profile](#activated-vs-available-profile), [Activation Chokepoint](#activation-chokepoint) |
