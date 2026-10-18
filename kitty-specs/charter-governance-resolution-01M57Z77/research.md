# Grounding brief (Phase 1 squad, 2026-10-18, main 783e650d6, spec-kitty 4.0.0rc8)

Five read-only lenses ran in parallel: one per issue (#6406 and #6407 shared a lens), plus a closeout-rules digest. Reproductions used scratch projects and fixture org packs; the `sddevelopment-be/spec-kitty-charter` checkout has no org packs and no synthesized graph, so it reproduces only #6405 (it detects `typescript`, defensible for a docs repository with an Astro site).

## Shared root

#6406, #6407 and the sibling non-directive defect share one root: `src/charter/activation/` has two identity paths. `ActiveCharterService.directives` resolves activation tokens through `kind_vocabulary.resolve_artifact_urn` (layer-aware, reads the declared `id:`), while `_resolve_directive_base`, `valid_ids` and several renderers guess ids with `_normalize_directive_id` and validate against the built-in catalog only. #4185 (`cb4252d05`) fixed the service but not the governance base. #6404 and #6408 are separate roots in the same subsystem; #6405 is independent (evidence collector).

## #6404 — synthesized tactics unreachable

- Emitter: `src/charter/activation/synthesizer/project_drg.py:350-356` writes `tactic:how-we-apply-X --applies--> directive:X` (introduced `cb9c4f8d0`, #677).
- Walks: `offering/drg/query.py:184-240` (scope/requires/suggests/vocabulary), `activation/cascade.py:102-110`, `reference_resolver.py:72`, `context_renderers/delivery_table.py:287`, `compiler.py:1812` never follow `applies`; `merge.py:92-98` and `models.py` RELATION_DESCRIPTIONS document it as inert; `tests/architectural/test_no_authored_applies_edge.py` gates shipped packs only.
- Built-in shape: `directive --suggests--> tactic` (49 edges), `--requires-->` (6).
- Reconcile hazard: `synthesizer/reconcile.py:236-253` and `_graph_delta` (446-451) assign edge ownership by `edge.source`; an edge sourced at a built-in directive would be treated as non-synthesized (pruned by `--prune`, duplicated on re-run).
- Observed side notes: without `--mission-type`, `context --json` skips DRG resolution (`action_governance_bundle.py:304`); with no activation keys every graph tactic is a root (`:347-350`), so the tactics appear for every action regardless of edges.
- Operator decision: emit `suggests` from the directive; fix reconcile ownership.

## #6405 — Gradle repository detected as typescript

- `src/charter/activation/evidence/code_reader.py:49-62` indicators lack `build.gradle.kts`, `settings.gradle(.kts)`, `gradlew`; `:240` stores basenames only to depth 3; `_detect_language` (`:319-344`) returns early on any `package.json` and picks `typescript` on any `tsconfig.json`. Culprit `602a8ca99` (#688).
- `synthesizer/write_pipeline.py:308-337` `_is_generic_scoped` uses a substring test (`java` matches `javascript-*`).
- `language_scope.infer_repo_languages` answers a different question (declared languages); not unified here.

## #6406 / #6407 — guessed ids and built-in-only validation

- `resolver.py:824` normalizes stems (`a86851a2b`, #3838); `valid_ids` built-in + charter-local (`resolver.py:812-815`, `fa77a97f1`); unknown id raises and `compact.py:320-324` / `context_json.py:155-159` swallow it (exit 0).
- Same guess elsewhere: `action_governance_bundle.py:341,373`, `context_renderers/template_include.py:139`, `context_renderers/selection_block.py:254`, `preset_application.py:287`, fallback `resolver.py:158`.
- Built-in-only validation also in `_validate_paradigm_selection` (`resolver.py:658-670`) and `_resolve_template_set_selection` (`:896-910`).
- Sibling defect: `ActiveCharterService.tactics` (`resolver.py:289-295`) and the other non-directive getters compare declared ids with stem tokens, so an org tactic with stem ≠ id is silently not delivered (confirmed live).
- Operator decisions: drop unknown ids with a diagnostic; one identity seam for every kind.

## #6408 — first selection materialises the catalog

- Deliberate: #4253 (`d0498021b`), #4400 ruling, ADR `docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md` (absent = all; present = allowlist).
- Writers: `pack_manager.activate` (`:685-772`, seed `:752`), cascade (`cli/commands/charter/activate.py:278`), interview `_promote_interview_selections` (`interview.py:44-130`), `org_charter.py:398-441`, migration `m_unify_charter_activation`. The preset path (`preset_application.py`) already replaces keys with preset + org-required ids.
- Contract text: `packs/built-in/missions/mission-steps/software-dev/charter/prompt.md:83`, `:305-307`.
- Consequence: a materialised list is a frozen allowlist; later built-ins stay out of force.
- Operator decision: opt-in `--only` + interview option; contract text and warning name the freeze.

## Proposed slicing

1. Identity seam + every-kind service + governance base/validation + renderers (#6406, #6407, sibling).
2. Synthesis edge + reconcile ownership (#6404).
3. Opt-in narrow activation + interview option + contract/warning text (#6408).
4. Code reader root-first + neutrality slug match (#6405).
