# Post-plan brownfield squad — Debugger Debbie (residual hunt)

Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z` · HEAD `5940b8ca` (src/tests identical to planning base `3717c7ea`; only kitty-specs differ).
Read-only. Probes: `scratchpad/debbie/{wide_probe.py,fr015_order.py,mutplug.py,p0_run.txt,audit.txt}` plus re-runs of `squad/{ban_probe,census_probe,dirty_probe}.py`.

## Governance applied
- **Profile debugger-debbie**: I used falsifier discipline, meaning every design claim was re-witnessed by a live probe or recorded as FALSE/PARTIAL. I used the Matrix-Maker lens to enumerate pin shapes (seed and non-seed, all AST nodes, YAML, JSON, txt, and files outside tests/architectural). I wrote no patches and produced a findings list only (avoidance boundary).
- **Directives**:
  - 001, 003 (decision/evidence records);
  - 030/032 (test and quality discipline);
  - DIRECTIVE_041/043 (content anchoring; non-vacuous gates) as the yardstick for "red-first" and floors;
  - DIRECTIVE_044 (single authority) for the C-004 check.
- **Tactics**: review-intent-and-risk-first (HIGH items first), code-review-incremental (per-WP), five-paradigm (falsify, trace via `--setup-plan`, matrix of mutations).
- **Charter SO#4** (red-first, never retry-to-green) and **SO#5** (gate non-vacuity) set the bar for "RED on base".

## Findings

[HIGH] research §F3 / WP10 red-first — "`test_context_markers_use_no_private_patch_targets` RED: 4 private targets" — **FALSE**.
- The AST sweep of `tests/charter/test_context_parity.py` found 6 `patch(` sites over 4 distinct targets.
- Only `charter.activation.profile_resolution._activation_aware_profile_map` has a `_`-prefixed segment: 2 sites, 1 distinct target.
- `charter.activation.catalog.resolve_doctrine_root`, `charter.activation.catalog.built_in_dir` and `charter.offering.directives.repository.built_in_dir` have no `_` segment. A "converted" test could keep patching them and pass.
- `_reset_agent_profile_cache()` (L189, L251) is a private *call*, not a patch, so the predicate does not see it.
- **Recommendation:**
  - Predicate = zero `patch`/`patch.object`/`monkeypatch.setattr` targets under `charter.|kernel.|specify_cli.|runtime.`, plus zero imports or calls of `_`-prefixed src names.
  - RED on base = 6 patch sites + 2 private calls. State that number.

[HIGH] research §E2 / erratum 3 / WP07 FR-009 — "`untrusted_path_audit/inventory.md:76` refers to its own directory" — **FALSE**.
- L76 literally cites `tests/architectural/surface_resolution_audit/inventory.md` ("see … for the sibling WP01-census row"). After WP07 that reference dangles.
- The tracer's FR-009 token regex (`…|_parse_inventory_rows|…|audited-surfaces|…`) also has permanent live hits in sibling surfaces WP07 does not own:
  - `untrusted_path_audit/audit.py:407,640`
  - `test_untrusted_path_containment.py:31,72,150,240`
  - `tool_artifact_enrolment/test_enrolment_inventory.py:147,236`
  - `untrusted_path_audit/inventory.md:210`
- So "0 live hits after" is unattainable as written.
- **Recommendation:**
  - Add `untrusted_path_audit/inventory.md:76` to WP07's edits.
  - Narrow the search to path-qualified tokens: `surface_resolution_audit`, `rekey_inventory`, `write_candidate_classification`, and `surface_resolution_audit/(inventory|audited-surfaces|RULESET)`.

[MEDIUM] §F2 / WP09 red-first — "relocated `TestTransitionMatrixInvariants` driven RED by recorded mutations; not currently duplicated" — **PARTIAL**.
- The relocated tests are GREEN on base (they already pass in test_parity.py), so there is no RED-on-base.
- The mutations do not discriminate. A pytest plugin patching the WPState `allowed_targets` gave these results:

  | mutation | surviving tests in test_transitions.py that go RED |
  |---|---|
  | `done→planned` | 5: `test_allowed_transitions_count`, `test_illegal_transition_rejected[done-planned]`, `test_validate_transition_matches_baseline`, `test_collapsed_matrix_catches_planted_row`, `test_terminal_exit_without_force_is_illegal[done]` |
  | `claimed→claimed` | 3 |

- `ALLOWED_TRANSITIONS` is a non-authoritative derived projection (transitions.py:9-13).
- **Recommendation:** treat `test_no_self_transitions_in_matrix` and `test_terminal_lanes_have_no_outbound_transitions` as retire-as-duplicate with those named survivors, and apply D-OP-4 (tracer evidence) to WP09. Do not claim C-001 RED.

[MEDIUM] §F2 / WP09 NFR-006 — "every test_parity.py test has a verdict" — **FALSE**.
- These two tests have no disposition in the retire, relocate or duplicate tables:
  - `TestReducerDeterminism::test_reduce_then_serialize_roundtrip` (L407)
  - `TestFullEventLogParity::test_realistic_log_identical_across_runs` (L660)
- **Recommendation:** add a row for each, with a survivor or a relocation.

[MEDIUM] §B5 — "drift-test params destructive 17, mutation 23, overwrite 2; total 49 files" — **FALSE**.
- Distinct files from the live allowlists and `census-rekey-map.csv`: destructive **15**, mutation **21**, overwrite 2.
- Adding join 3, kernel 1 and os-detect 3 gives **45**.
- **Recommendation:** derive the counts in the test and never hard-code them; fix the numbers in research, the tasks and the WP prompts.

[LOW] §F5 / WP11 — "oracle module keeps 10 nodes" — **FALSE**; the rest is **WITNESSED**.
- `--collect-only` shows 24 nodes. The oracle module keeps **8** (6 `ledger_results` consumers + `test_hollow_ledger_fails_coverage_floor` + `test_reason_normalizer_meta_test`). The new module gets 16 nodes / 15 functions (14 P0 nodes + 2 fail-closed).
- `--setup-plan`: `ledger_results` (M) is set up only for the 6 oracle nodes. No P0 or fail-closed node uses it.
- The AST closure of the 15 functions uses no `_bridge_oracle` names. The helper set matches the design, plus `_assert_reason_has_runnable_recovery_command` (L1853, inside the P0 block).
- The 16 nodes ran in **48.49 s** (NFR-004 < 60 s; headroom ~11 s).
- **Recommendations:**
  - Compare node IDs by `func[param]`, because the module path changes.
  - Note that the scaffold's `advance_to_step` imports the private `runtime.next._internal_runtime.engine._read_snapshot` (L294).

[LOW] D-OP-5 / WP10 Windows — "defer if the Windows-symlink check fails" — **PARTIAL**.
- `ci-windows.yml` runs only `-m windows_ci` tests behind a fixed paths-filter. `test_context_parity.py` is `pytestmark=[fast]`, so the Windows lane never executes it and the condition is untestable in CI.
- A full `copytree` mirror costs **0.05 s** (513 files, 3.7 MB).
- **Recommendation:** always copy and drop the symlinks. This removes the Windows dependency entirely.
- Cache-order is **WITNESSED** safe. There were 3 renders per process, in both orders, in both symlink and copy modes:
  - empty-directives mirror → `missing_artifact`;
  - real-directives mirror → `typo_suspected` (DIRECTIVE_049);
  - no leakage between renders.
- `get_built_in_pack_root` is uncached. `builtin_mission_type_ids()` is a process-wide `functools.cache`, but it is benign because the missions are mirrored unchanged.

[LOW] §D2 / WP06 lowering mutation — "special-case `known_ungated_files` (live 0)" — **PARTIAL**.
- `category_3_external_cli_entrypoints` is also live 0 (yaml 2).
- Setting live − 1 = −1 still reds the growth arm, so this is harmless but should be stated.
- Unlowered slack also exists: `category_2` is 3 in YAML vs 2 live, and `category_7` is 5 vs 4. Record these as an NFR-003 shrink opportunity, not a requirement.

[INFO] §C2 C-004 unification — "behaviour-preserving on HEAD" — **WITNESSED** for all 80 census sites and 10 dirty-predicate sites. `_ratchet_keys.enclosing_qualname` is a re-export of `anchoring.enclosing_qualname`.
- Latent divergence: for class-body statements the census version returns `<module>` where anchoring returns `K`, and for a nested class in a method it returns `K.m` where anchoring returns `K.m.Inner`. No live site is affected.

[INFO] §A2 ban widening — "94 findings, 1.4 s, no false positives, nothing missed" — **WITNESSED**.
- Findings: 6/2/22/56/2 plus 3/2/1 txt = 94. Wall time is 1.7 s, including interpreter startup. The scan covers 263 py files and 20 txt files.
- Residual sweep:
  - applying the widened predicates to **every AST node** (not only seeds) found only planted test fixtures outside the 94;
  - there are no Name/`Path(...)` tuples outside the join list, no tuple-keyed dicts, no f-string pins and no line-kwarg seeds;
  - there are 0 pins in `tests/**` outside `tests/architectural`.
- YAML `line:` fields are type-checked only and never part of a key (`test_inline_meta_read_gate.py:138`, `test_charter_path_literal_authority.py:219`): inline_meta 7, charter_path_literal 50, home_pin_anchor 40.
- Prose residue is left unflagged by design: 71 `TOTAL_RESULT_EVIDENCE`/`DEFERRED` strings (`"moments.py:91; …"`), and a destructive rationale citing `ordering.py:329`. The CSV's `rationale_sha256` equality will freeze the latter.

[INFO] D-OP-1 — **WITNESSED**.
- Exactly 3 of 80 entries need `occurrence=1` (`lanes/merge.py::_merge_branch_into` merge_abort; `m_0_10_8…apply` `wt_memory`/`wt_agents . unlink ( )`). There are 0 duplicate `CensusKey`s.
- 8 of the 22 destructive keys have argv-only token lines (`[ , , ] ,`), so argument swaps inside the same op are blessed silently. This is the accepted weakness; keep it in the tracer.

[INFO] Other claims — all **WITNESSED**:

| claim | evidence |
|---|---|
| WP02: 2 dead join entries | `kernel/paths.py:88`, `runtime/home.py:79` |
| All 12 B2–B4 descriptors resolve | each resolves uniquely via `resolve_descriptor` |
| WP06: exactly 4 non-enforcing leaves | `category_1` is derived, `skip_marker_blocks` is advisory, `unassigned_entries` and `masking_suppressions` are unread; 19 leaves are enforced |
| WP08: rich/typer ban inspects 0 files on base | `src/specify_cli/next` is absent; live `_internal_runtime` has 16 files; the only rich import under `runtime/next` is `runtime_bridge_retrospective.py:158`, which is out of scope |
| WP07: `audit.py` exits 1 on base | ghost rows |
| FR-012 reference list | complete |
| `destructive_op_allowlist: 56` preserved | its only registration path is `len(test_mutation_ownership_routing._ALLOWLIST)` at test_ratchet_baselines.py:465-469/627-631 (live 56 == 56). Nothing else in src or tests reads it. The re-key keeps 56 distinct keys. |

## Verdict
**PASS WITH FIXES.** The ban-widening, census re-key, baseline-leaf and bridge-split designs hold under live probes. Two HIGH items should be corrected before `/spec-kitty.tasks`:
1. WP10's private-patch predicate is too weak, and the RED count of 4 is wrong.
2. WP07 misses a live dangling reference, and its 0-hit acceptance cannot be met.

Also fold in the count errata: 45 files, 8 oracle nodes, and the WP09 dispositions and red-first posture.
