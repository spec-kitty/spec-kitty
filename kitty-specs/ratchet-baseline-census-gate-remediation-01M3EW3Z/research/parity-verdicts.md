# Parity verdict catalog: the #2631 parity/equivalence sweep (45 modules)

- **Mission**: `ratchet-baseline-census-gate-remediation-01M3EW3Z`, WP12 (FR-018, NFR-006, SC-005).
- **Issues**: #2631 (FR-016 parity/equivalence harm audit), a child of epic #5104 ("Test suite friction — ratchet, baseline & census gates").
- **Planning base**: `3717c7ea`. The sweep set is `git ls-tree -r --name-only 3717c7ea -- tests`, keeping basenames matching `*parity*.py` or `*equivalence*.py` (49 paths), minus the 4 `tests/_support/coverage_safety/` helpers and self-tests = **45 modules**. It is pinned to the base SHA so later deletions and renames (WP09, WP10) do not move it.
- **Completeness check**: `python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py --base 3717c7ea` must print `45/45 OK`.

## Churn provenance

The churn columns are copied, unchanged, from `research/grounding-2631_2972.md` Part 2. Nothing was re-measured for this catalog: the local checkout is shallow (`git rev-parse --is-shallow-repository` → `true`), and fetching deeper history would mutate a checkout that other agents share.

- **Measured at**: HEAD `34f19c6fb` (2026-09-26), in a session-local blobless clone with history since 2026-03-20.
- **Window**: `git log --since=2026-03-26`.
- **Method** (CaaCS-style), per file:
  - `git log --since=2026-03-26 --format=%H -- <file>`, then `git show --name-only <sha>` for each commit;
  - **all** = commits in the window that touched the file;
  - **src** = how many of those also touched `src/`;
  - **mass** = how many of those touched more than 60 files (relocations, format sweeps; noise for a co-change signal);
  - **pcm** = modifications after the file's creation commit, excluding mass commits;
  - **pcsrc** = how many of the pcm commits also touched `src/`.
- The checker compares every row's five churn cells with grounding Part 2. `n/a (shallow)` is allowed only for a module absent from Part 2, with the reason in the note. No row needed it.

## Discriminator (from #2620)

The format and the discriminator are those of #2620's standing catalog in `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-design-decisions.md` (the discriminator paragraph at L18, the table header at L20). Quoted from there:

> "a pinning test earns its keep ONLY if it pins a *behavioural / negative invariant* (import ban, layer ban, security boundary). If it pins *positive code shape* (a symbol lives at a path, a count, a call reads a string), or it co-changes with src on every refactor (ratio→1.0), it is scaffold-friction → convert-to-behavioural or retire."

In short: a pinning test earns its keep only if it pins a behavioural or negative invariant. Positive shape, or a co-change ratio approaching 1.0, is scaffold friction.

## Columns

#2620's six columns are kept in order: `suite / test file | category | pins invariant or shape? | CaaCS churn | verdict | note`. "CaaCS churn" is expanded into the five numeric sub-columns `all | src | mass | pcm | pcsrc`. Three columns are added: `surviving enforcer / NFR-006 proof`, `empty-target behaviour` (SC-005, filled for every ban or scan row) and `owning WP / follow-up`. `note` stays last.

- **pins invariant or shape?** starts with the discriminator class: `invariant`, `shape` or `mixed`.
- **surviving enforcer / NFR-006 proof** is required for every row whose verdict contains retire, convert or split. It holds a node ID (`::`), or a cited `reason:` plus a `mutation:` that shows nothing behavioural is lost. It reads `—` for plain keeps.
- **owning WP** names the WP of this mission that carries out the verdict. WP13 re-confirms those rows against the landed code (see "Reconciliation at closeout"). This file never pre-claims that the work is done.

## Catalog

| suite | category | pins invariant or shape? | all | src | mass | pcm | pcsrc | verdict | surviving enforcer / NFR-006 proof | empty-target behaviour | owning WP / follow-up | note |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| `tests/_factories/test_make_mission_parity.py` | behavioural-parity | invariant (single-schema delegation) | 5 | 2 | 3 | 2 | 0 | keep | — |  | — | Already catalogued in #2620. |
| `tests/architectural/test_basetemp_retention_doc_parity.py` | doc-parity | invariant (doc ↔ config) | 1 | 0 | 0 | 0 | 0 | keep | — |  | — |  |
| `tests/architectural/test_docs_cli_reference_parity.py` | doc-parity | invariant (live Typer tree = reference docs); planted-bad self-test at :476 | 12 | 7 | 5 | 7 | 3 | keep (retire 1 test) | `tests/architectural/test_docs_cli_reference_parity.py::test_visible_paths_match_reference` survives `test_retired_check_residual_option_is_absent` (:205), a retired-name tombstone |  | WP08 | The tombstone costs about 72 s wall. |
| `tests/architectural/test_execution_context_parity.py` | behavioural-parity + scan-ban | mixed: CWD-invariance is a behavioural invariant; :2018 and :2160 are negative bans; the `missing_seams` arm (:2193-2198) pins positive seam names | 12 | 9 | 5 | 6 | 3 | keep + consolidate | xfail → WP docstring map and the redundant `missing_seams` arm removed. reason: the kept negative ban already reds on a seam rename; mutation: rename both exempt seams → the ban reds via `gate.py:218` and `agent_retrospect.py:264` | fails: both bans read fixed source files (`_FRAGMENT_SOURCE_THREADING_FILES`, `_CANONICAL_STATUS_READ_FILES`) with `read_text`, so a missing target raises; there is no directory scan to go empty | WP08 | `test_cwd_parity` takes about 80 s and the full-sequence tests about 95 s. 0 `mark.xfail` markers remain on base. |
| `tests/architectural/test_glossary_authority_parity.py` | behavioural-parity | invariant (3-authority glossary agreement) | 3 | 1 | 1 | 1 | 0 | keep | — |  | — | Consolidation candidate with `test_glossary_pack_parity.py`. |
| `tests/architectural/test_glossary_pack_parity.py` | behavioural-parity | invariant (seed ↔ pack) | 6 | 6 | 4 | 1 | 1 | keep | — |  | — | Consolidation candidate with `test_glossary_authority_parity.py`. |
| `tests/architectural/test_local_gate_parity.py` | import-scan (singularity) | invariant (local selection imports the CI authority, never re-encodes it) | 1 | 0 | 0 | 0 | 0 | keep | — | fails: `test_local_gate_parity_module_exists` asserts `scripts/ci/local_gate_parity.py` is a file, and the AST scans `read_text` that one fixed path | — |  |
| `tests/audit/test_shape_registry_writer_parity.py` | behavioural-parity | invariant (derived from schema) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — |  |
| `tests/charter/synthesizer/test_synthesize_path_parity.py` | behavioural-parity | invariant (dry-run path = real path) | 5 | 5 | 3 | 1 | 1 | keep | — |  | — |  |
| `tests/charter/test_check_graph_kind_parity.py` | unit (production parity checker) | invariant (unit tests of a production checker) | 3 | 3 | 2 | 0 | 0 | keep | — |  | — | Misnamed: it is not a parity pin. |
| `tests/charter/test_config_stem_parity.py` | behavioural-parity | invariant (stem → URN or raise) | 7 | 5 | 5 | 1 | 0 | keep | — |  | — |  |
| `tests/charter/test_context_parity.py` | behavioural (misnamed parity) | shape: behavioural marker assertions, but the fixture pins private patch targets (`charter.activation.catalog.built_in_dir`, `...directives.repository.built_in_dir`, `profile_resolution._activation_aware_profile_map`, :186-236) | 12 | 12 | 5 | 6 | 6 | convert | on-disk packs mirror through the public pack seam; renamed `tests/charter/test_context_bootstrap_markers.py`; 10 → 0 src-coupling offenders. Survivor `tests/charter/test_context_bootstrap_markers.py::TestJsonEntryPointParity::test_json_entry_point_is_valid_bootstrap_payload` (name kept; cited by `context_contract.py`). reason: the four marker assertions are kept and only the private patch fixture changes; mutation: `test_src_coupling_scan_flags_planted_offenders` feeds planted `patch("charter.…")` and private-import sources to the same `_src_coupling_offenders` helper the ban uses |  | WP10 | The one true shape-coupling co-change row: pcsrc/pcm = 6/6. Each doctrine relocation (`873832aa1`, `b1d7a2c23`, `2b5335cf8`, `4e8fc0596`, `6fc2ac018`) forced a fixture rewrite. |
| `tests/charter/test_context_profile_lineage_parity.py` | behavioural-parity | invariant (2 surfaces agree, #4917) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — |  |
| `tests/charter/test_direct_write_kinds_parity.py` | behavioural-parity | invariant (single constant ↔ 2 consumers) | 2 | 1 | 0 | 1 | 0 | keep | — |  | — |  |
| `tests/charter/test_kind_vocabulary_recursion_parity.py` | behavioural-parity | invariant (#3426 list vs activate) | 3 | 3 | 2 | 0 | 0 | keep | — |  | — | Consolidation candidate: fold into `tests/doctrine/drg/test_recursion_parity_gate.py`. |
| `tests/charter/test_mission_type_activations_seed_read_parity.py` | behavioural-parity | invariant (two seeders agree) | 2 | 2 | 1 | 0 | 0 | keep | — |  | — |  |
| `tests/charter/test_resolver_activation_parity.py` | behavioural-parity | invariant | 2 | 2 | 0 | 1 | 1 | keep | — |  | — |  |
| `tests/charter/test_spdd_reasons_activation_parity.py` | behavioural-parity | invariant (a layer ban forces duplication; parity is the guard) | 2 | 2 | 0 | 1 | 1 | keep | — |  | — |  |
| `tests/compat/test_dry_run_parity.py` | behavioural-parity | invariant (dry-run = real run) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — |  |
| `tests/cross_branch/test_parity.py` | behavioural-parity | invariant (reducer determinism), duplicated | 3 | 2 | 3 | 0 | 0 | consolidate (deferred) | duplicates `tests/status/test_reducer.py:425,465`; no work in this mission (C-003 scope discipline) |  | follow-up filed at WP13 | 0 post-creation modifications; "T078" 0.1x-era scaffold. |
| `tests/doctrine/drg/test_recursion_parity_gate.py` | behavioural-parity | invariant (loader ↔ resolver) | 3 | 3 | 0 | 2 | 2 | keep | — |  | — | Canonical home for recursion parity. |
| `tests/doctrine/test_activation_parity_guard.py` | behavioural-parity | invariant (config ↔ derived, fail-closed) | 10 | 7 | 6 | 3 | 2 | keep | — |  | — |  |
| `tests/doctrine/test_model_task_routing_parity.py` | behavioural-parity | invariant (schema ↔ model) | 2 | 2 | 1 | 0 | 0 | keep | — |  | — |  |
| `tests/doctrine/test_packaging_parity.py` | packaging-parity | invariant (wheel and sdist ship the full pack) | 9 | 5 | 5 | 4 | 2 | keep | — |  | — | About 55 s. Overlap check with `tests/cross_cutting/packaging/test_packaging_safety.py` (consolidation candidate). |
| `tests/doctrine/test_relation_doc_parity.py` | doc-parity | invariant (enum ↔ doc) | 4 | 4 | 2 | 1 | 1 | keep | — |  | — |  |
| `tests/dossier/test_manifest_guard_parity.py` | behavioural-parity | invariant (cross-manifest) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — |  |
| `tests/integration/test_render_parity_golden.py` | golden + mutation arms | invariant (golden with `dropped_*_turns_parity_red` mutation arms) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — | The discriminator's good case. |
| `tests/kernel/test_lock_parity.py` | negative-invariant scan | invariant (negative: no public API returns a raw fd), planted self-test at :166 | 2 | 1 | 1 | 1 | 0 | keep | — | fails: the AST scan `read_text`s the one fixed `_LOCKS_SOURCE_PATH` (a missing file raises), and `test_aenter_and_enter_return_annotations_are_lock_record` asserts both entry points are found | — |  |
| `tests/kernel/test_runtime_root_resolver_parity.py` | behavioural-parity | invariant (2 resolvers agree) | 1 | 1 | 0 | 0 | 0 | keep | — |  | — | Keep until the resolvers are unified. |
| `tests/missions/test_surface_resolution_equivalence.py` | behavioural-parity (differential) | invariant (3–4 live read entry points agree on dir or typed error), carrying dead strict-xfail scaffold | 12 | 12 | 5 | 7 | 7 | keep + consolidate | dead strict-xfail scaffold removed (`_apply_xfail`, the always-`None` `xfail_reason` column, the stale RED/GREEN table); `tests/missions/test_surface_resolution_equivalence.py::test_equivalence_detects_planted_divergence` added through the real comparison |  | WP08 | Co-change 7/7 is the owning mission's build-out (6 of 7 modifications fall between 06-20 and 06-26), not shape pins. Retire once the resolvers collapse to one authority. |
| `tests/next/test_internal_runtime_parity.py` | import-ban scan + surface pins | mixed: 2 negative bans that are vacuous on base, 2 positive-shape surface pins, 1 frozen upstream golden | 4 | 3 | 4 | 0 | 0 | fix + retire parts | rich/typer ban converted, with floor ≥ 16 files and a planted test (`tests/next/test_internal_runtime_parity.py::test_rich_typer_ban_flags_planted_import`); `spec_kitty_runtime` ban → `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package`; 2 surface-shape pins → `tests/next/test_internal_runtime_parity.py::test_internalized_runtime_matches_upstream_snapshot` (mutation: a behaviour-preserving rename of `_read_snapshot` and its 3 internal call sites reds only the retired pin among this module's tests; `delattr` is not a valid mutation because it errors the golden) | vacuous on base: both bans `rglob` the deleted `src/specify_cli/next/_internal_runtime` (removed by `93dcbd75481c`, 2026-07-03), iterate 0 files and pass. After WP08: fails on a missing or empty target, floor ≥ 16 files of the live `src/runtime/next/_internal_runtime` | WP08 | The golden compares against the retired `spec_kitty_runtime` 0.4.x; keep it as a characterization golden, not "upstream parity". |
| `tests/next/test_next_replay_parity_integration.py` | behavioural-parity | invariant (events fixture replay) | 5 | 3 | 3 | 2 | 0 | keep | — |  | — |  |
| `tests/review/test_baseline_head_parity.py` | behavioural-parity | invariant (shared failure-identity namespace, real repo) | 6 | 6 | 0 | 5 | 5 | keep | — |  | — | Watch: co-change 5/5 is evolution of the same subsystem (#3611 etc.), not shape pins. |
| `tests/review/test_transition_gate_parity.py` | characterization oracle | invariant (base-commit goldens), plus 1 self-referential docstring meta-test | 5 | 4 | 1 | 3 | 2 | keep (retire 1 test) | reason: `test_wp09_hook_landmine_disposition_is_documented_accurately` (:280) tests its own docstring (self-referential); mutation: editing only the docstring reds it with no behaviour change |  | WP08 | The oracle arms are kept. |
| `tests/runtime/test_bridge_parity.py` | behavioural-parity + P0 acceptance | invariant (determinism + coverage floor), and since 2026-09-25 the P0 acceptance matrix for #4980/#4975 | 4 | 3 | 1 | 2 | 1 | split | P0 + fail-closed tests → `tests/runtime/test_next_board_authority.py` (16 nodes; e.g. `tests/runtime/test_next_board_authority.py::test_no_advancing_path_emits_unauthorized_step`); oracle (8 nodes) unchanged, retirement deferred |  | WP11; #5116 (after #2633) | Oracle module fixture about 391 s (`test_every_fixture_pair_is_parity_stable` setup 391.46 s); P0 tests about 40 s. Do not retire the oracle while #2633 is open. |
| `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` | behavioural end-to-end | invariant (real `charter generate`) | 3 | 3 | 0 | 2 | 2 | keep | — |  | — | 112 s across 2 tests. |
| `tests/specify_cli/cli/commands/test_wp02_seam_migration_equivalence.py` | behavioural-parity | invariant (slug-mid8 = full id via 3 CLI helpers), WP-named migration scaffold | 1 | 1 | 1 | 0 | 0 | consolidate (deferred) | fold into `tests/specify_cli/missions/test_handle_equivalence_matrix.py`; low priority, zero churn |  | follow-up filed at WP13 |  |
| `tests/specify_cli/invocation/test_registry_builtin_activation_parity.py` | behavioural-parity | invariant (dispatch-routing = governance gating) | 4 | 3 | 2 | 1 | 0 | keep | — |  | — |  |
| `tests/specify_cli/lanes/test_for_review_gate_parity.py` | behavioural-parity | invariant (hoisted leaf = real orchestrator path) | 3 | 3 | 0 | 2 | 2 | keep | — |  | — |  |
| `tests/specify_cli/missions/test_handle_equivalence_matrix.py` | behavioural-parity | invariant (handle forms agree) | 12 | 10 | 6 | 6 | 4 | keep | — |  | — | Canonical handle-equivalence home. |
| `tests/specify_cli/regression/test_twelve_agent_parity.py` | byte-golden | invariant (byte golden, narrowed by `b94a005c1` on 2026-08-15 to 3 canonical baseline files) | 18 | 12 | 10 | 8 | 3 | keep | — |  | — | Already remediated: churn before 08-15 was the friction; after it, 1 legitimate agent-add co-change. |
| `tests/status/test_dashboard_status_parity.py` | behavioural-parity | invariant (dashboard = CLI) | 2 | 2 | 2 | 0 | 0 | keep | — |  | — |  |
| `tests/status/test_migrate_lifecycle_envelope_node_id_parity.py` | behavioural-parity | invariant (forced duplication stays identical) | 2 | 1 | 0 | 1 | 0 | keep | — |  | — |  |
| `tests/status/test_parity.py` | import-ban scan + tombstone + behavioural-parity | mixed: mostly retired-subsystem scaffold (0.1x backport, sync, phase tombstone) plus triplicated determinism and genuine matrix invariants | 11 | 10 | 8 | 3 | 2 | retire + relocate | per-test survivors and mutations M1–M10 in the WP09 tracer entries; backport → `tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist` | vacuous: `TestBackportReadiness` bans `from specify_cli.sync`, a package that no longer exists, so it can never fire; `test_no_status_module_directly_imports_sync_at_toplevel` globs `specify_cli/status/*.py` with no floor, so an empty target passes | WP09 | 740 LOC. Matrix invariants relocate to `tests/status/test_transitions.py`; determinism consolidates into `tests/status/test_reducer.py`. |
| `tests/status/test_wp01_terminus_authority_parity.py` | behavioural-parity | invariant (tidy-first preservation), WP-named | 1 | 1 | 0 | 0 | 0 | keep | — |  | — | Rename or fold into the doctor/accept tests at the next campsite. |

## Already retired before this mission

`tests/architectural/test_contract_registry_parity.py` is not a row, because it is not in the base sweep. It was deleted in `177e06269` (2026-08-12, "test: assertively sanitize low-signal suite cruft (#3285)"), together with `tests/architectural/test_no_parity_scaffold.py`. The #2631 comment of 2026-08-17, which says it "still exists", is wrong. The disposition trail is in `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tasks/WP05-structural-scaffold-retirement.md:45,98`.

## Headline

- The sweep holds **45 modules**, and **35 are clean keeps**: mostly small, recent "two authorities must agree" guards with pcm ≤ 1.
- Only one row is true shape-coupling co-change: `tests/charter/test_context_parity.py`, with pcsrc/pcm = 6/6. The other two rows with a ratio of 1.0 (`test_surface_resolution_equivalence` 7/7, `test_baseline_head_parity` 5/5) are behaviour suites whose churn is their own subsystem's build-out.
- The net-negatives are **vacuous or tombstone tests**, not high-churn ones: bans scanning a deleted directory, bans on a dead package, a docstring meta-test, a retired-name tombstone.

## Reconciliation at closeout

WP13 must confirm these 8 WP-owned rows against the landed code and record the confirmation in the design-decisions tracer. A code_change WP may not edit this file.

1. `tests/next/test_internal_runtime_parity.py` (WP08): the rich/typer ban has a floor ≥ 16 files and the planted test exists; `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package` is green; the 2 surface-shape pins are gone and the golden survives.
2. `tests/missions/test_surface_resolution_equivalence.py` (WP08): the strict-xfail scaffold is gone, and `test_equivalence_detects_planted_divergence` exists and is green.
3. `tests/architectural/test_execution_context_parity.py` (WP08): the xfail → WP map and the `missing_seams` arm are gone, and the negative bans remain.
4. `tests/review/test_transition_gate_parity.py` (WP08): `test_wp09_hook_landmine_disposition_is_documented_accurately` is gone, and the oracle arms remain.
5. `tests/architectural/test_docs_cli_reference_parity.py` (WP08): `test_retired_check_residual_option_is_absent` is gone, and `test_visible_paths_match_reference` remains.
6. `tests/status/test_parity.py` (WP09): the module is deleted, and every survivor named in the WP09 tracer entries exists, including `tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist`.
7. `tests/charter/test_context_parity.py` (WP10): renamed to `tests/charter/test_context_bootstrap_markers.py` with 0 src-coupling offenders. If WP10 deferred under the FR-015 clause, record that as the verdict instead.
8. `tests/runtime/test_bridge_parity.py` (WP11): `tests/runtime/test_next_board_authority.py` collects **16** nodes, and the oracle module keeps exactly **8**.

The two `consolidate (deferred)` rows (`tests/cross_branch/test_parity.py`, `tests/specify_cli/cli/commands/test_wp02_seam_migration_equivalence.py`) get follow-up issues filed at WP13; no code changes in this mission.
