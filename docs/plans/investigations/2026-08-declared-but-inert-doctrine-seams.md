---
title: 'Research: the declared-but-inert doctrine/DRG seam family (#3608, #3530, #3629)'
description: 'Research brief for the declared-but-inert doctrine/DRG seam family: the shared declaration-vs-consumption root cause and per-issue accuracy verdicts (#3608, #3530, #3629).'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/3-2-x-milestone-roadmap.md
- docs/plans/domains/doctrine-charter-domain-plan.md
---
# Research: the "declared-but-inert" doctrine/DRG seam family (#3608, #3530, #3514, #3511, #3629)

> **Historical (3.2.x cycle).** Kept as a record; the "3.2.x" milestone below is the closed prior cycle. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

**Date:** 2026-08-23
**Branch:** `research/issues-3608-3530-3514-3511-3629`
**Base:** `main` @ `fea9f1b470` (== `upstream/main`)
**Milestone for all five:** 3.2.x (#4) — G1 "deepen Doctrine/Charter/DRG impact on runtime execution", G2 "strangle core domains onto canonical SSOTs", "no new shadow paths".

Each issue was re-verified against current `main`. Accuracy verdicts and the shared
root cause follow.

---

## Shared root cause

All five are instances of one disease:

> **A doctrine/DRG artifact is authored, schema-legitimized, and validated — and
> silently never takes effect at runtime, because the boundary between
> *declaration* and *consumption* is neither derived-from-a-single-source nor
> fail-loud nor test-pinned.**

This is the exact framing of the #3530 tracking issue ("a success report over an
inert result") generalized one level up: it is not only org packs that load-but-
don't-arrive — it is enum copies (#3608), schema fields (#3629 part 1), a
shrink-only *policy* (#3514), and integration seams (#3511). The system reports
success (or simply stays silent) over an inert result in every case.

Every one of these would be prevented by one of two moves:

1. **Derive, don't copy** — resolve the consumed set from the single canonical
   source (enum, schema) instead of hand-maintaining a parallel copy. (G2.)
2. **Fail loud at the declaration→consumption seam** — a typo, a missing tier, a
   dropped kind, or a dead field must raise or be pinned by a structural test,
   not fall through to `None`. (rc3 fail-loud burndown, epic #3410.)

### Mechanism taxonomy

| Mechanism | Issues | One-liner |
|---|---|---|
| **Duplicated authority that drifts** (SSOT violation) | #3608 | hand-copied `NodeKind` → drops URN kinds |
| **Dead declared field / inert seam** | #3629 (part 1), #3511 | schema field never read / seam never wired |
| **Layer-blind read** (org tier dropped) | #3530 (+ members) | built-in path ≠ org path for same kind |
| **No fail-loud on bad selection** | #3629 (part 2), #3530 (close cond.) | typo mints a dangling edge, pruned silently |
| **Documented-but-absent enforcement** | #3514 | the guard against drift is itself inert |

### Relationship map

- **#3608 ↔ #3629 part 1** — the *same silent-drop-at-the-DRG-boundary bug at two
  tiers.* #3629 part 1 drops declared `context-sources.*` fields at the
  **YAML→DRG extraction** boundary; #3608 drops legitimate DRG-URN kinds at the
  **URN-recognition/resolution** tier. Neither errors.
- **#3608 ↔ #3530** — #3608's silent fall-through of `glossary_pack:<id>` /
  `mission_type:<id>` selectors is a concrete instance of #3530's "doctrine that
  loads but does not arrive." (#3608 lives in the charter synthesizer resolution
  path, not org-pack load, so it was correctly filed separately — but it is the
  same family.)
- **#3629 part 2 ↔ #3530 closing condition** — both demand *fail-loud on
  misconfiguration* ("a misconfigured pack says so instead of reporting
  success"). Same doctrine, different call site.
- **#3511 is the constructive counterpart** — it is the *tracked home for
  deliberately-deferred inert seams.* The "good" (intentional, tracked)
  version of declared-but-inert, vs the accidental versions in #3608/#3629.
- **#3514 is the meta-level** — the test that would enforce the shrink-only
  drift policy is *itself* a declared-but-absent artifact. The same disease one
  level up: the guard against drift is inert.

### Family/provenance already recognized in the tickets

- Whack-a-copy / duplicated-constant: #3608 → #3562, #3461, #3427.
- Org-tier delivery: #3530 groups #3384/#3387/#3490/#3516/#3523/#3525/#3527/#3385
  (+ related #3488/#3489/#3386/#3407/#3388/#3412).
- Fail-loud burndown epic: #3410 (parent of #3629 via M2 PR #3628).
- Keystone: #2467 (parent of #3511 via #3507).

---

## Per-issue accuracy verdicts

### #3608 — `_DRG_NODE_KINDS` hand-copy drift — **STILL VALID (numbers shifted)**

- `src/charter/synthesizer/topic_resolver.py:37` is still a hand-maintained
  `frozenset` copy of `NodeKind` (`src/doctrine/drg/models.py`).
- **Drift recomputed on `main`:** `NodeKind` now has **16** members (ticket said
  16); the copy now has **10** (ticket said 9). Missing from copy: **6** —
  `anti_pattern`, `asset`, `glossary`, `glossary_pack`, `mission_step_contract`,
  `template`.
- **The whack-a-copy point is now *stronger*, not weaker:** since filing,
  `mission_type` was hand-added to the copy (someone whacked the ticket's example
  mole) while `anti_pattern` newly drifted *in* to the enum and was missed. The
  ticket's headline example `mission_type:<id>` now resolves, but
  `glossary_pack:<id>` is **still silently dropped** at
  `topic_resolver.py:236` (`if lhs not in _DRG_NODE_KINDS: return None`).
- **No guard test exists:** `grep -rn _DRG_NODE_KINDS tests/` → nothing.
- Fix direction (derive from enum + drift-guard test) unchanged and correct.
- **Recommendation:** refresh the ticket body's counts (16/10/6, note
  `anti_pattern` as the new mole and `mission_type` as the whacked one). Defect
  and fix stand.

### #3530 — org-tier doctrine loads but reaches no consumer (tracking) — **LARGELY RESOLVED; verify-and-close candidate**

- **7 of 8 direct members are now CLOSED:** #3384, #3387, #3490, #3516, #3523,
  #3525, #3527, #3385. The "related but different root cause" set is also mostly
  closed (#3488, #3489, #3386, #3407, #3388), with **only #3412 open** — and
  #3412 is explicitly *not a child*.
- The specific chain bug the body calls out ("every seam walked the full chain
  except the DRG graph merge, which took only the first pack") appears fixed:
  `src/doctrine/drg/merge.py:1122` now iterates `for fragment in org_fragments:`
  over the full declaration-ordered list.
- **Recommendation:** this is a tracking issue whose closing condition (a *chain*
  of org packs delivers *every* declared kind, and misconfig fails loud) now
  appears met except for the fail-loud-on-typo guard, which is #3629 part 2's
  territory. Propose: verify the closing condition with a real multi-pack org
  fixture, then close #3530 (leaving #3412 and #3629-part-2 to carry the residue).

### #3514 — `test_allowlist_shrink_only` documented but absent — **STILL VALID (P0)**

- `tests/architectural/test_charter_path_literal_authority.py` defines only:
  `test_injected_charter_literal_is_flagged`,
  `test_allowlisting_one_literal_does_not_waive_the_module`,
  `test_allowlisted_yaml_site_cannot_be_swapped_to_md`,
  `test_gate_green_against_seeded_allowlist`. **No `test_allowlist_shrink_only`.**
- The YAML header (`charter_path_literal_allowlist.yaml`) and the module docstring
  both still claim "adding an entry ... FAILS test_allowlist_shrink_only."
  `charter_path_literal_baseline` / `CHARTER_PATH_LITERAL_FLOOR` appear only in
  prose.
- **Recommendation:** pick option 1 (implement the shrink-only + FLOOR test) —
  the policy is real and valuable, and this is the *same disease as the family*
  (a declared guard that is inert). Option 2 (downgrade the docs) would be
  self-defeating given the theme. P0 is justified.

### #3511 — pack-metadata integration cutover — **STILL VALID (all seams inert)**

- Seam 1 (on-disk unified writers): absorption still in-memory only
  (`absorb_synthesis_manifest`, `pack_manifest.py`); no on-disk org/fetched/charter
  emitters wired.
- Seam 2 (retire stored `artifact_counts`): production path
  `snapshot.py:496` calls `resolve_counts(None, _count_artifacts(...))` — passes
  `constituents=None`, so the derive branch stays **inert**; and
  `pack_assembler._has_recognisable_pack_manifest` (line 416) **still requires**
  the `artifact_counts` key on disk.
- Seam 3 (`pack_id` resolver cutover): `ensure_pack_identity`
  (`src/doctrine/drg/org_pack_config.py`) still has **no production caller** (only
  `__all__` + docstring references).
- Seam 4 (lineage/absorption production callers): `resolve_pack_lineage_order`,
  `resolve_accompanying_doctrine_pack`, `absorb_synthesis_manifest` still
  library-only (no `src/` callers outside `__all__`).
- Sibling states: WP-core #3500 CLOSED (via #3507); #3501/#3502/#3503 (identity/
  lineage/split WPs), #3518 (consolidation), keystone #2467 all **OPEN**.
- **Recommendation:** accurate as written; sequencing note (items 1–2 depend on
  #3518 items 1 & 4) still holds. No edits needed.

### #3629 — M2 DRG-projection follow-ups — **STILL VALID (all three parts)**

- **Part 1 (dead `context-sources` family):** confirmed. The extractor
  (`src/doctrine/drg/migration/extractor.py:920-921`) reads **only**
  `context-sources.get("directives")`. `.tactics/.toolguides/.styleguides/`
  `.doctrine-layers/.additional` reach no delivery path. (Tactics *are*
  delivered, but via the separate `tactic-references` field at line ~930 — not
  `context-sources.tactics`.) The pydantic `ContextSources` attribute
  (`profile.py:277`) is never read for delivery.
- **Part 2 (no fail-loud on bad governance-profile selection):**
  `extract_governance_profile_scope_edges` (`extractor.py:1336`) builds target
  URNs from bare ids with no existence check; a typo mints a dangling `scope`
  edge that `generate_graph` prunes silently. Confirmed.
- **Part 3 (doc nit):** minor, unverified in depth; low-cost on next touch.
- **Recommendation:** accurate. Part 1 is the same silent-drop bug as #3608 at
  the extraction tier — consider co-scheduling. Part 2 is the same fail-loud gap
  as #3530's closing condition.

---

## Suggested disposition

1. **Cluster #3608 + #3629-part-1** as one "silent-drop at the DRG boundary" fix:
   derive the URN-kind set from `NodeKind` (+ drift-guard test), and decide
   wire-or-deprecate for `context-sources.*`. Both are G2 SSOT + fail-loud.
2. **#3514** — implement the missing shrink-only/FLOOR test (P0; theme-critical).
3. **#3629-part-2 + #3530 closing guard** — one fail-loud-on-nonexistent-selection
   guard covers both; then verify-and-close #3530 against a multi-pack fixture.
4. **#3511** — unchanged; gated behind #3518 (items 1 & 4) for seams 1–2.
