---
title: 'Issue #1111 Analysis — Branch Alignment Report'
description: "Architect Alphonso's branch-alignment analysis for issue #1111: how the affected branches diverge and what alignment is needed (2026-05-18)."
doc_status: deprecated
updated: '2026-08-12'
---
> **RETIRED (shipped)** — Epic [#1111](https://github.com/Priivacy-ai/spec-kitty/issues/1111)
> closed 2026-06-02 as COMPLETED; its close-out comment confirms the primary 3.2.0
> Charter/Doctrine release-critical scope this branch-alignment report analyzed shipped.
> Retained for historical reference; do not consult for current behavior.

# Issue #1111 Analysis — Branch Alignment Report

**Author:** Architect Alphonso (ad-hoc profile session)  
**Date:** 2026-05-18  
**Branch:** `feat/org-doctrine-layer`  
**Issue:** [Priivacy-ai/spec-kitty#1111](https://github.com/Priivacy-ai/spec-kitty/issues/1111) — *EPIC: 3.2.0 release work: Charter / Doctrine enhancement and remediation*

---

## 1. Branch summary

This branch carries **two completed missions** (both 100% `done`) plus their post-merge
remediations:

| Mission | ID | Slug | Status |
|---|---|---|---|
| A — Layered Doctrine Resolution (Org Layer) | 01KRNPEE | `layered-doctrine-org-layer-01KRNPEE` | merged, post-merge reviewed, HIGH-1/2 + MEDIUM-1 remediated |
| B — Charter-Mediated Doctrine Selection | 01KRTZCA | `charter-mediated-doctrine-selection-01KRTZCA` | 9/9 WPs done, squash-merged |

The branch currently tracks `feat/org-doctrine-layer` and is ahead of `main` by ~70+
commits. It is the accumulation point for the doctrine / charter subsystem rewrite that
feeds the 3.2.0 milestone.

---

## 2. Issue #1111 slice map — what is done, what is pending

The epic groups work into six slices (A–F). The table below cross-maps each slice and
its child tickets to the branch's missions.

### Slice F — Multi-context extensibility *(the slice this branch primarily implements)*

| Ticket | Title | Branch coverage |
|---|---|---|
| #832 | Organisation-layer DRG for proprietary governance and custom missions | **DONE** — Mission A (`layered-doctrine-org-layer-01KRNPEE`) is the direct implementation of #832. Three-layer resolution (`built-in → org → project`), `doctrine fetch` (git / HTTPS / API sources), `pack validate`, `pack assemble`, `doctor doctrine`, org-charter pre-fill, and `DoctrineLayerCollisionWarning` are all shipped. FR-001 through FR-029 (Mission A spec) map to this ticket. |
| #682 | Composable workflow sequencing | **PARTIAL** — Mission B's WP08 (mission-type profiles) ships per-mission-type governance profiles (`documentation`, `research`, `plan`, `software-dev`). This makes the *governance selection* per-mission-type composable. The action *sequence* itself (the `specify → plan → tasks → implement → review → merge` order) remains hardcoded. Full composable sequencing is not in scope for either mission on this branch. |
| #522 | [ADR-8] Monorepo / cross-repo charter visibility | **NOT started** — ADR-8 is referenced in Mission A's spec (FR-025 org-charter, FR-029) as a future design. No implementation landed. The `charter._drg_helpers._resolve_org_root` stub is *intentionally inert* (per the architecture review); org-root resolution lives in `specify_cli.doctrine.config.resolve_org_roots` and the cross-repo extension point is not yet wired. |

### Slice A — Lifecycle freshness & health UX

| Ticket | Title | Branch coverage |
|---|---|---|
| #1099 | `charter lint` must lint shipped graph plus optional project overlay | **PARTIAL** — Mission B added `OrgOverridesBuiltinChecker` and `OrgCharterDeviationChecker` to `charter_lint`. The org-layer lint surface exists. However, the specific complaint in #1099 ("`Scanned 0 nodes` / `No decay detected`" when the project DRG is silently absent) is about the *existing lint engine*'s silence on missing project DRG — the org-layer lint additions do not close that gap. |
| #1100 | Add session-start charter preflight for stale or missing synthesized doctrine | **NOT started** — `docs/development/doctrine-artifact-selection-preflight.md` was an internal design document produced during Mission B planning; it is not the session-start preflight described in #1100. No CLI hook at session start has been added. |
| #1101 | `charter status` must report synthesis freshness and missing project DRG state | **NOT started** |
| #1104 | `charter synthesize` bootstrap contract must produce or explicitly skip project DRG | **PARTIAL** — Mission A's synthesizer pipeline (`charter.synthesizer.*`) was refactored and extended. The `resynthesize_pipeline.py`, `write_pipeline.py`, and `validation_gate.py` files all changed. However, the explicit skip/produce contract described in #1104 (a caller-visible result distinguishing "produced" from "skipped in shipped-only mode") is not documented as an explicit deliverable in either mission's acceptance criteria. |

### Slice B — CI / release integrity

| Ticket | Title | Branch coverage |
|---|---|---|
| #1103 | CI must fail when committed shipped DRG is stale | **NOT started** — The branch adds a migration chain integrity gate (`tests/architectural/test_migration_chain_integrity`) and a no-dead-modules gate, but there is no CI job that regenerates `src/doctrine/graph.yaml` and diffs it against the committed copy. |

### Slice C — Repository / git policy

| Ticket | Title | Branch coverage |
|---|---|---|
| #1102 | Define and enforce git policy for charter and synthesized doctrine artifacts | **NOT started** — The branch modifies `.kittify/charter/charter.md` (updated for the new missions) but does not add a documented git policy for charter and doctrine artifacts. |

### Slice D — Dashboard parity

| Ticket | Title | Branch coverage |
|---|---|---|
| #1098 | Dashboard glossary tab renders empty when one seed term is not normalized | **NOT started** |

### Slice E — Source-of-truth clarification

| Ticket | Title | Branch coverage |
|---|---|---|
| #1007 | Clarify charter source of truth for projects with existing constitutions | **NOT started** |
| #1013 | Implement charter governance references and external-doc guidance | **PARTIAL** — `docs/development/runtime-charter-doctrine-boundary.md` and `docs/architecture/org-doctrine-layer.md` are net-new explanatory docs. They address the org-layer surface but not the general "which charter wins" question for pre-existing constitutions. |

---

## 3. Architectural assessment

### What the branch delivers well

**Three-layer doctrine resolution** is the structural centrepiece of Slice F. The branch
ships it end-to-end:

- `built-in → org → project` resolution with field-level merge and `DoctrineLayerCollisionWarning`
  (ADR `2026-05-16-1` documents the design rationale).
- Three fetch-source adapters (`GitSource`, `HttpsBundleSource`, `ApiSource`) with
  network calls confined strictly to `doctrine fetch` (Constraint C-001 preserved).
- `pack validate` and `pack assemble` as pre-publication tooling.
- `doctor doctrine` as the operator-facing unified view of the doctrine stack.
- **Charter-mediated selection** (Mission B): the charter is now the single authority
  over which doctrine artifacts are active per mission; the runtime reaches doctrine
  only through charter-exposed facades. Mission-type profiles (`software-dev`,
  `documentation`, `research`, `plan`) make governance per-mission-type composable.

**Architectural boundary** (`kernel ← doctrine ← charter ← specify_cli`) holds across
both missions. 96 architectural layer-rule tests pass at HEAD.

### Where the branch under-delivers relative to #1111

1. **Composable workflow sequencing (#682) is incomplete.** Mission B's mission-type
   profiles make governance *context* composable per mission type. The action *sequence*
   (`specify → plan → tasks → implement → review → merge`) is not yet a first-class
   overridable artifact. The epic acceptance test for #682 — *"mission action sequences
   are composable via the same first-class artifact pattern used by agent profiles,
   tactics, and step contracts already are"* — is not yet met.

2. **Monorepo / cross-repo charter visibility (#522) is unstarted.** The `_resolve_org_root`
   stub is intentionally inert. No per-package vs shared-root scoping exists.

3. **Slice A lifecycle UX (#1099–#1104) is largely untouched.** The session-start
   preflight (#1100) and `charter status` freshness reporting (#1101) are zero-started.
   The lint gap (#1099 — "Scanned 0 nodes" on missing project DRG) is not addressed by
   the org-layer lint additions.

4. **CI integrity (#1103) is not covered.** No job regenerates and diffs `src/doctrine/graph.yaml`.

5. **Dashboard glossary parity (#1098) is not covered.**

### Open technical debts on this branch

The architecture review (`docs/development/org-doctrine-layer-architecture-review.md`)
catalogues seven follow-ups. The ones with architectural bearing before #1111 can close:

| Follow-up | Severity | Relation to #1111 |
|---|---|---|
| ~30 glossary concepts unglossed | HIGH | Slice E / ADR-8 design work will be hampered by vocabulary drift |
| `DoctrineLayerCollisionWarning` carries string not structured data; `doctor.py` regex-parses it | MEDIUM | Risk of silent breakage in `doctor doctrine` output; affects Slice A (#1104 "contract must be precise") |
| `_resolve_org_root` is an inert stub without a deprecation marker | LOW | Misleads future readers of the monorepo / cross-repo work (Slice F #522) |
| `apply_org_charter_to_interview` not wired in non-interactive compile path | MEDIUM | Org charter pre-fill is missing from agent-driven bootstraps; affects Slice A UX intent |
| Blueprint `layered-doctrine-resolution-design.md` "full-replace" row not yet marked superseded | LOW | Documentation hygiene before any downstream mission reads it |

---

## 4. Mapping to epic acceptance criteria

The epic's acceptance criteria for `3.2.0 stable`:

| Criterion | Status on this branch |
|---|---|
| All Primary scope child tickets closed with evidence | **NO** — #682 and #522 are incomplete; #1099–#1104 and #1098 are untouched |
| Fresh-clone smoke: `charter status` reports stale/missing project DRG correctly | **NOT VERIFIED** — #1101 not implemented |
| Fresh-clone smoke: `charter lint` lints shipped + project overlay | **PARTIAL** — org-lint checks added; baseline "Scanned 0 nodes" gap (#1099) not addressed |
| Fresh-clone smoke: `charter synthesize` bootstrap produces project DRG or explicitly skips with known contract | **UNCERTAIN** — synthesizer refactored but explicit skip/produce contract not acceptance-tested |
| Fresh-clone smoke: session-start preflight catches degraded path | **NOT IMPLEMENTED** (#1100) |
| CI fails on deliberately stale `src/doctrine/graph.yaml` | **NOT IMPLEMENTED** (#1103) |
| Dashboard Glossary tab renders all valid terms when one seed term is malformed | **NOT IMPLEMENTED** (#1098) |
| Documented git policy in repo docs, followed by spec-kitty repo itself | **NOT IMPLEMENTED** (#1102) |
| Slice F seams open: three-layer DRG resolution end-to-end | **YES** — Mission A ships this fully |
| Slice F seams open: monorepo / cross-repo charter visibility has a landed design (ADR-8) plus minimum implementation | **PARTIAL** — ADR-8 is referenced; no implementation |
| Slice F seams open: mission action sequences composable via first-class artifact pattern | **NOT MET** — governance context is composable; sequence is not |
| Secondary scope (#1007, #1013, #707) either landed or explicitly deferred with rationale | **PARTIAL** — #1013 partially addressed in explanatory docs; #1007 and #707 not addressed |

---

## 5. Recommended next steps (architecture view)

Ordered by dependency and epic-gate risk:

1. **Composable workflow sequencing (#682)** — This is the highest-value remaining Slice F
   item. Mission-type profiles are now in place as the pattern; extending the same
   first-class artifact approach to the action sequence itself is the logical next mission.
   It unblocks the epic's strictest acceptance test.

2. **Slice A lifecycle UX** — #1100 (session-start preflight) and #1101 (`charter status`
   freshness) are both user-facing failures that the epic description lists as
   "first five surfaced during MVP rehearsal". They should be scoped together as one
   small mission (estimated WP02–WP04 range) to close the session UX gap.

3. **`DoctrineLayerCollisionWarning` structured-data refactor** — Do this before the next
   mission that touches `doctor doctrine`. The regex-parse brittleness is a time-bomb;
   fixing it now is a small, safe change (`base.py` + `agent_profiles/repository.py` +
   `doctor.py` + tests).

4. **Glossary update** — ~30 unglossed doctrine concepts (see architecture review
   section 3 cross-check table). This is documentation, but it gates vocabulary alignment
   for #522 (monorepo design) and #1007 (charter source-of-truth clarification).

5. **CI DRG integrity gate (#1103)** — Standalone CI job; low code-change cost; high
   release-integrity value.

6. **Dashboard glossary parity (#1098)** and **git policy (#1102)** — These are
   independent of the doctrine architecture and can be scoped in parallel with the items
   above.

---

## 6. Verdict

This branch is **architecturally sound for what it implements** and delivers the primary
structural prerequisite for Slice F (#832, partial #682). It is **not yet sufficient**
to close the 3.2.0 epic on its own. The gap is not rework of what is here — the
three-layer resolution, charter-mediated selection, and mission-type profiles are
solid — but a set of distinct remaining slices (Slice A lifecycle UX, Slice B CI
integrity, Slice D dashboard, Slice E source-of-truth, and the sequencing half of
Slice F) that require their own missions or focused PRs.

The branch can merge as a **preview capability** foundation for 3.2.0, with the
remaining slices tracked as explicit follow-on work before the stable tag.
