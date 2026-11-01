---
title: '`surface` names two unrelated domains — split the vocabulary, rename to `ToolSurfaceKind` and `TopologySurface`'
description: 'The overloaded word `surface` splits into two named types: `ToolSurfaceKind` for tool-facing artifacts and `TopologySurface` for the physical tree an artifact lives in.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-07-23'
---

**Status:** Accepted

**Date:** 2026-07-23

**Deciders:** Operator (Stijn Dejongh); recorded by `curator-carla` under governed
tidy-first Op `01KY7ECRZCB99JAD3WAQ9ZTSSS`.

**Technical Story:** coord-trust remediation branch `remediation/coord-lifecycle-gates`
(tracker [#2841](https://github.com/Priivacy-ai/spec-kitty/issues/2841)); motivating
defects [#1834](https://github.com/Priivacy-ai/spec-kitty/issues/1834) and
[#2885](https://github.com/Priivacy-ai/spec-kitty/issues/2885); sibling disambiguation
work [#2653](https://github.com/Priivacy-ai/spec-kitty/issues/2653) (`primary` / `merge`).

---

## Context and Problem Statement

The word **surface** currently names two unrelated concepts in this codebase, in two
bounded contexts that never touch each other:

1. **Tool surface** — `SurfaceKind` in `src/specify_cli/tool_surface/enums.py:13`
   (`COMMAND_SKILL`, `DOCTRINE_SKILL`, `CONTEXT_FILE`, `RULE`, `HOOK`, `AGENT_PROFILE`,
   `PLUGIN_MANIFEST`, `NATIVE_CONFIG`, `COMMAND_FILE`): *what kind of agent-facing
   artifact or configuration entry a definition describes*. Its domain is install /
   verify / repair / package for a concrete execution tool.
2. **Mission topology surface** — `Surface` in `src/mission_runtime/artifacts.py:23`
   (`PRIMARY` | `PLACEMENT`, with a `str` mixin and an `ArtifactSurface` back-compat
   alias): *which physical tree a mission artifact resolves to*. Its domain is artifact
   placement, read/write paths, and commit targets.

Two unrelated types both named `Surface`/`SurfaceKind` is exactly the failure mode this
project has already paid for twice — the four senses of `primary` and the three senses of
`merge` (#2653), whose load-bearing trap was reading one sense as another. `surface` is on
the same trajectory: the glossary's `PRIMARY partition` entry already had to write "which
surface an artifact kind is written to" while `repository root checkout` had to retire
"primary surface" as an alias.

The concrete architectural finding that made this urgent is narrower than naming. **There
is no single surface→filesystem translation seam.** `artifact_home_for` returns a
`Surface` *label* plus a commit target — it stops at the label. The actual translation
from that label to a directory on disk is scattered across at least six call paths:

- `mission_runtime.resolution.placement_seam(...).read_dir`
- `mission_runtime.resolution.coord_read_dir_for`
- `specify_cli.missions._read_path_resolver.resolve_planning_read_dir`
- `specify_cli.acceptance.gates_core._acceptance_matrix_read_dir`
- `specify_cli.post_merge.review_artifact_consistency._resolve_review_cycle_read_dir`
- `feature_dir_for_preview`

Together these are referenced from ~20 modules. Every one of them re-derives "where does
this actually live" from topology, existence checks, and fallbacks. That scattering is the
root of two active P0 defects, #1834 and #2885. A surface *vocabulary* that cannot be read
unambiguously is what allows six independent translations to drift without anyone noticing
they are the same operation.

This ADR records the vocabulary decision. It does not implement the seam.

## Decision Drivers

- **Single canonical authority** (charter governing principle) — one word must name one
  concept, and one operation must have one seam. Both are violated today.
- **Precedent set by #2653** — `primary` and `merge` were disambiguated by naming every
  sense explicitly and adding "Do NOT use when" guards, not by leaving context to
  disambiguate. `surface` gets the same treatment or the precedent is arbitrary.
- **The missing translation seam** — the enum is the vocabulary a future single seam will
  speak. Fixing the names before extracting the seam means the seam is born with the right
  vocabulary rather than inheriting a colliding one.
- **Explicitness over avoidance** — `PLACEMENT` was chosen historically to avoid the
  *word* "coord" while keeping the *concept*. Avoiding the word does not avoid the
  coupling; it only makes the coupling unreadable.
- **Existing three-sense overload of `merge`** — any new member naming the
  post-consolidation state must not re-import that ambiguity.

## Considered Options

- **Option 1 (chosen)** — Split the vocabulary: rename `SurfaceKind` → `ToolSurfaceKind`
  and `Surface` → `TopologySurface`, expand the topology members to
  `PRIMARY | COORD | LANE | CONSOLIDATED | TEMP`, and govern both senses in the glossary
  with cross-context "Do NOT use when" guards.
- **Option 2 (rejected)** — Leave both types named `Surface*` and rely on import path /
  module context to disambiguate.
- **Option 3 (rejected)** — Rename only one side (e.g. only the topology type), leaving
  `SurfaceKind` bare.

## Decision Outcome

**Chosen option: Option 1 — split the vocabulary and rename both sides.**

### The two-vocabulary distinction

`surface` is governed as an overloaded term with exactly two senses, mirroring the
`primary` (Senses A–D) and `merge` (Senses 1–3) treatment:

| | `surface` **Sense 1** | `surface` **Sense 2** |
|---|---|---|
| **Canonical term** | [Tool Surface](../../context/execution.md#tool-surface) | [Topology Surface](../../context/orchestration.md#topology-surface) |
| **Question answered** | *What kind of tool-facing artifact is this?* | *Which physical tree does this artifact live in?* |
| **Bounded context** | Execution (install / doctor / package) | Orchestration (placement / read-write paths) |
| **Type** | `ToolSurfaceKind` | `TopologySurface` |
| **Module** | `specify_cli/tool_surface/enums.py` | `mission_runtime/artifacts.py` |

The two senses share no members, no consumers, and no lifecycle. Nothing is unified by the
shared word; only confusion is.

### The rename decisions

- `SurfaceKind` → **`ToolSurfaceKind`**. The module is already `tool_surface`; the type
  name now matches the bounded context it lives in.
- `Surface` → **`TopologySurface`**, with the `ArtifactSurface` back-compat alias retired
  along with the old name. Per ADR
  [2026-07-01-1](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md), a legacy alias
  kept "just in case" is a resolver-shaped fallback in type clothing; require the canonical
  name and migrate.
- Members expand from `PRIMARY | PLACEMENT` to
  **`PRIMARY | COORD`** as landed in the rename, expanding to the full
  **`PRIMARY | COORD | LANE | CONSOLIDATED | TEMP`** — the full set of physical trees a
  mission artifact can resolve to, not just the two the current two-way partition needed.

### `PLACEMENT` → `COORD`

`PLACEMENT` avoided the *word* rather than the *concept*. The member has always meant "the
coordination surface"; every consumer read it that way, and `coord_read_dir_for` /
`_PLACEMENT_ARTIFACT_KINDS` sit one call apart proving it. Naming it `COORD` makes the
existing meaning legible instead of encoding it in tribal knowledge.

### `CONSOLIDATED`, not `MERGED`

The post-consolidation surface is named `CONSOLIDATED` because `merge` is already a
three-sense overloaded term here —
[Lane Consolidation](../../context/orchestration.md#lane-consolidation),
[Branch Integration / Git Merge](../../context/orchestration.md#branch-integration--git-merge),
and [Publish to origin/main](../../context/orchestration.md#publish-to-originmain). A
member named `MERGED` would not say which of the three had occurred, and in a git-based
codebase every reader would guess a different one. `CONSOLIDATED` names exactly one: the
surface that exists after lane consolidation. This is the same reasoning that governs
`primary` / `main` / `base` — when a word already carries N senses, do not spend it on an
N+1st.

### Naming a surface `COORD` is not conditioning on topology

The standing rule is that behaviour must not branch on topology — a caller must consume a
*resolved* path, not re-derive one from `if topology is COORD`. Naming a member `COORD`
does not violate that rule and must not be read as licence to reintroduce it:

- **Allowed (naming)** — a surface value that *identifies* a real physical tree, so a
  resolver can return "this artifact lives on the COORD surface" instead of returning an
  unlabelled path.
- **Forbidden (conditioning)** — `if surface is TopologySurface.COORD: <inline path
  derivation>` at a call site, in place of asking the seam for the resolved directory.

The distinction is the whole point of having a translation seam: the label is the seam's
*output vocabulary*, not an input to per-call-site branching.

### Consequences

#### Positive

- Two unrelated types stop colliding on one word; a reader who sees `TopologySurface` or
  `ToolSurfaceKind` knows the domain without opening the import.
- The expanded member set gives the future translation seam a complete vocabulary — `LANE`,
  `CONSOLIDATED`, and `TEMP` are trees that already exist in the system but had no name in
  this type, which is part of why six call paths each invented their own handling.
- The `surface` glossary treatment now matches the `primary` / `merge` treatment, so the
  disambiguation discipline reads as a rule rather than as three one-off calls.
- Retiring `ArtifactSurface` removes a legacy alias before it acquires consumers.

#### Negative

- A broad mechanical rename across `src/` and `tests/`. It is a bulk edit and carries the
  usual occurrence-classification obligation.
- Dropping the `str` mixin (if the rename does so) breaks any surviving
  `== "primary"` / `== "placement"` literal comparison; those comparisons are exactly the
  scattered-translation smell this ADR documents, so they must be converted, not preserved.
- **Landed state vs end state.** The rename commit ships only `PRIMARY | COORD` (the two members
  the old `Surface` carried, `PLACEMENT` renamed to `COORD`). `LANE`, `CONSOLIDATED` and `TEMP`
  are the decided end state but are **not** declared until the surface→filesystem translation seam
  that resolves them lands (mission IC-11) — a member no caller can resolve is a phantom, which the
  anti-phantom rule forbids. So code shows two members and this ADR describes five; that is intended,
  not drift. Anyone reading the enum before IC-11 sees two.

#### Neutral

- This ADR changes vocabulary only. The scattered translation remains scattered; #1834 and
  #2885 remain open. The seam extraction is separate work, and this ADR is deliberately
  the vocabulary prerequisite for it rather than a bundled fix.
- `MissionArtifactKind` and the `_PRIMARY_ARTIFACT_KINDS` / `_PLACEMENT_ARTIFACT_KINDS`
  partition sets are untouched by the vocabulary decision beyond the `PLACEMENT` → `COORD`
  member name.

### Confirmation

The decision is confirmed when: (a) no module outside `mission_runtime/artifacts.py`
declares or aliases a bare `Surface` type; (b) `ArtifactSurface` has no remaining
references; and (c) a future seam-extraction slice can state its contract as
"`TopologySurface` → `Path`" without first having to define what a surface is. Failure
signal: a new call site re-deriving a coordination directory inline rather than consuming
a resolved path — that would mean the label was read as a branching input, which
§"Naming a surface `COORD` is not conditioning on topology" forbids.

## Pros and Cons of the Options

### Option 1 — split the vocabulary, rename both sides

**Pros:**

- Each type name states its bounded context.
- Consistent with the `primary` (#2653) and `merge` disambiguation precedent.
- Gives the future translation seam a complete, unambiguous output vocabulary.

**Cons:**

- Bulk rename cost across two packages plus tests.
- Names three members ahead of their consumers.

### Option 2 — leave both named `Surface*`, disambiguate by import path

**Pros:**

- Zero code churn.

**Cons:**

- Import-path disambiguation fails exactly where it matters — in prose, in review comments,
  in agent-authored plans, and in `from ... import Surface` lines read out of context.
- Repeats the `primary` / `merge` failure the project has already paid to fix twice.
- Leaves the future seam speaking a colliding vocabulary.

### Option 3 — rename only the topology side

**Pros:**

- Smaller diff; fixes the side with the active defects.

**Cons:**

- Leaves a bare `SurfaceKind` that still reads as "the surface type" to anyone who has not
  met `TopologySurface`, so the collision persists asymmetrically.
- Half-applied disambiguation is worse than none: it implies the remaining bare name is
  *the* canonical sense.

## More Information

- Glossary entries: [Topology Surface](../../context/orchestration.md#topology-surface)
  and [COORD partition](../../context/orchestration.md#coord-partition) (Orchestration
  context); [Tool Surface](../../context/execution.md#tool-surface) (Execution context).
- [2026-07-01-1 — No legacy-compat branches in resolvers](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)
  — why `ArtifactSurface` is retired rather than kept as an alias.
- [2026-06-24-1 — Kind- and topology-aware artifact placement](2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
  — the placement model whose labels this ADR renames.
- [2026-06-26-1 — Single-authority seam + call-site gate](2026-06-26-1-single-authority-seam-and-call-site-gate.md)
  — the seam pattern the missing surface→filesystem translation should eventually follow.
