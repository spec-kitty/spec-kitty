---
title: 'Mission #883 Research Dossier (pre-spec, 4-lens squad)'
description: 'Point-in-time pre-spec research synthesis for mission #883 with file:line evidence; superseded by the ADR and brief where they differ.'
doc_status: deprecated
type: explanation
updated: '2026-07-14'
related:
- docs/adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md
- docs/archive/plans/engineering-notes/883-mission-type-authority-brief.md
---

# Issue #883 — Pre-spec research synthesis (4-lens squad)

> **Retired (deprecated).** Superseded via ADR `2026-07-14-2-doctrine-to-core-mission-type-resolution-unification` and canonical `docs/architecture/mission-type-resolution.md` (#883). Preserved as a historical record.

> **Point-in-time dossier.** This is the raw pre-spec research (four-lens squad
> plus the architect design pass) captured for maintainer/implementer reference —
> it retains the original file:line evidence. Two things happened *after* it was
> written: an adversarial second-opinion squad corrected several claims (e.g. the
> leak anchors here point at code later found dead; the real leak is
> `_load_action_doctrine_bundle` at `context.py:865`), and a spec-stage interview
> resolved Q1–Q4. **Where this dossier and the
> [ADR](../../../adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md)
> or the [mission brief](883-mission-type-authority-brief.md) differ, the ADR and
> brief are authoritative.** Read this for the evidence trail, not the final design.

---

## 0. OPERATOR DECISIONS (2026-07-14) — authoritative, overrides defaults below

**North star (end-goal):** `src/specify_cli/missions/` template tree can eventually be **DELETED**. `software-dev` becomes a built-in **doctrine** mission type on equal footing with documentation/research/plan — feeding **step contracts, gates, and templates** from doctrine → **through the charter** → into the **execution loop (FSM core)**. No `software-dev-default` special-casing; no hardcoded core knowledge of sw-dev.

**Operator's layer model:** DOCTRINE offers mission types + step contracts + prompts + governance (catalog). CHARTER activates a mission type and layers customizations onto it (like any other doctrine artifact). CORE is an FSM adhering to configured templates/steps/types keyed off mission type; semi-prepared for "states & transitions as config."

**#883 = slice 1 of the specify_cli/missions retirement epic.** It must be an intentional first step toward the north star, never entrench the split.

Decisions on the 4 crux questions:
1. **Surface strategy = FULL CONSUMER MERGE.** One charter-mediated resolution path (doctrine → charter → core) feeds BOTH the WP prompt (Surface B / prompt_builder:346) AND step-bootstrap context (Surface A / context --action). Seam designed GENERAL (governance = first consumer; templates/gates/step-contracts follow). Retire/absorb dead `governance_refs`.
2. **Leak fix = IN SCOPE NOW.** Key action path off `meta.json mission_type`; thread feature_dir/mission_type through `scope_router` → `build_charter_context` → `_append_action_doctrine_lines`; missing source = HARD ERROR; split `template_set` (retain for template-file selection, remove as mission-type proxy).
3. **Layers = 3 of 4.** Shipped mission-type governance + PER-TYPE PROJECT OVERRIDE (charter customization layer) + close leak. DEFER mission-instance addendum (spec it, don't build).
4. **Content = AUTHOR FULL SETS** for documentation, research, AND plan.

Awaiting: architect-alphonso design pass converting this into the concrete unified `doctrine→charter→core` seam + migration order + WP spine.

---

**Mission:** Add mission-type governance profiles for non-software missions.
**Branch:** `mission/883-mission-type-governance-profiles` @ spec-kitty-gate-doctrine clone (off upstream/main `a32d2fab8`).
**Lenses:** researcher-robbie (content/prior-art), architect-alphonso (resolution), paula-patterns (split-brain), doctrine-daphne (mechanism).

---

## 1. The one-line truth

The *mechanism* for mission-aware governance landed; the *content* did not. But "the content" is more tangled than the issue says: there are **THREE per-mission-type governance surfaces**, feeding **two different runtime consumers**, plus one **dead+dangling** field. #883 is really: **(a) unify to a canonical surface, (b) populate non-software content, (c) close a real leak in the action-scoped path, (d) add the enforcement test the ACs demand.**

## 2. The three surfaces (converged across all four lenses)

| # | Surface | Consumer | State |
|---|---------|----------|-------|
| **B** | `missions/<type>/governance-profile.yaml` (`selected_directives/tactics/...`) | `charter/mission_type_profiles.py` → `prompt_builder.py:346` → **WP prompt** | LIVE, keyed off `meta.json mission_type`, **hard-fails** (no sw-dev fallback), but **empty** for all 4 types |
| **A** | `missions/<type>/actions/<action>/index.yaml` (`scope` edges) | DRG `graph.yaml` → `charter context --action` → **step bootstrap** | LIVE, **populated** & per-type differentiated, but the runtime read **LEAKS** (see §3) |
| **—** | `mission_types/<type>.yaml` `governance_refs: []` | CLI display only (`mission_type.py:1486`) | **INERT** — no extractor reads it; `activate mission-type --cascade` is a **no-op**; `software-dev` holds **dangling** `DIR-010/DIR-011` (real ids are `DIRECTIVE_0NN`) |

## 3. The real leak (architect-alphonso — corrects the "already prevented" reading)

- Surface **B** is leak-proof and tested (`test_mission_type_profile_resolution.py`, FR-011 `template_set: null`).
- Surface **A LEAKS today:** `context.py:865,1465` compute `mission = (template_set or "software-dev-default").removesuffix("-default")`. A non-software mission that never set `template_set` resolves to **`software-dev`** and loads software-dev's action doctrine. Root cause: `scope_router.py:66` resolves `feature_dir` then **throws it away**, so `_append_action_doctrine_lines` is structurally blind to mission type.
- **Fix:** key the action path off `meta.json mission_type` (the source B already trusts); thread `feature_dir`/`mission_type` through `build_with_scope → build_charter_context → _append_action_doctrine_lines`; make "no mission-type governance source" a **hard error**, never a sw-dev fallback. `charter context --action` invoked without a feature_dir (planning from repo root) needs an explicit `--mission-type`/`--feature-dir` and a defined non-defaulting behavior.

## 4. `template_set` — split it (do NOT thread governance through it)

- **RETAIN** for template-file selection (`compiler.py`, `catalog.py`, `resolver.py`) — genuinely load-bearing.
- **REMOVE** as the mission-type proxy in governance routing (`context.py:865,1465`) — this is the "inferred `template_set`" the AC rejects.
- Whack-a-field trap (paula): `template_set` carries **three shapes** under one name — mapping (`mission_types/*.yaml`), string (`governance-profile.yaml`), derived-set (`catalog.py:353`). No shared canonicalizer.

## 5. Split-brain (paula) — ADJACENT, do NOT fold in

- Dual missions-tree: `specify_cli/missions/` (LIVE expected-artifacts/templates) vs `doctrine/missions/` (governance lives here; its `expected-artifacts.yaml` is a **dead read-path**, 0 non-test callers, already drifted unguarded).
- **Land governance entirely on the doctrine side; do NOT touch `specify_cli/missions/`.** Resist any "keep trees in sync" guard (entrenches the split) — derive-don't-sync is a separate/later mission. Pin a guard that the dead tree can't silently reactivate.
- `expected-artifacts.yaml` is the **wrong home** for governance (category error: governance → DRG nodes, not mission output artifacts). The transferable #2628 lesson is the anti-pattern ("no parallel surface"), not the model.

## 6. Mission-type key canonicalization (paula)

- **No single chokepoint** for the `mission_type` key (it's excluded from `kind_vocabulary`). Read raw at `mission_type_profiles.py:380` and again at `specify_cli/mission.py:556`.
- Route through **one** `canonicalize_mission_type()` in `charter.mission_type_profiles` (already owns `CANONICAL_MISSION_TYPES`); make both readers consume it. Don't add a second normalizer.

## 7. Mechanism gaps if we go the `governance_refs` route (daphne)

- **Gap A:** extractor never reads `governance_refs` → populating it changes `graph.yaml` by **nothing** → freshness gate stays green = **false assurance**.
- **Gap B:** `activate mission-type --cascade all` is a **no-op** (`activate.py:317` returns when `_source_urn` is None for mission-type). `scope` isn't in `REFERENCE_RELATIONS` either.
- No new artifact KIND is needed or wanted (`ArtifactKind` fixed at 8+template+asset; `mission-type` is deliberately not a kind).

## 8. Enforcement test the ACs demand (daphne — concrete)

New `tests/doctrine/drg/test_mission_type_governance_isolation.py` (doctrine-tier, built on generated graph):
1. **Non-leakage:** resolved doctrine set for each non-sw type is **disjoint** from a pinned sw-dev-only denylist (`paradigm:git-flow`, `trunk-based`, `shared-branch-ci`, testing/refactoring directives...).
2. **Non-vacuity twin (mandatory):** same denylist **is** present in software-dev's set (else #1 is vacuous — memory: prove the invariant fires).
3. **`governance_refs` resolvability:** every entry resolves via `resolve_artifact_urn` — **currently FAILS on `software-dev.yaml`**, surfacing the `DIR-010` placeholder.
4. **Round-trip** (only if we wire governance_refs→DRG): entry ⇒ matching `graph.yaml` edge + `regenerate-graph --check` fresh.

## 9. Prior-art constraints

- **#461** (largely landed): governance = DRG-resolvable artifacts + charter synthesis. No bespoke config format.
- **#832** (open, org-layer DRG): shipped→org→project 3-layer merge must stay **overridable**; don't make selections a floor.
- **#901** (4.0 governed front door): per-type profiles are the substrate for intent-scoped loading. #883 is a dependency.
- **ADR 2026-05-16-1:** reuse field-level merge + `DoctrineLayerCollisionWarning` for layer precedence; don't invent new rules.

## 10. The issue's 4-layer model vs reality (architect)

| Layer | Status |
|-------|--------|
| project_charter | EXISTS, live |
| shipped_mission_type_governance | EXISTS but EMPTY ← the content home |
| project_mission_type_override | PARTIAL — `governance.yaml` overrides are project-global, not per-type-scoped |
| mission_instance_addendum | **MISSING** — no surface reads a per-feature_dir addendum |

## 11. Genuine content gaps (robbie) — `[author-new]` vs `[reference-existing]`

- **Documentation** wants: source-of-truth `[ref:042-common-docs + common-docs styleguide]`, freshness `[ref:037 + author-new SLA styleguide]`, Divio-discipline `[author-new]`, audience `[author-new + instance layer]`, plain-language `[author-new]`, accessibility `[author-new]`, publication `[author-new]`, review-flow `[ref: documentation-curation-audit + gap-prioritization]`.
- **Research:** decision-doc `[ref:003]`, dialectic/premortem/reverse-spec tactics `[ref]`, citation discipline `[author-new]`, `spike-timebox-policy` procedure `[author-new — referenced by profile but file missing]`.
- **Plan:** decomposition/moscow/eisenhower/ADR/premortem tactics `[ref]`, context-aware-design `[ref:031]`, DDD/deep-module/c4 paradigms `[ref]`, planning-and-tracking styleguide `[ref]`. (DIR-010/DIR-001 *may* legitimately apply to plan — operator call.)
