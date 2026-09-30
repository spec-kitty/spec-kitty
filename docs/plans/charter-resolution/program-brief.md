---
title: Charter-Resolution Program Brief
description: 'Investigation-grounded brief for the charter-resolution program: root causes, mission decomposition, sequencing, risks and spec-time operator decisions.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---

# Mission Brief — Doctrine Reach & Resolution Honesty

**Prepared from:** a 4-lens design investigation (load-path, cascade/edges, reach/delivery, validation-honesty) traced against current `main` (`6ec05086f`, post-#3520/#3534).
**Rolls up to:** umbrella tracker **#3530** (org-tier doctrine loads healthy but reaches no consumer) and fail-loud epic **#3410**; reach sub-epic **#3526**.

---

## 1. Problem statement (BLUF)

Authored governance — org-pack and project-tier doctrine — **silently fails to reach the dispatched agent.** Content loads, validates, reports healthy, then drops somewhere between authoring and consumption. The operator sees green checks and empty results. Concretely, on `main` as of 2026-08-19: activating any built-in mission type cascades to **0** kinds; org packs authored in the canonical `drg/fragment.yaml` shape contribute **nothing** to cascade; org/project doctrine of a given kind is under-loaded relative to built-in (measured **71% tactic undercount**); glossary packs and 3 of 5 profile reference channels reach no agent; and several canonical facts are hand-restated in 5 places, two already drifted and failing open.

## 2. Root causes (one disease, six faces)

1. **Org/project tiers are second-class vs built-in.** Built-in discovery `rglob`s unconditionally; org/project use non-recursive `glob`; and the *loader* (`doctrine/base.py`, `agent_profiles/repository.py`) and the *charter-activation resolver* (`charter/kind_vocabulary.py`) each decide recursion independently, so they disagree per kind. → **#3490, #3426**
2. **Two DRG read-paths never meet.** Cascade reads root-level `*.graph.yaml` via `_drg_helpers.load_validated_graph`; org `drg/fragment.yaml` (`OrgDRGFragment`) is read by a *separate* path (`org_pack_loader.load_org_pack → merge.merge_three_layers`) consumed only by diagnostics. Nothing bridges fragment edges into cascade. → **#3572**
3. **Cascade traversal dead-ends.** `REFERENCE_RELATIONS = {requires, suggests, refines}`; `mission_type`/`action` nodes carry `scope`/`instantiates` edges that cascade never follows, so the forward closure reaches the action node and stops. → **#2829**
4. **Edges absent or unvalidated.** `collaboration.operating-procedures` is a validated `list[str]` whose *values* are never checked against nodes — measured **36 of 50** name no node; real edges are hand-pinned per-profile; a handful of activated artefacts have zero inbound edges. → **#2994, #3352, #3009**
5. **Delivery tables/renderers have silent no-ops.** `slot=None` with no stated reason (glossary), `body_fn=None` pointer-only (styleguide/toolguide), a schema field no renderer reads (operating-procedures), a struct field permanently shadowed by a required sibling (procedure step `description`), and a builder that can't resolve `.kittify/agent_profiles`. → **#3488, #3489, #3176**
6. **Canonical facts restated by hand / read through glob/name proxies, failing open.** Plural↔singular kind map in 5 sites (2 drifted); validator globs `*.graph.yaml` and misses `fragment.yaml`; `context --json` omits `procedures[]` that the text render ships; pack resolution is name-based instead of `pack_id`-keyed. → **#2981, #3573, #3389, #3574**

**Meta-cause:** *the resolution surface restates canonical facts instead of deriving them from a single total authority, and every divergence degrades silently (fake-green).* This is the #1868 "canonical seams in name only" thesis and the #3410 fail-loud thesis, expressed across charter resolution.

## 3. Proposed approach (four principles)

1. **Derive, don't restate.** Single derived authorities (recursion policy; plural↔singular kind vocab) built from `ArtifactKind`; collapse the hand-copies. House precedents already on `main`: `PROJECT_KIND_DIRS`, `ORG_PLURAL_TO_SINGULAR_KIND` / `_derive_plural_to_singular`.
2. **Bridge the read-paths.** Route org `drg/fragment.yaml` edges into the cascade graph via the *existing* `merge_three_layers` machinery (it already owns endpoint resolution + dedup) — do not re-implement.
3. **Fail loud, gated on migration.** Turn silent drops into warnings/errors; only flip fail-*closed* once the population is 100% migrated (fragment-cascade readiness, `pack_id` backfill completeness).
4. **Enforce with parity/totality gates.** A gate that binds loader↔resolver recursion *and* covers `str`-keyed maps (which escape today's `test_kind_mapping_totality.py`), so fixes cannot re-drift.

## 4. Mission decomposition (a program, not one mission)

> This is genuinely a **program** rolling up to #3530/#3410. Below is the recommended cut. The two enabling missions can start immediately in parallel; the completeness mission lands last because it re-ledgers golden counts.

### Enabling layer — land first, in parallel

**M1 — Single-authority resolution parity** · covers **#3490, #3426, #2981** · effort **M**
One recursion authority read by both loader and resolver (make org/project discovery recursive to match built-in; delete the redundant Styleguide/Asset overrides; fix `agent_profiles/repository.py`'s third divergence site). One derived plural↔singular kind map from `ArtifactKind`, collapsing the 4 charter duplicators (`activations.py:178/194`, `_activation_render.py:271/112`). Ship the shared **parity/totality gate** that (a) binds {kinds the loader scans recursively} == {kinds the resolver returns `recursive=True`}, and (b) covers `str`-keyed maps. Self-contained; **no golden-count ripple**.

**M2 — DRG read-path bridge** · covers **#3572, #3573** · effort **M**
Route `load_validated_graph`'s org layer through `merge_three_layers(built_in, org_fragments, project)` (add an `org_fragments` param populated by `specify_cli` via `charter.drg.load_org_drg`; build-time callers stay inert). Re-scope the D-005 warning to fire only when a root ships *neither* a root graph *nor* a fragment. Flip `TestGraphlessPackWithFragmentEdgeIsInvisibleToCascade` to assert the edge **does** cascade, and **atomically** update the #3573 validator so its message never becomes a lie. Enabling for all org-authored reach.

### Reach/delivery layer

**M3 — Operating-procedures: validate → triage → data-drive** · covers **#2994, #3352, #3488(op-proc channel)** · effort **L** · *hard internal order*
(1) Load-time validator: every `operating-procedures` entry must resolve to a real node (converts 36 silent fictional refs to loud). (2) Triage the 36 (author/repoint/delete). (3) Data-drive the extractor to emit `agent_profile --requires--> procedure`, guarded to resolvable targets, retiring the hand-pinned `_CURATED_ARTIFACT_EDGES`. **Must not** emit before targets resolve (else 36 dangling edges → `assert_valid` failure).

**M4 — Deliver loaded doctrine to the dispatched agent** · covers **#3489, #3176, #3389, #3488(render half)** · effort **M**
Fix the delivery-table/render no-ops: give `GLOSSARY_PACK` a real slot + term-list render row (or ratify document-only) and restore the "stated reason" for every remaining `None` row; render procedure step `description` (not just `title`); decide styleguide/toolguide inline-body-vs-pointer. Add the `#3176` builder-overlay seam so `.kittify/agent_profiles` is reachable. Promote `procedures[]` to a typed array in `context --json` (**versioned-contract bump** — do deliberately). Org-authored glossary/op-proc acceptance is **gated on M2**.

### Completeness layer — land last

**M5 — Kind-complete cascade + orphan wiring** · covers **#2829, #3009 residual** · effort **L** · *ADR-worthy*
Expand the cascade relation set to follow the action-hop relations (`scope`, `instantiates`; keep `in_tension_with`/`rejects`/`delegates_to`/`applies` excluded), so activating a mission_type reaches its dependent kinds. Author real inbound edges for the ~5 remaining `_ACTIVATED_BUT_ORPHANED` artefacts (or mark direct-activation-only). Lands **last** so it re-ledgers golden counts **once**, atop M2's fragment edges.

### Carve-out

**M6 — Project-tier DRG node emission** · covers **#3038** · effort **L**
Emit hand-authored project-tier `agent_profile` artefacts as DRG nodes (a filesystem-walk emitter, not just extending the answer-driven map). Reuses M1's single-authority discipline. **Asset half deferred behind #3037** (asset has no resolution/install path). Convert `project_drg._KIND_TO_NODE_KIND` to enum-keyed so the totality gate covers it.

### Cleanup rider (rideable on any mission)

**#3575** (delegation swap `builtin_missions_root → pack_paths.built_in_missions_root`, S) and the **doc-reference half of #3574** (replace the in-code deferral with an issue link, S). The **#3574 resolver cutover** (fail-loud `pack_id` resolution, **L**, gated on backfill completeness) belongs to its own later pack-identity mission — not this program.

## 5. Sequencing

```
M1 ─┐                         (enabling, no golden ripple)
M2 ─┼─► M3 ─► M4(org reach)    (M3/M4 org acceptance gated on M2; M3 before its data-drive)
    └─► M4(render/builder) ────►
                          M5    (LAST — re-ledger once, atop M2)
M1 ─► M6                        (reuses M1 discipline)
```
- **M1 ∥ M2** first — both enabling, independent.
- **M3** needs the validated node universe; its data-drive step must follow triage.
- **M4** render/builder parts are independent; its glossary/op-proc *org* acceptance waits on M2.
- **M5** is the only golden-count-heavy change on cascade reach — land it last so counts move once (with M2's edges already in).

## 6. Scope

**In:** charter resolution / cascade / delivery; org & project doctrine loading (recursion, tier node-admission); validation honesty & canonical-vocab consistency.
**Out:** asset resolution/install (**#3037**); the manifest-reliability boundary (**#3388/#3412** — #3530 explicitly marks these adjacent, different root cause); the `pack_id` fail-loud *flip* (needs a separate backfill-completeness gate).

**Already landed — do not redo:** most of **#3009** (membership set replacing the bare count, wire-8-delete-1, reachability companion); the service/repository half of **#3038** (`PROJECT_KIND_DIRS`); **#2981**'s cited WP08 precedent; **#3576** fixes only the #3575 *comment*, not the delegation.

## 7. Risks

- **Unconditional recursion** loads nested YAML not intended for loading — mitigated because globs are kind-specific (`*.tactic.yaml`); verify `.provenance/*.yaml` and `.md` files are not captured.
- **Cascade relation-set expansion (M5) ripples golden counts** — sequence adjacent to M2, re-ledger once.
- **Widening styleguide/toolguide bodies blows the NFR-001 token budget** — the reason they were pointer-only; treat as a doctrine decision, not a silent widen.
- **Data-driving op-procedures before triage** mints 36 dangling edges → `assert_valid` failure. Order is load-bearing.
- **`str`-keyed maps escape the totality gate** — re-key on `ArtifactKind` or add per-universe bidirectional equality tests.
- **Premature `pack_id` fail-closed** strands un-backfilled packs (why the flip is out of scope here).
- **Watch the baseline-red gotcha** — run new tests on the merge-base to confirm green-before.

## 8. Open questions — operator decisions at spec time

1. **Recursion (M1):** make org/project discovery unconditionally recursive (simplest, matches built-in) or keep a per-kind flag shared by loader+resolver?
2. **`anti_pattern` (M1):** is the charter-activatable kind map **9** kinds (faithful to `CHARTER_KIND_TOKENS`) or **10** (preserving today's `activations.py` `anti_patterns` entry)? — the #2976 ruling; must not be silently pre-empted.
3. **`--include` selector vocab (M1):** widen the selector surface to accept `glossary_pack`/`anti_pattern`, or accept a correctly-derived-but-unrunnable stanza?
4. **#3573 (M2):** fold into M2 for an atomic flip (**recommended**) or ship standalone with removal gated on #3572?
5. **Glossary delivery (M4):** real delivery slot vs document-only exclusion? inline terms vs surface-list + fetch pointer (token budget)?
6. **styleguide/toolguide (M4):** grant a budgeted inline body, or ratify pointer-only and make it discoverable in schema/docs?
7. **operating-procedures field (M3):** wire it into the procedure channel, or deprecate/rename? (either way, add the dead-entry diagnostic.)
8. **#3038 (M6):** filesystem-walk emitter vs synthesis-answer-driven node presence? asset explicitly behind #3037?
9. **#3389 asset asymmetry (M4):** after `procedures[]`, is `asset` deliberately reference-only forever, or a follow-up sixth typed array? — state it in the contract.
10. **`pack_id` fail-loud arming (later):** what backfill-completeness gate + doctor/audit surface proves 100% coverage before the flip?

## 9. Recommended first mission

**Lead with M1 (Single-authority resolution parity), M2 in parallel.** M1 is self-contained, ripples no golden counts, closes the highest-impact silent-loss defect (#3490's 71% tactic undercount + #3426), and — most importantly — installs the **parity/totality gate** that protects every later mission from re-drift. M2 is the other enabling fix and unblocks all org-authored reach, so start it alongside. Everything else sequences behind these two.
