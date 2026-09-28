# Research — squad-doctrine-single-owner-01M3KBP7

Grounded on main `4e81f4d5` (2026-09-28) and re-verified on `d95e60a2`.

## R-1 Consumer-safe deletion of an activatable artifact
- **Decision**: add an upgrade migration that strips the id from every project surface.
- **Rationale**: `charter.activation.compiler` raises `UnknownArtifactIdError` for an unknown `activated_*` stem, and the compile path does not catch it. Deleting the artifact therefore hard-fails every project that activated it. `m_3_2_6_retire_rtk_search_tooling` is the precedent.
- **Alternatives**:
  - A graceful-degrade test: rejected, because the compiler is fail-closed by design.
  - Keeping the styleguide as a stub: rejected, because it keeps a second owner.

## R-2 How edges are minted
- **Decision**: author the non-default relations as curated `_CURATED_ARTIFACT_EDGES` entries: procedure → tactic `suggests`, procedure → procedure `suggests`, and tactic → procedure `refines`.
- **Rationale**: procedure YAML `references` of type tactic or procedure always mint `requires`, and tactic `references` always mint `suggests`. `refines` has no YAML path at all.
- **Alternatives**: extending the reference schemas with a relation field. Rejected as a schema change that is out of scope.

## R-3 Delivery of `refines`
- **Finding**: `refines` is traversed by charter cascade (`cascade.py`), but not by action-context resolution or the profile channel. The procedure keeps reaching agents through its existing inbound edges: brownfield `requires`, DIRECTIVE_046 `suggests`, and the renata/priti operating procedures.

## R-4 Casting-table grammar
- **Decision**: put the table in the procedure's `notes`, under the literal anchor `Example casting (examples, not rules):`. Each line has the form `- <label>: \`id\`, \`id\` — <question>`, where `<label>` is a point-cut token or `escalation`.
- **Rationale**: the procedure schema forbids extra fields. A fixed anchor plus line grammar lets the lens guard parse the table without passing vacuously.

## R-5 DIRECTIVE_001 → paula-scout relation
- **Decision**: conditional (FR-014). Downgrade to `suggests` only if the reachability goldens show no loss of delivery. `tests/doctrine/test_paula_patterns_artifacts.py` pins the current relation.

## R-6 Migration target version
- **Decision**: `target_version = "4.0.0rc5"`, the installed version at authoring time, following `m_4_0_0rc5_hosted_endpoint_session_backfill`. `MigrationRegistry.get_applicable` then selects it both for projects already on rc5 (`target == from_v and detect()`) and for projects upgrading from older versions.

## R-7 #5202 guidelines (grounding, d95e60a2)
- **Loader:** `src/charter/offering/missions/repository.py:510` builds `<mission>/actions/<action>/guidelines.md`. Its only consumer is `src/charter/activation/context_renderers/bootstrap_text.py:65-71`, which swallows errors (`except Exception: pass`). Nothing reads `mission-steps/*/guidelines.md`, and the skills renderer renders only `prompt.md`.
- **Drift:** four software-dev files. The correct halves are:
  - `implement:11` and `review:21` "repository root checkout" come from `actions/`;
  - the supply-chain sections come from `mission-steps/`;
  - `review:9` is rewritten to "approved or done, and present in the review base";
  - `tasks:26` "unnecessary overhead" comes from `actions/`.
  - The other 13 pairs are byte-identical.
- **Tests pinning paths:**
  - `tests/doctrine/missions/test_referential_integrity.py:93,200`
  - `tests/doctrine/test_wp_authoring_contract_roundtrip.py:53-59,124-160`
  - `tests/doctrine/missions/test_repository.py:318-345`
  - `tests/architectural/_builtin_pack_provenance_baseline.yaml:122,137,175,177`
- **ADR** `docs/adr/3.x/2026-08-13-1-…:36-37` names `mission-steps/` canonical, and so does CLAUDE.md. `docs/architecture/04_implementation_mapping/README.md:176,402` is stale.

## R-8 #5078 printed recipes
- `workflow_executor.py:1378,1455,1514`
- `implement.py:424`
- `tasks_parsing_validation.py:337,339,537,567,661`
- `charter/_synthesis.py:749`
- `mission_setup_plan.py:137`

`safe-commit` (`safe_commit_cmd.py`, `git/commit_helpers.py:994-1060`) stages and commits only the named paths. It refuses protected destinations unless they are configured. The implement prompt's WP-agent PR instruction is at `mission-steps/software-dev/implement/prompt.md:329-335`.

## R-9 #5220
All 10 items are live.
- `bug-fixing-checklist` is activated in `default.yaml:61` and this repo's `charter.yaml:80`.
- It is cited by implementer-ivan:136, node-norris:165, frontend-freddy:173 and drupal-dries:204. A profile retarget must go through `collaboration.operating-procedures`, which mints `requires` edges.
- The overlay produces the `when` at `directive.graph.yaml:167` (`hand_authored_overlay.py:1419-1428`).
- Quad-A is delivered to implement/review only through `testing-principles`' inline copy.
- DIRECTIVE_052 is not action-scoped. The `test-first-bug-fixing → 052` edge is load-bearing.

## R-10 #5221
Live: A1, A3, A4, B1, B4, C1, C3, D1, D2, D3, E (64 slug citations). Partly stale:
- A2: the 17-section config moved to internal in 414bbe89;
- B3: the 052 → reconcile edge exists;
- C2: freddy and norris already carry IoC;
- B2 is stale: tidy-first is already in 025.

Other constraints:
- The lint asset pins the `structural_lint_config` key (`assets/docs_structural_lint.py:95-97`).
- Moving `iterative-deepening-review` requires moving `tracker-organisation-workflow` with it (`:129,:144`).
- `boring-code-review` is wired in `action.graph.yaml:374,551`, the action indexes, and `default.yaml:58`/`minimal.yaml:45`.

## R-11 Consumer migration
One data-driven migration: a tuple of `Retirement(kind_key, stem, reference_prefix, successor=None|(kind_key, stem))`. Successor activation applies to:
- `bug-fixing-checklist` → procedure `test-first-bug-fixing`;
- `locality-of-change` (tactic) → `avoid-gold-plating`;
- `common-docs-curation` → the scaffold/write/find tactics;
- `boring-code-review` tactic → styleguide;
- `behavior-driven-development` tactic → `bdd-scenario-formulation`;
- `iterative-deepening-review` and `tracker-organisation-workflow`: no consumer successor;
- `adversarial-squad-cadence`: none, because the procedure is already required via brownfield and reachable through its edges.
