---
title: 'Issue #1040 — ADRs as First-Class Primitive: Scope Inclusion Assessment'
description: "Architect Alphonso's scope-inclusion assessment for issue #1040 (ADRs as a first-class primitive): whether and how to fold it into the mission (2026-05-18)."
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Issue #1040 — ADRs as First-Class Primitive: Scope Inclusion Assessment

> **Status update (2026-09-30).** The 3.3.x milestone this assessment targets was retired on 2026-08-23 without shipping. #1040 is still open and sits on the *Product backlog* milestone. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Author:** Architect Alphonso (ad-hoc profile session)  
**Date:** 2026-05-18  
**Issue:** [Priivacy-ai/spec-kitty#1040](https://github.com/spec-kitty/spec-kitty/issues/1040) — *Feature request: make ADRs a first-class Spec Kitty primitive*  
**Context:** Evaluating whether to pull #1040 into the 3.2.0 epic (#1111) given the charter/doctrine
enhancements landing on `feat/org-doctrine-layer`.  
**Related documents:**  
- `docs/development/epic-1111-slice-landing-plan.md` — full slice gap analysis  
- `docs/development/slice-f-gap-analysis.md` — Slice F codebase-to-intent detail  

---

## Question

> *"Would including #1040 into the scope make sense? As we are planning core
> charter/doctrine enhancements anyway, making a per-mission 'decisions' store would
> make sense. These can be used for ADR aggregation/lookup by the teams. I think this
> fits the product vision well, and ties in nicely to our enhanced mission-type
> governance work."*

---

## Verdict

**Do not include #1040 in 3.2.0 scope. Open a scoped follow-on research mission instead.**

The product vision fit is real and the architectural seam is already present in the
codebase. However, four open design questions in the issue are unanswered, the issue
carries a `research-mission` label for that reason, and the 3.2.0 epic already has
seven unfinished primary-scope tickets — all P1-bugs or MVP-blockers. Including a
design-spike item compounds the release gate without closing it.

The right move is: land the minimum seam now (three small changes, no design
decisions required), open a research mission to answer the four open questions, and
deliver the full typed primitive in 3.3.x.

---

## The case for inclusion

### 1. Mission B created the exact activation hook

`src/doctrine/missions/software-dev/governance-profile.yaml` (Mission B output) already
has `activations: []` and `selected_procedures: []`. The activation registry
(`charter.activations.ActivationEntry`) is the runtime contract for "when doing action
X, trigger artifact Y". A per-mission-type declaration to prompt for ADR creation
during `plan` or `research` actions requires a one-line addition to the profile — no
schema change, no new module.

Architect Alphonso's agent profile (`src/doctrine/agent_profiles/built-in/architect-alphonso.agent.yaml`)
already references `tactic-references: [{id: adr-drafting-workflow}]`. That tactic has
no canonical output path. The per-mission `adrs/` path gives it one.

### 2. The dossier indexer already discovers ADRs

`src/specify_cli/dossier/indexer.py:258` matches filenames containing `"architecture-decision"`
or `"adr"` and classifies them as `"policy"` artifacts. The discovery layer exists.
A typed primitive would replace the heuristic filename match with schema-validated
identity — an additive change over what already works.

### 3. Charter context already points agents at ADRs

`src/charter/context_renderers/authority_paths.py` hardcodes `docs/adr/2.x/`
as a default authority path with the annotation:

> *"architectural intent — when you change a structural boundary, read the relevant ADR"*

Every agent already receives this pointer in their governance context. A per-mission
`kitty-specs/<mission>/adrs/` would be a natural addition alongside it.

### 4. The product vision tie is architecturally clean

Mission-type governance profiles (Mission B) define what governance artifacts apply
per mission type. Without a typed ADR primitive, procedures that produce decision
records have no canonical landing zone — their output ends up buried in `research.md`
or `plan.md`. The primitive gives the procedure a typed home. The dependency flows
in the right direction: `specified governance profile → produces → typed artifact`.

---

## The case against inclusion in 3.2.0

### 1. Four open design questions remain unanswered

The issue explicitly flags these and they are not trivial:

| Question | Why it matters |
|---|---|
| Where does canonical storage live? `kitty-specs/adrs/` vs `kitty-specs/<mission>/adrs/` vs both? | Determines the indexer scan path, the CLI `list` scope, and the dossier manifest entry |
| What is the minimum schema? (frontmatter fields, supersession links, evidence links) | A schema that is too thin won't support SaaS/tracker projection; too heavy and migration burden grows |
| How are IDs assigned? (path-derived, ULID, date-derived, frontmatter override) | ID stability matters for cross-mission supersession links |
| How does Spec Kitty distinguish owned ADR artifacts from linked external docs? | Projects with existing `docs/decisions/` or `spec/architecture/` conventions need a clear boundary |

Answering these wrong creates migration burden the issue explicitly wants to avoid.
Answering them right takes a research pass.

### 2. The 3.2.0 epic has seven unfinished primary-scope tickets, all P1-bugs

Slices A, B, C, D, and E are all unstarted. Four of the Slice A tickets are
MVP-blockers and P1-bugs. Adding a design-spike to the same release gate makes
"3.2.0 stable" harder to close without delivering user-visible value proportional
to the risk.

### 3. "Per-mission decisions store" and "ADRs as first-class primitive" are different scopes

The instinct behind the question — a per-mission decisions store for ADR
aggregation/lookup — is *narrower* than what #1040 asks for. #1040 asks for:
- A typed artifact primitive with schema/version metadata and status lifecycle.
- A project-level cross-mission ADR index.
- CLI surface: `adr list`, `adr new`, `adr validate`, `adr supersede`, `adr link`.
- Agent prompt changes for `plan` and `research` missions.
- SaaS/dashboard projection of decision records.

The narrow form — `kitty-specs/<mission>/adrs/*.md` with agreed frontmatter, a
discovery entry in `expected-artifacts.yaml`, and an authority-paths pointer — can be
done without answering any of the four open questions. That narrow seam is the right
3.2.0 contribution.

---

## What to do: the minimum seam (3.2.0)

Three changes, no design decisions required, no new modules:

### Change 1 — `expected-artifacts.yaml` for `software-dev`

```yaml
optional_always:
  # existing entries ...
  - artifact_key: "evidence.adrs"
    artifact_class: "policy"
    path_pattern: "adrs/*.md"
    blocking: false
```

Same pattern for `research`, `documentation`, and `plan` mission types. This registers
the per-mission `adrs/` directory as a known optional artifact class. The dossier
indexer already handles it; this makes the classification schema-driven rather than
heuristic.

### Change 2 — `authority_paths.py` session-scoped path

Extend `DEFAULT_AUTHORITY_PATHS` (or the charter-context section-body renderer) to
include the mission-local `adrs/` path when it exists, alongside the project-level
`docs/adr/2.x/`:

```python
# In render_authority_paths, when a feature_dir is known:
"<mission>/adrs/": (
    "mission-local decision records — when you make a structural decision "
    "during this mission, record it here"
)
```

This gives every agent an explicit pointer to their mission's decision store without
any schema changes.

### Change 3 — ADR template file

Add `src/specify_cli/missions/software-dev/templates/adr.md` with a minimal
frontmatter schema:

```markdown
---
id: <ULID or date-slug>
title: ""
status: proposed   # proposed | accepted | superseded | deprecated | rejected
date: YYYY-MM-DD
supersedes: []
evidence:
  - research: ""
  - wp: ""
  - ticket: ""
---

## Context

## Decision

## Consequences
```

The template is the convention surface. It requires no loader, no validator, no CLI.
It is discoverable by the indexer immediately.

These three changes take a few hours and require no design decisions. They constitute
the "minimum seam" that the full typed primitive (#1040) will build on.

---

## What to do next: the follow-on research mission (3.3.x)

Open a research mission scoped to answering the four open design questions. The output
is an ADR (for the ADR primitive) plus an implementation spec. Suggested scope:

**Research phase outputs:**
- Canonical storage decision: single location vs dual (`kitty-specs/adrs/` + `kitty-specs/<mission>/adrs/`).
- Minimum schema validated against three real existing ADR corpora in the repo
  (`docs/adr/2.x/*.md`, `kitty-specs/*/research/architecture-decisions/`, spec-kitty-saas ADRs).
- ID strategy decision: recommend ULID-based frontmatter ID with path as fallback,
  matching the mission identity model (ADR `2026-04-09-1`).
- External-doc boundary decision: link vs import vs ignore, with migration guidance
  for projects that have their own `docs/decisions/` convention.

**Implementation phase outputs (3.3.x mission):**
- Typed `AdrArtifact` Pydantic model in `specify_cli/dossier/` or a new
  `specify_cli/decisions/` module.
- `spec-kitty adr list/new/validate/supersede/link` CLI surface.
- Cross-mission project-level index at `.kittify/indexes/adrs.json`.
- Discovery hook in the dossier indexer replacing the heuristic filename match.
- `plan` and `research` mission-type governance profiles updated to activate the
  `adr-drafting-workflow` procedure.
- Dashboard/SaaS projection (if `spec-kitty-saas` scope permits).

---

## Codebase tie-in map

| Existing artifact | Connection to #1040 | 3.2.0 seam | 3.3.x work |
|---|---|---|---|
| `governance-profile.yaml` → `activations: []` | Activation hook for ADR-prompting during `plan`/`research` | Add `adr-drafting-workflow` procedure reference | Wire to typed artifact creation |
| `authority_paths.py` → `docs/adr/2.x/` | Already surfaces project ADR directory | Add mission-local `adrs/` path | Parametrise from mission context |
| `dossier/indexer.py` → heuristic `"adr"` filename match | Discovery already works | Register in `expected-artifacts.yaml` | Replace heuristic with typed loader |
| `expected-artifacts.yaml` → `optional_always` | Optional artifact registration | Add `adrs/*.md` entry | Schema-validate via `AdrArtifact` |
| Architect Alphonso profile → `adr-drafting-workflow` tactic | Profile declares intent; tactic has no output path | ADR template gives it a landing zone | Full procedure wired to CLI creation |
| `charter.context` section anchors | `docs/adr/2.x/` appears as authority path | Mission-local path added | ADR status surfaced in governance context |
