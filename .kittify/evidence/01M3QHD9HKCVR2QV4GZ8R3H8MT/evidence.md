# #5353 slice 2 (tests/charter): umbrella ledger

PR: https://github.com/spec-kitty/spec-kitty/pull/5416. Totals: 31 KEEP, 21 FIX, 17 RETIRE, 0 SPLIT (69 unique tests; 72 high-signal hits in 38 files).

# Slice 2 (#5353, tests/charter): implementation plan and ownership

Verdicts: `verdicts-A.md` (items prefixed **A#**) and `verdicts-B.md` (items prefixed **B#**).

**Totals over 69 unique tests:** 31 KEEP, 21 FIX, 17 RETIRE, 0 SPLIT. A#3 and B#7 are the same test; both verdicts are RETIRE.

## Orchestrator rulings (they override the verdict files where they conflict)

1. **Submodule root resolution (B#9): product bug, fix it.**
   - The test name and docstring say "resolves to the submodule's own working tree". #2011 ruled that ascending to the superproject is wrong, and #2624 names submodule boundaries as stops.
   - Intended result: the submodule working tree (`<super>/submod`, what `git rev-parse --show-toplevel` gives there). A linked worktree of a submodule resolves to the submodule's MAIN working tree, following the "canonical root = main checkout" contract.
   - Leave the archived `kitty-specs/**` contract untouched (it is an immutable snapshot). Correct the `src` docstring instead.
2. **Action-token regression (A bug 1): product bug, fix it.**
   - `ALLOWED_ACTIONS` plus the `_activation_render.py` labels return to the canonical short tokens `charter.interview` / `charter.context` (data-model §7; matches the sibling `charter.generate`).
   - These are sed collateral from e72f8b8a0b (#3664). No persisted YAML or doc uses the long forms.
   - Do not add a long-form alias (single canonical authority).
   - `test_allowed_actions_is_the_canonical_10_token_set` gets re-pinned red-first.
   - `tests/architectural/test_no_stale_charter_path_literals.py` only polices `patch()` targets and file paths, so the dotted tokens are fine there. Run that gate file anyway.
3. **`anti_pattern` alias (A bug 2): deferred, needs an operator ruling.** The orchestrator files an issue. A#18's oracle excludes `anti_pattern`, with a comment that cites the issue.
4. **`load_validated_graph` docstring (B bug 2):** correct `Raises:` to `DRGValidationError`. This is a docstring-only src edit, owned by O.

## Ownership (committed edits). The two sets are disjoint.

### Implementer O (Opus): owns ALL committed `src/` edits

| Items | Test files |
|---|---|
| B#9 (+ product fix `src/charter/resolution.py`, possibly `src/kernel/git_topology.py`) | `tests/charter/test_canonical_root_resolution.py` |
| A bug 1 product fix, A#18 FIX, A#19 RETIRE (`src/charter/activation/activations.py`, `_activation_render.py`) | `tests/charter/test_activations.py` |
| A#40 FIX, B#25 FIX | `tests/charter/test_resolver_tier_axis_via_factory.py` |
| A#2 FIX | `tests/charter/synthesizer/test_adapter_contract.py` |
| B#6 FIX, B#7=A#3 RETIRE, B#8 FIX (make TestPresentFixture hermetic: never skip; the fixture is written by the test or re-keyed) | `tests/charter/synthesizer/test_fixture_adapter.py` (+ fixture files under `tests/charter/fixtures/synthesizer/` if re-keyed) |
| B#23 FIX | `tests/charter/test_parser.py` |
| B#1 FIX | `tests/charter/evidence/test_orchestrator.py` |
| B bug 2 docstring | `src/charter/activation/_drg_helpers.py` (docstring only) |

### Implementer M (Sonnet): test-only, mechanical

| Items | Test files |
|---|---|
| B#2–5 FIX (`dataclasses.FrozenInstanceError`) | `tests/charter/synthesizer/test_evidence.py` |
| B#18 FIX (`DRGValidationError`, `match=`) | `tests/charter/test_merged_graph_on_live_path.py` |
| B#20–22 FIX (`ValueError`, `match=`) | `tests/charter/test_pack_manager.py` |
| B#14, B#15 FIX | `tests/charter/test_generator.py` |
| B#19 RETIRE | `tests/charter/test_mission_type_profiles.py` |
| B#26 RETIRE | `tests/charter/test_schemas_additive_fields.py` |
| B#27 RETIRE | `tests/charter/test_sonar_complexity_a_helpers.py` |
| A#4 RETIRE, A#6 FIX | `tests/charter/synthesizer/test_interview_mapping.py` |
| A#25 FIX, A#26 RETIRE | `tests/charter/test_invocation_context.py` |
| A#8, A#9 RETIRE | `tests/charter/synthesizer/test_orchestrator_synthesize.py` |
| A#31–33 RETIRE | `tests/charter/test_pack_context.py` |
| A#34, A#38 RETIRE | `tests/charter/test_path_conventions_slot.py` |
| A#17 RETIRE | `tests/charter/test_action_sequence_dispatch.py` |
| A#20 RETIRE | `tests/charter/test_builtin_missions_root.py` |
| A#22 RETIRE | `tests/charter/test_context.py` |

### Shared file: `ruff.toml`

Each implementer may edit ONLY the per-file-ignores entries of test files it owns. The baseline is shrink-only: if a change clears a frozen violation, remove that entry in the same commit. Expected: `test_evidence.py` loses B017/PT011, `test_merged_graph_on_live_path.py` PT011, `test_sonar_complexity_a_helpers.py` PT011 if it cleared, and possibly F401 lines. Verify with `tests/architectural/test_ruff_pytest_style_baseline.py`.

Planted breaks may touch any `src/` file temporarily. They are ALWAYS reverted and never committed.

---
# Bundle A verdicts: "can this test ever fail?" (tests/charter, slice 2 of #5353)

Reviewer: reviewer-renata (read-only). Procedure: `test-suite-quality-assessment`. Rubric: DIRECTIVE_041, `test-desiderata-and-boundaries` styleguide, `development-assist-test-cleanup` procedure.

Baseline: every candidate file was run on its own (`uv run --frozen pytest <file> -q`) and is green. One real exception: `test_fixture_adapter.py::TestPresentFixture` **always skips** (see #3 and Deferred D1).

Tier rule used: `src/charter/activation/**`, `src/charter/offering/drg/**` and the cascade are **core**. Other `src/charter/offering/**` modules, config loaders and `specify_cli` preflights are **glue**.

Every planted break below is **proposed only**. The implementer proves it.

## Summary

| # | file::test | verdict | tier | planted break (src path :: function :: mutation) OR covering guard |
|---|---|---|---|---|
| 1 | synthesizer/test_adapter_contract.py::TestProtocolConformance::test_fixture_adapter_isinstance_synthesis_adapter | KEEP | core | `activation/synthesizer/fixture_adapter.py :: FixtureAdapter.generate :: rename to generate_one` -> runtime Protocol check fails |
| 2 | synthesizer/test_adapter_contract.py::TestProtocolConformance::test_fixture_adapter_has_optional_batch | FIX | core | `activation/synthesizer/fixture_adapter.py :: FixtureAdapter.generate_batch :: return [self.generate(r) for r in requests if self._fixture_path(r).exists()]` (silent partial batch) |
| 3 | synthesizer/test_fixture_adapter.py::TestPresentFixture::test_present_fixture_body_is_dict | RETIRE | core | guard `synthesizer/test_orchestrator_synthesize.py::TestRunAllTupleCount::test_run_all_tuples_are_body_provenance_pairs`; break `fixture_adapter.py :: FixtureAdapter.generate :: body=str(body)` |
| 4 | synthesizer/test_interview_mapping.py::TestInterviewMappingsTable::test_all_entries_are_interview_section_mapping | RETIRE | core | guard `TestInterviewMappingsTable::test_section_labels_are_nonempty_strings`; break `activation/synthesizer/interview_mapping.py :: INTERVIEW_MAPPINGS :: append bare ("stray", ("directive",))` |
| 5 | synthesizer/test_interview_mapping.py::TestR9ShippedOnlyDrgInvariant::test_r9_default_is_shipped_only | KEEP | core | `interview_mapping.py :: resolve_sections :: _use_built_in_only_drg: bool = False` -> default call raises |
| 6 | synthesizer/test_interview_mapping.py::TestResolveFullSnapshot::test_context_is_dict | FIX | core | `interview_mapping.py :: _append_table_driven_results :: "kinds": list(mapping.kinds) -> "kinds": []` |
| 7 | synthesizer/test_manifest.py::test_manifest_v2_schema_accepts_runtime_model_dump | KEEP | core | `activation/synthesizer/manifest.py :: SynthesisManifest :: add serialized field run_label: str = ""` -> `additionalProperties: false` rejects |
| 8 | synthesizer/test_orchestrator_synthesize.py::TestRunAllTupleCount::test_run_all_returns_list | RETIRE | core | guard `TestRunAllTupleCount::test_run_all_expected_count` (+ mypy on the `-> list[...]` annotation); break `synthesize_pipeline.py :: run_all :: return results[:-1]` |
| 9 | synthesizer/test_orchestrator_synthesize.py::TestSynthesizeEntryPoint::test_synthesize_returns_synthesis_result | RETIRE | core | guard `TestSynthesizeEntryPoint::test_synthesize_result_has_inputs_hash`; break `activation/synthesizer/orchestrator.py :: synthesize :: return delta` (not the SynthesisResult) |
| 10 | synthesizer/test_validation_gate.py::TestAcceptValidOverlay::test_empty_overlay_with_empty_shipped | KEEP | core | `activation/synthesizer/validation_gate.py :: validate :: if not project_overlay.nodes: raise ProjectDRGValidationError(...)` |
| 11 | synthesizer/test_validation_gate.py::TestAcceptValidOverlay::test_project_node_with_shipped_node | KEEP | core | `validation_gate.py :: validate :: merged = project_overlay` (skip merge_layers) -> cross-layer edge dangles |
| 12 | synthesizer/test_validation_gate.py::TestAcceptValidOverlay::test_multiple_project_nodes_no_edges | KEEP | core | `offering/drg/validator.py :: validate_graph :: report edgeless nodes as orphan errors` |
| 13 | synthesizer/test_validation_gate.py::TestOrgAwareBaseLayer::test_org_referencing_edge_passes_with_org_drg | KEEP | core | `validation_gate.py :: validate :: base_layer = built_in_drg` (ignore org_drg) |
| 14 | synthesizer/test_write_pipeline.py::test_gate_skips_language_scoped_artifact | KEEP | core | `activation/synthesizer/write_pipeline.py :: _is_generic_scoped :: return True` |
| 15 | synthesizer/test_write_pipeline.py::test_gate_passes_on_neutral_generic_content | KEEP | core | `write_pipeline.py :: _run_neutrality_gate :: if lint_result.hits: -> if lint_result is not None:` |
| 16 | synthesizer/test_write_pipeline.py::test_gate_passes_on_empty_results | KEEP | core | `write_pipeline.py :: _run_neutrality_gate :: prepend if not results: raise NeutralityGateViolation(...)` |
| 17 | test_action_sequence_dispatch.py::TestResolveActionSequence::test_result_is_a_list | RETIRE | core | guard `TestResolveActionSequence::test_software_dev_returns_builtin_sequence`; break `activation/mission_type_profiles.py :: _resolve_action_slot :: return tuple(action_sequence)` |
| 18 | test_activations.py::test_valid_artifact_kinds_are_accepted | FIX | core | `activation/activations.py :: _SINGULAR_TO_PLURAL_KIND :: {k: v for k, v in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.items() if k != "tactic"}` |
| 19 | test_activations.py::test_allowed_mission_types_is_a_frozenset | RETIRE | core | guards `test_activations.py::test_resolver_wildcard_tokens_match_every_context`, `::test_invalid_mission_type_is_rejected`, `test_interview_mapping_mission_alias.py::test_synthetic_mission_type_is_picked_up_by_both_rosters` (+ mypy); break `activations.py :: ALLOWED_MISSION_TYPES :: drop \| {"any", "generic"}` |
| 20 | test_builtin_missions_root.py::test_builtin_missions_root_matches_constructor_default | RETIRE | core | guard `test_mission_type_profile_override.py::TestShippedProfilesHonourInvariant::test_all_shipped_profiles_have_id_equal_to_mission_type`; break `activation/mission_type_profile_repository.py :: MissionTypeProfileRepository._default_built_in_dir :: return builtin_missions_root() / "nope"` |
| 21 | test_call_site_propagation.py::test_unsafe_bypass_propagates_through_compiler | KEEP | core | `activation/compiler.py :: _load_yaml_asset :: load_charter_file(path, unsafe=unsafe) -> load_charter_file(path)` -> raises |
| 22 | test_context.py::TestBuildContextV2::test_returns_charter_context_result | RETIRE | core | guard `TestBuildContextV2::test_mode_is_bootstrap_on_first_load` (+ `test_action_normalized`); break `activation/context.py :: build_charter_context :: return result.text` |
| 23 | test_integration.py::TestPerformance::test_load_governance_config_performance | KEEP | glue | the `@pytest.mark.timeout(2)` is the oracle; break: insert a full DRG load (`load_validated_graph()`) or `time.sleep(3)` into `load_governance_config` |
| 24 | test_invocation_context.py::TestContextPreconditionError::test_is_runtime_error | KEEP | core | `activation/invocation_context.py :: class ContextPreconditionError(RuntimeError) -> (Exception)` |
| 25 | test_invocation_context.py::TestProjectContextGuards::test_require_pack_context_returns_value | FIX | core | `invocation_context.py :: ProjectContext.require_pack_context :: return self.pack_context -> return PackContext.from_config(self.require_repo_root())` (re-reads config instead of returning the stored snapshot) |
| 26 | test_invocation_context.py::TestBuildOperationalContext::test_returns_operational_context_instance | RETIRE | core | guard `test_operational_context.py::test_explicit_operational_context_round_trip`; break `invocation_context.py :: build_operational_context :: return OperationalContext()` |
| 27 | test_kind_vocabulary.py::test_charter_kind_tokens_artifact_entries_all_resolve | KEEP | glue | `offering/artifact_kinds.py :: CHARTER_KIND_TOKENS :: literal typo "glossary-packs"` -> `from_operator_token` raises ValueError |
| 28 | test_mission_type_profile_override.py::TestProjectOverrideRidesTheOverlay::test_shadow_emits_collision_warning | KEEP | core | scanner false positive (`pytest.warns(..., match=)` is the assert); break `offering/base.py :: _load :: drop the DoctrineLayerCollisionWarning warn()` |
| 29 | test_mission_type_profiles.py::TestUnknownMissionTypeError::test_is_value_error_subclass | KEEP | core | `activation/mission_type_profiles.py :: class UnknownMissionTypeError(ValueError) -> (LookupError)` |
| 30 | test_org_drg_loader.py::TestOrgDRGFragmentSchema::test_all_8_canonical_kinds_validate | KEEP | core | `offering/drg/org_pack_loader.py :: _ORG_DRG_KIND_ALIASES :: remove "paradigms"` -> model_validate raises |
| 31 | test_pack_context.py::test_pack_roots_is_tuple | RETIRE | core | guard `test_pack_context.py::test_pack_context_is_hashable`; break `activation/pack_context.py :: PackContext.from_config :: pack_roots = [builtin_root, *org_pack_roots]` |
| 32 | test_pack_context.py::test_activated_kinds_is_frozenset | RETIRE | core | guard `test_pack_context.py::test_pack_context_is_hashable`; break `pack_context.py :: _read_activated_kinds :: return set(_BUILTIN_ARTIFACT_KINDS) if activated is None else activated` |
| 33 | test_pack_context.py::test_activated_mission_types_is_frozenset | RETIRE | core | guard `test_pack_context.py::test_pack_context_is_hashable`; break `pack_context.py :: _read_list_key :: return set(str(item) for item in raw)` |
| 34 | test_path_conventions_slot.py::TestValidPathKeysCanonicalHome::test_valid_path_keys_is_a_frozenset | RETIRE | glue | guard `TestValidPathKeysCanonicalHome::test_valid_path_keys_matches_historical_specify_cli_value` (+ mypy on the `frozenset[str]` annotation); break `offering/missions/models.py :: VALID_PATH_KEYS :: drop "data"` |
| 35 | test_path_conventions_slot.py::TestValidatePathConventionsFunction::test_none_is_a_no_op | KEEP | glue | `offering/missions/models.py :: validate_path_conventions :: if path_conventions is None: raise ValueError(...)` |
| 36 | test_path_conventions_slot.py::TestValidatePathConventionsFunction::test_empty_mapping_is_a_no_op | KEEP | glue | `models.py :: validate_path_conventions :: if path_conventions == {}: raise ValueError("empty")` |
| 37 | test_path_conventions_slot.py::TestValidatePathConventionsFunction::test_each_valid_key_accepted_individually | KEEP | glue | `models.py :: validate_path_conventions :: subtract a stale local key set lacking "data"` -> red on `[data]` |
| 38 | test_path_conventions_slot.py::TestValidatePathConventionsFunction::test_all_valid_keys_together_accepted | RETIRE | glue | guards #37 (parametrized) and `TestMissionTypePathConventionsField::test_all_valid_keys_accepted_together`; break `models.py :: validate_path_conventions :: unknown = sorted(set(pc) - (VALID_PATH_KEYS - {"data"}))` |
| 39 | test_references_missing_failclosed.py::test_raise_if_bundle_incomplete_is_noop_when_bundle_complete | KEEP | glue | `specify_cli/cli/commands/charter/_synthesis.py :: _raise_if_bundle_incomplete :: first_missing_bundle_file(repo_root / ".kittify")` -> raises |
| 40 | test_resolver_tier_axis_via_factory.py::test_tier_axis_methods_are_static_because_the_axis_is_ungated | FIX | core | `activation/resolver.py :: DoctrineService.resolve_content_asset (still @staticmethod) :: if "templates" not in PackContext.from_config(project_dir).activated_kinds: raise FileNotFoundError(name)` |
| 41 | test_topic_resolver_node_kinds.py::test_every_nodekind_value_resolves_at_gate | KEEP | core | `activation/synthesizer/topic_resolver.py :: _DRG_NODE_KINDS :: ... - {"glossary_pack"}` -> None for that param |

---

## Per-test reasoning

### 1. `test_fixture_adapter_isinstance_synthesis_adapter`: KEEP (core)
`SynthesisAdapter` is `@runtime_checkable`, so `isinstance` performs a real structural check. It inspects `id`, `version` and `generate` on the instance, which is the whole FR-003 conformance contract. The test goes red when the Protocol gains a member that FixtureAdapter lacks, or when FixtureAdapter loses one. The planted rename of `generate` turns the check False.

The sibling `test_fixture_adapter_has_required_attributes` repeats the same thing with a hand-listed subset. It is the weaker of the two and a light consolidation candidate, but it is outside the bundle.

### 2. `test_fixture_adapter_has_optional_batch`: FIX (core)
- **Weakness.** `hasattr(adapter, "generate_batch")` pins presence only. Presence has no behavioural consequence: `synthesize_pipeline._dispatch_batch` falls back to sequential `generate` when the method is absent, and the output is identical. The actual contract lives in the docstring of `BatchCapableSynthesisAdapter.generate_batch` (`adapter.py`): the result must have the same length as the input, be element-aligned, and raise rather than return a partial sequence. Nothing asserts that contract directly.
- **Stronger oracle.** Use a tmp `fixture_root`. Write two fixture YAMLs at the paths computed with the public `compute_inputs_hash` + `short_hash` for two distinct requests A and B.
  - (a) `adapter.generate_batch([A, B])` must equal `[adapter.generate(A), adapter.generate(B)]`. Compare `.body` and `.notes` element-wise; the notes carry the per-request hash, so a misalignment shows.
  - (b) `generate_batch([A, C])`, where C has no fixture, must raise `FixtureAdapterMissingError` whose `expected_path` names C.
- **Planted break.** `fixture_adapter.py :: FixtureAdapter.generate_batch :: return [self.generate(r) for r in requests if self._fixture_path(r).exists()]` is a "tolerant batch" that silently drops C.
  - The current test stays green, because the attribute still exists.
  - The fixed test's (b) goes red, because nothing is raised.
  - The pipeline's `zip(..., strict=True)` would still catch the resulting length mismatch downstream, but it would surface as a bare `ValueError` instead of the operator-actionable `FixtureAdapterMissingError`.

### 3. `test_present_fixture_body_is_dict`: RETIRE (core)
- **This test never runs.** It always hits `pytest.skip("Fixture not present")`. `_make_request` now hashes to `fd8f2b3c6906`, but the only fixtures on disk are `d6250694fe91` and `eb35535fb02c` (verified with `-rs`). Its assertion is also a strict subset of the sibling `test_present_fixture_returns_adapter_output`, which skips for the same reason.
- **Covering guard (live).** `tests/charter/synthesizer/test_orchestrator_synthesize.py::TestRunAllTupleCount::test_run_all_tuples_are_body_provenance_pairs` asserts `isinstance(body, Mapping)` for every body. Those bodies come from `FixtureAdapter.generate`, which loads real on-disk fixtures, and the test passes today.
- **Planted break.** `fixture_adapter.py :: FixtureAdapter.generate :: AdapterOutput(body=str(body), ...)` turns the guard red.
- **Follow-up.** The masked skip of the whole class is filed as Deferred D1.

### 4. `test_all_entries_are_interview_section_mapping`: RETIRE (core)
- **Why retire.** The element type is a static contract: `INTERVIEW_MAPPINGS: tuple[InterviewSectionMapping, ...]` is checked by mypy. Behaviourally, every sibling in the class reads `.section_label` or `.kinds` off each entry.
- **Covering guard.** `TestInterviewMappingsTable::test_section_labels_are_nonempty_strings`.
- **Planted break.** Append a bare tuple `("stray", ("directive",))` to `INTERVIEW_MAPPINGS`. The guard raises `AttributeError: 'tuple' object has no attribute 'section_label'`, and mypy rejects it as well.

### 5. `test_r9_default_is_shipped_only`: KEEP (core)
The test's real oracle is "the default call does not raise". The R-9 invariant is implemented purely as the sentinel default `_use_built_in_only_drg=True` plus the `ValueError` guard. Flipping the default to `False` makes the plain call raise, so the test goes red. The trailing `isinstance(result, list)` is only a formality; the implementer may drop it. The refusal branch is pinned by `test_r9_shipped_only_drg_false_raises`.

### 6. `test_context_is_dict`: FIX (core)
- **Weakness.** `isinstance(ctx, dict)` holds for any dict. The consumed contract is the shape of the context: `targets.py:271-272` reads `answer_context.get("kinds", [])` and `.get("source_section")`. Nothing in `test_interview_mapping.py` asserts `kinds` or `source_section`; only `["answer"]` is checked, at lines 435 and 495.
- **Stronger oracle.** Use `contexts = dict(resolve_sections({"testing_philosophy": "tdd"}))` and assert:
  `contexts["testing_philosophy"] == {"answer": "tdd", "kinds": ["tactic", "styleguide"], "source_section": "testing_philosophy", "answer_source": "testing_philosophy"}`.
  Write the kinds as literals. Do not read them back from `INTERVIEW_MAPPINGS`, because that would be a self-constructed oracle.
- **Planted break.** `interview_mapping.py :: _append_table_driven_results :: "kinds": list(mapping.kinds) -> "kinds": []`.
  - The current test stays green, because the context is still a dict.
  - The fixed test goes red.
  - The run_all count test would also go red downstream, but that happens only indirectly, and far from the cause.

### 7. `test_manifest_v2_schema_accepts_runtime_model_dump`: KEEP (core)
This is a scanner false positive. `jsonschema.Draft202012Validator(schema).validate(dumped)` raises `ValidationError` on any mismatch. The schema declares `additionalProperties: false` at both the top level and the artifact level, and lists `required:` fields. Adding a new serialized field to `SynthesisManifest`, or renaming a required one, turns the test red.

Note that the test pops `bundle_content_hash` before validating. This is a documented, deliberate narrowing to the v2 shape. The oracle file lives in `kitty-specs/`; see Deferred D2.

### 8. `test_run_all_returns_list`: RETIRE (core)
- **Why retire.** The type half is static: `run_all(...) -> list[tuple[Mapping, ProvenanceEntry]]` runs under `strict = true` mypy, so `return tuple(results)` is a `[return-value]` error. The behavioural half, one pair per target, is pinned more precisely elsewhere.
- **Covering guard.** `TestRunAllTupleCount::test_run_all_expected_count`, which asserts `len == 7`.
- **Planted break.** `synthesize_pipeline.py :: run_all :: return results[:-1]` turns the guard red (6 != 7). The current test stays green.

### 9. `test_synthesize_returns_synthesis_result`: RETIRE (core)
- **Covering guards.** `TestSynthesizeEntryPoint::test_synthesize_result_has_inputs_hash` and `::test_synthesize_result_has_target_kind` use the same harness and read attributes that only exist on `SynthesisResult`. The first also asserts a hex `inputs_hash`.
- **Planted break.** In `orchestrator.py :: synthesize`, return the `ReconciliationDelta` instead of the `SynthesisResult`. Both guards then go red with `AttributeError`.

### 10–13. `TestAcceptValidOverlay` ×3 and `test_org_referencing_edge_passes_with_org_drg`: KEEP (core)
All four are scanner false positives. `validate()` has a `-> None / raises ProjectDRGValidationError` contract, so these tests are the **accept half** (no false rejection) of an accept/reject pair whose reject half is pinned by the sibling classes (dangling source/target, duplicate edge, cycle). Each can go red:

- **#10:** raising on an empty overlay, i.e. treating it like a load failure.
- **#11:** skipping `merge_layers`, so `directive:PROJECT_001 -> directive:DIRECTIVE_003` dangles.
- **#12:** a validator that reports edgeless nodes as orphans.
- **#13 (core, #4121):** dropping the `org_drg` substitution (`base_layer = built_in_drg`), so the org-pack reference dangles. This test is the positive twin of `test_org_referencing_edge_without_org_drg_is_dangling`. Both are needed; neither is redundant.

### 14–16. Neutrality gate no-raise tests: KEEP (core)
`_run_neutrality_gate` raises `NeutralityGateViolation` on failure. The sibling `test_gate_fires_on_biased_generic_content` proves two assumptions these tests depend on: the helper's staged path resolves for `tactic` artifacts, and the term `pytest` is banned. Without that, the silent `if not staged_path.exists(): continue` would make all three vacuous.

- **#14:** if `_is_generic_scoped` returns True, "Use pytest…" is linted and raises. Low-level scoping is also pinned in `test_phase3_integration.py::test_phase3_is_generic_scoped_logic`.
- **#15:** pins the false-positive side, so any over-triggering goes red.
- **#16:** low value but not inert. It pins "zero results is a no-op" against a future "no targets" precondition.
- **Suggested improvement (not required).** In #14 and #15, add an Assumption-check (Quadruple-A) that `stage.path_for_content("tactic", ...)` exists before calling the gate. The no-raise tests would then fail loudly if the staged-path naming ever diverged from the gate's.

### 17. `test_result_is_a_list`: RETIRE (core)
- **Why retire.** The mock's `action_sequence` is already a list, so the test cannot distinguish coercion from pass-through.
- **Covering guard.** `TestResolveActionSequence::test_software_dev_returns_builtin_sequence` asserts `result == expected`, with `expected` a list. Because `tuple == list` is False in Python, that guard pins the exact same type contract.
- **Planted break.** `mission_type_profiles.py :: _resolve_action_slot :: return tuple(action_sequence)` turns the guard red.
- The harness itself is over-mocked; see Deferred D4.

### 18. `test_valid_artifact_kinds_are_accepted`: FIX (core)
- **Weakness.** The docstring promises that "both the eight canonical plural forms AND their singular aliases are accepted". The body feeds only the eight hand-listed plurals and asserts nothing about the result. Singular→plural normalisation is covered for `styleguide` only, by `test_singular_artifact_kind_is_accepted_and_normalised`. The list also omits `templates`, `assets` and `glossary_packs`, which `_ALLOWED_KINDS` accepts.
- **Stronger oracle.** Parametrize over a **literal** table of `(input, expected_normalised)` pairs:
  - the 11 accepted plurals, each mapping to itself;
  - the singular aliases `directive`, `tactic`, `styleguide`, `toolguide`, `paradigm`, `procedure`, `agent_profile`, `mission_step_contract` and `glossary_pack`, each mapping to its plural.

  Assert `ActivationEntry(..., artifact_kind=inp).artifact_kind == expected`.
  - Do **not** include `anti_pattern` until Suspected Bug 2 is ruled on.
  - Do **not** `xfail` it either (DIRECTIVE_041).
- **Planted break.** `activations.py :: _SINGULAR_TO_PLURAL_KIND = {k: v for k, v in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.items() if k != "tactic"}`.
  - The current test stays green, because it feeds only plurals, which bypass the map.
  - The existing styleguide test stays green.
  - The fixed test goes red on `("tactic", "tactics")`.

### 19. `test_allowed_mission_types_is_a_frozenset`: RETIRE (core)
- **Why retire.** Immutability is enforced statically by the `ALLOWED_MISSION_TYPES: frozenset[str]` annotation, which mypy checks. The behavioural content is fully guarded by three tests:
  - `test_activations.py::test_resolver_wildcard_tokens_match_every_context` pins the wildcards: constructing with `mission_type="any"`/`"generic"` raises if they are missing.
  - `::test_invalid_mission_type_is_rejected` pins closure.
  - `tests/charter/test_interview_mapping_mission_alias.py::test_synthetic_mission_type_is_picked_up_by_both_rosters` pins derivation from the built-in accessor.
- **Planted break.** Drop `| {"any", "generic"}` from `ALLOWED_MISSION_TYPES`. The wildcard guard goes red, while the current test stays green.

### 20. `test_builtin_missions_root_matches_constructor_default`: RETIRE (core)
- **Weakness.** The name promises "matches constructor default", but the only assertion is `repo is not None`.
- **Covering guard.** `tests/charter/test_mission_type_profile_override.py::TestShippedProfilesHonourInvariant::test_all_shipped_profiles_have_id_equal_to_mission_type` default-constructs `MissionTypeProfileRepository()` and asserts that every built-in mission type's profile loads. That is the observable meaning of "the constructor default is the right root".
- **Planted break.** `_default_built_in_dir :: return builtin_missions_root() / "nope"`. Each `repo.get(mt)` returns None and the guard goes red. The current test stays green, unless the base repository raises on a missing dir, in which case both go red and the retirement is still sound.
- The file's other two tests keep the accessor/authority equality.

### 21. `test_unsafe_bypass_propagates_through_compiler`: KEEP (core)
This is a type-only false positive. Without `unsafe` forwarding, `load_charter_file` raises `CharterEncodingError` on the ambiguous bytes, so the test goes red if `_load_yaml_asset` drops `unsafe=unsafe`.

- **Cleanup (non-verdict).** The docstring pins `compiler.py:594`, which is stale; the call is now at about line 1476. The trailing comment refers to "the pytest.raises wrapper above", which does not exist. Strip both. A stronger optional oracle is the `bypass_used=True` provenance, if it can be observed through a public seam.

### 22. `test_returns_charter_context_result`: RETIRE (core)
- **Covering guards.** The same `_call` harness feeds `test_action_normalized` (`result.action`) and `test_mode_is_bootstrap_on_first_load` (`result.mode`, `result.first_load`). These pin the returned object's observable contract.
- **Planted break.** `context.py :: build_charter_context :: return result.text` turns both guards red with `AttributeError`.
- The harness stubs the `assert_valid` gate; see Deferred D3.

### 23. `TestPerformance::test_load_governance_config_performance`: KEEP (glue)
The oracle is `@pytest.mark.timeout(2)`. pytest-timeout is installed and the marker is registered in `pytest.ini`. A regression that makes the loader pull the full DRG, or hang, goes red. The `isinstance(config, GovernanceConfig)` check is only a formality, and the parse correctness is already pinned by `TestLoadersReadCharterYaml::test_load_governance_config_reads_charter_yaml`.

The test is not marked `performance`, which conflicts with the repo convention (#3595) of holding wall-clock budgets out of normal runs; see Deferred D6.

### 24. `test_is_runtime_error`: KEEP (core)
The base class is the whole contract: callers may `except RuntimeError`. Changing the base to `Exception` turns the test red. The name matches the body exactly, so there is nothing vacuous about it.

### 25. `test_require_pack_context_returns_value`: FIX (core)
- **Weakness.** `pc is not None` accepts any non-None object. The sibling `test_require_repo_root_returns_value` asserts equality; this one does not.
- **Stronger oracle.** Build a real `pc = PackContext.from_config(tmp_path)` from the provisioned minimal config, construct `ctx = ProjectContext(pack_context=pc)`, and assert:
  - `ctx.require_pack_context() is pc`;
  - `pc.activated_mission_types == frozenset({"software-dev"})`, as an assumption check.
- **Planted break.** `invocation_context.py :: ProjectContext.require_pack_context :: return PackContext.from_config(self.require_repo_root())`. The break re-reads config instead of returning the stored snapshot. It is type-correct, so mypy does not catch it.
  - With the current `from_repo` setup, the test stays green: a fresh non-None PackContext comes back.
  - The fixed test goes red: `is pc` fails, or `require_repo_root` raises because `repo_root` is None.
  - A cruder copy-paste slip, `return self.repo_root`, would also stay green today, although mypy would flag that one.

### 26. `test_returns_operational_context_instance`: RETIRE (core)
- **Covering guard.** `tests/charter/test_operational_context.py::test_explicit_operational_context_round_trip` asserts that every argument survives assembly.
- **Planted break.** `build_operational_context :: return OperationalContext()` ignores all arguments, so the guard goes red while the current test stays green. The default half is pinned by the sibling `test_all_fields_none`.

### 27. `test_charter_kind_tokens_artifact_entries_all_resolve`: KEEP (glue)
`ArtifactKind.from_operator_token` either returns a member or raises `ValueError`, so the `isinstance` is a formality and the call itself is the oracle. Any token in `CHARTER_KIND_TOKENS` that stops resolving (a typo, or a kind removed from the enum) turns the test red. Mis-mapping is structurally impossible because resolution is by `member.value`.

A cheap optional tightening is `ArtifactKind.from_operator_token(t).operator_token == t`, a round-trip over the whole universe. The file's names and docstrings still say "eight"; see Deferred D8.

### 28. `test_shadow_emits_collision_warning`: KEEP (core)
This is a scanner false positive: `pytest.warns(DoctrineLayerCollisionWarning, match="software-dev")` is an assertion. If the base repository stops warning on shadowing, the test goes red.

### 29. `test_is_value_error_subclass`: KEEP (core)
The docstring states the contract: "MUST remain a ValueError subclass". `callers` catch `ValueError`. Changing the base class turns the test red.

### 30. `test_all_8_canonical_kinds_validate`: KEEP (core)
`OrgDRGFragment.model_validate` raises `pydantic.ValidationError` on an unknown kind, so removing any of these kinds from `_ORG_DRG_KIND_ALIASES` turns the test red. The lockstep with `_ALLOWED_KINDS` is guarded in `tests/doctrine/test_org_pack_augmentation.py`, around line 425.

The name is stale: the universe now also holds `templates`, `assets`, `glossary_packs` and `mission_types`. Rename it by dropping the "8"; see Deferred D8.

### 31–33. `test_pack_roots_is_tuple`, `test_activated_kinds_is_frozenset`, `test_activated_mission_types_is_frozenset`: RETIRE (core)
- **Why the type matters.** Immutability is load-bearing because `PackContext` is a `functools.cache` key: `resolve_layered_mission_types` in `offering/missions/mission_type_repository.py:79` is cached on it. The behavioural guard of that is hashability.
- **Covering guard.** `tests/charter/test_pack_context.py::test_pack_context_is_hashable`. It uses `_MINIMAL_CONFIG`, which exercises both relevant paths:
  - `mission_type_activations` is **present**, so it goes through `_read_list_key`;
  - `activated_kinds` is **absent**, so it takes the `_BUILTIN_ARTIFACT_KINDS` default.

  Dataclass `__hash__` covers every field; none is excluded.
- **Planted breaks** (each turns the guard red with `TypeError: unhashable type`, while the type-only test stays green on the sibling branch):
  - **#31:** `pack_roots = [builtin_root, *org_pack_roots]`.
  - **#32:** `_read_activated_kinds :: return set(_BUILTIN_ARTIFACT_KINDS) if activated is None else activated`.
  - **#33:** `_read_list_key :: return set(...)`.

  mypy also rejects each of them.

### 34. `test_valid_path_keys_is_a_frozenset`: RETIRE (glue)
- **Why retire.** The annotation `VALID_PATH_KEYS: frozenset[str]` enforces the type statically.
- **Covering guard.** `test_valid_path_keys_matches_historical_specify_cli_value` pins the value, and pins it against the `specify_cli` dual-home copy.
- **Planted break.** Dropping `"data"` turns the guard red, while the current test stays green.

### 35–37. `validate_path_conventions` accept tests: KEEP (glue)
`validate_path_conventions` raises `ValueError`, so these are scanner false positives.
- **#35 and #36** pin the docstring's "None / {} is a pure no-op" contract, with direct coverage at the public seam. They overlap with the model-level `test_defaults_to_none` and `test_empty_mapping_accepted`, but go through the function rather than pydantic, so they are kept.
- **#37** pins agreement between the validator's key set and the published `VALID_PATH_KEYS`. A validator that subtracts a stale local copy goes red on the missing key. Its self-referential parametrization is safe, because the value itself is pinned by the historical-value test.

### 38. `test_all_valid_keys_together_accepted`: RETIRE (glue)
- **Why retire.** Validation is a per-key set difference, so any break that reddens "all together" also reddens at least one #37 case. The same contract is also asserted at model level.
- **Covering guards.** #37 and `TestMissionTypePathConventionsField::test_all_valid_keys_accepted_together`.
- **Planted break.** `unknown = sorted(set(pc) - (VALID_PATH_KEYS - {"data"}))` turns `#37[data]` and the model-level guard red.

### 39. `test_raise_if_bundle_incomplete_is_noop_when_bundle_complete`: KEEP (glue)
`_raise_if_bundle_incomplete` raises `TaskCliError`, so this test is the accept half of the sibling refusal test `test_raise_if_bundle_incomplete_raises_task_cli_error`. Checking the wrong root turns it red. The file is misplaced; see Deferred D5.

### 40. `test_tier_axis_methods_are_static_because_the_axis_is_ungated`: FIX (core)
- **Weakness.** The name and docstring promise that the tier axis is *ungated* by activation. The assertion is a structural proxy, `@staticmethod`. The docstring claims the proxy makes gating impossible "without changing the signature", but that claim is false: a static method can still read activation state from disk through `PackContext.from_config(project_dir)`. The existing `test_factory_methods_delegate_to_doctrine_tier_functions` also misses such a gate. It runs with no config, so the default `activated_kinds` includes `templates` and the gate passes.
- **Stronger oracle** (behavioural, against output):
  1. In `project_dir`, write `.kittify/config.yaml` with `activated_kinds: [directives]` (templates deactivated) and `mission_type_activations: [software-dev]`, and place an OVERRIDE-tier content template.
  2. Assert `DoctrineService.resolve_content_asset(_CONTENT_NAME, project_dir, _MISSION) == charter.offering.resolver.resolve_template(_CONTENT_NAME, project_dir, _MISSION)`, with the same tier and path.
  3. Repeat for `resolve_command_asset` and `resolve_mission_definition`.

  The static-method pin may stay as a secondary structural note, but it is not the oracle.
- **Planted break.** In `activation/resolver.py :: DoctrineService.resolve_content_asset`, keeping `@staticmethod`, prepend `if "templates" not in PackContext.from_config(project_dir).activated_kinds: raise FileNotFoundError(name)`.
  - The current test stays green, because the method is still a staticmethod.
  - The delegate test stays green, because it has no config and so all kinds are active.
  - The fixed test goes red with `FileNotFoundError`.

### 41. `test_every_nodekind_value_resolves_at_gate`: KEEP (core)
`is not None` is not a weak check here: `None` is precisely `_resolve_drg_urn`'s "rejected at the membership gate" signal. The test is parametrized over the live `NodeKind`, so removing any value from `_DRG_NODE_KINDS` turns that case red. With `project_artifacts=[]`, the only possible non-None result is `[]`, so tightening to `== []` is equivalent. Doing so would also subsume `test_previously_dropped_kind_resolves_at_gate`; see Deferred D9. The rejection branch is pinned by `synthesizer/test_topic_resolver.py::test_unknown_drg_kind_falls_through_to_unresolved`.

---

## Verdict counts

| Verdict | Count | Items |
|---|---:|---|
| KEEP | 22 | 1, 5, 7, 10, 11, 12, 13, 14, 15, 16, 21, 23, 24, 27, 28, 29, 30, 35, 36, 37, 39, 41 |
| FIX | 5 | 2, 6, 18, 25, 40 |
| RETIRE | 14 | 3, 4, 8, 9, 17, 19, 20, 22, 26, 31, 32, 33, 34, 38 |
| SPLIT-BY-KIND | 0 | — |
| **Total** | **41** | |

Scanner false positives, where the call raises or the check is `pytest.warns`/`timeout`/a gate-sentinel: #5, 7, 10–16, 21, 23, 27, 28, 30, 35–37, 39, 41.

## Suspected product bugs

### Bug 1 (high confidence): the operator action vocabulary was renamed as collateral of the module split

**What changed.** `src/charter/activation/activations.py::ALLOWED_ACTIONS` contains `"charter.activation.interview"` and `"charter.activation.context"`, and `"charter.generate"` is unchanged.

**Evidence:**
- `git show e72f8b8a0b` (#3664, "M2b — physical offering<->activation two-module split") shows the diff `-"charter.interview"` → `+"charter.activation.interview"` and `-"charter.context"` → `+"charter.activation.context"`. This is a module-path rename applied mechanically to **string action tokens**. `charter.generate` was untouched because no `charter.generate` module moved.
- The contract `kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/data-model.md` §7 (around line 203) specifies `"charter.interview", "charter.generate", "charter.context"`.
- `src/charter/activation/_activation_render.py:106-108` was renamed the same way.

**Consequence.**
- An operator entry `activation_context: {action: charter.interview}` is now **rejected**; this was verified at runtime.
- The accepted form looks like a Python module path, and it no longer matches its sibling `charter.generate`.
- `tests/charter/test_activations.py::test_allowed_actions_is_the_canonical_10_token_set` pins the renamed tokens while its failure message claims "data-model.md §7 pins" them. The test is pinning the wrong behaviour.

**Action.** File a product finding. Restoring the tokens needs `ALLOWED_ACTIONS`, the `_activation_render` labels and that test to change together, plus a check for any persisted charter or YAML using the new tokens.

### Bug 2 (medium confidence): `anti_pattern` is advertised as an activation alias but rejected

**What is inconsistent:**
- `offering/artifact_kinds.py::CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL` includes `anti_pattern -> anti_patterns`. The comment says: "10 kinds, including ANTI_PATTERN … C-003/FR-005 require the anti_pattern entry be preserved".
- `PackContext` carries `activated_anti_patterns`.
- `ActivationEntry._validate_kind` rejects both `anti_pattern` and `anti_patterns`, because `_ALLOWED_KINDS` lacks `anti_patterns`.

**The error message contradicts itself** (captured at runtime):

`artifact_kind='anti_pattern' is not a known DoctrineService kind. … Accepted (singular alias): ['agent_profile', 'anti_pattern', …]`

**Action.** Needs a ruling. Either anti-patterns are activation-registry-addressable, in which case add `anti_patterns` to `_ALLOWED_KINDS` and its two lockstep mirrors, or the alias map and the message must not advertise them. CLAUDE.md states that anti_pattern is *not* charter-activatable, which contradicts the `artifact_kinds.py` comment. This blocks the complete oracle for #18.

## Deferred (out of slice)

These are candidates only, not verdicts.

- **D1: masked-defect skip.** `tests/charter/synthesizer/test_fixture_adapter.py::TestPresentFixture` (3 tests) always skips because of fixture-hash drift: it expects `fd8f2b3c6906`, but the disk holds `d6250694fe91` and `eb35535fb02c`. This is "skip keyed on not-present" (DIRECTIVE_041). Re-key or regenerate the fixture, and turn the skip into a hard failure.
- **D2: planning artefacts as oracles.** Two tests read contracts from `kitty-specs/` mission directories:
  - `synthesizer/test_adapter_contract.py::TestContractStructuralEquivalence`, which skips if the file is missing;
  - #7 (`test_manifest.py`).

  Mission artefacts are not a stable home for test oracles. Consider relocating the schemas to `tests/` fixtures or a `contracts/` package path.
- **D3: gate stubbed out of the harness.** `tests/charter/test_context.py::TestBuildContextV2._call` patches `charter.offering.drg.validator.assert_valid`, the validation gate, plus two other seams ("stubbing a new gate out of an old harness").
- **D4: over-mocked harness.** `tests/charter/test_action_sequence_dispatch.py` uses `sys.modules` injection of fake modules; its docstring admits "unavoidable collision". This coupling is implementation-bound.
- **D5: misplaced files.**
  - `tests/charter/test_references_missing_failclosed.py` mostly tests `specify_cli.cli.commands.charter._synthesis` and the `charter synthesize` CLI, and belongs under `tests/specify_cli/cli/…`.
  - `tests/charter/test_resolver_tier_axis_via_factory.py` also spans `specify_cli/runtime/resolver.py`.
- **D6: unmarked wall-clock budget.** `tests/charter/test_integration.py::TestPerformance` (both tests) use `@pytest.mark.timeout(2)` without the `performance` marker, unlike the #3595 convention (`test_validation_gate.py:264/282` and `test_write_pipeline.py:311` are held out).
- **D7: stale comments.**
  - `tests/charter/test_call_site_propagation.py` carries a stale `compiler.py:594` line pin in the #21 docstring and a nonexistent "pytest.raises wrapper above".
  - `tests/charter/test_invocation_context.py::_provision_minimal_config` has a docstring claiming that `from_config` "fail-closes unconditionally" when the key is absent. This contradicts `test_from_repo_without_kittify_returns_empty_mission_types`, whose claim of total construction is the correct one.
- **D8: stale "eight" names.** The universes have grown past eight:
  - `test_kind_vocabulary.py`: the module docstring, `test_from_operator_token_maps_all_eight_artifact_kinds` (lists `template` and omits `glossary-pack`) and `test_charter_kind_tokens_is_eight_artifact_tokens_plus_mission_type` (there are 9 tokens);
  - `test_org_drg_loader.py::test_all_8_canonical_kinds_validate`;
  - the #18 test list.
- **D9: red-first scaffolding.** `test_topic_resolver_node_kinds.py::test_previously_dropped_kind_resolves_at_gate` is a dev-assist leftover that is a strict subset of #41. Tighten #41 to `== []` and retire D9 (development-assist-test-cleanup, RETIRE (ii)).
- **D10: provenance tokens.** WP, T and FR ids appear in names and docstrings across `test_activations.py`, `test_pack_context.py` (T040-x) and `test_builtin_missions_root.py`. Strip them from kept tests.
- **D11: Bug 1 pin.** `tests/charter/test_activations.py::test_allowed_actions_is_the_canonical_10_token_set` pins the Bug 1 tokens. Fix it together with the product.

## Implementation grouping

The work is grouped by `src/` file so that implementers never touch the same file. Planted breaks are *proved* (applied, observed, reverted) by the implementer. The test-file edits are listed alongside.

### Oracle-design work (needs a strong model)

| Group | Items | Test files edited | src files the planted breaks touch |
|---|---|---|---|
| O1: resolver ungated axis | #40 FIX | `tests/charter/test_resolver_tier_axis_via_factory.py` | `src/charter/activation/resolver.py` |
| O2: activation vocabulary | #18 FIX, #19 RETIRE (same file). Coordinate with Bugs 1 and 2; the FIX table excludes `anti_pattern` pending the ruling. | `tests/charter/test_activations.py` | `src/charter/activation/activations.py` |
| O3: batch-adapter contract | #2 FIX, #3 RETIRE (+ optionally D1) | `tests/charter/synthesizer/test_adapter_contract.py`, `tests/charter/synthesizer/test_fixture_adapter.py` | `src/charter/activation/synthesizer/fixture_adapter.py` |

### Mechanical work

| Group | Items | Test files edited | src files the planted breaks touch |
|---|---|---|---|
| M1: interview mapping | #4 RETIRE, #6 FIX (literal-dict oracle given above) | `tests/charter/synthesizer/test_interview_mapping.py` | `src/charter/activation/synthesizer/interview_mapping.py` |
| M2: invocation context | #25 FIX, #26 RETIRE | `tests/charter/test_invocation_context.py` | `src/charter/activation/invocation_context.py` |
| M3: synth orchestration | #8 RETIRE, #9 RETIRE | `tests/charter/synthesizer/test_orchestrator_synthesize.py` | `src/charter/activation/synthesizer/synthesize_pipeline.py`, `src/charter/activation/synthesizer/orchestrator.py` |
| M4: pack context | #31, #32, #33 RETIRE | `tests/charter/test_pack_context.py` | `src/charter/activation/pack_context.py` |
| M5: path conventions | #34, #38 RETIRE | `tests/charter/test_path_conventions_slot.py` | `src/charter/offering/missions/models.py` |
| M6: action slot | #17 RETIRE | `tests/charter/test_action_sequence_dispatch.py` | `src/charter/activation/mission_type_profiles.py` |
| M7: missions root | #20 RETIRE | `tests/charter/test_builtin_missions_root.py` | `src/charter/activation/mission_type_profile_repository.py` |
| M8: context result | #22 RETIRE | `tests/charter/test_context.py` | `src/charter/activation/context.py` |

### No overlap

Each `src/` file above belongs to exactly one group. The overlapping pairs are already merged into one group each: `activations.py` (#18/#19 in O2), `invocation_context.py` (#25/#26 in M2) and `fixture_adapter.py` (#2/#3 in O3). KEEP items need no edits, apart from the optional cleanups in D7–D10, which are comment-only and test-only.

---
# Bundle B verdicts: "Is the oracle precise and honest?" (`tests/charter`)

Reviewer: reviewer-renata (read-only), procedure `test-suite-quality-assessment`, slice 2 of #5353.
Candidates: `candidates-B.md` (29 tests). Environment: Python 3.11.15, Linux, primary checkout (not a lane worktree), `uv run --frozen`.
Rubric: `test-desiderata-and-boundaries` styleguide, `development-assist-test-cleanup` procedure, DIRECTIVE_041, `TEST_QUALITY_TRIAGE.md`.

## Summary

| # | file::test | verdict | tier | planted break (src path :: function :: mutation) OR covering guard |
|---|---|---|---|---|
| 1 | `evidence/test_orchestrator.py::test_dry_run_evidence_on_spec_kitty_repo` | FIX | glue | `src/specify_cli/cli/commands/charter/synthesize.py` :: `synthesize` (dry-run branch) :: write the synthesis manifest before `if dry_run_evidence:`. Only exposed when the auth banner is present; see section 1 |
| 2 | `synthesizer/test_evidence.py::test_code_signals_is_frozen` | FIX | glue | `src/charter/activation/synthesizer/evidence.py` :: `CodeSignals` :: drop `frozen=True`, add `unsafe_hash=True`, and turn `stack_id` into a read-only `@property` over `_stack_id` |
| 3 | `synthesizer/test_evidence.py::test_corpus_entry_is_frozen` | FIX | glue | same file :: `CorpusEntry` :: same mutation on `topic` |
| 4 | `synthesizer/test_evidence.py::test_corpus_snapshot_is_frozen` | FIX | glue | same file :: `CorpusSnapshot` :: same mutation on `snapshot_id` |
| 5 | `synthesizer/test_evidence.py::test_evidence_bundle_is_frozen` | FIX | glue | same file :: `EvidenceBundle` :: same mutation on `collected_at` |
| 6 | `synthesizer/test_fixture_adapter.py::TestPresentFixture::test_present_fixture_returns_adapter_output` | FIX | glue | `src/charter/activation/synthesizer/fixture_adapter.py` :: `FixtureAdapter.generate` :: `notes=None` (or `adapter_id_override="x"`) |
| 7 | `synthesizer/test_fixture_adapter.py::TestPresentFixture::test_present_fixture_body_is_dict` | RETIRE | glue | Guard: #6 after its fix, which asserts `output.body == <written mapping>`. Break: `fixture_adapter.py` :: `generate` :: `body=list(loaded.items())` turns fixed #6 red |
| 8 | `synthesizer/test_fixture_adapter.py::TestPresentFixture::test_fixture_deterministic_generated_at` | FIX | glue | `fixture_adapter.py` :: `_deterministic_generated_at` :: `return datetime.now(UTC)` |
| 9 | `test_canonical_root_resolution.py::test_submodule_resolves_to_submodule_working_tree` | FIX (+ suspected bug) | core | `src/charter/resolution.py` :: `resolve_canonical_repo_root` :: `if common_dir.parent.name == "modules": return common_dir.parent.parent.parent` (the #2011 "walks up into the superproject" regression) |
| 10 | `test_catalog.py::test_catalog_filters_language_scoped_artifacts` | KEEP | core | False positive: behavioural (writes fixtures, loads the catalog, asserts membership) |
| 11 | `test_catalog.py::test_catalog_keeps_language_scoped_artifacts_when_active_languages_are_unset` | KEEP | core | False positive: behavioural |
| 12 | `test_directive_selection_id_form_3908.py::test_this_repository_compact_context_keeps_its_activated_governance` | KEEP | core | Checkout-topology guard; does not fire in the primary checkout (passed) |
| 13 | `test_generator.py::test_write_compiled_charter_ignores_stale_symlinked_charter_md` | KEEP | glue | Legitimate platform guard; precise oracle |
| 14 | `test_generator.py::test_write_compiled_charter_rejects_symlinked_output_dir` | FIX | glue | `src/charter/activation/compiler.py` :: `write_compiled_charter` :: delete the first `_assert_safe_charter_output_dir(...)` and move the second after `_bootstrap_charter_yaml(...)` |
| 15 | `test_generator.py::test_write_compiled_charter_rejects_symlinked_output_dir_without_repo_root` | FIX | glue | same as #14 |
| 16 | `test_governance_references.py::test_collect_governance_references_rejects_symlink_escape` | KEEP | glue | Legitimate platform guard; precise oracle |
| 17 | `test_interview_mapping_mission_alias.py::test_synthetic_mission_type_is_picked_up_by_both_rosters` | KEEP | core | False positive (subprocess sentinel); the only guard of the roster D/E derivation |
| 18 | `test_merged_graph_on_live_path.py::test_load_validated_graph_rejects_invalid_merge` | FIX | core | `src/charter/activation/_drg_helpers.py` :: `load_validated_graph` :: `assert_valid(merged)` becomes `assert_valid(merged, strict=True)` (typo gives `TypeError`) |
| 19 | `test_mission_type_profiles.py::TestMissionTypeProfileOpenStr::test_pydantic_validation_error_not_raised_for_unknown` | RETIRE | core | Guard: `tests/charter/test_mission_type_profiles.py::TestMissionTypeProfileOpenStr::test_custom_type_accepted_without_validation_error`. Break: `src/charter/activation/mission_type_profiles.py` :: `MissionTypeProfile.mission_type` :: annotate as `Literal["software-dev","documentation","research","plan"]` turns the guard red |
| 20 | `test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_malformed_org_layer_yaml_is_not_silently_skipped` | FIX | core | `src/charter/offering/missions/mission_type_repository.py` :: `_load_layered_mission_type_file` :: raise a new `MalformedMissionTypeError(Exception)` (not a `ValueError`) with the same message |
| 21 | `test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_unreadable_org_layer_directory_raises_naming_the_directory` | FIX | core | `mission_type_repository.py` :: `scan_mission_types_dir` :: drop the `try/except OSError` around `directory.iterdir()` so the raw `PermissionError` propagates |
| 22 | `test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_activate_on_malformed_org_layer_type_raises_real_cause_not_generic_unknown_id` | FIX | core | same mutation as #20, reached through `CharterPackManager.activate` |
| 23 | `test_parser.py::TestCharterParser::test_real_charter_parsing` | FIX | glue | `src/charter/parser.py` :: `CharterParser.HEADING_PATTERN` :: `r"^(#{2,3})\s+([\w &:-]+)$"`, so headings containing backticks or parentheses silently merge into the previous section |
| 24 | `test_project_registration.py::test_namespaced_profile_identity_cannot_escape_provenance_directory` | KEEP | core | False positive: asserts on a manifest value, not on source text |
| 25 | `test_resolver_tier_axis_via_factory.py::test_only_charter_resolver_imports_the_doctrine_tier_functions` | FIX | core | `src/charter/activation/template_resolver.py` :: module scope :: add `from charter.offering import resolver as _tiers` and call `_tiers.resolve_template(...)` |
| 26 | `test_schemas_additive_fields.py::TestExistingDirectivesFixturesStillLoad::test_existing_directives_yaml_fixture_still_loads` | RETIRE | glue | Guard: `tests/charter/test_schemas_additive_fields.py::TestDirectiveReferencesField::test_round_trip_without_references`. Break: `src/charter/activation/schemas.py` :: `Directive.references` :: remove `Field(default_factory=list)` (make it required) turns the guard red |
| 27 | `test_sonar_complexity_a_helpers.py::TestResolveIncludeKind::test_resolve_include_kind_unknown_token_fails_closed` | RETIRE | glue | Guard: `tests/charter/test_context_include.py::TestUnknownSelectors::test_unknown_kind_fails_closed` (`raises(ValueError, match="Unknown artifact kind token")`). Break: `src/charter/activation/context_renderers/template_include.py` :: `_resolve_include_kind` :: `return ArtifactKind[kind.upper().replace("-", "_")]` (`KeyError`) turns the guard red |
| 28 | `test_symlink_loop_guards.py::test_resolve_relative_path_within_root_loop_raises_escape_error` | KEEP | core (DRG) | Precise typed oracle; the skip is a platform guard (ineffective, see section) |
| 29 | `test_symlink_loop_guards.py::test_path_guard_assert_allowed_loop_raises_violation` | KEEP | glue | Precise typed oracle; the skip is a platform guard (ineffective, see section) |

---

## Per-test reasoning

### 1. `tests/charter/evidence/test_orchestrator.py::test_dry_run_evidence_on_spec_kitty_repo`: FIX (glue)

- **Skip.** Conditional `pytest.skip(...)` when `"logged_out_on_connected_teamspace" in result.stderr`. The reason text: "charter synthesize requires connected-teamspace auth; skipping in a logged-out environment". No issue is referenced.
- **Observed.** The skip does not fire here: `1 passed` in 12.2 s.
- **Weakness 1: the skip is keyed on the wrong signal.**
  - The banner comes from the readiness coordinator (`src/specify_cli/readiness/render.py::render_auth_guidance` → `_auth_recovery.emit_structured_stderr`), and that path is advisory: it never exits non-zero (the renderer has an outer `except Exception: return`, and nothing raises `typer.Exit`).
  - So the test comment "exits non-zero before doing real work" is false. The skip fires whenever the banner is printed, even when the child succeeded.
  - It fires on a developer machine with a stale stored session that has a private teamspace, which is when `detect_logged_out_with_connected_teamspace` returns a handle. In CI (no session) it does not fire.
- **Weakness 2: the skip sits above an auth-independent invariant.** The skip runs before the manifest-mutation assertion ("`--dry-run-evidence` must never mutate the real repo manifest", #2672), so in that environment the #2672 guard is masked too.
- **Stronger oracle.**
  - Make the child deterministic instead of skipping. Give it an isolated `HOME` (`env["HOME"] = str(tmp_path)`) so there is no stored session and no banner, or set the readiness opt-out `SPEC_KITTY_ENABLE_SAAS_SYNC=0`. `is_saas_sync_enabled()` still gates the readiness coordinator.
  - Delete the skip.
  - If a skip must stay, key it on `result.returncode != 0 and banner in stderr`, and run the manifest-invariant assert before it.
- **Planted break.** In `src/specify_cli/cli/commands/charter/synthesize.py`, make the dry-run path write `.kittify/charter/synthesis-manifest.yaml` before the `if dry_run_evidence:` branch.
  - In a banner-emitting environment the current test skips, so it is not red.
  - The fixed test (isolated HOME, no skip) goes red on `manifest_after == manifest_before`.
  - Honest scope: in CI the current test already catches this. The masked window is local only, so this is low priority.

### 2 to 5. `tests/charter/synthesizer/test_evidence.py::test_{code_signals,corpus_entry,corpus_snapshot,evidence_bundle}_is_frozen`: FIX (glue, mechanical)

- **Weakness.**
  - All four classes are `@dataclass(frozen=True)` (`src/charter/activation/synthesizer/evidence.py:32,71,80,103`). The module docstring even promises "FrozenInstanceError on mutation".
  - `pytest.raises(Exception)` passes on any error raised by the assignment: `AttributeError` from a read-only property or slot, a `TypeError` from a custom `__setattr__`, or a `RecursionError` from a buggy override.
  - None of those prove the instance is immutable as a whole.
- **Stronger oracle.** `with pytest.raises(dataclasses.FrozenInstanceError, match="cannot assign to field 'stack_id'"):` (field name per test). Collapse the four tests into one test parametrized over `(factory, field, value)`.
- **Planted break** (`evidence.py`, per class):
  - Replace `@dataclass(frozen=True)` with `@dataclass(unsafe_hash=True)`.
  - Rename the asserted field to `_stack_id` / `_topic` / `_snapshot_id` / `_collected_at` and expose it through a read-only `@property`.
  - Assigning the asserted name now raises `AttributeError: property ... has no setter`, so the current test stays green, and `test_all_dataclasses_are_hashable` stays green thanks to `unsafe_hash`.
  - Every other field is now mutable: the frozen contract is broken.
  - The narrowed `FrozenInstanceError` test goes red.
- **Coverage check.** No other test in `tests/charter` or `tests/doctrine` asserts on `FrozenInstanceError` for these classes.

### 6. `.../test_fixture_adapter.py::TestPresentFixture::test_present_fixture_returns_adapter_output`: FIX (glue)

- **Skip.** Conditional `pytest.skip("Fixture not found at ... Create the fixture to enable this test.")`.
- **Observed: the skip FIRES in this environment and is a permanent masked green.**
  ```
  SKIPPED test_fixture_adapter.py:248: Fixture not found at .../project-decision-doc-directive/fd8f2b3c6906.directive.yaml. Expected hash: fd8f2b3c6906.
  ```
- **Root cause (test-side).**
  - The comment says the request matches `eb35535fb02c`. However, `_make_request()` builds a different doctrine snapshot (`"Document decisions via ADRs."`) from the conftest's recorded one (`"Document significant architectural decisions via ADRs."`).
  - The conftest `sample_synthesis_request` itself also hashes to `d6e987d08651` (computed here), and that file does not exist either.
  - The committed files `eb35535fb02c` and `d6250694fe91` match neither. The test has not run in its current form.
  - This is a skip keyed on "fixture not present", which DIRECTIVE_041 forbids: a hash-normalisation regression would move the path and make the test skip, not fail.
- **No covering guard.**
  - `grep` over `tests/charter` and `tests/doctrine` finds no other assertion on `FixtureAdapter` output `notes`, `adapter_id_override` or determinism of `generated_at`.
  - Other synthesizer tests only consume the adapter indirectly.
- **Stronger oracle.** Make the test hermetic and hash-agnostic:
  - build the request;
  - compute `path = FixtureAdapter(fixture_root=tmp_path)._fixture_path(req)`, or the public equivalent via `compute_inputs_hash` + `short_hash`;
  - write a known YAML mapping there;
  - call `generate`;
  - assert `output.body == mapping`, `output.adapter_id_override is None` and `output.notes == f"fixture:{full_hash[:12]}"`;
  - remove the skip.
- **Planted break.** `src/charter/activation/synthesizer/fixture_adapter.py` :: `FixtureAdapter.generate` :: `notes=None`. The current test skips, so it is not red. The fixed test goes red.

### 7. `.../test_fixture_adapter.py::TestPresentFixture::test_present_fixture_body_is_dict`: RETIRE (glue)

- **Skip.** Same "Fixture not present" skip; it fires here and masks a green.
- **Why retire.** The body is a `type-only-assert` (`isinstance(output.body, dict)`) that #6 already contains verbatim.
- **Covering guard.** #6 once fixed, which asserts `output.body == mapping`, a strictly stronger oracle.
- **Planted break proving the guard.** `fixture_adapter.py` :: `generate` :: `body=list(loaded.items())`. Fixed #6 goes red.
- **Condition.** Retire only together with the #6 fix. Until then, neither runs.

### 8. `.../test_fixture_adapter.py::TestPresentFixture::test_fixture_deterministic_generated_at`: FIX (glue)

- **Skip.** Same skip; it fires here.
- **Contract.** `_deterministic_generated_at` (hash-seeded epoch) is the determinism contract of the fixture adapter, and nothing else pins it.
- **Stronger oracle.**
  - Use the same hermetic tmp fixture as #6.
  - Assert `out_a.generated_at == out_b.generated_at`.
  - Also assert that it equals `_EPOCH + timedelta(microseconds=<offset from hash>)`, or at least that it differs for two different requests, which proves it is hash-seeded rather than constant.
  - Remove the skip.
- **Planted break.** `fixture_adapter.py` :: `_deterministic_generated_at` :: `return datetime.now(UTC)`. The current test skips, so it is not red. The fixed test goes red.

### 9. `tests/charter/test_canonical_root_resolution.py::test_submodule_resolves_to_submodule_working_tree`: FIX (core), with a suspected product bug

- **Skips.** Both are fine as guards.
  - `skipif(platform.system() == "Windows", reason="submodule edge cases differ on Windows; documented in resolver contract")` is a platform guard.
  - The runtime skip when `git submodule add` fails is a tool guard.
  - Neither fires here (`1 passed`).
- **Weakness: vacuous oracle.**
  - The docstring promises "returns the submodule's own working tree", but the only assertion is `result.is_absolute()`.
  - Reproduced here in a scratch repo, the resolver returns `<super>/.git/modules`.
  - That is neither the submodule working tree (`<super>/submod`, per `git rev-parse --show-toplevel`) nor the superproject. It is a directory inside `.git/`.
  - `src/charter/resolution.py::resolve_canonical_repo_root` returns `common_dir.parent`, and for a submodule `common_dir = <super>/.git/modules/submod`.
- **The contract is self-contradictory.** In `kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md`:
  - line 96 tabulates `<repo>/.git/modules` as the result;
  - the note on line 100 claims this "is the submodule's working tree" and that `common_dir.parent.parent` is the working tree. Both claims are false: `common_dir.parent.parent` is `<super>/.git`.
- **Stronger oracle.** Red-first, and it needs a product decision.
  - Assert `result == (superproject / "submod").resolve()` (the submodule working tree, consistent with the #2011 / #2624 boundary rulings).
  - If the operator instead rules the current value intended, pin `result == superproject / ".git" / "modules"` explicitly and fix the contract prose. Either way, never `is_absolute()`.
- **Planted break.** `src/charter/resolution.py` :: `resolve_canonical_repo_root` :: `if common_dir.parent.name == "modules": return common_dir.parent.parent.parent`. This returns the superproject root, which is exactly the #2011 regression class.
  - Every other row in the file uses a plain repo or worktree, so they stay green.
  - The current submodule test stays green, because the result is still absolute.
  - The fixed test goes red.

### 10, 11. `tests/charter/test_catalog.py::test_catalog_filters_language_scoped_artifacts` / `..._when_active_languages_are_unset`: KEEP (core)

- **False positive.** The scanner saw file writes followed by `in` asserts. These are behavioural:
  - they write real YAML into a tmp doctrine root;
  - they point `resolve_doctrine_root` and `built_in_dir` at it (two seam patches at a true filesystem boundary);
  - they call `load_doctrine_catalog(active_languages=...)`;
  - they assert present and absent membership per kind.
- **Why the oracle is precise.** Both the generic keep and the python drop are asserted, so a filter that dropped everything, or nothing, goes red.

### 12. `tests/charter/test_directive_selection_id_form_3908.py::test_this_repository_compact_context_keeps_its_activated_governance`: KEEP (core)

- **Skip.** `if resolve_canonical_repo_root(REPO_ROOT) != REPO_ROOT: pytest.skip("repository-level charter assertion must read the canonical checkout under test")`.
  - It is a checkout-topology guard (it fires in lane worktrees), not a defect mask.
  - #3908 is a closed, fixed regression, and the synthetic siblings in the same file pin the mechanism with `tmp_path` fixtures.
- **Observed.** It does not fire here: the whole file ran, `4 passed`.
- **Why keep.** The assertions are content-based, and it is the only guard that the committed charter keeps resolving.
- **Note.** In lane worktrees it always skips, so agents never see it there. That is acceptable, because CI runs in a primary checkout.

### 13. `tests/charter/test_generator.py::test_write_compiled_charter_ignores_stale_symlinked_charter_md`: KEEP (glue)

- **Skip.** `try: os.symlink(...) except (OSError, NotImplementedError): pytest.skip("symlinks not supported on this platform")` is the correct platform-guard idiom. The scanner did not recognise the inline form.
- **Oracle.** `files_written == ["charter.yaml"]`, the target is unchanged, and the symlink is untouched. All three are precise.

### 14. `tests/charter/test_generator.py::test_write_compiled_charter_rejects_symlinked_output_dir`: FIX (glue, mechanical)

- **Skip.** A legitimate platform guard (same idiom as #13).
- **Weakness.**
  - The primary oracle (`raises(FileExistsError, match="Charter output path")`) is precise.
  - The post-raise "nothing leaked" assertions check `outside_dir / "charter.md"` and `references.yaml`, but `write_compiled_charter` never writes either file (`src/charter/activation/compiler.py:515-574`, which returns `files_written=["charter.yaml"]`). They are stale leftovers from the retired multi-file bundle, and vacuously true.
- **Stronger oracle.** `assert not (outside_dir / "charter.yaml").exists()` and `assert list(outside_dir.iterdir()) == []`.
- **Planted break.** `compiler.py` :: `write_compiled_charter` :: delete the first `_assert_safe_charter_output_dir(...)` call and move the second after `_bootstrap_charter_yaml(...)`.
  - The write then lands in `outside_dir/charter.yaml` through the symlink, and the late guard still raises `FileExistsError("Charter output path ...")`.
  - The current test stays green: the raise still matches, and `charter.md` and `references.yaml` still do not exist.
  - The fixed test goes red.

### 15. `tests/charter/test_generator.py::test_write_compiled_charter_rejects_symlinked_output_dir_without_repo_root`: FIX (glue, mechanical)

The same defect and fix as #14: the no-write check is `charter.md`, and the function only writes `charter.yaml`. The planted break is identical, and the `repo_root=None` branch (`output_dir.is_symlink()`) raises the "Charter output directory" message after the write.

### 16. `tests/charter/test_governance_references.py::test_collect_governance_references_rejects_symlink_escape`: KEEP (glue)

- **Skip.** A platform-guard idiom; it does not fire.
- **Oracle.** `safe is False` plus the message `"escapes the repository root"`. Precise.
- **Minor.** It writes `outside-governance.md` into `tmp_path.parent` (shared basetemp). Harmless today, but `tmp_path / "outside"` with the repo root at `tmp_path / "repo"` would be cleaner. Deferred.

### 17. `tests/charter/test_interview_mapping_mission_alias.py::test_synthetic_mission_type_is_picked_up_by_both_rosters`: KEEP (core)

- **False positive.** The "literal scan" is a subprocess `"OK"` sentinel. The real assertions (`"analysis" in ALLOWED_MISSION_TYPES` / `_MISSION_IDENTIFIER_ANSWERS`) run in the child, and a failure there makes `returncode != 0`, which is asserted first with stdout and stderr attached.
- **Coverage.** This is the only guard that rosters D and E derive from `MissionTypeRepository` rather than from literals. `tests/charter/test_activations.py` only checks `isinstance(ALLOWED_MISSION_TYPES, frozenset)`.
- **Housekeeping.** Strip the "RED-first / WP03 / T012-T014" labels from the docstring (development-assist lens). Not a verdict change.

### 18. `tests/charter/test_merged_graph_on_live_path.py::test_load_validated_graph_rejects_invalid_merge`: FIX (core, mechanical)

- **Weakness.**
  - `pytest.raises(Exception)` (the comment reads "assert_valid may raise a variety") passes on any failure along the load path.
  - Observed here, the real exception is `charter.offering.drg.validator.DRGValidationError: 1 validation error(s): Dangling target: edge (directive:a --requires--> directive:missing) references non-existent node 'directive:missing'`.
- **Stronger oracle.** `with pytest.raises(DRGValidationError, match=r"Dangling target: .*directive:missing"):`.
- **Planted break.** `src/charter/activation/_drg_helpers.py` :: `load_validated_graph` :: `assert_valid(merged)` becomes `assert_valid(merged, strict=True)`.
  - The result is a `TypeError`, and the validator never runs.
  - The current test stays green (`TypeError` is an `Exception`). So does the mock-based sibling `test_load_validated_graph_invokes_assert_valid`, because a `MagicMock` accepts any kwargs.
  - The fixed test goes red.
- **Contract drift.** The `load_validated_graph` docstring says `Raises: ValueError`, but `DRGValidationError` subclasses `Exception`, not `ValueError`. See "Suspected product bugs / contract drift".

### 19. `tests/charter/test_mission_type_profiles.py::TestMissionTypeProfileOpenStr::test_pydantic_validation_error_not_raised_for_unknown`: RETIRE (core)

- **Skip.** `except ImportError: pytest.skip("pydantic not installed")`. Dead code: pydantic is a hard runtime dependency (`pyproject.toml:67`, `"pydantic>=2.0"`), and the module under test imports it. The skip can never fire.
- **Why retire.** Its oracle ("no `ValidationError` for an unknown type" plus the value round-trips) is exactly what the two siblings already assert: `test_custom_type_accepted_without_validation_error` and `test_arbitrary_string_accepted`. Any `ValidationError` in those siblings fails them too. This is T029 development-assist scaffolding, duplicated three times.
- **Covering guard.** `tests/charter/test_mission_type_profiles.py::TestMissionTypeProfileOpenStr::test_custom_type_accepted_without_validation_error`.
- **Planted break.** `src/charter/activation/mission_type_profiles.py` :: `MissionTypeProfile.mission_type: Literal["software-dev","documentation","research","plan"]`. The guard raises `ValidationError` and goes red.

### 20. `tests/charter/test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_malformed_org_layer_yaml_is_not_silently_skipped`: FIX (core, mechanical)

- **Weakness.**
  - `pytest.raises(Exception)` plus the file path in the message. The `noqa` says "message content is the assertion".
  - But the exception class is load-bearing product contract:
    - `src/specify_cli/cli/commands/charter/activate.py` catches `except (ValueError, DRGLoadError)` around `manager.activate` and renders a clean `Error:` / `typer.Exit(1)`;
    - the multi-org-root fallback loop (`activate.py:263-281`) catches `ValueError` to try the next candidate root;
    - the raise-site docstring (`mission_type_repository.py:417-420`) promises `ValueError`.
  - Observed here: `ValueError: Malformed YAML in mission-type file <path>: ...`.
- **Stronger oracle.** `with pytest.raises(ValueError, match=re.escape(f"Malformed YAML in mission-type file {bad_file}")):`.
- **Planted break.** `src/charter/offering/missions/mission_type_repository.py` :: `_load_layered_mission_type_file` :: `raise MalformedMissionTypeError(f"Malformed YAML in mission-type file {yaml_file}: {exc}")`, where `class MalformedMissionTypeError(Exception)` is a plausible "dedicated error" refactor that forgets the `ValueError` base.
  - The current test stays green: the path is still in the message.
  - The CLI would now crash with a traceback, and the multi-root loop would abort.
  - The fixed test goes red.

### 21. `.../test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_unreadable_org_layer_directory_raises_naming_the_directory`: FIX (core, mechanical)

- **Skip.** `if os.name != "posix" or os.geteuid() == 0: pytest.skip("chmod-based unreadability needs POSIX and a non-root user")` is a legitimate platform guard. It does not fire here.
- **Weakness.** A broad raise plus the directory path in the message. Observed: `ValueError: mission-type directory exists but cannot be read: <dir>: [Errno 13] ...`.
- **Stronger oracle.** `pytest.raises(ValueError, match=re.escape(f"mission-type directory exists but cannot be read: {mt_dir}"))`.
- **Planted break.** `mission_type_repository.py` :: `scan_mission_types_dir` :: remove the `try/except OSError` translation around `list(directory.iterdir())`.
  - The raw `PermissionError: [Errno 13] Permission denied: '<mt_dir>'` propagates, and its `str()` contains `str(mt_dir)`, so the current test stays green.
  - The CLI's `except ValueError` no longer catches it, so an operator would see a traceback.
  - The fixed test goes red.

### 22. `.../test_pack_manager.py::TestMissionTypeMalformedOrgLayerLoudFails::test_activate_on_malformed_org_layer_type_raises_real_cause_not_generic_unknown_id`: FIX (core, mechanical)

- **Weakness.** A broad raise, plus `not isinstance(..., UnknownActivationIdError)` (itself a `ValueError` subclass, `activation_engine.py:84`), plus the path in the message.
- **Stronger oracle.**
  ```python
  with pytest.raises(ValueError, match=re.escape(f"Malformed YAML in mission-type file {bad_file}")) as exc_info:
  ```
  Keep the `not isinstance(exc_info.value, UnknownActivationIdError)` assertion.
- **Planted break.** The same mutation as #20, reached end to end through `CharterPackManager.activate`. The current test stays green (not an `UnknownActivationIdError`, path present). The fixed test goes red.

### 23. `tests/charter/test_parser.py::TestCharterParser::test_real_charter_parsing`: FIX (glue)

- **Skip.** `if not Path(".kittify/charter/charter.md").exists(): pytest.skip("Real charter not found")`.
  - The path is cwd-relative, so the skip fires whenever pytest runs from any directory other than the repo root. It is a masked green, not a platform guard.
  - It does not fire here, because the run was from the repo root.
- **Literal scan.** It reads a data file, not source. That is fine.
- **Weakness.**
  - Loose oracle: `"Purpose" in headings or "Technical Standards" in headings` and "at least one structured section".
  - A parser that drops or merges most headings still passes.
  - Observed: the live charter parses into 52 sections, including headings with backticks and parentheses (for example "Local Docker Development Governance (`spec-kitty-saas`)").
- **Stronger oracle.**
  - Anchor the path to the file (`Path(__file__).resolve().parents[2] / ".kittify/charter/charter.md"`) and drop the skip; the repo always carries its charter.
  - Assert a structure-level invariant that does not pin charter prose: the multiset of `level == 2` section headings equals the `^## (.+)$` headings found outside code fences (the same for `###`).
- **Planted break.** `src/charter/parser.py` :: `CharterParser.HEADING_PATTERN = re.compile(r"^(#{2,3})\s+([\w &:-]+)$", re.MULTILINE)`.
  - Headings with backticks or parentheses stop being split out.
  - "Purpose" is still found, and structured sections still exist, so the current test stays green.
  - The heading-completeness assertion goes red.

### 24. `tests/charter/test_project_registration.py::test_namespaced_profile_identity_cannot_escape_provenance_directory`: KEEP (core)

- **False positive.** `"team%2Fops-responder" in entry.provenance_path` is an assertion on a produced manifest value, not a source-text scan.
- **Oracle.** It is behavioural and precise: `Path(entry.provenance_path).parent == Path(".kittify/charter/provenance")` (no escape) plus the encoded identity, and `verify(manifest, tmp_path)` checks the sidecar integrity end to end.

### 25. `tests/charter/test_resolver_tier_axis_via_factory.py::test_only_charter_resolver_imports_the_doctrine_tier_functions`: FIX (core, oracle design)

- **Weakness.** An import-boundary scan is the right *kind* of oracle, but this one is a line-based substring scan.
  - **(a)** It misses `from charter.offering import resolver` (plain, aliased or function-local), because the line does not contain `"charter.offering.resolver"`. That is the same blind spot the architectural gate documents fixing as "A5" (4/9 catch rate).
  - **(b)** It misses a multi-line `from charter.offering.resolver import (` continuation only if split oddly. Minor.
  - **(c)** The positive half, `"from charter.offering.resolver import (" in charter_body`, pins formatting: reflowing to a one-line import reds it with no behaviour change.
- **Coverage split.**
  - The `specify_cli/runtime/resolver.py` half is already covered AST-precisely by `tests/architectural/test_charter_sole_door_resolver_imports.py::test_no_direct_doctrine_resolver_import_outside_the_owning_layers`.
  - The positive half is covered by `::test_detector_finds_the_real_sanctioned_imports`, which asserts `src/charter/activation/resolver.py` is in the inside census.
  - The architectural gate exempts all of `src/charter/**` (`OWNING_LAYER_PREFIXES`), so the only unique contract here is "within `src/charter`, `template_resolver.py` must not import the tier functions".
- **Stronger oracle.** Replace the text scan with the AST census: `resolver_import_census()` inside sites, then `assert "src/charter/activation/template_resolver.py" not in {s.rel_path for s in inside}`. Preferably, add it to the architectural gate as an intra-charter sole-door assertion and delete this test, so there is one source of truth. Drop the other two halves as duplicates.
- **Planted break.** `src/charter/activation/template_resolver.py` :: module scope :: add `from charter.offering import resolver as _tiers` and call `_tiers.resolve_template(...)` in one method.
  - The current test stays green: the line lacks the substring.
  - The architectural gate stays green: `src/charter/**` is exempt.
  - The census-based assertion goes red.

### 26. `tests/charter/test_schemas_additive_fields.py::TestExistingDirectivesFixturesStillLoad::test_existing_directives_yaml_fixture_still_loads`: RETIRE (glue)

- **Skip.** `if not paths: pytest.skip("No directives.yaml fixtures found in the repo tree")`.
- **Observed: masked in CI, polluted locally.**
  - `git ls-files | grep -c 'directives.yaml$'` returns **0**, so in a clean checkout (CI) the skip always fires.
  - It passed here (in 6.1 s) only because `repo_root.rglob` walked into gitignored `.worktrees/*/.kittify/charter/directives.yaml` from unrelated stale lane worktrees. The `.worktrees` filter branch is a no-op `pass`.
  - `directives.yaml` is a retired legacy bundle file: it appears only in migrations and freshness code (`m_unify_charter_activation_finalize.py`, `charter_runtime/freshness/computer.py`).
  - It also catches all exceptions on load (`except Exception: continue`).
- **Covering guard.**
  - `tests/charter/test_schemas_additive_fields.py::TestDirectiveReferencesField::test_round_trip_without_references` loads a legacy directive with no `references` and asserts the default and the dump.
  - `tests/charter/test_schemas.py::TestDirectivesConfig` covers the wrapped config.
- **Planted break.** `src/charter/activation/schemas.py` :: `Directive.references: list[str]` without `Field(default_factory=list)` (required field). The guard raises `ValidationError` and goes red.

### 27. `tests/charter/test_sonar_complexity_a_helpers.py::TestResolveIncludeKind::test_resolve_include_kind_unknown_token_fails_closed`: RETIRE (glue)

- **Weakness.**
  - `pytest.raises(Exception)`, justified by "class not re-exported here". That is false: the observed exception is plain `ValueError("Unknown artifact kind token 'not-a-real-kind'. Valid operator tokens: ...")`.
  - It is Sonar-extraction development-assist scaffolding that pins a private helper.
- **Covering guard.** `tests/charter/test_context_include.py::TestUnknownSelectors::test_unknown_kind_fails_closed` asserts `raises(ValueError, match="Unknown artifact kind token")` through the public `build_charter_context_include`. Its call path reaches `_resolve_include_kind` at `src/charter/activation/context.py:408`. `tests/charter/test_context_selection_render.py:630` is a second covering guard.
- **Planted break.** `src/charter/activation/context_renderers/template_include.py` :: `_resolve_include_kind` :: `return ArtifactKind[kind.upper().replace("-", "_")]`.
  - A `KeyError` is raised for the bogus token.
  - The current test stays green, which shows it is not the protecting test. The covering guard goes red.
- **Alternative.** If the operator prefers to keep a helper-level test, narrow it to `ValueError, match="Unknown artifact kind token 'not-a-real-kind'"` (a mechanical FIX). Retiring is recommended because the public-path guard already carries the contract.

### 28. `tests/charter/test_symlink_loop_guards.py::test_resolve_relative_path_within_root_loop_raises_escape_error`: KEEP (core, DRG org-pack config)

- **Skip.** `skipif(not hasattr(os, "symlink"), reason="os.symlink unavailable on this platform")`.
  - A legitimate intent, but an ineffective guard: CPython always defines `os.symlink` on Windows, so an unprivileged Windows run ERRORs on `symlink_to` instead of skipping.
  - Mechanical follow-up: use the `try: ... except (OSError, NotImplementedError): pytest.skip(...)` idiom from `test_generator.py` / `test_governance_references.py`.
  - It does not fire here (`4 passed`).
- **Oracle.** `raises(OrgPackSubdirEscapeError)` is precise enough.
  - The loop lives inside `root`, so the only raising branch is the `resolve_rejecting_loops` `OSError` translation.
  - On 3.11/3.12 without the fix, a `RuntimeError` escapes (red); on 3.13+ there is no raise (red).
  - An optional tightening is `match="could not be resolved under root"`.

### 29. `tests/charter/test_symlink_loop_guards.py::test_path_guard_assert_allowed_loop_raises_violation`: KEEP (glue)

- **Skip.** The same ineffective-but-legitimate guard as #28.
- **Oracle.** `raises(PathGuardViolation)` with the loop placed inside an allowed prefix (`.kittify/doctrine`), so only the loop branch (`path_guard.py:74-80`) can raise. That is precise.

---

## Verdict counts

| Verdict | Count | Items |
|---|---|---|
| KEEP | 9 | 10, 11, 12, 13, 16, 17, 24, 28, 29 |
| FIX | 16 | 1, 2, 3, 4, 5, 6, 8, 9, 14, 15, 18, 20, 21, 22, 23, 25 |
| RETIRE | 4 | 7, 19, 26, 27 |
| SPLIT-BY-KIND | 0 | none |

Total: 29. Scanner flag accuracy for this bundle:
- **literal-source-scan:** 6 flagged; 5 are false positives (#10, #11, #17, #23 data-read, #24), and only #25 is a real source scan.
- **broad-raises:** all 8 flagged are real.
- **skip-or-xfail:** 17 flagged; 8 are platform or tool guards that are fine as guards (#9, #13 to #16, #21, #28, #29), and 6 are masked greens (#1, #6, #7, #8, #23, #26). Of the remaining 3, #12 is a checkout-topology guard and #19 is a dead import guard. No xfails in the bundle.

## Suspected product bugs

1. **`charter.resolution.resolve_canonical_repo_root` returns a path inside `.git/` when called from a git submodule** (core, #9).
   - **Reproduction.** Superproject with a submodule `submod`, then `resolve_canonical_repo_root(<super>/submod)` returns `<super>/.git/modules`. For comparison, `git rev-parse --show-toplevel` gives `<super>/submod`.
   - **Why it is wrong.** The result is neither the submodule working tree nor the superproject. Downstream charter reads (`charter_bundle.py`, `charter/activate.py`, `activation/sync.py`, `dashboard/charter_path.py`, `analysis_report.py`) would look for `.kittify` under `<super>/.git/modules/`.
   - **Why it is invisible.** The governing contract table (`canonical-root-resolver.contract.md:96`) records this value, but its note (line 100) misdescribes it as the submodule working tree. The test's `is_absolute()` oracle hides the discrepancy.
   - **Tracking.** Related tracker state: #2011 (submodule root misresolution, a different resolver) is CLOSED; the root-detection epic #2624 is OPEN and names submodule boundaries. Recommend a child issue under #2624 plus a red-first exact-path assertion.
2. **Contract drift (minor, not a runtime bug by itself).**
   - `load_validated_graph` documents `Raises: ValueError`, but it raises `DRGValidationError(Exception)` (`src/charter/activation/_drg_helpers.py:134` vs `src/charter/offering/drg/validator.py:27`).
   - CLI call sites that rely on `except ValueError` (for example `activate.py`'s `except (ValueError, DRGLoadError)`) would not catch a merged-graph validation failure that surfaces through them. I did not reproduce such a traceback; recorded for triage only.
3. **Stale synthesizer fixtures (test-data defect).**
   - `tests/charter/fixtures/synthesizer/directive/project-decision-doc-directive/{eb35535fb02c,d6250694fe91}.directive.yaml` match neither `_make_request()` (`fd8f2b3c6906`) nor the conftest `sample_synthesis_request` (`d6e987d08651`).
   - The present-fixture path of `FixtureAdapter` has not been exercised in this directory. Not a `src` bug, but it is why #6 and #8 are silent.

## Deferred (out of slice)

- **Possibly orphaned fixture files.** The two `project-decision-doc-directive` fixture files named above (and possibly others under `tests/charter/fixtures/synthesizer/`) need an audit: which fixture files any passing test actually loads.
- **Inert marker.** `requires_symlinks` is registered in `pytest.ini:40`, but nothing consumes it: there is no conftest deselect and no CI `-m` filter. It is a label only.
- **Ineffective symlink guards.** Tests with `skipif(not hasattr(os, "symlink"))` (#28, #29, and likely siblings elsewhere) do not guard unprivileged Windows. A suite-wide idiom sweep is better filed than swept.
- **Shared basetemp write.** `test_governance_references.py::test_collect_governance_references_rejects_symlink_escape` writes into `tmp_path.parent`.
- **Over-mocked sibling (candidate for bundle A).** `test_merged_graph_on_live_path.py::test_load_validated_graph_invokes_assert_valid` is a mock-called oracle (`mock_validator.called`). A behavioural #18 (after its fix) proves the same contract more strongly.
- **Environment-coupled live-repo tests.** `test_orchestrator.py` (#1, 12 s, subprocess against the real repo) and `test_parser.py::test_real_charter_parsing` are integration tests that live in unit-marked files. #1 also rewrites guard bytes of the real repo manifest (restored by the fixture). Consider moving them to an integration lane.
- **Development-assist labels to strip on the tests kept:**
  - #17: "RED-first", "WP03", "T012-T014";
  - `test_mission_type_profiles.py`: T029/T030 in section headers;
  - `test_schemas_additive_fields.py`: the WP01 docstring;
  - `test_sonar_complexity_a_helpers.py` as a whole: a Sonar-WP mega-file of private-helper tests, which should get a development-assist-test-cleanup pass (retire the helper tests the public-path suites already cover).

## Implementation grouping

These are split so that implementers never touch the same test file. All planted breaks are proposals only.

| Group | Kind | Items | Test files touched | `src/` files the planted breaks touch |
|---|---|---|---|---|
| **G1: narrow broad raises** | mechanical | 2, 3, 4, 5, 18, 20, 21, 22 | `tests/charter/synthesizer/test_evidence.py`, `tests/charter/test_merged_graph_on_live_path.py`, `tests/charter/test_pack_manager.py` | `src/charter/activation/synthesizer/evidence.py`, `src/charter/activation/_drg_helpers.py`, `src/charter/offering/missions/mission_type_repository.py` |
| **G2: stale no-write assertions** | mechanical | 14, 15 | `tests/charter/test_generator.py` | `src/charter/activation/compiler.py` |
| **G3: retire duplicates** | mechanical (delete; verify the guard with the planted break) | 19, 26, 27 | `tests/charter/test_mission_type_profiles.py`, `tests/charter/test_schemas_additive_fields.py`, `tests/charter/test_sonar_complexity_a_helpers.py` | `src/charter/activation/mission_type_profiles.py`, `src/charter/activation/schemas.py`, `src/charter/activation/context_renderers/template_include.py` |
| **G4: hermetic fixture adapter** | oracle design | 6, 7 (retire into 6), 8 | `tests/charter/synthesizer/test_fixture_adapter.py` | `src/charter/activation/synthesizer/fixture_adapter.py` |
| **G5: import-boundary census** | oracle design | 25 | `tests/charter/test_resolver_tier_axis_via_factory.py` (and optionally `tests/architectural/test_charter_sole_door_resolver_imports.py`, running only that gate file) | `src/charter/activation/template_resolver.py` |
| **G6: parser heading completeness** | oracle design | 23 | `tests/charter/test_parser.py` | `src/charter/parser.py` |
| **G7: deterministic CLI subprocess** | oracle design (environment isolation) | 1 | `tests/charter/evidence/test_orchestrator.py` | `src/specify_cli/cli/commands/charter/synthesize.py` |
| **G8: submodule resolver** | **product decision plus product fix** (red-first) | 9 | `tests/charter/test_canonical_root_resolution.py` | `src/charter/resolution.py` (and possibly `src/kernel/git_topology.py`), plus the contract `kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md` |

The groups share no `src/` or test files. G8 needs an operator ruling on the intended submodule result before implementation, and should be filed under #2624. G1 to G3 can be taken by one mechanical implementer; G4 to G7 are independent and can be parallel.
