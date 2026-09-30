---
title: 07 — Existing Infra Pattern + MissionStatus / MissionFlow Extraction Assessment
description: Assessment of mirroring the existing doctrine/charter infra-context pattern for new contexts and whether MissionStatus/MissionFlow can be extracted as domains.
doc_status: deprecated
updated: '2026-06-03'
---
# 07 — Existing Infra Pattern + MissionStatus / MissionFlow Extraction Assessment

This document answers a concrete design instruction: *mirror the existing doctrine/charter
infra-context pattern for the new contexts; centralize their construction; and check whether
**MissionStatus** (aggregate root) and **MissionFlow** (pure-domain FSM driven by mission-type/step
config) are clean extractions.* Read-only investigation, 2026-06-03; `path:line` cited.

**Headline:** the pattern we want to mirror is **already in the codebase and partly already wired
for this exact purpose.** This shifts the design from "invent a context model" to "extend and
unify the one that exists." It also surfaces a **naming collision** we must resolve first.

---

## 1. The existing infra-context pattern (the thing to mirror)

Spec Kitty already implements a clean, layered, "config-bundled-into-an-immutable-snapshot,
roots-passed-as-data" pattern. It is the template for `MissionExecutionContext` / `MissionStatus`.

### 1a. Layered roots as data — `DoctrineService`

`src/doctrine/service.py:22-33` takes **roots as inputs**, not config to read:
```python
def __init__(self, built_in_root=None, project_root=None,
             org_roots=None, active_languages=None): ...
```
- Per-artefact precedence (project > org [later wins] > built-in) is applied **inside each
  repository at load time** (`service.py:35-53`); the service only hands down three roots per artefact kind.
- **Reusable shape:** *service bundles roots; repositories apply precedence.*

### 1b. Frozen context snapshots + guard methods — `PackContext` / `ProjectContext`

- `PackContext` (`src/charter/pack_context.py:74`) — frozen; bundles activation state + `pack_roots`
  (built-in first, then org). Constructed **only** via `PackContext.from_config(repo_root)` (`:151`),
  which reads `.kittify/config.yaml` **once**. **Hard invariant C-005:** the doctrine resolver
  receives a `PackContext` and **never reads config itself** (`pack_context.py:1-20`).
- `ProjectContext` (`src/charter/invocation_context.py:69`) — frozen; bundles
  `repo_root, pack_context, org_root, specs_dir, architecture_dir`. Factory `from_repo(repo_root)`
  (`:88`). **Guard methods** `require_repo_root()/require_pack_context()/require_org_root()` raise a
  typed `ContextPreconditionError` (`:36`) with actionable hints — not `ValueError`.

### 1c. Two-stage construction (pure assembler + root-resolving builder)

- **Pure assembler** reads nothing, just packages caller-supplied data.
- **Root-resolving builder** lives one layer up, calls the canonical root helpers, reads state/config.
- Canonical root helpers (roots-as-data, **C-008: doctrine never reaches into `.kittify`**):
  `resolve_doctrine_root()` (built-in/shipped, `src/charter/catalog.py:153`),
  `resolve_project_root()` (`src/charter/_doctrine_paths.py:36`),
  `resolve_org_roots()` (`src/doctrine/drg/org_pack_config.py:170`),
  `resolve_layer_roots(repo_root) -> {"project","org"}` (`cli/commands/charter/_layer_roots.py:10`).
- Project-root/base-dir helpers: `locate_project_root` (`core/project_resolver.py:16`),
  `get_main_repo_root` (`core/paths.py:219`), `find_repo_root` (`task_utils/support.py:30`),
  `require_explicit_feature` (`core/paths.py:408`).
- The three `.kittify` flavours are classified by the **state-roots** subsystem:
  `StateRoot` enum (`src/specify_cli/state/contract.py`: `PROJECT=.kittify/`, `FEATURE=kitty-specs/<f>/`,
  `GLOBAL_RUNTIME=~/.kittify/`, `GLOBAL_SYNC=~/.spec-kitty/`, `GIT_INTERNAL=.git/spec-kitty/`),
  `check_state_roots` (`state/doctor.py:233`), `get_kittify_home` (`src/kernel/paths.py:24`).

### 1d. Guidance-location resolution (two systems)

- **5-tier template chain** — `src/doctrine/resolver.py:133-213`: OVERRIDE → LEGACY → GLOBAL_MISSION →
  GLOBAL → PACKAGE_DEFAULT, returning frozen `ResolutionResult(path, tier, mission)`. Tier roots
  supplied **as data** by the caller (`TierRoot`, `template_catalog.py:69`).
- **Action-scoped doctrine** — `src/charter/context.py`: `build_charter_context(repo_root, *, action,
  depth, …)` (`:122`) → `PackContext.from_config` → `_load_action_doctrine_bundle` (`:797`) which
  loads the DRG, **filters by activation** (`filter_graph_by_activation`, `:837`), resolves
  `action:{mission}/{action}` (`resolve_context`, `:839-840`), and partitions into
  directive/tactic/styleguide/toolguide buckets. This is "which guidance applies to this action,"
  computed once and bundled.

### 1e. The dependency-direction law (hard constraint on placement)

`kernel ← doctrine ← charter ← specify_cli`, pinned by `tests/architectural/test_layer_rules.py`.
→ A context **dataclass** must live in the lowest layer that can own it (charter); its
**state-reading builder** lives in `specify_cli`/`runtime`. Mirror this split exactly.

---

## 2. ⚠️ `OperationalContext` already exists — naming collision

`OperationalContext` is **already a live, frozen dataclass**: `src/charter/invocation_context.py:155`,
with a pure assembler `build_operational_context()` (`:220`) and a wired builder
`build_operational_context_for_claim()` (`runtime_bridge.py:2119`, explicitly "shared so OC
construction is not forked", `:2133`) plus `_build_operational_context_for_decision()` (`:2182`).

**But its current semantics are runtime-SESSION facts, not filesystem facts:**
`active_model, active_profile, active_role, current_activity, tech_stack`.

The design instruction uses "OperationalContext = filesystem aspects." That is a **different
concept** from the existing object. Per DIRECTIVE_032 (Conceptual Alignment — `04`), we must
resolve this before building. Options to decide in session:

| Option | Effect |
|--------|--------|
| **Keep `OperationalContext` = session facts** (as built) and name the filesystem context separately (e.g. `MissionExecutionContext` / `ExecutionTopologyContext` / `MissionPaths`) | No collision; clearest; matches the existing wiring |
| **Rename existing → `SessionContext`** and free `OperationalContext` for filesystem aspects | Truer to the instruction's wording, but renames a live, wired object (migration cost + churn) |
| **Compose**: `OperationalContext` becomes the umbrella holding both a `session` sub-context and a `topology`/`paths` sub-context | Single object passed through; honors "one context threaded"; bigger object |

> Recommendation to debate: **keep `OperationalContext` as session facts**, introduce the
> filesystem/topology concept under a distinct name, and let a single **central builder** assemble
> the *family* (identity + session + topology + status aggregate). This avoids renaming wired code
> and keeps each context a deep, single-responsibility module.

---

## 3. Central construction point

There is **no DI container**; construction is per-command but de-duplicated through shared builders:
- `_build_doctrine_service_with_org_layer(repo_root)` (`cli/commands/charter/generate.py:24`) — the
  fullest example: resolves all three roots, builds `DoctrineService`, gets `PackContext` via
  `ProjectContext.from_repo(...).require_pack_context()`, wraps in `ActivationDoctrineService`.
- `build_operational_context_for_claim/_decision` (`runtime_bridge.py:2119/2182`) — already the
  shared OperationalContext builder.

**Where the "central CLI module to construct the contexts" should live:** mirror the existing split —
- **dataclasses + pure assemblers** in `charter` (`invocation_context.py`), import-clean of `specify_cli`;
- **root-resolving / state-reading builders** in `specify_cli`/`runtime`. The natural home for a
  unified *mission-runtime context factory* is the proposed `src/specify_cli/mission_runtime/`
  package (doc `06` §4), which would expose one `build_mission_context(cwd, mission, op_kind)` that
  assembles identity → topology → session → status, calling the existing builders rather than forking them.

---

## 4. MissionStatus as aggregate root — assessment

**Verdict: feasible, and `status/` is unusually close** because it is already event-sourced.

### What's already aggregate-shaped

- `reduce(events) -> StatusSnapshot` (`reducer.py:117`) is a **pure deterministic fold = aggregate hydration**.
- `validate_transition(from, to, ctx)` (`transitions.py:266`) is a **pure invariant check**.
- `emit_status_transition_transactional` (`coordination/status_transition.py:378`) **already does the
  aggregate dance ad-hoc**: resolve identity once (`_identity_for_request`), lock
  (`BookkeepingTransaction.acquire`), append, fan out.

### The problem it would fix (the sprawl)

~**130 `read_events`/`materialize`/`get_wp_lane` references across ~24 files** and **14
`emit_status_transition*` callers**, each doing the same triad: `feature_dir = repo_root /
"kitty-specs" / mission_slug` → call primitive. Duplicated literal at `workspace/context.py:357,553,
639,677,733`, `core/worktree_topology.py:137`, `agent_utils/status.py:119`, and ~10 more. *This
triad is exactly what the aggregate absorbs.*

### Proposed interface (collapses the 20-param `emit_status_transition`)

```
status = MissionStatus.load(context)              # context carries mission_id + read/write roots
status.claim(wp_id, actor)                         # internal: validate_transition + guard + in-mem append
status.transition(wp_id, to_lane, actor, *, evidence=…, review_result=…)
status.lane_of(wp_id)                              # replaces get_wp_lane
status.snapshot()                                  # replaces reduce(read_events(...))
status.save()                                      # atomic append under lock + materialize + fanout hook
```

### Invariants it owns (today scattered or single-path)

legal-edge-only transitions (`transitions.py:266`), per-transition guards (`transitions.py:60-78`),
claim-conflict detection (`transitions.py:99-117`), per-transition evidence (`emit.py:211-239`),
one-writer/atomic-batch lifecycle (lock + `append_events_atomic_verified`, `store.py:286`),
rollback-aware hydration (`reducer.py:33-114`).

### Stays OUTSIDE (application services that *query* the aggregate by identity)

- **Dependency gating** (`core/dependency_graph.py:50`) — reads *sibling* WP state; crosses the WP
  boundary, so it must consume the snapshot, not live inside (small-aggregate rule, `04`).
- **Phase resolution** (`phase.py`) — write policy; comes from context.
- **SaaS fan-out / dossier sync** (`emit.py:735`) — post-save side effect in the application layer.
- **Path resolution / canonicalization** — belongs in the injected context.

### Seams to cut (3)

1. **Repository over `store.py`** — wrap `read_events`/`append_event*` behind
   `StatusEventRepository(context)`; all path use is already isolated to `_events_path` (`store.py:94`).
2. **Move path resolution to context** — `_events_path`, `_SlugResolver` (`store.py:99`),
   `materialize` snapshot write (`reducer.py:330`), `_load_mission_id` (`emit.py:61`), lock-root
   inference (`emit.py:354`) all sniff paths today; context supplies them. Resolvers already exist
   (`get_status_read_root`, `canonicalize_feature_dir`, `resolve_mission_read_path`) — consolidation, not new logic.
3. **Wrap reduce/materialize as hydration + projection** — `load = reduce(repo.events())`;
   `save = append_events_atomic_verified(...)` + post-save materialize/fanout.

**Cost:** the mechanical migration of ~130 read + 14 write sites. **Drop, don't migrate:** the
20-param dual-signature and phase-1 frontmatter mirror (`emit.py:305-336`) are legacy cruft.

---

## 5. MissionFlow as pure-domain FSM — assessment

**Verdict: the pure FSM is ~80% already built; the "driven by mission-type config" premise is
net-new design work.**

### What's already pure (no fs/git/cli imports)

- `ALLOWED_TRANSITIONS` (30 edges, `transitions.py:20-57`) + guard fns (`:92-220`) + `validate_transition` (`:266`).
- The **WP State Pattern**: `WPState` ABC + 9 frozen state classes, `wp_state_for()`
  (`wp_state.py`), `TransitionContext` (`transition_context.py`). ADR `2026-04-06-1` proves the two
  representations are equivalent (property-tested).
- Pure gate logic: `dependency_readiness_for_wp` (`core/dependency_graph.py:50`), graph algorithms.

### The gap that makes "MissionFlow" net-new

The lane graph + gates are **100% hardcoded module constants and identical across all 4 mission
types.** `mission_type` flows through the status layer as **display/identity metadata only** — it
**never** parameterizes `ALLOWED_TRANSITIONS` or guards (`transitions.py`/`wp_state.py` contain zero
`mission`/`mission_type` references). A documentation mission and a software-dev mission move their
WPs through the **identical** `planned→…→done` lanes today; their differing `action_sequence` is a
*planning-DAG* concern (`spec-kitty next` / step contracts), orthogonal to the lane FSM.

The latent schema exists but is **unwired**: `MissionOrchestration` (`doctrine/missions/models.py:76-85`)
defines `states + transitions + guards + required_artifacts` — but it is schema-generation-only and
nothing in `status/` consumes it.

### Purity violations to invert (guard inputs gathered via I/O)

`emit.py` reads disk to populate guard inputs: `_derive_from_lane` → `read_events`+`reduce`
(`emit.py:196-200`), `_infer_subtasks_complete` reads `tasks.md` (`:243-265`),
`_infer_implementation_evidence` reads the event log (`:268-270`). `merge_gates.py` evaluators
(`:141-276`) and `work_package_lifecycle.py:84-242` similarly fuse decision with I/O.

### Seams to cut (5)

- **A — Lift the FSM definition out of constants.** Make `ALLOWED_TRANSITIONS`/`_GUARDED_TRANSITIONS`
  (and `_STATE_MAP`) into a `MissionFlowDefinition` value object **constructed from** a
  `MissionType`/`MissionOrchestration` descriptor. The string-name guard dispatch is already a
  declarative table — promote it to data. *(Load-bearing: this is what makes the domain doctrine-driven.)*
- **B — Inject guard inputs.** Replace `emit.py`'s `_infer_*`/`_derive_from_lane` with an impure
  `MissionFlowAdapter` that builds a `TransitionContext` from disk, then calls the pure
  `MissionFlow.evaluate(current_lane, target, ctx)`. *(Load-bearing.)*
- **C — Split each gate into pure verdict + impure loader** (generalize the
  `dependency_readiness_for_wp` pure / `build_dependency_graph` impure pattern to merge/review gates).
- **D — Extract lifecycle policy from transaction mechanics** — pull the pure decision (current
  lane+actor → `list[TransitionRequest]`) out of `work_package_lifecycle.py`; leave lock + append as adapter.
- **E — Collapse the dual representation** (flat matrix vs State Pattern) onto one internal model to remove drift risk.

> **Important scoping note:** MissionFlow has **two separable deliverables**. (i) *Extract* the
> existing pure FSM behind a façade (low risk, high cleanup value — seams B–E). (ii) *Make it
> mission-type-configurable* (seam A — net-new capability). #1619 only needs (i). (ii) is a larger,
> independently valuable bet that should be its own decision, not smuggled into the execution-context unification.

---

## 6. Refined context family (supersedes `06` §2 sketch)

Given the existing pattern, the target family — all assembled by one central builder in
`mission_runtime/`, each a deep module mirroring `PackContext`/`ProjectContext`:

| Object | Layer | Owns | Status today |
|--------|-------|------|--------------|
| **Mission Identity** | charter/doctrine | `mission_id`, `mid8`, `slug`, `mission_run_id` | scattered; consolidate |
| **Execution Topology / `MissionExecutionContext`** *(filesystem aspects)* | dataclass in charter; builder in specify_cli/runtime | primary/coord/lane/integration roots+branches, `lanes.json`, `read_dir`/`write_dir`/`destination_ref`/`cwd`/`prompt_source_dir` | **NEW** (the #1619 object) |
| **`OperationalContext`** *(session facts)* | charter (`invocation_context.py:155`) | model/profile/role/activity/tech_stack | **EXISTS, wired** — keep, don't repurpose |
| **`MissionStatus`** aggregate | specify_cli `status/` | WP-lane state, transitions, guards, atomic save | **EXISTS as free functions** — formalize into aggregate (§4) |
| **`MissionFlow`** pure domain | specify_cli `status/` (or `mission_runtime/flow/`) | FSM edges, guards, gate verdicts | **EXISTS as pure functions** — façade (§5 i); config-drive later (§5 ii) |

Relationship: `MissionStatus.load(context)` takes the **Execution Topology** context for paths and
delegates edge legality to **MissionFlow**. The central builder constructs Identity → Topology →
Session(`OperationalContext`) → `MissionStatus` for a given operation.

---

## 7. Updated open questions (extends `06` §6)

1. **Naming collision (§2):** keep `OperationalContext`=session and name the filesystem context
   distinctly, rename existing → `SessionContext`, or compose an umbrella? *(DIRECTIVE_032 — decide first.)*
2. **MissionStatus scope:** does the aggregate own `save()` (commit seam, closing #1618), or only
   in-memory state with the transaction layer committing? (Ties to `05` I-4.)
3. **MissionFlow split:** ship only the **extraction/façade** (i) now, and treat **config-driven
   lanes** (ii, seam A + wiring `MissionOrchestration`) as a separate later epic? (Recommended.)
4. **Where MissionFlow lives:** stays in `status/`, or moves to `mission_runtime/flow/` as a sibling of the contexts?
5. **Central builder signature:** one `build_mission_context(cwd, mission, op_kind)` returning the
   family, or lazy/compositional access? Does `op_kind` (read/write/review) belong in the builder or the call?
6. **Migration ratchet unchanged:** the #1619 e2e regression (main+lane CWD parity) is still the gate built first.
7. **Reconcile with epic #992** ("centralize domain invariants") — MissionStatus + MissionFlow *are*
   the domain-invariant centralization; #1619 is their execution-topology consumer.
