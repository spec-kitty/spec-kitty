verdict: approved

# WP09 review, cycle 1 (reviewer-renata lens)

Scope: `git diff 5c2abd41..a8e0984b` on lane-i (commits 80fb35a1 red-first, 4c03782a census fix, a8e0984b main work). The binding contracts were the charter, the WP09 prompt, spec FR-005/006/008/012/014/021/023 and SC-002/007/008, and every `Handoff-to-WP09` block in the lane history.

I checked every claim independently against throwaway `git worktree add` checkouts of base dccf6aa7, 5c2abd41/80fb35a1 and a8e0984b, placed in the scratchpad. All of them have been removed again. The lane itself was never modified.

## Blocking findings

None.

## Implementer decisions: verdict on each

1. **DIRECTIVE_003 typed reference dropped from avoid-gold-plating: CORRECT.**
   - Empirical proof: I restored the 5c2abd41 version of `avoid-gold-plating.tactic.yaml` in a throwaway a8e0984b worktree and regenerated. `test_decision_documentation_on_implement.py::test_shipped_corpus_passes_the_gate` and `test_directive_003_implement_to_review.py::test_implement_lacks_003_but_review_still_delivers_it` then go red (2 failed, 6 passed).
   - No relation choice keeps both. A tactic's YAML references always mint `suggests` (extractor.py:1052-1058), and `resolve_context` follows `suggests` within depth. The only other levers would be deleting WP07's boring-code-review → avoid-gold-plating reference, which would cost avoid-gold-plating its delivery at implement, or adding a non-delivery relation that would be semantically false. Neither is better.
   - Delivery of DIRECTIVE_003 per action is identical to base: specify, plan, tasks and review deliver it and implement does not, in both the default-pack and unfiltered cases at d=1 and d=2.
   - The prose claim "which the review action delivers" is true.
   - WP07's intent is kept for 024 and 001. For 003 only the typed edge is lost, and the id is still cited in prose.
   - The out-of-map edit is disclosed in the Activity Log. WP07's pin was rewritten to assert both the absence of the typed reference and the presence of the prose citation.
2. **avoid-gold-plating → DIRECTIVE_024/001 kept as `suggests`: CORRECT.**
   - At base (tactic.graph.yaml:930-941), `tactic:locality-of-change` → DIRECTIVE_001, 003 and 024 were all `suggests`.
   - The tactic reference walk hard-codes `Relation.SUGGESTS`. WP07's handoff cited `_relation_for_ref_type`, which covers directive frontmatter only, so the handoff was wrong.
3. **FR-014 (DIRECTIVE_001 → paula-scout `suggests`): CONFIRMED at union level. The wording in the rationale is slightly overstated (see note N3).**
   - I re-measured with the canonical helpers, flipping the edge in memory. Union d1 is 149 either way, d2 170, profile 191. No members are lost or gained.
   - In the real `charter context` bundle (`_load_action_doctrine_bundle`), paula-scout and strategic-domain-classification are delivered exactly where they were at base, in all 20 cells (default-pack and unfiltered × 5 actions × 2 depths).
4. **Cascade totals: arithmetic verified. The documentation jump is mechanically correct, and whether it is desired is for the operator to decide (see N2).**
   - Totals: 44→129, 141→137, 110→118, 161→165.
   - Plan's loss of issue-triage-state-machine and its closure comes from WP07 moving tracker-organisation-workflow into the internal pack, not from WP09's wiring.
5. **Dead reachability pins: acceptable for this WP; follow-up recommended (N4).**
   - `_ACTION_UNREACHABLE_D1/_D2`, `_PROFILE_UNREACHABLE`, `_PROFILE_RESCUES` and `_ACTION_D1_D2_SPREAD` are referenced only by their definitions and by comments or docstrings. The implementer's statement is accurate.
   - Because nothing reads them, updating them by measured delta is harmless.
6. **Census fix: CORRECT.**
   - `charter.drg` re-exports `resolve_existing_org_roots` (drg.py:100-104, `__all__` :150). The same door is already used by `specify_cli/cli/commands/charter/_layer_roots.py:83`.
   - The import stays function-local, so the comment's laziness claim holds.
   - The census and migration tests pass.
7. **Main's changes survive the regeneration: CONFIRMED.**
   - main's delta cc788d50..dccf6aa7 was DIRECTIVE_053, op-or-mission-selection, curated entry (23), priti's reference and a provenance-baseline repo_paths change. All of it is present at HEAD: the two curated edges at extractor.py:549-570, the graph fragments, and ledger (23) followed by WP09's (24).
   - The provenance baseline diff dccf6aa7..a8e0984b only removes entries or lowers counts. Its one `+` line is `provenance: 20 -> 19`. main's research/prompt.md `repo_paths: 1` is kept.
   - `regenerate-graph --check` exits 0.

## Other checks

- **Generated files:** `regenerate-graph --check` (lane-local) reports "DRG graph is fresh", exit 0. The roundtrip, pack-manifest-no-author-edit and freshness gates are green.
- **Red-first tests are non-vacuous:** running the four new test files at 80fb35a1 gives 56 failed, 38 passed (implementer reported 47+4+4+1). They pass at HEAD.
- **SC-007 BASE literals independently reproduced:** at base the default pack delivers {025, 030, 034, 037} for implement and review at d1 and d2. Unfiltered delivers all 8 owners. HEAD is a superset of BASE in every cell.
- **Delivery diff, base vs head, over 20 cells:** the only losses are retired ids, and the only gains are their successors, the supply-chain toolguides and tactic, 025/034 at tasks, and red-main at tasks (unfiltered). There is no collateral loss.
- **Reachability, base vs head:** d1 148→149, d2 167→170, profile 188→191. Only retired ids leave, which matches the test_reachability ledger.
- **Handoffs:** every Handoff-to-WP09 item from WP01, WP04, WP05, WP06, WP07, WP08 and WP11 is either implemented or deferred with a correct reason. The deferrals: the WP07 requires→suggests correction, WP05's 025 already being `requires`, and the BDD paradigm edges being minted by the extractor.
  - WP11's renata reason text has been regenerated (agent_profile.graph.yaml:854 now names the procedure).
  - No `adversarial-evidence-contract` text remains in any edge reason.
- **Hygiene:** no `#NNNN` in the new pack prose, the provenance baseline only shrinks, and the terminology gate is green.
- **Lint and types:** `ruff check` and `ruff format --check --force-exclude` pass on all 21 touched .py files.
  - The formatter reports 10 files as unformatted only when `--force-exclude` is omitted. All 10 are on the pre-existing #473 formatter-debt exclude ratchet.
  - `mypy src/charter/offering/drg` reports 3 no-any-return errors, identical at base dccf6aa7 (loader.py:135, extractor.py:107/140).

## Non-blocking notes (fold in if convenient)

- **N1: ledger arithmetic is off by one.** In `tests/doctrine/drg/migration/test_extractor_projection.py:739`, :752 and :771, ledger entry (24) says "1050 -> 1064 edges", "EDGES -51 / +65" and "`suggests` +7".
  - Measured on the shipped graph (`load_built_in_graph`, and also by counting `- source:` in the fragments): 1050 → **1063**, removed 51, added **64**. The histogram is requires +6, **suggests +6**, scope -1, refines +2.
  - Fix: change those three numbers. No test reads them, but this is the audit record the WP's review guidance relies on.
- **N2: documentation cascade grows 44→129 (+86 gained, curation lost).**
  - Path: `mission_type:documentation -requires-> action:documentation/design -scope-> DIRECTIVE_001 -suggests-> paula-scout -refines-> procedure:adversarial-squad-deployment`, then that procedure's `requires`/`suggests` closure.
  - With the two `refines` edges removed the total is 43, so the growth comes entirely from FR-012's refines edges, which the spec says cascade follows (spec line 229, research R finding).
  - The added closure includes documentation-unrelated artifacts: python-conventions, sonar, zombies-tdd, the aggregate-design-rules/DDD family, mutation-testing, BDD and TDD tactics.
  - It only takes effect on opt-in `charter activate mission-type documentation --cascade`. That keeps it within the spec, but it is a consumer-visible broadening the spec never measured.
  - Recommend recording it in the PR for an operator decision. One option: cascade could not follow `refines` out of a node that was reached only by `suggests`.
- **N3: FR-014 rationale is stated too broadly.** The extractor.py:320-327 comment and the test_reachability ledger say "zero members lost or gained". That is true for the union sets and for the bundle surface.
  - Raw per-action `resolve_context` does shift, measured with the edge flipped in memory. Under `suggests`, paula-scout drops from software-dev/specify and /plan at d1 and d2. DIRECTIVE_032, anti-corruption-layer and domain-event-capture are added at d2 for implement, review and documentation/design (review-intent-and-risk-first is also added for documentation/design).
  - The bundle is unaffected, so this is not a delivery regression. Suggest wording such as "union sets and bundle delivery unchanged".
- **N4: dead pins in test_reachability.py.** `_ACTION_UNREACHABLE_D1` (:303), `_D2` (:427), `_PROFILE_UNREACHABLE` (:549), `_PROFILE_RESCUES` (:682) and `_ACTION_D1_D2_SPREAD` (:104) are unasserted. Under the charter's campsite rule ("stub → delete"), the follow-up should either re-assert them or delete them. File an issue.
- **N5: shallow clones skip a spec positive control.** `tests/doctrine/test_retired_ids_absent.py:181` skips the SC-002 git-show positive control on a shallow clone, which is what CI usually uses. The synthetic controls still run, but SC-002 names this control explicitly. Consider fetching the base commit in the CI lane, or failing loudly on the gate lane.
- **N6: requires/suggests twin edges.** Three new pairs carry both `requires` and `suggests`: testing-principles→quad-A, bdd-scenario-formulation→GWT and bdd-lifecycle→GWT. This follows the existing 14 profile→directive twins, so it is consistent, but it adds noise. Optional: have curated `requires` suppress the minted `suggests` twin.
- **N7: default.yaml under-activates.** It still omits DIRECTIVE_041-053, so under the default pack only 025/030/034/037 of the epic owners are delivered. This is unchanged from base and the implementer flagged it. Worth an issue, because the header claims "activates ALL built-in artifacts".
- **N8: out-of-map edits are disclosed and justified:** avoid-gold-plating.tactic.yaml, test_change_scope_review_single_owner.py, test_template_asset_e2e.py and _retired_activation.py.

## Commands run (lane-i at 74857c8d; packs/src identical to a8e0984b)

```
PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs .venv/bin/python -m specify_cli doctrine regenerate-graph --check
  -> "DRG graph is fresh", exit=0

.venv/bin/python -m pytest -q -n 8 --dist loadfile tests/doctrine/drg tests/doctrine/test_owner_delivery.py \
  tests/doctrine/test_retired_ids_absent.py tests/doctrine/test_retirement_table_consistency.py \
  tests/doctrine/test_change_scope_review_single_owner.py tests/doctrine/test_paula_patterns_artifacts.py \
  tests/doctrine/test_relation_doc_parity.py tests/doctrine/test_directive_consistency.py \
  tests/doctrine/agent_profiles/test_context_sources_migration.py tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py \
  tests/doctrine/test_template_asset_e2e.py tests/charter/test_cascade.py tests/charter/test_context.py \
  tests/charter/test_profile_channel_delivery.py tests/charter/test_decision_documentation_on_implement.py \
  tests/charter/test_directive_003_implement_to_review.py tests/charter/test_consistency_check.py \
  tests/architectural/test_no_legacy_terminology.py tests/architectural/test_doctrine_regenerate_graph_roundtrip.py \
  tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_builtin_pack_provenance_ratchet.py \
  tests/architectural/test_operating_procedures_resolve.py tests/architectural/test_doctrine_census.py \
  tests/cross_cutting/packaging/test_packaging_safety.py tests/specify_cli/test_documentation_drg_nodes.py \
  tests/specify_cli/upgrade/test_normalize_activation_absence.py \
  tests/specify_cli/upgrade/migrations/test_retired_activation.py \
  tests/specify_cli/upgrade/migrations/test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py
  -> 1158 passed, 2 skipped in 282.93s, EXIT 0

.venv/bin/python -m pytest -q -n 8 --dist loadfile -m "not slow" tests/doctrine tests/charter
  -> 11 failed, 6603 passed, 37 skipped in 646.83s
  All 11 are known false reds or expected red until WP10:
   env: test_pack_manager[unreadable]; test_references_missing_failclosed x2; test_reject_not_drop_cli x2;
        test_presence_gate_bundle_authority::...survives_charter_md_deletion; evidence/test_orchestrator::test_dry_run_evidence_on_spec_kitty_repo;
        test_phase3_integration::test_phase3_dry_run_evidence_smoke
   WP10: test_activation_parity_guard::test_this_project_charter_pack_is_coherent;
         test_model_task_routing_resolves::test_charter_references_surface_model_task_routing_body;
         test_activate_resolves_no_answers_edit::TestSpddActivationDoesNotFlip::test_config_sourced_compile_keeps_spdd_active
  (The same 11 the implementer classified. The union of the content WPs' Expected-red-until-WP09 lists is green.)

Red-first non-vacuity (throwaway worktree @80fb35a1):
  pytest the 4 new test files -> 56 failed, 38 passed

FR-004 counterfactual (throwaway worktree @a8e0984b, avoid-gold-plating restored from 5c2abd41, regenerated):
  pytest test_decision_documentation_on_implement.py test_directive_003_implement_to_review.py -> 2 failed, 6 passed

ruff check --force-exclude <21 touched .py>          -> All checks passed!
ruff format --check --force-exclude <21 touched .py> -> 11 files already formatted (10 others are on the #473 exclude ratchet)
mypy src/charter/offering/drg src/specify_cli/upgrade/migrations/_retired_activation.py
  -> 3 no-any-return (loader.py:135, extractor.py:107/140), identical on base dccf6aa7

Probes (scratchpad/rev09/*.py): FR-014 in-memory flip; action-bundle delivery base vs head across 20 cells;
  cascade_activation_targets base / head / head-without-refines; shipped edge multiset diff; reachability base vs head.
```
