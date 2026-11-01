---
title: Living Glossary Context and Curation Model
description: Puts term ownership in domain contexts, curation rules in doctrine, and enforcement in a runtime hook, so terminology drift is caught while the work happens.
status: Accepted
doc_status: active
kind: ADR
date: '2026-02-23'
---

## Context and Problem Statement

Glossary behavior in 2.x now spans three layers:

1. Domain context definitions under `glossary/contexts/`.
2. Curation tactics/styleguides in doctrine (including HiC terminology and candidate promotion rules).
3. Runtime execution hook integration (`execute_with_glossary`) for mission primitives.

This architecture existed in code and tests but lacked a dedicated ADR describing the model and invariants.

## Decision Drivers

1. Preserve consistent domain semantics across AI-assisted workflows.
2. Keep glossary scope composable by domain context.
3. Tie curation quality to explicit doctrine artifacts.
4. Make glossary checks opt-in by metadata but enabled-by-default for safety.

## Considered Options

1. Keep a single monolithic glossary document with no context partitioning.
2. Adopt context-owned living glossary with doctrine-guided curation and runtime hook integration (chosen).
3. Defer glossary governance to external, non-repository tooling.

## Decision Outcome

**Chosen option:** Adopt context-owned living glossary with doctrine-guided curation and runtime hook integration.

### Decision Details

1. Glossary terms are organized by bounded context files under `glossary/contexts/` (for example `dossier`, `lexical`, `system-events`, `technology-foundations`).
2. New terminology enters as `candidate`; promotion authority remains with the Human-in-Charge.
3. Curation process is codified as a doctrine tactic plus writing styleguide (`glossary-curation-interview`, `kitty-glossary-writing`).
4. Mission primitive execution can pass through glossary middleware via `execute_with_glossary`; metadata/config determine enablement and strictness.

### Consequences

#### Positive

1. Terminology governance is explicit, context-scoped, and testable.
2. Definition quality is reinforced by reusable doctrine artifacts.
3. Runtime checks align generated outputs with glossary semantics.

#### Negative

1. More governance files to maintain when terminology evolves.
2. Cross-context linking introduces additional link-integrity risk without tests.

#### Neutral

1. Existing mission execution contracts remain intact, with glossary checks layered on top.

## Confirmation

This decision is validated when:

1. Glossary context links and anchors resolve.
2. Doctrine curation artifacts validate and resolve references.
3. Primitive glossary hook behavior honors metadata/config precedence.
4. New context additions can be introduced without breaking existing references.

## More Information

Implementation references:

1. `glossary/README.md`
2. `glossary/contexts/*.md`
3. `src/doctrine/tactics/glossary-curation-interview.tactic.yaml`
4. `src/doctrine/styleguides/writing/kitty-glossary-writing.styleguide.yaml`
5. `src/doctrine/missions/glossary_hook.py`
6. `src/doctrine/missions/primitives.py`
7. `src/specify_cli/missions/glossary_hook.py`
8. `tests/doctrine/missions/test_glossary_hook.py`
9. `tests/doctrine/missions/test_primitives.py`
10. `tests/doctrine/test_glossary_link_integrity.py`
11. `tests/doctrine/test_tactic_compliance.py`
