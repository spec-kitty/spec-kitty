---
title: The Artifact Placement Seam
description: How a mission artifact's kind and topology resolve to a physical tree, the two composition roots, and where callers still bypass the seam.
doc_status: active
updated: '2026-10-02'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/branch-target-routing.md
- docs/adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md
- docs/adr/3.x/2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md
- docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md
- docs/adr/4.x/2026-10-01-3-decision-ledger-primary-partition.md
- docs/context/orchestration.md
---
# The Artifact Placement Seam

This page explains the layering that decides **where a mission artifact physically lives**
— which directory a read resolves to, which branch a write commits against — and names the
places a caller can still bypass that decision. It exists because three missions in a row
spent their discovery budget re-deriving facts this page now states once: `#3014` was filed
on a false premise about the layering, and this mission (`read-side-seam-primary-primitive-
closure-01KYKMMT`) was re-scoped twice before the layering itself was pinned down correctly.

This page is **explanatory, not normative**. The binding placement rules live in
[ADR 2026-06-24-1](../adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md) and
[ADR 2026-07-23-1](../adr/3.x/2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md)
(see [Citations](#citations)); this page does not restate their rules, only shows how the code
that implements them is layered. Every code-shape claim below carries a `module:symbol`
citation so a future rename shows up as a broken reference rather than silent drift.

## What "routing" means here

"Routing" on this page means exactly one thing: **mapping a mission artifact's *kind* — a
`MissionArtifactKind` member such as `SPEC` or `STATUS_STATE`
(`src/mission_runtime/artifacts.py:63`) — together with the mission's *topology*, to a
`TopologySurface` (`src/mission_runtime/artifacts.py:23`): the physical tree the artifact
resolves to for reading or writing. This is the **placement sense** of "routing."

"Routing" is heavily overloaded elsewhere in this codebase — branch selection, git-commit
targets, dispatch/profile matching, sync fan-out, model/task assignment, and more all use the
same word for unrelated decisions. Do not infer any of those senses from this page. The full
disambiguation, with a "do NOT use when" guard for every governed sense, lives in the
`Routing` entry of [`docs/context/orchestration.md`](../context/orchestration.md#routing) —
consult it rather than guessing from context.

## The layer table

The question "where does this artifact live?" passes through five layers before it reaches a
filesystem path. Each layer has exactly one owner; a caller that reaches past its own layer
(picking a surface, or assembling a path, itself) is the semi-compliance shape [§4](#the-compliance-taxonomy)
names.

| Layer | Question answered | Owning module:symbol | Aware of |
|---|---|---|---|
| **L0 — entry** | *What* artifact am I reading or writing? | The caller names a `MissionArtifactKind` and asks a `PlacementSeam` (`src/mission_runtime/resolution.py:2302`) for `read_dir`, `write_target` or `write_dir` | kind only — nothing about *where* |
| **L1 — partition classification** | Which partition does this kind belong to — PRIMARY or COORD? | The `_PRIMARY_ARTIFACT_KINDS` / `_PLACEMENT_ARTIFACT_KINDS` frozensets and `assert_partition_invariant` (`src/mission_runtime/artifacts.py:165`, `:207`, `:353`) | kind only — **topology-blind** |
| **L2a — declared decision** | Where does this fact *architecturally* live, independent of what is materialized on disk right now? | `declared_read_surface` (`src/mission_runtime/resolution.py:2630`) | kind + topology; **materialization-BLIND** |
| **L2b — affirmative decision** | Where does this read resolve *right now*, given what is actually materialized? | `_classify_artifact_surface` (`src/mission_runtime/resolution.py:2679`), consuming `probe_coord_state` (`src/specify_cli/missions/_read_path_resolver.py:287`) | kind + topology + **materialization** |
| **L3 — candidate discovery / assembly** | Which concrete directories exist for this handle, and how is the final path assembled? | `resolve_planning_read_dir` (`src/specify_cli/missions/_read_path_resolver.py:1429`) and the module-private leaf `_compose_primary_feature_dir` (`src/specify_cli/missions/_read_path_resolver.py:1320`) | filesystem + handle form — this is where paths are **built** |
| **L4 — translation** | Given a chosen surface, *which* already-discovered location is it? | `translate_surface` (`src/mission_runtime/resolution.py:2588`) over a `SurfaceLocations` record (`:2556`) | neither kind nor topology — it **selects** a field off an already-populated record, and **refuses** (`ValueError`) when that field is absent |

**L2 is two functions, not one, and the split is deliberate.** `declared_read_surface` is
materialization-*blind* precisely so it can disagree with an already-resolved surface stamp —
that disagreement is what lets `GateExecutionContext.surface_cannot_hold`
(`src/specify_cli/acceptance/execution_context.py:196`, `#2885`) refuse rather than silently
pass an empty surface. Describing L2 as "one decision module" erases the reason that guard can
fire at all. `_classify_artifact_surface`'s own docstring names this: it defers to
`declared_read_surface` first and only consults the materialization-aware `CoordState`
classifier when the declared answer is `COORD`.

**L4 selects; it does not assemble.** `translate_surface` reads a field off a `SurfaceLocations`
record that L3 already populated and raises when the field is `None` — it never touches the
filesystem or builds a path from parts. Treating L4 as the place to "fix" a placement bug
teaches the exact misappropriation this page exists to prevent: re-adding discovery logic at a
call site instead of routing through L0–L3.

**A third `read_dir` route, not shown as a table row.** `PlacementSeam.read_dir`
(`src/mission_runtime/resolution.py:2359`) short-circuits exactly one kind —
`MissionArtifactKind.RETROSPECTIVE` — to `resolve_retrospective_home`
(`src/specify_cli/retrospective/writer.py:37`) at `resolution.py:2403`, **before** any of L2's
classification runs. See [Honest bounds](#honest-bounds) for why this is load-bearing rather
than a footnote.

## Both composition roots

There are two composition roots, not one, and both are reached through the same seam object:

- **The read root** — `resolve_artifact_surface` (`src/mission_runtime/resolution.py:2826`),
  projected by `PlacementSeam.read_dir`.
- **The write root** — `resolve_placement_only` (`src/mission_runtime/resolution.py:1864`),
  projected by `PlacementSeam.write_target` (`:2345`).

Both are constructed via one entry point, `placement_seam(repo_root, mission_slug)`
(`src/mission_runtime/resolution.py:3020`), which also asserts the L1 partition invariant
before returning — "two roots, one seam."

**This is the intent, not a landed invariant with zero exceptions** — see
[Honest bounds](#honest-bounds) for the measured count of direct callers that reach either root
without going through `PlacementSeam`.

### The write location (write_dir)

The write root answers *which ref* a commit lands on; it has no opinion on *which directory*
the bytes are written into. That second question belongs to `PlacementSeam.write_dir(kind)`
(`src/mission_runtime/resolution.py:2426`), added by mission
`coord-artifact-single-home-01M3V4BE` (Mission contract
`contracts/write-location-accessor.md`; decision record: the 2026-10-01 amendment of
[ADR 2026-06-19-1](../adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md)). It returns a
`WriteLocation` (`src/mission_runtime/write_location.py:77`: `path`, `checkout_root`,
`surface`, `coord_state_before`, `establishment`, `seed`).

`write_dir` is **not a third composition root**: it consults the same materialization-blind
`declared_read_surface` decision (L2a) that `read_dir` does, then branches:

- declared PRIMARY (a PRIMARY-partition kind, or any kind on `lanes` / `single_branch`) →
  `_declared_primary_write_dir`, identical to `read_dir` with no side effects;
- a published Mission's E2-eligible COORD kind, or `STATUS_STATE` → `_published_e2_write_dir`,
  the PRIMARY Mission dir with no coordination probe, so a coordination branch that
  consolidation has already torn down cannot raise here;
- every other COORD kind of a coordination-routed Mission →
  `specify_cli.coordination.coord_seed.establish_coord_write_location`
  (`src/specify_cli/coordination/coord_seed.py:1107`), the one place that **materializes,
  seeds, restores or refuses**.

The difference from `read_dir` is the whole point: a reader may fall back to the PRIMARY
partition on an `EMPTY` coordination surface (the loud fallback of ADR 2026-06-19-1, which
reads keep); a writer never does, so a COORD record cannot land on the repository root
checkout. The per-state behaviour table lives in the ADR amendment and is not repeated here.

## The compliance taxonomy

A call site's relationship to the seam falls into one of four shapes:

| Shape | What the caller does | Verdict |
|---|---|---|
| **Compliant (tier-1)** | Names a `MissionArtifactKind`, asks `placement_seam(...).read_dir(kind)` / `.write_target(kind)`, and fails loud on an unresolved surface | Target state |
| **Delegating-but-lenient** | Names a kind, delegates the surface decision to the seam, but the surrounding code never supplies the fail-closed input the leaf needs (e.g. a missing `coordination_branch`) | Censused as a bypass on the *leniency* axis, not the *routing* axis |
| **Semi-compliant** | Passes an already-canonical mission handle, but picks its own surface/resolver directly instead of asking the seam for the kind's home | **This page's headline concept** — see below |
| **Non-compliant** | Uses a raw or unrecognized handle, or hand-assembles a path from parts | Should red the read-side bypass census; one currently-permanent exception is named in [Honest bounds](#honest-bounds) |

**Semi-compliance is the headline shape, and it is invisible to a handle-hygiene gate.** A call
site can canonicalize its mission handle perfectly — passing every check the canonicalizer
authority gate (formerly `tests/architectural/test_resolution_authority_gates.py`,
`CANONICALIZER_PRIMITIVE_NAMES`; that file has been deleted) ran — and still choose its own surface by calling a
kind-blind resolver (`resolve_feature_dir_for_mission`,
`src/specify_cli/missions/_read_path_resolver.py:1695`) directly, instead of asking
`placement_seam(...).read_dir(<kind>)` to make the decision. The handle is canonical; the
*routing* is not. A gate that only checks handle canonicalization form (def-use canonicality)
cannot see this, because canonicality and routing-compliance are orthogonal axes.

**Which gate catches it, and which does not (US7.4):**

- **Does NOT catch it:** the (now-deleted) canonicalizer authority gate
  (formerly `tests/architectural/test_resolution_authority_gates.py`) — it verified the *handle argument*
  passed to a small allow-listed set of primitives is already canonical; it has no opinion on
  which primitive or surface the caller chose.
- **Does catch it:** the read-side bypass census
  (`tests/architectural/test_no_read_side_bypass.py`,
  `test_no_read_side_bypass_outside_sanctioned_and_allow_listed`) — it scans for calls to the
  kind-blind primitives by name (`primary_feature_dir_for_mission` while it existed;
  `resolve_feature_dir_for_mission` today) anywhere outside a named sanction, independent of
  whether the handle passed to them is canonical.

## Honest bounds

**Surface members with no production producer.** `TopologySurface` (`src/mission_runtime/
artifacts.py:23`) has five members — `PRIMARY`, `COORD`, `LANE`, `CONSOLIDATED`, `TEMP` — all
declared together so `translate_surface`'s totality assertion (`assert_surface_totality`,
`src/mission_runtime/artifacts.py:384`) has no phantom member to skip. Only `PRIMARY` and
`COORD` are wired to a production caller today; `LANE`, `CONSOLIDATED`, and `TEMP` are declared
with the seam but have **no production producer yet** — the enum's own docstring
(`artifacts.py:42-49`) says so directly. Do not read their presence in the enum as evidence a
caller resolves them today.

**The residual `PLACEMENT` rename debt.** ADR `2026-07-23-1` renamed the `TopologySurface`
member `PLACEMENT` → `COORD`. The frozenset that decides *which artifact kinds* route to that
surface, however, is still named `_PLACEMENT_ARTIFACT_KINDS` (`src/mission_runtime/
artifacts.py:207`) — the rename reached the enum member but not this frozenset's name. This is
named here, not laundered: a future cleanup can rename the frozenset without changing any
behavior, since membership (not the Python identifier) is what every consumer reads.

**The `RETROSPECTIVE` short-circuit is a foundation site, not a footnote.** `PlacementSeam.
read_dir` routes `MissionArtifactKind.RETROSPECTIVE` to `resolve_retrospective_home`
(`src/specify_cli/retrospective/writer.py:37`) before `resolve_artifact_surface` ever runs —
because a second RETROSPECTIVE-home computation would duplicate the single authority that
function already is. `resolve_retrospective_home` itself calls the module-private leaf
`_compose_primary_feature_dir` (`src/specify_cli/missions/_read_path_resolver.py:1320`)
directly, never `read_dir` again. This mission proved the short-circuit is load-bearing, not
cosmetic: an intermediate draft that routed the wrapper *through* `read_dir(RETROSPECTIVE)`
produced a **real recursion cycle** (`resolve_retrospective_home → read_dir(RETROSPECTIVE) →
resolve_retrospective_home → …`), caught only by call-graph tracing, not by a `RecursionError`
at runtime (the cycle's other legs terminate, so nothing crashed). The standing rule this
leaves behind: **any site beneath this short-circuit is a foundation site** — it must call the
leaf directly and permanently, never route back through `read_dir`.

**Two composition roots, measured bypass count (not a zero-exception invariant).** Re-derived
directly from the tree by AST-matching `Call` nodes (`ast.walk` over `src/**/*.py`, this
page's own re-derive-don't-copy discipline). **Re-measured 2026-10-02 on the tip of the
mission's last stacked lane (`1404842433`), because the earlier 12 + 6 figures predate the
`merge` → `consolidation` module renames and this mission's write-side work.** `PlacementSeam.
write_dir` adds no `resolve_placement_only` or `resolve_artifact_surface` caller of its own.

| Root | Total call expressions | Reached via `placement_seam(...)` or in-module projections | Direct callers outside `resolution.py` |
|---|---|---|---|
| `resolve_placement_only` (write) | 16 | 2 in `resolution.py`: `PlacementSeam.write_target` (`resolution.py:2352`) and the issue-matrix projection `_issue_matrix_ref` (`:2104`) | **14**, across 8 modules (`coordination/commit_router.py` ×6, `coordination/status_transition.py` ×2, `consolidation/executor.py`, `consolidation/done_bookkeeping.py`, `lanes/for_review_gate.py`, `cli/commands/safe_commit_cmd.py`, `cli/commands/agent/tasks_shared.py`, `mission_runtime/write_target_degrade.py`) |
| `resolve_artifact_surface` (read) | 11 | 2 in `resolution.py`: `PlacementSeam.read_dir` (`:2419`) and the thin projection `coord_read_dir_for` (`:2992`) | **9**, across 7 modules (`consolidation/forecast.py`, `policy/merge_gates.py` ×2, `cli/commands/accept.py`, `migration/runtime_state_cutover.py` ×2, `acceptance/execution_context.py`, `missions/_read_path_resolver.py` (`:1772`), `mission_runtime/issue_matrix_partition.py`) |

None of these 23 direct callers is a defect by itself — several are the composition root's own
adjacent infrastructure (e.g. `GateExecutionContext` in `acceptance/execution_context.py`
legitimately consumes `resolve_artifact_surface` directly, since it *is* the gate-facing
consumer of that authority, not a bypass of it). The count exists so "one seam object" is never
read as a landed zero-exception invariant — it is the destination, measured against the
current tree, not a claim about it. The count went **up** (18 → 23) between measurements
because the tree grew, not because callers were added to bypass the seam; the figure is a
snapshot, not a ratchet.

**The write-side rederivation gate has a blind spot, and its cap is zero.**
`tests/architectural/test_no_write_side_rederivation.py` guards the COORD write location in
two ways: a census of COORD writer functions must not obtain their directory from a read
resolver (`read_dir(<COORD kind>)` and the other read resolvers), and must not compose a
`KITTY_SPECS_DIR` path onto a worktree-named operand. Both scans cover **only the bodies of
the census functions** (`_COORD_WRITER_CENSUS`). A future caller that builds the Mission dir
through `specify_cli.coordination.legacy_resolution._checkout_mission_dir`
(`src/specify_cli/coordination/legacy_resolution.py:56`, documented for non-coordination
checkouts only) is outside that scan, and so is a writer that is not in the census. The live
allowlist is empty and the cap is 0 (`tests/architectural/_baselines.yaml`:
`test_no_write_side_rederivation: coord_writer_allowlist: 0`). The honest statement is "the gate
proves the census writers do not re-derive", not "no writer re-derives"; the gate is not
weakened to hide that.

**`#3055` — one deliberately-deferred edge (historical; now routed).** At the time of the audit,
`decisions/emit.py:71` (`src/specify_cli/decisions/emit.py`) still called `resolve_feature_dir_for_mission` directly
rather than routing through the seam. It was allow-listed, not routed, because the
coord-authority gate (formerly `tests/architectural/test_resolution_authority_gates.py`, since
deleted) independently sanctioned this exact call as a permanent legitimate coord-owned write bypass, keyed on the
literal primitive name — the gate must learn the seam idiom (recognize a kind-aware
`read_dir(<COORD kind>)` call as the same sanctioned bypass) before this site can route without
breaking that gate. `#3055` tracked the follow-up. (Superseded: the site was routed onto
`read_dir(STATUS_STATE)` in write-side-seam-matrix-tracer WP02, and the sanctioning gate was deleted
in #3285; see the `decisions/emit.py:71` row in
[`read-side-seam-classification.md`](../development/reference/read-side-seam-classification.md).) This is the one edge *this mission audited*
as directory-identical-routable and deliberately deferred. It is not the only unrouted
sanctioned `resolve_feature_dir_for_mission` coord-write: `widen/state.py:63`,
`agent_tasks_ports.py:322`, and `lanes/recovery.py:765` carry the same coord-authority
sanction, and `widen/state.py:63`'s rationale is verbatim-identical to this one — they were
simply not re-audited for the directory-identical-routing property this mission established
for `emit.py:71`. So the honest statement is "the one edge adjudicated and deferred," not "the
one call site in tension."

**Current state (2026-10-02).** `decisions/emit.py:_mission_dir` no longer calls
`resolve_feature_dir_for_mission` or `read_dir` at all: it resolves the decision-event write
location through `placement_seam(...).write_dir(STATUS_STATE).path`, because a decision event is a
COORD record and `read_dir` would degrade an `EMPTY` coordination surface to the repository root
checkout. Of the three sibling sanctions, `agent_tasks_ports.py` (`RealCoordCommitRouter.
feature_write_dir`) and `lanes/recovery.py` (`reconcile_status`) now also take `write_dir`;
`widen/state.py:63` (`WidenPendingStore.__init__`) still calls `resolve_feature_dir_for_mission`.

## Partition-Move Audit Checklist

[ADR 2026-06-24-1](../adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
establishes read/write symmetry as the governing rule for the L1 partition:
a kind's read side and write side must resolve to the *same* partition
(PRIMARY or COORD). That symmetry is a property of the **kind
classification** (`_PRIMARY_ARTIFACT_KINDS` / `_PLACEMENT_ARTIFACT_KINDS`,
`src/mission_runtime/artifacts.py`), not of any single call site — so moving
a kind between partitions is a whole-symmetry operation. Reclassify the
write side without correcting every reader and you get a documented, real
production regression, not a theoretical one:

**The PR #3437 (issue #3371) case.** A prior mission correctly reclassified `lanes.json`
(`LANE_STATE`) as PRIMARY and moved its **write** target accordingly — but
one reader, `implement._resolve_lanes_dir`, still read it via the coord
STATUS surface. Coord-topology `implement` then couldn't find its own lane
state and refused. Every unit suite stayed green, because none of them
exercised the coord read path end-to-end; the only test that caught the
break was `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`, a
coord-topology full-workflow smoke test — pass on `main`, fail on the
branch. **This is the standing lesson: an e2e test, not a unit test, is
what catches a partition-move straggler**, because unit tests exercise a
resolver function directly with an already-correct `feature_dir`, while the
break lives in *which* `feature_dir` an out-of-loop caller hands that
function.

**The checklist**, next time a kind's partition classification moves:

1. **Grep every reader** of the moved kind — every call to
   `read_lanes_json` / `require_lanes_json` / a kind-specific `resolve_*_dir`
   helper, not just calls through `placement_seam(...).read_dir(<kind>)`.
   The seam is the compliant path; the point of this step is finding the
   ones that *aren't* on it.
2. **Classify each reader** into one of three buckets:
   - Uses the seam (`placement_seam(repo_root, slug).read_dir(<kind>)`) —
     compliant; moves automatically with the kind's classification.
   - Receives its directory from an **out-of-loop coord-resolving caller**
     (a caller that independently resolves a coord/status surface and hands
     the result down) — trace that caller too; it is invisible to a grep
     scoped to the moved kind's own helper names.
   - Resolves the coord surface directly, bypassing the seam — broken by
     construction; this was `implement._resolve_lanes_dir`'s shape in the
     PR #3437 case.
3. **Watch for graceful-degradation callers especially.** Some out-of-loop
   coord-resolving callers (merge ordering, `policy/merge_gates`, the
   bulk-edit diff-base fallback) don't crash on a stale surface — they
   silently `SKIP` a gate or fall back to an empty graph. A caller that
   degrades gracefully on the wrong surface hides the break instead of
   surfacing it, which is worse than a crash for audit purposes: nothing
   in the test output points at the mismatch. (This is the same
   fail-open-hides-a-break shape the charter's C-009 class names elsewhere.)
4. **Prove it with an e2e test, not just unit reads.** A unit test that
   calls the resolver directly with a hand-built `feature_dir` cannot catch
   a caller that resolves the *wrong* `feature_dir` upstream — by
   construction, it never gives the caller the chance to go wrong. Run (or
   add) a full-workflow / topology-level test that exercises the reader
   through its real call chain, for both PRIMARY-only and coord topologies.

### Worked example: `DECISION_LEDGER` moved COORD to PRIMARY (2026-10-01)

Mission `coord-artifact-single-home-01M3V4BE` moved `MissionArtifactKind.DECISION_LEDGER`
(`decisions/index.json` and the `DM-*.md` files) from `_PLACEMENT_ARTIFACT_KINDS` to
`_PRIMARY_ARTIFACT_KINDS` (`src/mission_runtime/artifacts.py:165`, `:207`; the kind sits in the
PRIMARY frozenset at `:197`). The decision and its reasoning are in
[ADR 2026-10-01-3](../adr/4.x/2026-10-01-3-decision-ledger-primary-partition.md). This is the
checklist above applied, step by step:

1. **Grep every reader.** The reader blast radius was enumerated up front (the Mission's
   research record, D12) instead of being found by symptom, and every reader that flips has a
   focused test of its post-flip answer
   (`tests/mission_runtime/test_decision_ledger_reader_flips.py`).
2. **Classify each reader.** Seam readers moved with the classification automatically. The
   shared predicates (`kind_is_coordination_residue`, and `is_coord_residue_churn` in
   `src/specify_cli/coordination/coherence.py`) changed their verdict for the ledger at every
   caller, including the topology-less ones that project COORD by default. The writer
   (`decisions/emit.py` and the store) was already PRIMARY since #4966, so the *taxonomy* was
   the straggler of that earlier intent, not a reader.
3. **Graceful-degradation callers.** The consolidation planning-recency pass is the case the
   checklist warns about: it can silently overwrite a merged file. It now excludes any path
   covered by a registered merge driver
   (`src/specify_cli/consolidation/planning_recency.py`), so the
   `spec-kitty-decision-index` driver (`union_decision_index` / `run_decision_index_driver`,
   `src/specify_cli/consolidation/drivers.py:1236`, `:1280`) owns reconciling `index.json`
   instead of a target-favouring restore dropping a lane-added decision entry.
4. **Prove it end to end.** `tests/integration/test_coord_single_home_workflow.py` runs the
   ledger through create, `spec-commit`, `accept`, consolidate and a fresh clone, for the
   coordination topologies, not only unit reads.

One consequence is specific to this move: the *events* about decisions
(`decisions.events.jsonl`, `DECISION_LOG`) did **not** move; they stay COORD, so a Mission can
have a PRIMARY ledger whose events live on the coordination branch. A divergence between the
two is a recorded finding (`DECISION_LEDGER_ONLY_ON_COORDINATION`, `DECISION_LOG_FORKED`;
`src/specify_cli/decisions/fork.py:407`, `:442`, `:514`), repaired by `doctor decisions
--repair`, and teardown refuses with `COORDINATION_LEDGER_UNREPAIRED`
(`src/specify_cli/coordination/teardown.py:151`) rather than dropping an unreconciled ledger.

**Coordination residue note.** `_COORD_RESIDUE_DIRS` (`src/mission_runtime/artifacts.py:303`)
maps a Mission-relative directory name to the kind it holds, which
`kind_is_coordination_residue` then judges by the kind's partition. Its `decisions`
entry maps to `DECISION_LEDGER`; since the move, `decisions/` is a **PRIMARY-partition kind and
is never reset as residue**: the directory still maps to the same kind, and only the kind's
partition membership changed.

## Two-Axis Resolver-Site Classification

Auditing a resolver call site for correctness (not just for seam
compliance) means answering two independent questions, not one:

**Axis A — raise or degrade.** When the target cannot be resolved, does the
call site raise (fail-closed — e.g. `require_lanes_json` raising
`MissingLanesError`, or `resolve_write_target_or_degrade`
(`src/mission_runtime/write_target_degrade.py`) called with
`degrade_ref=None`), or does it silently degrade to a fallback ref or an
empty/skipped result (fail-open — e.g. the same helper called with a
caller-supplied `degrade_ref`, or the graceful-degradation callers named
above)? Both arms are legitimate in the right place; the audit question is
whether the *caller* chose the arm deliberately for its own correctness
requirements, or inherited it by accident from a shared helper's default.

**Axis B — anchor-root.** Does the call site route its `repo_root` through
`get_main_repo_root()` (`src/specify_cli/core/paths.py`) before resolving —
anchoring at the primary checkout regardless of which worktree the process
is physically running from — or does it resolve directly off whatever
`repo_root` (or cwd) it was handed, which may itself be a lane worktree? An
unanchored call site invoked from inside a lane worktree silently resolves
against that worktree's own tree instead of the primary checkout, producing
a worktree-local answer for a question that has exactly one correct answer
mission-wide.

**The two axes are orthogonal — classify both, not just one.** A call site
that raises loudly (Axis A) but is unanchored (Axis B) fails safe against
the *wrong* root — a clean exception that still doesn't prove the right
directory was ever examined. A call site that degrades quietly (Axis A) but
is correctly anchored (Axis B) at least looks in the right place, but can
still mask a real gap behind a plausible-looking fallback. Neither
combination is "obviously fine because it raises" or "obviously broken
because it degrades" — record both axes for a call site before signing off
on it.

## Citations

- [ADR 2026-06-24-1: Kind- and Topology-Aware Artifact Placement — One Partition, Read/Write
  Symmetry](../adr/3.x/2026-06-24-1-kind-and-topology-aware-artifact-placement.md) — the
  governing decision for the L1 partition (`_PRIMARY_ARTIFACT_KINDS` /
  `_PLACEMENT_ARTIFACT_KINDS`) and for read/write symmetry across the two composition roots.
- [ADR 2026-07-23-1: `surface` names two unrelated domains — split the vocabulary, rename to
  `ToolSurfaceKind` and `TopologySurface`](../adr/3.x/2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md)
  — the governing decision for the `TopologySurface` vocabulary (including the
  `PRIMARY`/`COORD`/`LANE`/`CONSOLIDATED`/`TEMP` members) and the forbidden-conditioning rule
  (naming a surface is not licence to branch behavior on it).
- [ADR 2026-06-19-1: coordination-worktree-empty surface policy](../adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md)
  — the 2026-10-01 amendment governs `PlacementSeam.write_dir` and the per-state write behaviour; the
  2026-06-21 amendment still governs the read-side loud fallback.
- [ADR 2026-10-01-3: the decision ledger is a PRIMARY-partition kind](../adr/4.x/2026-10-01-3-decision-ledger-primary-partition.md)
  — the partition move in the worked example above.

See also the `Routing` disambiguation in
[`docs/context/orchestration.md`](../context/orchestration.md#routing) for every other sense of
"routing" this page deliberately does not cover, and
[`branch-target-routing.md`](branch-target-routing.md) for the **branch** sense — which git
branch a commit lands on, a related but distinct question from the placement question this page
answers.
