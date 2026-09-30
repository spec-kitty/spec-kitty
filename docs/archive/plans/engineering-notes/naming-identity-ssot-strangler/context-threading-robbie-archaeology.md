---
title: Context-Threading Design Archaeology — Robbie
description: "Researcher Robbie's design archaeology of context-threading: tracing how the threading design evolved, read-only at 3.2.0."
doc_status: deprecated
updated: '2026-06-16'
---
# Context-Threading Design Archaeology — Robbie

**Author:** Researcher Robbie (design archaeology)
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0 (read-only — no commit/switch)
**Date:** 2026-06-16
**Directives applied:** DIR-003 (Decision Documentation — every finding below carries a commit
SHA, ADR path, doc line, or grep count as its source).
**Mode:** investigation + validation.

> **Operator's claim under test:** *"We had considered the read paths, and a consolidated API
> (also consumed by the dashboard). The new coordination and ContextObjects were created
> explicitly for dealing with this → branches and names passed through method chains as a
> context value object, rather than recalculated/re-derived in multiple paths."*
>
> **Hypothesis:** the intended SSOT is ALREADY a Context-value-object + consolidated-API design
> (compute-once, thread-through); the split-brain is a **NON-ADOPTION** problem (consumers
> re-derive inline instead of threading), not a **missing-SSOT** problem.

**VERDICT: SUPPORTED.** The compute-once / thread-through design was stated *explicitly* in an
ADR and two mission specs, the consolidated read API was built and is broadly consumed (incl. by
the dashboard), and the surviving split-brain is provably consumers re-deriving inline next to the
very API they import. This builds on (does not repeat) the 00-OVERVIEW capstone, which already
established the read *authority* is consolidated while *projection/entry* is scattered (§5(a));
this note supplies the **provenance and stated-intent** that the capstone asserts but does not cite.

---

## 1. Provenance — when/why the Context objects and consolidated read API were introduced

`git log --follow --diff-filter=A` on each load-bearing file:

| Surface | First commit (SHA · date) | Mission / WP | Stated purpose (from commit body) |
|---|---|---|---|
| `coordination/types.py` (`GitChangeSet`, `PolicyVerdict`, `PendingEventHandle`, `CommitReceipt`) | `35dc95394` · 2026-05-28 | **01KSPTVW** Mission-Coordination-Branch-Atomic-Event-Log, **WP05** | *"Implements the single chokepoint for coordination-branch writes."* |
| `missions/_read_path_resolver.py` (`resolve_mission_read_path`) | `0ba35654e` · 2026-05-28 | **01KSPTVW**, **WP08** | *"New `_read_path_resolver.py` exposes `resolve_mission_read_path(repo_root, slug, mid8)`. Returns the coordination worktree when present, the primary checkout otherwise. **Wired into** … `core/execution_context.py::_resolve_mission_slug` (the engine behind agent context resolve and **all action-context callers**)."* |
| `coordination/surface_resolver.py` (`ResolvedStatusSurface`, `resolve_status_surface`) | `a5f30616e` · 2026-06-06 | **01KTDVHZ** merge-done-surface-resolver, WP01 | *"feat(merge-done-surface-resolver): fix coord-branch write/read **surface divergence** (#1732)."* |
| `workspace/context.py` (`WorkspaceContext` VO) | (frozen dataclass, `:148`) | execution-workspace family | value-object carrier for workspace/branch facts |

**Reading of the provenance:** the coordination `types.py` value objects (`35dc95394`) and the
`_read_path_resolver` (`0ba35654e`) were born *the same day, in the same mission (01KSPTVW)*,
explicitly framed as **"the single chokepoint"** (write) and a **single resolver "wired into … all
action-context callers"** (read). `surface_resolver` (`a5f30616e`) was then created specifically to
**"fix … surface divergence"** — i.e. to *stop* the read/write paths diverging. So the objects were
not incidental helpers; they were introduced *as* the divergence-elimination mechanism. This
corroborates the operator's "created explicitly for dealing with this" framing.

---

## 2. Was "thread a context value object instead of re-deriving" intent EXPLICITLY stated?

Yes — in three independent places, escalating from principle → contract → WP acceptance criterion.

### 2a. ADR `2026-03-09-1` — "Prompts Do Not Discover Context, Commands Do" (the root intent)

`docs/adr/3.x/2026-03-09-1-prompts-do-not-discover-context-commands-do.md`. This is the
canonical statement of compute-once / thread-through. Direct quotes:

- Decision driver 2: **"Single source of truth for feature, WP, dependency, and branch context."**
- Core decision (`:71`): **"Prompts do not discover context. Commands do."**
- Chosen Option 3 (`:57`): *"Introduce a canonical action-context resolver command and make
  prompts consume it … `next` and legacy slash commands **both** use this resolver."*
- Canonical contract (`:88`): the resolver SHALL return `feature_slug`, `feature_dir`,
  `mission_key`, `target_branch`, `wp_id`, `workspace_path`, … — i.e. names/branches/paths
  **resolved once and handed downstream as a value bundle**.
- Verification point 6 (`:174`): *"`spec-kitty next` and legacy slash-command execution resolve the
  **same** `feature_slug`, `wp_id`, `resolved_base`, and `workspace_path` for the same repository
  state."* — this is precisely "compute once, do not re-derive in multiple paths."

The ADR even names the disease the operator describes: *"Prompt templates are compensating by asking
the model to **rediscover context from cwd, branch name, feature directories, and heuristics**"*
(`:34`) — the prose analogue of inline `[:8]`/path re-derivation in code.

### 2b. Overhaul doc `09` — the fragments-as-value-objects model (the design crystallization)

`docs/archive/plans/engineering-notes/runtime_and_state_overhaul/09-context-decomposition-model.md`:

- Hypothesis under test (`:4`, attributed to Stijn — the operator): *"'Context' is not one object.
  It is several domain-owned chunks … each modeled in its proper domain, then **aggregated by
  composition** into fit-for-purpose composites **passed through the API**."*
- `:57`: *"Six fragments. **Five are immutable value objects**."*
- `:65` — the decisive line for the read path: **F2 `FilesystemLayout`** is *"derived (from F0 +
  roots + conventions)"*, current state **"partial (`resolve_mission_read_path`,
  `CoordinationWorkspace`) → consolidate (NEW)"**. The read path is *intended* to be a threaded
  value object; it is recorded as only **partially** consolidated.
- `:47`: *"a fragment is **not a data bag**. It encapsulates its domain's derivation rules … the
  four duplicated path-builders (`02`) collapse into the Filesystem fragment's rules."* — the
  explicit anti-re-derivation rule.
- `:11` cross-ref: the composed value object *"already exists as `ActionContext`
  (`core/execution_context.py:44`, **ADR 2026-03-09-1 'commands resolve context, prompts consume
  it'**)"* — the doc itself ties the VO to the ADR.

### 2c. Mission WP `01KTPKST/WP04` — the acceptance criterion (the contract made testable)

`kitty-specs/execution-context-unification-01KTPKST/tasks/WP04-read-path-consolidation.md`:

- Objective: *"Fold the duplicate `feature_dir_resolver.candidate_feature_dir_for_mission` into the
  canonical `_read_path_resolver.resolve_mission_read_path` (**one read primitive** — FR-002)."*
- *"Route `prompt_source_dir` through the context's PromptSourceFragment … **not an independent
  derivation** (FR-012)."*
- Done-when: *"`--mission <mid8>` and `--mission <full-slug>` resolve **identically** … missing
  surface raises a structured error."* — i.e. **no re-derivation drift, no silent fallback.**

**Finding (DIR-003):** the "thread a context value object instead of re-deriving" intent is not
inferred — it is stated at the ADR level (principle), the `09` model level (value-object design),
and the `01KTPKST/WP04` level (testable acceptance). The operator's recollection is **documented**,
not reconstructed.

---

## 3. Was a single consolidated read/identity API designed — "also consumed by the dashboard"?

Yes on both halves.

**(a) The consolidated read API exists and is the designated SSOT.** Per the 00-OVERVIEW capstone
(§3 table rows C/D) and confirmed here, the read authority is `_read_path_resolver` —
`resolve_mission_read_path` (the C-005 read primitive) with `resolve_status_surface` as the status
projection. Overhaul doc `17` (`17-consolidated-domain-model.md:42`) names the **Shared Kernel** as
the *"code module: cross-domain commons — path · identity · status resolvers (OHS facades) …
`resolve_action_context`, `resolve_mission_read_path`"* — explicitly *"used to build Contexts"*
(`:12`). The identity SSOT is `lanes/branch_naming.py` — `mid8()` (`:122`), `resolve_mid8()`
(`:169`), the canonical 8-char derivation (confirmed by the 00-OVERVIEW §3 row A).

**(b) The dashboard consumes it — and simultaneously bypasses it (the smoking gun).**
`src/specify_cli/dashboard/scanner.py`:
- **Line 313** imports the consolidated read API: `from specify_cli.coordination.surface_resolver
  import (…)` — the dashboard *is* a consumer of the consolidated surface, exactly as the operator
  said.
- **Line 438**, in the *same file*, re-derives identity inline:
  `mid8 = … (mission_id[:8] if mission_id else None)` — instead of calling the existing
  `branch_naming.mid8()` / `resolve_mid8()` SSOT.

The dashboard is therefore the single clearest proof of the **non-adoption** thesis: one module both
imports the consolidated API *and* hand-rolls `mission_id[:8]` a few lines later. The SSOT is not
missing; the call is.

---

## 4. Adoption timeline — did consumers migrate onto the API, or did inline re-derivation persist?

Both happened — broad adoption of the read API *and* a stubborn residue of inline identity
re-derivation that the ratchet does not yet catch. Grep counts on this branch (`src/`, Python):

| Signal | Count | Reading |
|---|---|---|
| Callers of `resolve_mission_read_path` | **33** | The read API was **broadly adopted** — the consolidation largely *worked*. |
| Files calling `resolve_action_context` | 9 | Action-context projection adopted across the lifecycle commands. |
| Callers routed through `resolve_mid8(` (the identity SSOT) | 9 | Identity SSOT *is* used … |
| Bare `…_id[:8]` re-derivations in non-test `src/` | **27** | …but **27 sites still slice mid8 by hand**, incl. `dashboard/scanner.py:438`, `status/aggregate.py:250`, `git/sparse_checkout.py:286`, `implement.py:386`, `doctor.py:3070/3162`. |

**Why the residue survives — enforcement blind spot (corroborates randy-reducer 2c / 00-OVERVIEW
§4):** the AST ratchet `tests/architectural/test_no_worktree_name_guess.py` keys on the
*name-composition* idiom (`endswith(f"-{mid8}")`); a **bare `mission_id[:8]`** is not a name compose,
so it **escapes the ratchet**. The consolidated API landed and was adopted for *path* reads, but the
*identity-derivation* class was never fully routed and is not policed — so it persisted (and can
regrow). This is the textbook signature of a **stalled-adoption / completeness-gap** strangler, not a
missing-SSOT one: the seam exists, most traffic uses it, a sub-class never migrated and the oracle
doesn't flag it.

**Caveat (do not over-read the counts):** several of the 27 `[:8]` sites are *inside* the SSOT
itself (`branch_naming.py:139`), in docstrings (`branch_naming.py:180`,
`context/mission_resolver.py:6`), or are unrelated truncations (`invocation_id[:8]` for log labels at
`executor.py:469`). The live naming/identity residue is the ~10-site cluster the 00-OVERVIEW already
scoped to WP04 (§6); this note's contribution is the *provenance + intent* behind why those sites are
a regression of an intended design, not the raw count.

---

## 5. Verdict on the operator's claim (evidence-bound)

| Claim component | Verdict | Key evidence |
|---|---|---|
| "We had considered the read paths" | **SUPPORTED** | ADR `2026-03-09-1` drivers 1–3; doc `09:65` lists `resolve_mission_read_path` as the F2 read-path VO. |
| "a consolidated API (also consumed by the dashboard)" | **SUPPORTED** | `_read_path_resolver`/`surface_resolver` are the consolidated read surface (doc `17:42`); `dashboard/scanner.py:313` imports it. |
| "new coordination and ContextObjects created explicitly for dealing with this" | **SUPPORTED** | `coordination/types.py` (`35dc95394`, "single chokepoint"); `surface_resolver` (`a5f30616e`, "fix surface divergence #1732"); VOs `ResolvedStatusSurface`/`WorkspaceContext`. |
| "branches/names passed through method chains as a context value object, rather than re-derived" | **SUPPORTED (as intent), STALLED (in adoption)** | Intent: ADR core decision `:71`, doc `09:47` ("not a data bag"), WP04 "one read primitive / not an independent derivation". Adoption gap: 27 bare `[:8]` sites incl. `scanner.py:438`. |

**Overall: the operator's intuition is SUPPORTED, and the hypothesis is CONFIRMED.** The intended
SSOT is *already* a Context-value-object + consolidated-API design (compute-once, thread-through),
designed at ADR level and built across missions 01KSPTVW / 01KTDVHZ / 01KTPKST. The remaining
split-brain is a **non-adoption / completeness-gap** problem — consumers (most visibly the dashboard)
re-derive `mid8`/paths inline beside the very API they import, and the ratchet does not yet flag the
bare-`[:8]` idiom — **not** a missing-SSOT problem.

**Implication for the 3.2.1 slice (consistent with 00-OVERVIEW §6):** the correct move is *routing +
ratchet extension* (WP04: route the ~10 bare `[:8]` sites through `mid8()`; extend
`test_no_worktree_name_guess.py` to flag bare `<…>_id[:8]` derivation), **not** designing a new
consolidated API — that API already exists and is the SSOT. Building a new one would itself create the
parallel-implementation anti-pattern this mission exists to kill.
