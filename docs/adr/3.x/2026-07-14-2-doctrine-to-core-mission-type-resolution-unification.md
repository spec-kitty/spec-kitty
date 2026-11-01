---
title: 'ADR: Doctrine → Charter → Core Mission-Type Resolution Unification (governance first)'
description: '`resolve_mission_type_context` becomes the one charter-mediated mission-type resolver; an unknown type hard-errors instead of defaulting or being inferred from `template_set`.'
status: Accepted
date: '2026-07-14'
doc_status: active
kind: ADR
updated: '2026-07-14T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty resolves per-mission-type behaviour — governance, templates, gates,
step contracts — through **two parallel trees and three competing governance
surfaces**, with a hardcoded `software-dev` bias woven through the core loop.

The two trees:

- `src/doctrine/missions/<type>/` — the canonical catalogue. It is already the
  source of truth: `MissionTemplateRepository.default_missions_root()`
  (`doctrine/missions/repository.py:98-110`) resolves here, and
  `template/manager.py:88` copies it into the deployed `.kittify/missions/`.
- `src/specify_cli/missions/<type>/` — **derived copies** that several core
  readers still bind to directly (dossier `ManifestRegistry.load_manifest`,
  `dossier/manifest.py:163-193`; `_packaged_missions_dir`, `mission.py`; template
  resolution, `core/project_resolver.py`). The two trees have already drifted with
  no parity guard (see #2628) — and the drift runs **specify_cli-ahead**: the
  `specify_cli` copies carry live entries (e.g. `runtime.charter-lint.decay` →
  `lint-report.json`, a `blocking: false` flag) that the doctrine copies lack.
  The doctrine-side `expected-artifacts.yaml` reader (`repository.py:304`) exists
  but is **dead** (tests-only).

The three governance surfaces per mission type:

- `mission_types/<type>.yaml` `governance_refs` — **inert** (no runtime reader;
  only CLI display) and **dangling**: `software-dev.yaml:11-12` references
  `DIR-010/DIR-011`, which resolve to nothing (real ids are `DIRECTIVE_0NN`).
- `missions/<type>/governance-profile.yaml` `selected_*` — live via
  `prompt_builder.py:346`, correctly keyed off `meta.json mission_type`,
  **hard-fails** rather than falling back — but ships **empty** for all four types.
- `missions/<type>/actions/<action>/index.yaml` — live, populated, action-grained,
  generating DRG `scope` edges consumed by `charter context --action`.

The concrete defect this creates: the action-scoped path infers mission type as
`(template_set or "software-dev-default").removesuffix("-default")` in
`_load_action_doctrine_bundle` (`charter/context.py:865`, reached from both
`build_charter_context:252` and `build_charter_context_json:3254`). A
documentation, research, or plan mission that never set `template_set` silently
loads **software-dev** doctrine. This is exactly the failure #883 exists to close:
non-software missions inheriting test-first/implementation/code-review doctrine by
default. A **second incarnation** of the same default lives in
`specify_cli/mission.py:575` (`get_mission_type` returns `software-dev` when
`meta.json` omits the key), and it feeds the **dossier** path — so the leak has
two surfaces, and one of them (dossier) sits behind a package boundary the charter
layer may not import.

Underlying all of this is a north-star intent the team has now made explicit: the
`src/specify_cli/missions/` tree should eventually be **deleted**, and
`software-dev` should become an ordinary built-in **doctrine** mission type on
equal footing with `documentation`, `research`, and `plan` — feeding step
contracts, gates, and templates from the doctrine, **through the charter**, into
the execution loop, with no `software-dev-default` special-casing and no
hardcoded core knowledge of `software-dev`.

This ADR records the architecture that gets us there and the decision to land
mission-type **governance** as its first proven slice (issue #883). Its claims and
work breakdown were pressure-tested by an adversarial four-lens second-opinion
review before acceptance; the review's corrections are folded in below.

## Decision Drivers

- **Single canonical authority (DIRECTIVE_044).** Three governance surfaces and
  two mission trees violate single-source; a fix that adds a fourth surface or a
  "keep the trees in sync" guard entrenches the split instead of removing it.
- **Close the software-dev-default leak by construction (DIRECTIVE_043)** — on
  every surface that carries it, not only the prompt path.
- **Layered, mission-aware governance (issue #883, epic #461, #832).** Governance
  must resolve as `project_charter ⊕ shipped_mission_type ⊕ project_override`,
  keyed off `meta.json mission_type`, overridable in #832's shipped → org →
  project order.
- **Extend, do not invent (#2628 lesson).** Reuse existing doctrine machinery
  rather than parallel declaration/merge mechanisms — while being honest about
  where "reuse" still requires real adapter work.
- **A widening seam, not a governance dead-end.** Doctrine *offers*, charter
  *activates and customises*, core (an FSM "semi-prepared for states & transitions
  as config") *consumes*. The resolution seam #883 builds must be the general path
  templates, gates, and step contracts flow through next.
- **The doctrine path goes live; the `specify_cli` path is removed — a transparent
  swap.** The dead doctrine read-paths become the live source of truth and the
  derived `specify_cli/missions/` copies are deleted, with behaviour preserved so
  the user never notices the swap. Preservation is verified by **transitional**
  parity scaffolding that is added at the start of the migration and **deleted
  before merge** — not by a surviving parity gate. Enduring verification is
  behavioural, at the doctrine-module and integration level.
- **No code kept solely to avoid test churn.** Tests are expected to change
  substantially; shims, compat wrappers, and signatures preserved only to keep old
  callers green are anti-patterns here. The suite is updated to assert the new
  behaviour rather than the code contorted to protect the old suite.
- **The `MissionType` doctrine artefact becomes load-bearing.** It is enhanced to
  be the single doctrine answer to "what is this mission type, what steps does it
  contain, what gates are checked?" — its steps (action sequence / step contracts),
  its gates (expected-artifacts), and its governance all resolve *through* it,
  doctrine → charter → core. It stops being a mostly-inert descriptor.

## Considered Options

1. **Populate `governance_refs`** (the 2026-07-04 triage's suggestion).
2. **Fill `governance-profile.yaml` only**, leaving the action-scoped leak in place.
3. **A unified `doctrine → charter → core` resolution seam** — one charter-mediated
   resolver keyed off `meta.json`, feeding both consumers; governance as the first
   slot of a bundle whose later slots are templates/gates/step contracts;
   `governance_refs` retired; the leak closed; `software-dev` demoted to a peer —
   **chosen**, delivered as slice 1 of a `specify_cli/missions` retirement epic.
4. **Full dual-tree merge now.**

## Decision Outcome

**Chosen option:** "A unified `doctrine → charter → core` resolution seam"
(Option 3), delivered as **slice 1 of a `specify_cli/missions` retirement epic**.

### Decisions recorded

- **One charter-mediated resolver.**
  `charter.mission_type_profiles.resolve_mission_type_context(repo_root, *,
  mission_type=None, feature_dir=None) -> ResolvedMissionType` is the single entry
  point for per-mission-type resolution. It resolves the type from an explicit
  argument → `feature_dir/meta.json` → **hard error for an *unknown* type**. It
  never infers the type from `template_set` and never defaults to `software-dev`.
  It subsumes three functions already keyed by mission type
  (`resolve_action_sequence:266`, `resolve_mission_type_governance:325`,
  `load_profile:175`); their live callers (including the 5 FSM-path callers of
  `resolve_action_sequence`) are **migrated onto the resolver**. A former function
  is kept only where it is genuinely the right long-term API, never as a wrapper
  retained solely to avoid editing callers. Their **two distinct hard-fail
  policies** — action-sequence validates against the activation set with no escape
  hatch; governance tolerates an unknown type when a project override exists
  (`:392`) — are preserved as explicit branches, not flattened.
- **Known-type-with-empty-grain is legitimate, not an error.** `plan` ships no
  action indices and an empty type-grain today; a known mission type resolving to
  an empty governance set is valid. Only an *unknown* mission type hard-fails.
- **A bundle sourced from the load-bearing `MissionType` artefact.**
  `ResolvedMissionType` carries populated `governance`, `action_sequence`,
  `expected_artifacts` (gates), and `step_contracts` (steps) slots in slice 1; the
  `template_set` slot is populated in a later slice. All slots are sourced from the
  doctrine `MissionType` artefact and the files it references (a sibling
  `governance-profile.yaml`, the action indices, the step contracts, and
  expected-artifacts), never from the `specify_cli` copies. The bundle is how the
  artefact becomes load-bearing at the core. **(Operator decision Q3: slice 1
  covers governance + gates + steps; templates follow.)**
- **Ordered, structured output.** Governance resolves to a structured
  `ResolvedGovernance` whose selections are **ordered** (list-backed with an
  explicit, tested sort — not sets), so rendering is deterministic. Determinism is
  a correctness property of the resolver (verified by a doctrine-module test), not a
  reason to freeze a byte-snapshot of the old path forever.
- **Both live consumers converge on the resolver.** The rewire targets the *live*
  code: `prompt_builder.py:346` (Surface B) and `_load_action_doctrine_bundle`
  (`context.py:865`, reached via `build_charter_context:252` **and**
  `build_charter_context_json:3254`). The dead `_render_action_scoped:1500` /
  `_append_action_doctrine_lines:1451` pair and its lone test are **deleted**, not
  threaded.
- **Close the leak by threading the real mission type — with per-entry behaviour.**
  `mission_type`/`feature_dir` is threaded into the two live `build_charter_context*`
  entry points; the ~40 test callers are **updated to the new signature** (not
  shielded by a compat overload kept solely to avoid editing them). Behaviour is
  defined **per entry**, not as a blanket hard-fail: the prompt path supplies
  `feature_dir`; planning-from-root (`charter/context.py:90`) requires an explicit
  `--mission-type`; the genuinely mission-less callers (dispatch `executor.py:270`,
  and `workflow.py:675`, which already degrades to `"Governance: unavailable"`) get
  a defined neutral/degrade path, never a silent software-dev load.
- **A single mission-type canonicalizer (`WP-CANON`), across the package boundary.**
  The type key is read raw in at least two places — `mission_type_profiles.py:380`
  and `specify_cli/mission.py:575` (the latter silently defaulting to
  `software-dev`). Because `charter/` may not import `specify_cli` (layer rule,
  `test_layer_rules.py`), the canonicalizer lives where both may consume it, and
  `get_mission_type`'s software-dev default is removed. Until this lands, the leak
  is closed on the prompt/action-doctrine path but **remains live on the dossier
  path**; the ADR does not claim otherwise.
- **The inert `governance_refs` field is replaced, not merely dropped.** The
  hand-authored, dangling `governance_refs` (`models.py:186`, CLI display
  `mission_type.py:1486,1505`, dangling `software-dev.yaml:11-12`) is removed —
  but the *intent* it gestured at (a mission type declaring its governance) is
  fulfilled properly by the load-bearing artefact: governance resolves through the
  charter-mediated resolver keyed by the type, DRG-resolvable, no danglers.
  **(Operator decision Q1: the `MissionType` artefact *references* the live sibling
  `governance-profile.yaml` for type-grain governance — the schema'd, hard-failing
  surface the resolver already reads — rather than absorbing governance as a field;
  governance-profile.yaml is not retired.)** This removes the inert field and its
  authored content updates the tests that asserted it
  (`test_mission_type_repository.py:44`,
  `test_charter_mission_type_commands.py:242,247`, `test_activation_filtered_drg.py`
  docstring, the `drg.py:169` comment) to the new behaviour — the tests move with
  the behaviour, they are not preserved to keep the field alive.
- **Two governance grains, unioned, URN-normalized disjointness.**
  `actions/<action>/index.yaml` is the canonical **action-grain** (already live +
  DRG scope edges, config-stem ids); `governance-profile.yaml selected_*` is the
  canonical **type-grain** (and the project-override target). The resolver unions
  and de-dupes them; a guard forbids the same artifact in both grains, **after
  normalizing both grains to canonical URNs** (string equality across `003-…` vs
  `DIRECTIVE_003` vs a URN gives false assurance). This is "two mechanisms with a
  canonical-URN disjointness guard," not a claim of a single authored surface.
- **Per-type project override — via the overlay stack, with the real adapter cost
  named.** The override lives at
  `.kittify/doctrine/mission_types/<type>/governance-profile.yaml` and rides the
  existing `doctrine/base.py` builtin → org → project overlay loader
  (`base.py:213-311`) with its field-merge and `DoctrineLayerCollisionWarning`.
  This is **not free**: `base.py:249` keys overlays on an `id` field and skips
  files without one, and `governance-profile.yaml` keys on `mission_type`.
  **(Operator decision Q2: ride the overlay stack.)** `WP-OVERRIDE` adds an `id` to
  `MissionTypeProfile` (a coordinated `extra="forbid"` change across the built-in
  files) plus a `BaseDoctrineRepository[MissionTypeProfile]` subclass, so the
  override flows through the same builtin → org → project loader every other
  doctrine artefact uses — giving #832 org-layer support and collision auditing for
  free once the adapter exists. A bespoke second field-merge in the resolver was
  rejected to avoid a duplicate merge site. `WP-OVERRIDE` owns the adapter and ships
  its own precedence + collision test.
- **Governance is a sibling of the state list, not a property of it.** Keyed off
  the same `mission_type` the FSM uses for `action_sequence` (`decision.py:601`,
  `runtime_bridge_composition.py:186`), never attached to individual state
  definitions — so the two config axes stay separable when full "states as config"
  lands.
- **`software-dev` becomes a peer doctrine type** with no new authoring; its
  effective governance is **preserved so the user does not notice the swap** —
  verified by *transitional* parity scaffolding (deleted before merge), not locked
  by a surviving gate. Only documentation, research, and plan gain content. The
  surviving `meta.json`-less fallback to `software-dev` in `mission.py` is scoped to
  **template-file selection**, not governance, after `WP-CANON`.

### Corollaries (scope boundaries)

- **#883 delivers slice 1, not the whole retirement.** In scope: `WP-CANON`, the
  resolver seam, the leak fix, `governance_refs` retirement, the per-type override
  (ridden through the overlay stack), authored governance for
  documentation/research/plan, **step-contract resolution through the artefact
  (Q3)**, one **gated** reader migration for gates (see below), and the enforcement
  gates. Out of scope, left as clean seams: **template resolution** (`template_set`
  slot), enumeration / `mission-runtime`, removing the `software-dev` fallback in
  `mission.py:466,469`, and finally deleting the copy step
  (`template/manager.py:88`) and the `specify_cli/missions/` tree.
- **The dossier migration is a gated, isolated swap (operator decision).** The dead
  doctrine reader goes live and the `specify_cli` copies are removed, user-invisibly.
  It runs as a detachable lane, **non-blocking for the enforcement gate**: (1)
  reconcile the drifted `expected-artifacts.yaml` **upward** into the doctrine tree
  (porting the `runtime.charter-lint.decay`/`lint-report`/`blocking` entries); (2)
  add a **transitional** dossier content-parity test proving software-dev's resolved
  required-artifact set is unchanged across the swap — this scaffold is **deleted in
  this lane's final commit**, not merged; (3) build the `ConfigResult` →
  `ExpectedArtifactManifest` adapter (`repository.get_expected_artifacts` returns
  `ConfigResult`, not the model the six consumer sites expect, and there is no
  `from_dict` today) with cache preservation; (4) flip the reader; (5) delete the
  `specify_cli` copies. Never delete before the parity scaffold is green; delete the
  scaffold once the swap is proven. The enduring dossier-behaviour assertions live
  as doctrine-module + integration tests against the now-canonical doctrine tree. If
  reconciliation reveals deep drift, only the final flip defers to slice 2.
- **The mission-instance addendum layer is specified but not built** (a future
  `meta.json governance_addendum` as the highest field-merge layer) — deferred,
  YAGNI.
- **The dual-tree split is on the deprecation path, not entrenched.** No new
  content is added to `specify_cli/missions/`; and critically **no surviving
  "keep in sync" or parity ratchet is introduced** — a permanent parity gate would
  entrench the very split this swap removes. Parity is proven transitionally and the
  scaffold is deleted; the copies are removed, leaving one source.
- **Testing posture (operator-mandated).** Parity/snapshot tests are transitional
  migration scaffolds — added at the start of a swap, deleted before merge. Enduring
  tests verify **behaviour** and shift down to **doctrine-module unit tests +
  integration-level checks** (e.g. "a documentation mission resolves documentation
  governance and gates, not software-dev doctrine"), not byte pins on the removed
  path. No code — wrapper, shim, or preserved signature — is kept solely to avoid
  updating tests; the suite is expected to change substantially and is updated to
  the new behaviour.

### Work-package spine (as refined by the second-opinion review)

Four lanes; ~10–12 WPs (Q3 adds the steps lane). Lane A: **WP-TIDY** (remove the
inert `governance_refs` + dangling refs; behaviour-preserving; first). Lane B
(critical path): **WP-CANON** (single mission-type canonicalizer) → **WP-SEAM**
(resolver + ordered `ResolvedGovernance` + `MissionType`-artefact-sourced bundle +
Surface B rewire; a *transitional* byte-parity scaffold guards the swap and is
deleted in this lane's final commit) → **WP-LEAK** (rewire the live Surface A
bundle + delete the dead pair + split `template_set`; red-first behavioural test
first) → **WP-OVERRIDE** (per-type override ridden through the overlay stack: `id`
on `MissionTypeProfile` + `BaseDoctrineRepository` subclass + precedence/collision
test). Lane C (parallel authoring): **WP-CONTENT-DOC / -RESEARCH / -PLAN** — split
×3 because "author 3 sets" hides **6–8 net-new DRG-resolvable artifacts**
(Divio-type, plain-language, accessibility, publication, freshness-SLA styleguides;
citation discipline; and the already-referenced-but-missing `spike-timebox-policy`
procedure). Lane D (detachable, non-blocking): **WP-GATES-RECONCILE** →
**WP-GATES-MIGRATE** (gates/dossier swap; transitional dossier-parity scaffold,
deleted at the end of the lane) and **WP-STEPS-MIGRATE** (route step-contract
resolution through the artefact bundle and off any `specify_cli` path; same
transitional-parity-then-delete discipline). Join: **WP-ENFORCE** — the *enduring*
behavioural non-leakage/non-vacuity assertions, authored as **doctrine-module +
integration tests**, not a surviving parity ratchet. Transitional parity scaffolds
are added at each swap's start and deleted before merge; enduring tests verify
behaviour and move down to the doctrine module + integration level. Tests are a
first-class, per-WP change surface — and the suite is expected to change
substantially rather than be shielded by compat shims.

### Consequences

#### Positive

- The software-dev-default leak becomes impossible by construction on the
  action-doctrine path in slice 1, and on the dossier path once `WP-CANON` +
  the gated migration land.
- Governance collapses from three surfaces + a dead field to two URN-normalized
  grains resolved through one function, overridable via the established overlay
  stack.
- After slice 1 the core is measurably **less** dependent on
  `specify_cli/missions/` (the dossier gate reader is migrated behind a parity
  gate and the derived `expected-artifacts.yaml` copies are deleted), and a proven
  `doctrine → charter → core` path exists for later slices to widen to templates
  and gates by filling a reserved slot and repointing one reader each.
- `software-dev` loses its special status with no behavioural change.

#### Negative

- The rerouting risks reordering/de-duping software-dev directives; because the
  existing content-contract suite is substring-based, the swap is guarded by
  **transitional** byte- and dossier-parity scaffolds (deleted before merge), with
  enduring behaviour verified by doctrine-module + integration tests — real test
  work, and a deliberate rewrite of the suite rather than compat-shielding it.
- The per-type override and the dossier migration each carry named adapter cost
  (overlay `id` handling; `ConfigResult` → `ExpectedArtifactManifest`); neither is
  the "free repoint" a naive reading would assume.
- Slice 1 populates governance, gates, and steps; the `template_set` slot is
  declared on the artefact but populated in a later slice.

#### Neutral

- This ADR does not migrate templates or the remaining `specify_cli/missions/`
  readers (enumeration, `mission-runtime`, the copy step), and does not delete the
  tree; those are explicit later slices of the retirement epic.

### Confirmation

Two kinds of check confirm the mission — and only the first kind survives it.

**Enduring (behavioural, doctrine-module + integration):** (1) each non-software
mission's **unioned (type ⊕ action)** resolved set is disjoint from a curated,
URN-normalized software-dev-only denylist, with a **non-vacuity twin** proving
software-dev *does* resolve that set (exercised through a *shared* action name so it
cannot pass vacuously); (2) an *unknown* `mission_type` hard-fails on every
resolution path while a *known type with an empty grain* (e.g. `plan`) resolves
empty without error; (3) the doctrine `MissionType` artefact is the sole source of
type/steps/gates/governance and every authored governance id resolves in the DRG;
(4) an integration check exercises a real documentation/research/plan mission and
observes domain-appropriate governance and gates, no software-dev doctrine.

**Transitional (parity scaffolds, deleted before merge):** software-dev's rendered
governance and its resolved dossier required-artifact set are proven unchanged
across each swap (the `lint-report` entries reconciled upward first); these scaffolds
verify the swap is user-invisible and are then removed, so no parity ratchet
survives to re-entrench the split. The mission is *not* confirmed by keeping the old
substring content-suite frozen; that suite is rewritten to the new behaviour.

### Decisions resolved with the operator (formerly open)

- **Q1 — Governance declaration shape:** the `MissionType` artefact **references a
  sibling `governance-profile.yaml`** for type-grain governance (the live, schema'd,
  hard-failing surface the resolver already reads), unioned with the action-grain
  `actions/<action>/index.yaml`. governance-profile.yaml is kept, not absorbed into
  `mission_types/<type>.yaml`. Lower churn; the override rides the profile.
- **Q2 — Overlay adapter form:** **ride the `doctrine/base.py` overlay stack.**
  `WP-OVERRIDE` adds an `id` to `MissionTypeProfile` + a `BaseDoctrineRepository`
  subclass so per-type overrides get builtin → org → project ordering and collision
  warnings from the shared loader (and #832 org-layer support) rather than a bespoke
  second merge site.
- **Q3 — Artefact depth in slice 1:** **governance + gates + steps.** Step-contract
  resolution routes through the artefact bundle in slice 1 (`WP-STEPS-MIGRATE`);
  only `template_set` (templates) defers to a later slice.
- **Q4 — ADR meta:** **Accepted, epic altitude** (this record; one ADR governs the
  retirement arc, with #883 as slice 1).

Genuinely still open (settled inside the named WPs, not architecture-level): the
exact denylist membership for the non-leakage test, and the precise per-entry
degrade behaviour for the mission-less `build_charter_context` callers.

## Pros and Cons of the Options

### Option 1 — Populate `governance_refs`

**Pros:** matches the field's apparent intent; smallest edit.

**Cons:** inert (no runtime reader); cannot carry the tactics/styleguides/
procedures/paradigms non-software governance is made of; changes `graph.yaml` by
nothing, so the freshness gate gives false assurance. Leaves the leak and the
split untouched.

### Option 2 — Fill `governance-profile.yaml` only

**Pros:** ships non-software content on the live prompt path with no new plumbing.

**Cons:** leaves the action-scoped and dossier-path leaks in place — the headline
acceptance criterion stays unmet — and does nothing toward the north star.

### Option 3 — Unified `doctrine → charter → core` seam (CHOSEN)

**Pros:** closes the leak on the action path (and the dossier path via `WP-CANON` +
the gated migration); collapses three surfaces + a dead field to two
URN-normalized grains + one resolver; reuses the overlay stack for layering
(adapter cost named, not hidden); demotes `software-dev` to a peer with no
behavioural change; leaves a proven, widening seam for later slices.

**Cons:** larger than a content-only change; centralises resolution (mitigated by
a new ordered byte-snapshot gate + dossier parity gate); names real adapter work
on the override and dossier surfaces; forward-shapes reserved bundle slots.

### Option 4 — Full dual-tree merge now

**Pros:** reaches the end-state in one mission.

**Cons:** unbounded blast radius across every `specify_cli/missions/` reader in a
single change; high regression risk against software-dev; violates the slice
discipline that lets each reader migration be independently verified.

## More Information

- Technical story: [#883](https://github.com/Priivacy-ai/spec-kitty/issues/883)
  (slice 1) under epics [#461](https://github.com/Priivacy-ai/spec-kitty/issues/461),
  [#901](https://github.com/Priivacy-ai/spec-kitty/issues/901); related
  [#832](https://github.com/Priivacy-ai/spec-kitty/issues/832),
  [#2628](https://github.com/Priivacy-ai/spec-kitty/pull/2628).
- This ADR was refined by an adversarial four-lens second-opinion review
  (test-strategy, architecture-refutation, implementer-reality, slice-discipline);
  the corrections — dead-code leak anchors, the cross-boundary `mission.py:575`
  default, the non-free overlay adapter, the substring-not-byte content suite, the
  drifted expected-artifacts trees, and the `plan` empty-grain policy — are folded
  into the decisions above.
- Governing layer-merge contract reused:
  [2026-05-16-1 — Doctrine-Layer Merge Semantics](2026-05-16-1-doctrine-layer-merge-semantics.md).
- Adjacent resolution-seam precedent:
  [2026-07-08-1 — MissionResolver Port](2026-07-08-1-mission-resolver-port.md),
  [2026-06-26-1 — Single-Authority Seam + Call-Site Gate](2026-06-26-1-single-authority-seam-and-call-site-gate.md).
- Load-bearing anchors: seam `charter/mission_type_profiles.py:175,266,325,392,440`;
  live consumers `runtime/next/prompt_builder.py:346`, `charter/context.py:252,865,3254`;
  dead pair to delete `charter/context.py:1451,1500`; canonicalizer targets
  `charter/mission_type_profiles.py:380`, `specify_cli/mission.py:575`; overlay stack
  `doctrine/base.py:213,249,289-311`; FSM reads `decision.py:601`,
  `runtime_bridge_composition.py:186`; retirement targets dossier
  `dossier/manifest.py:163-193` → dead doctrine reader
  `doctrine/missions/repository.py:304`, copy step `template/manager.py:88`,
  hardcoded software-dev `mission.py:466,469`; retired field `models.py:186`,
  `mission_type.py:1486,1505`; dangling refs `software-dev.yaml:11-12`;
  content suite (substring, not byte) `tests/specify_cli/next/test_wp_prompt_governance_contract.py`.
