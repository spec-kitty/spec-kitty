---
title: '2026-08-04 — Next doctrine slice: wheel cutover, mission-type relocation, public API surface'
description: 'Preliminary research on the post-#3176 scope: kernel/doctrine/charter wheel packaging, the missions/ tree relocation, and a stable public API for the doctrine & charter modules.'
doc_status: deprecated
updated: '2026-08-04'
---

# Next doctrine slice — preliminary research

> **Retired (deprecated).** Design shipped via merged mission `doctrine-public-api-surface-01KZPDSR` (#3179). Preserved as a historical record.

Branch: `research/doctrine-wheel-mission-types-public-api` (off `upstream/main` @ `abca7ec9`).
No mission created yet — this is pre-spec research only, gathered by reading the tracker, the
existing ADRs, and the current tree, so a future `/spec-kitty.specify` starts from a settled
picture rather than re-discovering it.

## Trigger

[#3176](https://github.com/Priivacy-ai/spec-kitty/issues/3176) is the last named,
composite-key-excluded call site (`projection.py:115`) blocking `default_profile_repository()`
from going through `charter.resolver.DoctrineService`'s unified builder — the "sole door" for
doctrine/charter construction (mission `charter-sole-door-bypass-closure-01KZ3WAA`, parent
[#1868](https://github.com/Priivacy-ai/spec-kitty/issues/1868)). Once it lands, every production
caller constructs doctrine/charter services through one builder, not through scattered direct
constructors. That precondition matters for all three threads below: you cannot draw a credible
public-API boundary, or cut a wheel, around a module whose own internals are entered through more
than one door.

The user's framing names three threads for "the next doctrine slice": **(a)** wiring of the wheel
modules, **(b)** moving the mission types, **(c)** a public API on doctrine & charter, by analogy
to the old FastAPI epic. Each is a real, separately-tracked thread already — this note maps them
and how they interlock.

## (a) Wheel modules — already assessed, decision made, not yet executed

This is the most mature thread. [#3101](https://github.com/Priivacy-ai/spec-kitty/issues/3101)
("Split `src/doctrine/` (and assess `src/charter/`) into a separate installable wheel/package")
already went through a design-spike mission (`doctrine-charter-split-unification-01KZ0SRB`) that
produced [ADR 2026-08-02-1](../../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md)
("Accepted"). Key findings, verified against the current tree:

- **Decision: Option B** — assess and sequence one atomic `kernel → doctrine → charter` cutover,
  deferred as a single no-partial follow-on. Option A (extract charter now) was rejected as
  unresolvable (charter has 109 `doctrine` and 8 `kernel` import statements; neither wheel is
  published) and as reproducing the PR #779 "partial cutover" hybrid that ADR
  [2026-04-25-1](../../../adr/3.x/2026-04-25-1-shared-package-boundary.md) already rejected.
- **Groundwork already landed, verified present:**
  - `src/kernel/pyproject.toml` — `spec-kitty-kernel`, zero first-party deps, the true root.
  - `src/doctrine/pyproject.toml` + `src/doctrine/hatch_build.py` — declares `spec-kitty-kernel`
    dependency, build-verified with a real `hatch build` (force-includes the out-of-tree
    `packs/` tree as a wheel-root sibling). Both files carry a `DORMANT PACKAGING GROUNDWORK`
    banner: not built, published, or consumed by CI or any runtime import path yet.
  - `tests/architectural/test_charter_no_specify_cli_import.py` — AST-walk gate proving charter
    carries **zero `specify_cli` import edges at any scope** (module, function, `try`/`except`).
    This is what makes charter "extractable in principle."
  - There is **deliberately no `src/charter/pyproject.toml` yet** — minting one now would be the
    first half of the forbidden partial cutover.
- **What the AST gate does NOT prove** (table in the ADR, worth re-reading before scoping): string
  import indirection, entry-point/plugin discovery, duck-typed data coupling, and — explicitly
  flagged as **unproven** — charter↔glossary/runtime edges. Confirmed still true: no
  `src/charter/pyproject.toml` exists and `src/glossary`, `src/mission_runtime`, `src/runtime` are
  not in the ADR's closure test.
- **Deferred follow-on issue set, named by the ADR itself** (not exhaustive of the epic, but the
  cutover's own scope): #3101 (parent), #3091 (missions/ tree relocation — changes what the
  doctrine wheel must carry), #3022 (extract built-in packs into `spec-kitty-packs-open` — a
  further split of the payload the build hook currently ships), #3036 (a live contradiction: an
  architectural gate requires the repo-coupling the shippable-doctrine rule forbids — must resolve
  before doctrine ships standalone), #3039 (mis-scoped gate wearing a doctrine name — would follow
  the wrong package post-split), #2986 (**the same function-local-import blind spot WP10 closed for
  charter→specify_cli is still open for runtime→doctrine** — the boundary-test half of the
  extended pattern is unsound for that pair until fixed).
- **Enforcement pattern to reuse, not reinvent:** boundary test (pytestarch + AST fallback) →
  pyproject-shape test (compat ranges only, no path sources) → `clean-install-verification` CI job
  (fresh venv, install published wheels, run a real command). All three already exist for the
  `spec-kitty-events`/`spec-kitty-tracker` precedent; the ADR's whole point is extending the same
  triad, not inventing a second one.

**Open question for the next slice:** the ADR's confirmation criterion is explicit — "falsified if
the charter layer turns out to carry non-import coupling to `specify_cli` that the AST gate never
covered." A pre-cutover pass should specifically probe for duck-typed/data coupling and
charter↔glossary/runtime edges before treating the cutover as mechanical.

## (b) Mission-type relocation — two overlapping efforts, one epic

Two issues, both children of [#2466](https://github.com/Priivacy-ai/spec-kitty/issues/2466)
("Epic: Doctrine/Charter extensibility & pack ecosystem"), cover this:

- [#3091](https://github.com/Priivacy-ai/spec-kitty/issues/3091) — "Phase 1b: relocate the
  `missions/` doctrine tree to `packs/built-in`." Deferred out of Phase 1 (the
  `relocate-builtin-doctrine-packs-01KYT87F` mission) by unanimous post-plan adversarial-squad
  ruling: `missions/` readers span four layers, including `src/kernel/paths.py`
  (`files("doctrine")/"missions"`), and routing a kernel-layer reader through the doctrine-layer
  `resolve_pack_root` is a C-004 upward-import violation (pushing the resolver into kernel is a
  separate C-002 kernel-extraction task, Phase 2). First task named: a cross-layer `missions/`
  reader inventory (doctrine + kernel + charter + specify_cli + upgrade migrations) with a
  per-reader move/stay decision, before any move.
- [#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468) — "Promote mission types + step
  contracts to full doctrine artifact kinds." `mission_step_contract` is already a first-class
  `ArtifactKind`; `mission-type` deliberately is not (`artifact_kinds.py` raises
  `MissionTypeNotAnArtifactKind`, admitted only via an org-DRG kind-alias side channel). Depends on
  [#2467](https://github.com/Priivacy-ai/spec-kitty/issues/2467) (the pack-split keystone — no
  dependencies itself, the foundation the rest of #2466 builds on). Sizing **L**. **Top risk,
  stated in the issue itself:** this reverses a deliberate, tested, documented "no silent fallback"
  contract (R-009/CL-1, FR-032, pinned by `tests/doctrine/test_org_pack_augmentation.py`) —
  requires an explicit decision record plus a compat path, must not land as a quiet behavior
  change.
- Also relevant, same epic family: [#2652](https://github.com/Priivacy-ai/spec-kitty/issues/2652)
  ("EPIC: specify_cli/missions retirement — slice 2+") — a *different* but overlapping retirement:
  deleting the derived `src/specify_cli/missions/` tree so `software-dev` becomes an ordinary peer
  doctrine type. Sequenced #2658 (template-slot) → #2659 (activation-driven enumeration, blocked on
  an external provisioned-default-charter issue #2657) → #2660 (remove the `meta.json`-less
  fallback in `mission.py`) → #2661 (delete the doctrine→`.kittify` copy step + type-dirs). Its own
  amendment is explicit: availability must be derived from the **charter activation set**
  (`activated_mission_types`), never from what exists on disk — "no second availability source."

**These two efforts (missions/ tree relocation, and specify_cli/missions retirement) are not the
same ticket but they converge on the same end state** — a single canonical mission-type source
with no filesystem-position-implies-availability logic anywhere. Scoping the next slice should
make explicit which of #3091 / #2468 / #2652's remaining sub-issues it actually claims, since all
three are independently sequenced today and #2468 in particular carries a named "reverses a tested
contract" risk that wants its own decision record before implementation.

## (c) Public API on doctrine & charter — filed as [#3179](https://github.com/Priivacy-ai/spec-kitty/issues/3179)

This was the thread with no existing tracker coverage when this research started — filed as #3179
(`Feature`, `priority:P2`, milestone `3.2.x`, parented under #2466) once the gap below was
confirmed.

**The analogy the user drew is precise.** [#645](https://github.com/Priivacy-ai/spec-kitty/issues/645)
("Epic: Stable Application API Surface") and its child
[#460](https://github.com/Priivacy-ai/spec-kitty/issues/460) ("Transport migration: FastAPI/OpenAPI
for the frontend application API boundary") solved exactly this class of problem for the
dashboard: many independent readers of the same `kitty-specs/*/` data (routers, CLI, internal
walks) with no enforced single entry point → service extraction → formalized typed contracts →
architectural test enforcing the single-entry-point invariant → *then* a transport/framework
choice (FastAPI/OpenAPI). The framework migration was explicitly sequenced **last**, after
semantic stabilization and contract hardening — "should follow ... rather than lead them" (#460's
own text). That ordering is the transferable lesson, not FastAPI itself (doctrine/charter's
"transport" is a Python import surface, not HTTP).

**Current state of the doctrine/charter import surface, verified against the tree today:**

| | `doctrine/__init__.py` | `charter/__init__.py` |
|---|---|---|
| Declares `__all__` | Yes — 3 names (`ArtifactKind`, `BaseDoctrineRepository`, `DoctrineService`) | Yes — a broad re-export list (bundle, catalog, compiler, context, interview, parser, schemas, scope, sync, org_extends, mission_type_profiles, ...) |
| Actual external consumer surface | Far wider: **79 files** under `specify_cli`/`runtime`/`charter` do `from doctrine.<submodule> import ...` directly, across **~30 distinct submodule paths** (`drg.models` ×25, `drg.org_pack_config` ×14, `service` ×12, `missions.mission_type_repository` ×12, `artifact_kinds` ×12, `drg.loader` ×11, `agent_profiles.profile` ×9, `pack_paths` ×8, ...) | Not measured in this pass; charter's `__init__` is already closer to a real surface, but nothing pins that it's *complete* or that deep-import bypasses don't exist |
| Architectural test pinning "no deep import, use the public surface" | None found | None found |
| Closest existing precedent for a *versioned, frozen* contract | — | [#2787](https://github.com/Priivacy-ai/spec-kitty/issues/2787) ("E1: freeze `charter context --json` as a stable, activation-scoped external contract, `context_schema_version`") — already froze **one CLI JSON payload's shape**, enforced by `CONTEXT_CONTRACT_TOP_LEVEL_KEYS` (the pinned constant behind the #3161 dead-symbol-gate allowlist triaged earlier this session) |

So: doctrine's declared public surface (3 names) is a significant undercount of its real consumer
surface (~30 submodule paths); charter's is closer but unenforced; and the one place this project
has already done "freeze a stable contract" for charter is scoped to a single CLI command's JSON
output, not the importable Python surface. A "create a public API on doctrine & charter" slice, by
the #645/#460 pattern, would need to: (1) inventory the real consumer surface (the 79-file/30-path
list above is a starting point, not a finished census), (2) decide what actually belongs on the
public surface vs. stays internal, (3) widen `__init__.py`/`__all__` (or introduce a dedicated
`doctrine.api`/`charter.api` module) to match, (4) add an architectural test enforcing "external
callers import only from the public surface" (the same idiom as
`test_shared_package_boundary.py`/`test_charter_no_specify_cli_import.py`, pointed at internal
submodules instead of `specify_cli`), and (5) only then treat the wheel cutover's public surface as
settled — this is a **precondition for (a), not a parallel, unrelated effort**: you cannot publish
a wheel with a credible external contract if 79 internal call sites are already reaching past the
declared `__all__`.

Issue #3179 now owns this explicitly, with a tracker home the way (a) and (b) already do.

## How the three threads interlock

```
#3176 lands (sole door closed: one builder, one entry point into doctrine/charter construction)
        │
        ▼
(c) Public API inventory + enforcement  ──────────────┐
  (#3179)                                               │  public surface must be
        │                                                │  settled before the wheel's
        ▼                                                │  external contract is credible
(a) kernel → doctrine → charter wheel cutover  ◄─────────┘
  (#3101, ADR 2026-08-02-1, Option B, no-partial)
        │
        │  "what the doctrine wheel must carry" is not settled
        │  until missions/ has a final home
        ▼
(b) missions/ tree relocation + mission-type-as-doctrine-kind
  (#3091, #2468, #2652 — three overlapping, independently-sequenced efforts)
```

The ADR itself already names #3091 as changing what the doctrine wheel must carry, so (b) is not
strictly gating (a) — but any (a) work that ships before (b) settles risks re-packaging the same
tree twice. The public-API thread (c) was the one genuinely new piece with no tracker issue and no
architectural test — now filed as #3179 — but the wheel cutover's own confirmation criterion (a
credible external contract, not just an import-edge count) still depends on it landing.

## Suggested next steps (not yet committed to a mission)

1. ~~File the missing tracker issue for (c)~~ — done: [#3179](https://github.com/Priivacy-ai/spec-kitty/issues/3179),
   parented under #2466, milestone `3.2.x`.
2. Before scoping any mission, resolve which of #3091 / #2468 / #2652's remaining sub-issues the
   "mission types move" slice actually claims — they are three separately-sequenced efforts today,
   not one ticket.
3. Treat #3036 and #2986 (named directly in the ADR's deferred set) as pre-conditions for the
   wheel cutover, not optional cleanup — #3036 is a live contradiction between two gates, and #2986
   is the same blind spot WP10 already closed for one direction (charter→specify_cli) still open
   for the other (runtime→doctrine).
4. Re-run the charter↔glossary/runtime coupling assessment the ADR explicitly leaves unproven,
   before assuming the charter half of the cutover is as mechanical as the kernel/doctrine half.

## Addendum (2026-08-04) — PR #3175 landed; follow-ups reviewed

[PR #3175](https://github.com/Priivacy-ai/spec-kitty/pull/3175) ("Charter as Sole Door: Close
Bypass Access Paths" — the mission #3176 belonged to) merged. Its landing pass filed five
follow-ups (#3181–#3185); reviewed each against the three threads above:

| # | Verdict | Disposition |
|---|---|---|
| #3181 (pip-audit CVE bump) | Out of scope | Dependency security bump, unrelated; already closed |
| #3182 (stale TIER-1 override templates teach the now-banned raw `DoctrineService`/`AgentProfileRepository` construction + reference a deleted `constitution context` command) | **Adjacent — campsite/enabler tooling** | Triaged: `Bug`, `doctrine,tidy-up,catfooding,priority:P2`, milestone `3.2.x`, parented under #2466. Dogfood template content invisible to the AST gates; relevant to (c) as the kind of artifact that should model the canonical construction path once #3179 settles it, but not itself part of the doctrine/charter package surface |
| #3183 (`UnknownMissionTypeError` message conflates "activated in config" with "has a loadable profile") | **Direct fit — thread (b)** | Triaged: `Bug`, `doctrine,priority:P2`, milestone `3.2.x`, parented under #2652. This is the exact activation-vs-availability vocabulary collision #2652's own AC note addresses ("no second availability source") — a mission-type-relocation slice should resolve this, not inherit it |
| #3184 (~15 unmarked leftover files in `tests/regression/`) | Out of scope | Test-suite hygiene; belongs under #1931 (Test suite friction epic), not this doctrine slice |
| #3185 (GC2b gate-coverage red on main) | Out of scope | CI gate-baseline drift, unrelated; already closed (not planned) |
