# Contract: Drupalling Dries Profile & Lineage

**Mission**: `drupalling-dries-profile-01M28X69`

There is no HTTP or GraphQL surface in this mission. The contracts that matter are the **loader
contracts** — the shapes the pack loader, DRG extractor, and validator accept, and the assertions
that prove conformance. Each clause below is directly testable and is the acceptance criterion for
its requirement.

---

## C-P1 — The profile loads and is selectable

**Requirement**: FR-001, FR-013

```
GIVEN  packs/built-in/agent_profiles/drupalling-dries.agent.yaml exists
WHEN   the agent-profile repository loads the built-in pack
THEN   a profile with profile-id "drupalling-dries" is present
AND    it does NOT appear in AgentProfileRepository.skipped_profiles
AND    its roles include "implementer"
AND    `spec-kitty doctor doctrine --json` reports 0 skipped profiles
```

**Negative clause** — the guard that makes this non-vacuous:

```
GIVEN  a deliberately malformed copy of the profile (in a fixture, not the shipped pack)
WHEN   the repository loads it
THEN   it appears in skipped_profiles
AND    the doctor report does NOT describe the pack as healthy
```

FR-013 is about failure being *visible*. A test that only asserts the happy path would pass
against a loader that silently swallows everything.

---

## C-P2 — Lineage resolves to the implementer persona

**Requirement**: FR-005, C-002

```
GIVEN  the regenerated DRG graph
WHEN   the edges from agent_profile:drupalling-dries are queried
THEN   exactly one specializes_from edge exists, targeting agent_profile:implementer-ivan
AND    resolve_profile traversal reaches implementer-ivan's inherited discipline
AND    the specializes_from subgraph remains a DAG
```

**Endpoint form**: both endpoints must be `<kind>:<id>` with `kind` a `NodeKind` member. Any other
token is refused at merge with `unresolved_edge_endpoint`. This is the failure mode CLAUDE.md
documents as having once silently dropped a documented edge, so it is asserted explicitly rather
than assumed.

---

## C-P3 — Directive and tactic edges are minted from the profile

**Requirement**: FR-005

```
GIVEN  the profile declares directive-references 010, 024, 025, 030, 034, 051
AND    tactic-references dependency-hygiene, tdd-red-green-refactor,
       supply-chain-install-safety, bug-fixing-checklist
WHEN   the DRG extractor runs
THEN   a requires edge exists from agent_profile:drupalling-dries to each
AND    every target URN resolves to an existing node
```

No edge in this clause is hand-authored. If one is missing, the profile's reference block is wrong
— that is the diagnostic this contract is for.

---

## C-P4 — Graph fragments are fresh

**Requirement**: NFR-002, R-002

```
GIVEN  the repository's own pack and source, in a synced dev environment
WHEN   `spec-kitty doctrine regenerate-graph --check` runs
THEN   it exits 0
AND    the pack it reports on is the repository's packs/built-in, NOT a globally installed copy
```

The second clause is load-bearing. A globally installed CLI reports freshness for the pack inside
its own venv and exits 0 while saying nothing about the change under review — verified during
Phase 0 (research.md R-003).

---

## C-P5 — Node inventory rises by exactly four

**Requirement**: NFR-002, NFR-007

```
GIVEN  the built-in pack before and after this mission
WHEN   the filesystem-derived inventory is compared to the loaded graph
THEN   node counts rise by exactly 4: 1 agent_profile, 2 styleguide, 1 toolguide
AND    the glob-derived expectation and the graph agree
```

`tests/doctrine/_builtin_inventory.py` derives expectations by globbing source files, independently
of the graph under test — so a loader that skips a shipped file reds rather than passing vacuously.

---

## C-P6 — The boundary is reciprocal and non-contradictory

**Requirement**: FR-004, NFR-007, SC-004

```
GIVEN  both the Dries and Frontend Freddy profiles
WHEN   their avoidance-boundary declarations are read
THEN   Dries defers generic browser component authorship to Frontend Freddy by name
AND    Freddy defers Drupal-native theming to Drupalling Dries by name
AND    both express that Dries VERIFIES the theming JS it authored while Freddy
       AUTHORS generic browser component work
AND    no field of frontend-freddy.agent.yaml outside avoidance-boundary is modified
```

**Judgement clause (SC-004)**: ten sample Drupal frontend tasks, assigned by a reader using only
the two boundary declarations, resolve to exactly one profile each with no ties. Not machine-
checkable; the honest form is a reviewer checklist, and it is recorded as such rather than dressed
up as an automated assertion.

---

## C-P7 — Activation stays opt-in

**Requirement**: FR-012, NFR-005, SC-006

```
GIVEN  a project that has not activated drupalling-dries
WHEN   governance context is loaded for any action
THEN   no Drupal material appears in it
AND    the rendered context is byte-identical to its pre-mission content

GIVEN  the same project
WHEN   `charter activate agent-profile drupalling-dries` runs
THEN   the profile becomes available with no bespoke step
```

---

## C-P8 — Provenance is present

**Requirement**: FR-010, C-003

```
GIVEN  each delivered artifact
WHEN   its references or attribution section is read
THEN   it credits amazee.io drupal-agents-md (Vanilla variant) as the distillation source
AND    no section reproduces the source verbatim
```
