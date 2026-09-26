# Grounding: #2631 (FR-016 parity/equivalence harm audit) and #2972 (pytest-rule census)

Researcher Robbie, investigation mode, read-only. HEAD `34f19c6fb` (2026-09-26). No repo edits.
The local checkout is shallow (50 commits), so churn comes from a blobless clone (history since 2026-03-20; session-local, not committed). The raw churn tables are summarised below.

---

## Part 0: Tracker state

| Issue | State | Relevance |
|---|---|---|
| #2631 | OPEN, P3, `status:triage`. On 2026-09-26 it was re-parented under the new epic **#5104** ("Test suite friction — ratchet, baseline & census gates"; its children are #2631, #2972, #3011, #3026, #5085). | This audit. |
| #2630 | **CLOSED not_planned (duplicate of #2633)** on 2026-07-14. | The issue's "wait for #2630" precondition is formally moot. |
| #2633 | **OPEN**, P2. Promoted to `status:ready` on 2026-09-26. It was rescoped on 2026-08-17: the sentinels were retired when `test_bridge_compat_surface.py` was deleted in `177e06269` (#3285). What remains is deleting the 34 thin delegates plus repointing about 14 callers. | This is the real remaining gate for `test_bridge_parity.py` (see Stijn's comment on #2631 from 2026-08-17). |
| #2531 | CLOSED completed on 2026-07-12 via PR #2558. | The seam suites have existed for about 2.5 months. |

Comments on #2631 that matter:
- 2026-08-17 (Stijn): item 2 is unblocked on the sentinel side, but the parity oracle should not be retired until #2633's delegate deletion lands. The same comment says `test_contract_registry_parity` "still exists", and **that is wrong** (see below).
- 2026-09-14 (Stijn, after #4315 / ADR `2026-09-14-1`): the `test_golden_count_ban.py` and `_shard_registry`/shard-map KEEP rows cited as context are **reversed (retired)**. The live parity scope is unaffected.
- 2026-08-02 triage said "keep open". The 2026-09-25 groom moved it to `status:triage`.

**Does the #2630 precondition hold?** Partly. `tests/runtime/test_bridge_compat_surface.py` is gone (confirmed on disk). #2633's delegate deletion has **not** landed: #2633 is open and `src/runtime/next/runtime_bridge.py` is still 3544 LOC. So the ticket's own condition, "do not retire while the REACH-entangled delegate deletions are open", **still blocks retirement of the two-run oracle**. It does not block the split recommended in section 3.

## Part 1: What happened to the three named suites

| Named suite | Status |
|---|---|
| `tests/architectural/test_execution_context_parity.py` | Exists. 2209 LOC, 21 tests. |
| `tests/missions/test_surface_resolution_equivalence.py` | Exists. 1248 LOC, 14 test functions (the matrix is parametrized). |
| `tests/architectural/test_contract_registry_parity.py` | **DELETED** in `177e06269` (2026-08-12, "test: assertively sanitize low-signal suite cruft (#3285)"). `tests/architectural/test_no_parity_scaffold.py` went in the same commit. It was created in `625963ca1` (2026-07-07). The disposition trail is in `kitty-specs/assertive-test-suite-sanitation-01KZME3P/tasks/WP05-structural-scaffold-retirement.md:45,98`. |

Other `*parity*` suites deleted inside the window, which shows the class is already being pruned:
- `tests/review/test_census_parity.py` (`c844a0df2`, #2873)
- `tests/sync/test_mission_created_payload_parity.py` (`66038e2a5`, sync retirement)
- `tests/specify_cli/invocation/cli/test_dispatch_parity.py` (`2146506bd`)

## Part 2: The sweep, churn method and full table

Sweep: `find tests -name '*parity*.py' -o -name '*equivalence*.py'` returns **49 files**: 45 test modules plus 4 `_support/coverage_safety` helpers or self-tests.

Churn method (CaaCS-style):
- For each file: `git log --since=2026-03-26 --format=%H -- <file>`, then `git show --name-only` on each commit.
- **all** = commits in the window. **src** = how many of those also touched `src/`.
- **mass** = commits touching more than 60 files (relocations, format sweeps). They are noise for a co-change signal.
- **pcm / pcsrc** = modifications *after the creation commit*, excluding mass commits, and how many of those touched `src/`. This is the discriminator-relevant "does it co-change on every refactor" figure.

**Full run:** all 45 modules except `test_bridge_parity.py` were run with `.venv/bin/python -m pytest <files> -n 8 --dist loadfile -rs`. Result: **761 passed, 0 skipped, 0 failed, 205 s**. `test_bridge_parity.py` was run separately: **24 passed in 435.96 s**.

| file | all | src | mass | pcm | pcsrc | LOC | discriminator | verdict |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `_factories/test_make_mission_parity.py` | 5 | 2 | 3 | 2 | 0 | 210 | invariant (single-schema delegation) | KEEP (already catalogued) |
| `_support/coverage_safety/*equivalence*` (4 files) | 1–2 | – | all | 0 | 0 | 81–149 | tooling self-test (anti-vacuity harness) | KEEP (not a parity pin) |
| `architectural/test_basetemp_retention_doc_parity.py` | 1 | 0 | 0 | 0 | 0 | 91 | doc↔config invariant | KEEP |
| `architectural/test_docs_cli_reference_parity.py` | 12 | 7 | 5 | 7 | 3 | 522 | invariant (live Typer tree = reference docs); planted-bad self-test at :476 | KEEP. Retire the tombstone `test_retired_check_residual_option_is_absent` (:205): it is a retired-name absence pin and 72 s wall |
| **`architectural/test_execution_context_parity.py`** | 12 | 9 | 5 | 6 | 3 | 2209 | **mixed**: CWD-invariance is a behavioural invariant; :2018 is a negative ban; :2160 partly pins positive shape | **KEEP + CONSOLIDATE** (see section 3) |
| `architectural/test_glossary_authority_parity.py` | 3 | 1 | 1 | 1 | 0 | 319 | invariant (3-authority glossary agreement) | KEEP |
| `architectural/test_glossary_pack_parity.py` | 6 | 6 | 4 | 1 | 1 | 212 | invariant (seed↔pack) | KEEP; consolidation candidate with glossary_authority |
| `architectural/test_local_gate_parity.py` | 1 | 0 | 0 | 0 | 0 | 160 | invariant (local selection imports CI authority) | KEEP |
| `audit/test_shape_registry_writer_parity.py` | 1 | 1 | 0 | 0 | 0 | 53 | invariant (derived-from-schema) | KEEP |
| `charter/synthesizer/test_synthesize_path_parity.py` | 5 | 5 | 3 | 1 | 1 | 315 | invariant (dry-run path = real path) | KEEP |
| `charter/test_check_graph_kind_parity.py` | 3 | 3 | 2 | 0 | 0 | 235 | unit tests of a production parity checker | KEEP (misnamed, not a pin) |
| `charter/test_config_stem_parity.py` | 7 | 5 | 5 | 1 | 0 | 226 | invariant (stem→URN or raise) | KEEP |
| **`charter/test_context_parity.py`** | 12 | 12 | 5 | 6 | **6** | 428 | assertions are behavioural markers, but **the fixture pins private patch targets** (`charter.activation.catalog.built_in_dir`, `...directives.repository.built_in_dir`, `profile_resolution._activation_aware_profile_map`, :186-236) | **CONVERT** (section 3). pcsrc/pcm = **1.00** |
| `charter/test_context_profile_lineage_parity.py` | 1 | 1 | 0 | 0 | 0 | 149 | invariant (2 surfaces agree, #4917) | KEEP |
| `charter/test_direct_write_kinds_parity.py` | 2 | 1 | 0 | 1 | 0 | 90 | invariant (single constant ↔ 2 consumers) | KEEP |
| `charter/test_kind_vocabulary_recursion_parity.py` | 3 | 3 | 2 | 0 | 0 | 144 | invariant (#3426 list-vs-activate) | KEEP; consolidate with `doctrine/drg/test_recursion_parity_gate.py` |
| `charter/test_mission_type_activations_seed_read_parity.py` | 2 | 2 | 1 | 0 | 0 | 165 | invariant (two seeders agree) | KEEP |
| `charter/test_resolver_activation_parity.py` | 2 | 2 | 0 | 1 | 1 | 257 | invariant | KEEP |
| `charter/test_spdd_reasons_activation_parity.py` | 2 | 2 | 0 | 1 | 1 | 326 | invariant (a layer ban forces duplication; parity is the guard) | KEEP |
| `compat/test_dry_run_parity.py` | 1 | 1 | 0 | 0 | 0 | 214 | invariant (dry-run = real run) | KEEP |
| `cross_branch/test_parity.py` | 3 | 2 | 3 | 0 | 0 | 160 | invariant (reducer determinism) but **duplicates** `status/test_reducer.py:425,465` | CONSOLIDATE |
| `doctrine/drg/test_recursion_parity_gate.py` | 3 | 3 | 0 | 2 | 2 | 262 | invariant (loader↔resolver) | KEEP (canonical home for recursion parity) |
| `doctrine/test_activation_parity_guard.py` | 10 | 7 | 6 | 3 | 2 | 540 | invariant (config↔derived fail-closed) | KEEP |
| `doctrine/test_model_task_routing_parity.py` | 2 | 2 | 1 | 0 | 0 | 158 | schema↔model invariant | KEEP |
| `doctrine/test_packaging_parity.py` | 9 | 5 | 5 | 4 | 2 | 250 | invariant (wheel/sdist ship full pack), about 55 s | KEEP; check overlap with `tests/cross_cutting/packaging/test_packaging_safety.py` |
| `doctrine/test_relation_doc_parity.py` | 4 | 4 | 2 | 1 | 1 | 192 | enum↔doc invariant | KEEP |
| `dossier/test_manifest_guard_parity.py` | 1 | 1 | 0 | 0 | 0 | 254 | cross-manifest invariant | KEEP |
| `integration/test_render_parity_golden.py` | 1 | 1 | 0 | 0 | 0 | 221 | golden plus mutation arms (`dropped_*_turns_parity_red`) | KEEP (the discriminator's good case) |
| `kernel/test_lock_parity.py` | 2 | 1 | 1 | 1 | 0 | 387 | structural, but a *negative* invariant (no API returns a raw fd), with a planted self-test at :166 | KEEP |
| `kernel/test_runtime_root_resolver_parity.py` | 1 | 1 | 0 | 0 | 0 | 100 | invariant (2 resolvers agree) | KEEP until unified |
| **`missions/test_surface_resolution_equivalence.py`** | 12 | 12 | 5 | 7 | **7** | 1248 | **behavioural differential invariant**, but it carries dead strict-xfail scaffold | **KEEP + CONSOLIDATE** (section 3) |
| **`next/test_internal_runtime_parity.py`** | 4 | 3 | 4 | 0 | 0 | 169 | 2 negative bans that are **VACUOUS**, 2 positive-shape surface pins, 1 frozen upstream golden | **FIX + RETIRE parts** (section 3) |
| `next/test_next_replay_parity_integration.py` | 5 | 3 | 3 | 2 | 0 | 29 | invariant (events fixture replay) | KEEP |
| `review/test_baseline_head_parity.py` | 6 | 6 | 0 | 5 | **5** | 272 | invariant (shared failure-identity namespace, real repo) | KEEP. Co-change 1.00 is feature evolution of the same subsystem (#3611 etc.), not shape pins. Watch it |
| **`review/test_transition_gate_parity.py`** | 5 | 4 | 1 | 3 | 2 | 304 | characterization oracle (base-commit goldens), plus **1 self-referential docstring meta-test** | KEEP the oracle arms; **RETIRE** `test_wp09_hook_landmine_disposition_is_documented_accurately` (:280) |
| **`runtime/test_bridge_parity.py`** | 4 | 3 | 1 | 2 | 1 | 1862 | invariant (determinism + coverage floor), **and since 2026-09-25 also the P0 acceptance matrix for #4980/#4975** | **SPLIT** (section 3). Do not retire yet |
| `specify_cli/charter_runtime/test_references_parity_refresh.py` | 3 | 3 | 0 | 2 | 2 | 338 | behavioural end-to-end (real `charter generate`), 112 s across 2 tests | KEEP |
| `specify_cli/cli/commands/test_wp02_seam_migration_equivalence.py` | 1 | 1 | 1 | 0 | 0 | 174 | behavioural (slug-mid8 = full id via 3 CLI helpers). WP-named migration scaffold | CONSOLIDATE into `test_handle_equivalence_matrix.py` (low priority, zero churn) |
| `specify_cli/invocation/test_registry_builtin_activation_parity.py` | 4 | 3 | 2 | 1 | 0 | 188 | invariant (routing = governance gating) | KEEP |
| `specify_cli/lanes/test_for_review_gate_parity.py` | 3 | 3 | 0 | 2 | 2 | 266 | invariant (hoisted leaf = real orchestrator path) | KEEP |
| `specify_cli/missions/test_handle_equivalence_matrix.py` | 12 | 10 | 6 | 6 | 4 | 1202 | invariant (handle forms agree) | KEEP (canonical handle-equivalence home) |
| `specify_cli/regression/test_twelve_agent_parity.py` | 18 | 12 | 10 | 8 | 3 | 292 | byte-golden, **already narrowed** by `b94a005c1` (2026-08-15) to 3 canonical baseline files | KEEP (already remediated; churn before 08-15 was the friction; after it, 1 legitimate agent-add co-change) |
| `status/test_dashboard_status_parity.py` | 2 | 2 | 2 | 0 | 0 | 117 | invariant (dashboard = CLI) | KEEP |
| `status/test_migrate_lifecycle_envelope_node_id_parity.py` | 2 | 1 | 0 | 1 | 0 | 22 | invariant (forced duplication stays identical) | KEEP |
| **`status/test_parity.py`** | 11 | 10 | 8 | 3 | 2 | 740 | **mostly retired-subsystem scaffold** (0.1x backport, sync, phase tombstone) plus duplicated determinism | **RETIRE most, RELOCATE the rest** (section 3) |
| `status/test_wp01_terminus_authority_parity.py` | 1 | 1 | 0 | 0 | 0 | 124 | behavioural (tidy-first preservation), WP-named | KEEP. Rename or fold into doctor/accept tests at the next campsite |

**Headline numbers:**
- Of 45 modules, **35 are clean KEEPs**. Most are small, recent "two authorities must agree" guards with pcm ≤ 1.
- Ratio 1.0 co-change *after creation*, with non-trivial volume, appears in only 3 files: `charter/test_context_parity.py` (6/6), `missions/test_surface_resolution_equivalence.py` (7/7) and `review/test_baseline_head_parity.py` (5/5). Only the first is shape-coupling. The other two are behaviour suites whose churn is the owning mission's own build-out: 6 of surface_resolution's 7 modifications fall between 06-20 and 06-26.
- The actual net-negatives are **vacuous or tombstone tests**, not high churn.

## Part 3: Net-negatives, with concrete convert-or-retire actions

### N1. `tests/next/test_internal_runtime_parity.py`: two import bans that can never fail
- `test_no_spec_kitty_runtime_imports_in_internal_package` (:89) and `test_no_rich_or_typer_imports_in_internal_package` (:118) both `rglob` `src/specify_cli/next/_internal_runtime` (:95-101, :120-126).
- **That directory no longer exists.** `src/specify_cli/next/` was deleted by the unshim (commit `93dcbd75481c`, 2026-07-03). The live package is `src/runtime/next/_internal_runtime/`.
- Both tests iterate zero files and pass. This is a textbook Standing Order #5 violation: there is no concrete floor.
- Action (**FIX, not retire**; these are keep-class negative invariants):
  - Repoint both to `src/runtime/next/_internal_runtime`.
  - Add a floor: `assert py_files`, meaning at least N files.
  - Add a planted-offender self-test.
  - Or retire them in favour of a pytestarch rule in `tests/architectural/test_layer_rules.py`. `test_shared_package_boundary.py:59` already guards `spec_kitty_runtime` repo-wide, which makes the first ban redundant; retire that one and keep the rich/typer layer ban as a LayerRule.
- `test_public_surface_matches_contract` (:142) and `test_submodule_surface_matches_contract` (:161) are **positive shape pins**: `__all__` equality and `hasattr(engine, "_read_snapshot")`, where the latter is a private name. Action: RETIRE. The golden-replay test exercises the public entries behaviourally.
- `test_internalized_runtime_matches_upstream_snapshot` compares against a frozen `spec_kitty_runtime` 0.4.x golden, and that upstream package is retired. Keep it as a characterization golden for now, but it should be relabelled: it is no longer "upstream parity".
- Proof nothing behavioural is lost:
  - The planted-offender self-test goes red with the scan repointed and green on the live tree.
  - `tests/architectural/test_shared_package_boundary.py` and `test_layer_rules.py` stay green.
  - `tests/next/` stays green.

### N2. `tests/status/test_parity.py` (740 LOC): mostly retired-subsystem scaffold
- **`TestBackportReadiness`** (:75-190): about 9 parametrized cases plus 2 scans proving status modules import "without `specify_cli.sync`".
  - `src/specify_cli/sync` **does not exist**; it was retired with the sync transport and is listed in `tests/architectural/test_no_retired_subsystems.py:28`.
  - Blocking `sys.modules["specify_cli.sync"]` for a package that doesn't exist, and scanning for `from specify_cli.sync`, can never fire. The CLAUDE.md "sync is dead" canon applies.
  - Action: RETIRE. `test_no_retired_subsystems.py` is the canonical guard.
- **`TestPhaseCap::test_phase_module_deleted`** (:200) is a tombstone ("module X is gone"), the same class #3285 retired. Action: RETIRE (or add `status/phase.py` to the retired-paths list in `test_no_retired_subsystems.py`).
- **`TestReducerDeterminism` / `TestFullEventLogParity`** (:213-690): the behavioural invariant is real, but it is **triplicated**, with `tests/status/test_reducer.py:143,177,425,465` and with `tests/cross_branch/test_parity.py`. Action: CONSOLIDATE into `tests/status/test_reducer.py`. Keep one realistic-log fixture test and delete `tests/cross_branch/test_parity.py` (0 post-creation modifications, "T078" 0.1x-era scaffold).
- **`TestTransitionMatrixParity`** (:695+) contains genuine invariants: no self-transitions, terminal lanes have no outbound edges, enum ↔ canonical lanes. Action: RELOCATE to `tests/status/test_transitions.py`.
- Proof:
  - Before deleting, run the RED-first mutation for each surviving invariant: shuffle the reducer sort key, add a `done→planned` matrix row, and add a self-transition. Each should turn the relocated test red.
  - `tests/architectural/test_no_retired_subsystems.py` stays green.
  - `tests/status/` stays green.

### N3. `tests/charter/test_context_parity.py`: behaviour asserted through private patch targets (co-change 6/6)
- The assertions are behavioural markers: first-load state, `Cause: missing_artifact`, the `section:terminology-canon` fetch stanza.
- But the fixture patches private seams, and the 50-line comment at :195-230 is literally a changelog of patch targets that relocations broke: `resolve_doctrine_root` → `resolve_pack_root` → `built_in_dir`.
- Every doctrine relocation (`873832aa1`, `b1d7a2c23`, `2b5335cf8`, `4e8fc0596`, `6fc2ac018`) forced a rewrite. That is the discriminator's "co-changes with src on every refactor".
- Action: CONVERT.
  - Build a real on-disk project whose pack/doctrine root is supplied through the public config or env seam (`.kittify/config.yaml` pack paths or the `SPEC_KITTY_*` pack env), instead of `patch("charter.activation.catalog.built_in_dir")`.
  - Keep the four marker assertions.
  - Rename to `test_context_bootstrap_markers.py`. It is not a byte-parity test, whatever the docstring says.
- Proof: each marker assertion is mutation-checked with `tests/_support/coverage_safety/equivalence.py` (inject a known-bad input, and the test must go red), and `tests/charter/` plus `tests/doctrine/` stay green.

### N4. `tests/missions/test_surface_resolution_equivalence.py`: keep the gate, strip the dead scaffold
- The behavioural differential (3–4 live read entry points must agree on dir or typed error) is **still load-bearing**, because the entry points still coexist.
- The strict-xfail machinery is dead: every `_MATRIX` row has `xfail_reason=None` (:490-575), and :478-486 records the drain to 13/0 on 2026-06-21.
- The docstring's RED/GREEN cell table (:38-108) is stale and misleading.
- Action: CONSOLIDATE.
  - Delete `_apply_xfail`, the reason column and the stale table (roughly 150 LOC).
  - Keep `_assert_equivalent` and the matrix.
  - Retire the module once the resolvers collapse to one authority. At that point the differential compares a function with itself.
- Proof: the matrix still reports all parametrized cells passing, and a planted divergence (monkeypatch one entry point to return primary) goes red.

### N5. `tests/architectural/test_execution_context_parity.py`: keep the core, trim scaffold
- The CWD/execution-mode invariance tests (`test_cwd_parity`, `test_full_sequence_*`, each with a `*_ratchet_catches_divergence` self-test) are exemplary behavioural invariants. Post-creation churn is 6 modifications, 3 of which touched src; since July only 2 test-only fixture fixes (`4a94f88ba`, `b38233ad5`).
- Scaffold to strip:
  - The "xfail → convergence-WP map" docstring (:110-160, :1397-1413, :1800). There are 0 `mark.xfail` markers left in the file.
  - In `test_no_feature_dir_anchored_status_event_reads` (:2160), the `missing_seams` check (:2193-2198) is a **positive** symbol-name pin ("function named X must exist"). Renaming a seam turns it red with no behavioural change.
- Action: drop the `missing_seams` half and keep the negative "no `feature_dir`-anchored read" ban. `test_no_local_coord_path_composition_in_status_surfaces` (:2018) is a negative ban; keep it.
- Cost note: `test_cwd_parity` takes about 80 s and the full-sequence tests about 95 s.

### N6. `tests/runtime/test_bridge_parity.py`: re-evaluation (item 2)
- **The file has changed character.** On 2026-09-25 `286462211` (the #4980/#4975 P0 fix) added **571 lines**: 17 behavioural P0 acceptance tests (:1383-1862), including review-reject re-dispatch, coord/lanes_with_coord implement dispatch, and named blocked-floor recoveries.
- Those are live P0 regression pins. They are not #2531 scaffold and must not be retired.
- The original #2531 oracle part (:1150-1330, the two-run determinism and coverage floor) is where the cost sits. It needs a module fixture of about **391 s** (measured: `test_every_fixture_pair_is_parity_stable` setup 391.46 s). The P0 tests together take about 40 s.
- The catalog's figure of about 2.5 min is stale; on this sandbox it is 6.5 min.
- `_bridge_oracle.py` also carries 8 positional `bridge:NNNN` line anchors (e.g. :448, :465, :518) into a file that has since changed size. These are stale comments and not enforced, but they are exactly the anchor class that `test_ratchet_positional_anchor_ban` targets.
- Action:
  - **Now:** SPLIT the P0 acceptance matrix into a behaviour-named module, for example `tests/runtime/test_next_board_authority.py`. Replace the `bridge:NNNN` anchors with symbol names.
  - **After #2633 lands:** RETIRE or relax the two-run oracle, or move it to the nightly tier (the `ci-nightly.yml` full run) instead of per-PR. Its own docstring concedes it cannot catch a consistent behaviour shift.
- Proof:
  - The moved P0 tests stay green with identical node count (17).
  - `tests/runtime/test_bridge_decide_next.py` and `tests/next/` stay green.
  - `test_no_dead_symbols.py` stays green after #2633.

### Minor
- Retire `review/test_transition_gate_parity.py::test_wp09_hook_landmine_disposition_is_documented_accurately` (:280). It is a test about the module's own docstring.
- Retire `architectural/test_docs_cli_reference_parity.py::test_retired_check_residual_option_is_absent` (:205), a retired-name tombstone.

### Suggested catalog rows (tracer format)
| suite | category | invariant or shape? | CaaCS churn | verdict | note |
|---|---|---|---|---|---|
| `test_execution_context_parity` | behavioural-parity | invariant (plus 1 positive seam-name pin) | 12 all / 6 pcm / 3 src | keep + consolidate | strip dead xfail map and `missing_seams` |
| `test_surface_resolution_equivalence` | behavioural-parity | invariant | 12 / 7 / 7 (the owning mission's build-out) | keep + consolidate | strip dead strict-xfail scaffold; retire on resolver unification |
| `test_contract_registry_parity` | – | – | – | **already retired** (`177e06269`, #3285) | #2631 comment of 08-17 is wrong |
| `test_bridge_parity` | behavioural-parity plus P0 acceptance | invariant | 4 / 2 / 1 | split now; oracle retire/relax after #2633 | about 391 s oracle fixture |
| `test_internal_runtime_parity` | mixed | 2 vacuous negative bans plus 2 shape pins | 4 / 0 / 0 | fix bans, retire shape pins | scanned path deleted 2026-07-03 |
| `status/test_parity` | mixed | retired-subsystem tombstones plus duplicated determinism | 11 / 3 / 2 | retire most, relocate matrix invariants | sync/0.1x/phase are dead |
| `charter/test_context_parity` | behavioural (misnamed) | shape via private patch targets | 12 / 6 / **6** | convert | the one true "co-changes on every refactor" row |
| `cross_branch/test_parity` | behavioural-parity | invariant, duplicate | 3 / 0 / 0 | consolidate into `test_reducer.py` | |

---

## Part 4: TASK B, #2972 (pytest-rule hygiene census)

- **State:** OPEN, P3, `status:triage`, labels `tech-debt catfooding tidy-up`. On 2026-09-26 it was re-parented from #1931 to epic **#5104** (the same epic as #2631).
- **Disposition is unchanged by the comments:**
  - 2026-07-27, Planner Priti rationale: "one ticket, zero children, bookmark not backlog, P3".
  - 2026-09-14 Sonar refresh: "disposition **still holds — do not mission, no children, consume as per-WP campsite**". The census grew: S9073 697, S5778 380, S9083 276, S8714 61, S9100 28, S9081 26, about half of 2596 open findings, all in `tests/`. S5779 moved to **#2969**. The `src/` half was carved into #4299–#4305 under #1928.
  - 2026-09-26: bot groom only.
- **#1842 is CLOSED (completed, 2026-07-07**, via PRs #2429/#2432). That is **20 days before #2972 was filed** (2026-07-27). The body's instruction to "route S8997 through #1842" therefore points at a closed ticket.
- **The S8997 subset (54 sites) has not been routed anywhere live.** A tracker search for S8997/monkeypatch global-state found nothing relevant (only #4773, closed, unrelated). The 2026-09-14 refresh table no longer even lists S8997. Its current count is unknown, so re-query Sonar before claiming it.
- **Recommendation for the mission:**
  1. Keep #2972 **out of scope as a work item**. No WP, no children.
  2. Campsite-clean the pytest-rule findings (S5778/S9073/S9083/S8997/…) **only in test files the mission already touches**. This is Standing Order #2 and matches the issue body's point 3. The natural overlap: every parity file the mission converts or relocates in section 3 should leave clean.
  3. Issue-matrix row: `#2972 | campsite/deferred | per-WP campsite on touched test files only; census bookmark stays open (close at ~0 or when superseded)`. Per Standing Order #8, post a tracker comment naming the mission.
  4. Flag to the operator: the S8997 routing target (#1842) is closed. Either file a small S8997 state-leak slice under #5104/#1931, or amend #2972's body. The mission must not silently absorb it.
