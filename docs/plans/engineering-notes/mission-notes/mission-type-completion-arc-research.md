---
title: 'Mission-type completion arc — pre-spec research (#2652 / S0–S4)'
description: 'Pre-spec research for the mission-type completion arc (#2677 DRG edges, #2657 default-charter, #2659 enumeration): ADR slice mapping, DRG-edge design, 3-track decomposition.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/mission-notes/index.md
- docs/adr/3.x/2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md
- docs/adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md
- docs/plans/engineering-notes/883-mission-type-authority-brief.md
---

# Mission-Type Completion Arc — Pre-Spec Research

> **Historical (mission closed).** The mission this research grounded, `mission-type-drg-edges-01KXKY2N`, has closed (see its `retrospective.yaml` under `kitty-specs/`). Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

**Scope.** Research supporting three sibling missions under epic **#2652**, produced by a 3-lens pre-spec
squad (architect-alphonso, python-pedro, paula-patterns) verified against `main` HEAD `e162a8900`
(post-#2676 merge). Owned as planning deliverables by the two missions specced from it:
`mission-type-drg-edges-01KXKY2N` (#2677) and `activation-driven-enumeration-01KXKY7J` (#2657 + #2659-E1).
Transient by intent — fold into the owning missions' `kitty-specs/` artifacts on close.

## 1. The governing ADR maps the whole arc to sequenced slices

ADR `2026-07-15-1` ("Doctrine Offers, Charter Activates, Runtime Consumes Only Activated") states the
binding rule and its slices. Our three issues map onto them:

| ADR slice | Meaning | Issue | Mission |
|-----------|---------|-------|---------|
| **S0** | `mission_type` (+ `mission_step_contract`) as first-class DRG nodes — *and their edges* | #2651 minted nodes; **#2677** wires edges | **A** (drg-edges) |
| **S1** | `init` provisions the default charter (`packs/default.yaml`) | #2657 | **B** (enumeration) |
| **S2** | collapse the read-time "absent key → all" fallback onto `default.yaml` | #2657 | **B** |
| **enum** | canonicalise enumeration onto the activation set (E1) | #2659-E1 | **B** |
| **S3** | gate the runtime `_runtime_template_key`/`get_or_start_run` path (E2) | #2659-E2 | **C (deferred)** |
| **S4** | wire the `template_set` slot (templates as activation-scoped config) | later | future |

Guards to land with the work (ADR G1–G6): **G2** (built-in list derived from `MissionTypeRepository.default()`
+ drift test) was **already delivered by #2676** for `show_origin.py`/`home.py`. G1 (single availability
seam), G3 (default charter one artefact) are Mission B's. G4/G5/G6 are downstream.

## 2. Brief A — DRG-edge design (#2677 / Mission A)

**Bottom line: one edge class resolves all 8 orphans with zero new node kinds.**

- The 8 orphans are `mission_type:{software-dev,documentation,research,plan}` + `action:plan/{plan,research,review,specify}`,
  minted edge-less by #2651 (`src/doctrine/drg/models.py:46` — "nodes only, no edges yet"). They push the
  shipped-graph orphan count to **18 > ceiling 14** (`test_shipped_graph_orphan_count_within_documented_residual`,
  **red on main**).
- **Minimal-correct fix:** emit `mission_type:X → action:X/<step>` with relation **`requires`**, sourced from
  each type's `action_sequence` (`mission_types/<id>.yaml`), targeting `action:*` nodes that **already exist**
  (24 of them). `mission_type:plan → action:plan/{specify,research,plan,review}` de-orphans both the plan
  type node (outbound) and the 4 plan action nodes (inbound). Count 18 → **10 ≤ 14** — **do not raise the ceiling**.
- **`requires`** is correct: composition-of-mandatory-ordered-parts, the relation the **charter cascade**
  traverses (making the currently-no-op mission-type cascade meaningful); no cycle (actions only emit `scope`
  outbound); validator-clean (all sequence steps have index dirs → no dangling target).
- **The other operator-intended targets need node populations that don't exist**: `mission_step_contract`
  (0 nodes; but steps = action nodes already), WP `template:` nodes (16 exist but wrong population;
  `template_set` null for 3/4 types — #883 template deferral), `asset` (0 nodes — `assets/built-in/` is just
  a README), `guard`/`gate` (no `NodeKind` at all). All **honest future scope**; none touch the orphans.
- **Generator workflow:** add `extract_mission_type_edges` beside `_discover_mission_type_nodes`
  (`extractor.py:768`), emit into `all_edges` before calibrate/sort; `spec-kitty doctrine regenerate-graph`
  rewrites + commit `graph.yaml` (byte-identity freshness gate). Re-pin the S0 placeholder
  `test_mission_type_nodes_have_no_incident_edges` (invert), update the `models.py:46` comment, note the
  residual doc. Open forks: relation `requires` vs `instantiates` (recommend `requires`); `retrospect`
  actions (in no `action_sequence`) — leave (already non-orphan).

## 3. Brief B — Default-charter + enumeration current state (#2657 + #2659 / Mission B)

- **#2657 real remaining scope (smaller than the epic implies):** the dead `except ImportError → CANONICAL`
  branch is **already gone** (retired by #2669); the behavioral "absent key → all four" fallback **remains**,
  single-sourced at `pack_context.py:277`. `packs/default.yaml`, `load_default_pack_activation_ids()`, and
  the legacy-provisioning migrations (`m_3_2_0rc35_default_charter_pack`, `..._activate_builtin_mission_types`)
  **all exist**. Remaining = **S2** (read-time authority → default-pack data; delete `_BUILTIN_*` as a
  fallback source; keep fail-closed) + **S1** (fresh-`init` provisioning — the real gap; no init path writes
  the keys today).
- **#2659 splits E1/E2:** **E1** (route `list_available_missions` `mission.py:489` + `discover_missions`
  `mission.py:806` + `_packaged_missions_dir` through `existing_mission_types`) is low-risk and needs only
  #2657. **E2** (flip `_build_discovery_context` `runtime_bridge_io.py:230-241` root specify_cli→doctrine +
  activation-gate) is hot-loop and blocked **additionally on #2658** (templates-as-config). The doctrine
  `plan` sidecar even lacks the top-level `steps:` block the runtime schema needs — a disposable
  doctrine-vs-specify_cli parity scaffold is required before the flip.
- **Ordering:** #2657 MUST precede E1 — the E1 filter is untestable while an implicit absent-key fallback
  re-expands to all four (masks deactivation).

## 4. Brief C — Mission decomposition (3 tracks, not one)

The three issues touch **three subsystems with no shared write-seam** (doctrine/drg vs charter vs
specify_cli/runtime). Recommended decomposition:

- **Mission A = #2677** — standalone `doctrine/drg`; **clears the red main gate**; ship first.
- **Mission B = #2657 + #2659-E1** — `charter` + `specify_cli`; internally #2657(S2→S1) → E1.
- **Mission C = #2659-E2** — deferred, gated on #2658 + parity scaffold.

Foldable-issue map: #2658 (prerequisite for E2 only — do not fold), #2660/#2661 (downstream/terminal),
#1923 (coordinate only on the `DOCUMENTED_ORPHAN_RESIDUAL = 14` constant — #2677 wires *its* 8 orphans,
#1923 curates the *other* 14). Post-#2676 drift: #2657's cited `mission_type_profiles.py:388` is now the
`existing_mission_types` docstring; the fallback moved to `pack_context.py:277`.
