---
work_package_id: WP07
title: Cascade, activate CLI, presets, synthesis, interview
dependencies:
- WP06
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- FR-022
- C-007
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T036
- T037
- T038
- T039
- T040
- T041
- T042
phase: Phase 4 - Non-explicit writers and cascade
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_cascade_stop_at_denied.py
- tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/cascade.py
- src/charter/activation/preset_application.py
- src/charter/activation/synthesizer/reach_only.py
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/_resynthesis_preflight.py
- src/specify_cli/cli/commands/charter/interview.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/test_cascade.py
- tests/charter/test_kind_cascade_exhaustive.py
- tests/charter/test_cascade_stop_at_denied.py
- tests/charter/presets/**
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_flags.py
- tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py
- tests/specify_cli/cli/commands/charter/test_activate_preset.py
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py
- tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
- src/specify_cli/_completion_manifest.json
- tests/conftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Cascade, activate CLI, presets, synthesis, interview

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP07 --note "..."`.

---

## Objective

The cascade walk stops at an excluded artifact and reports it ("Skipped, deactivated" with the
`requires` flag, plus "Unreached (behind a deactivated artifact)"); `--include-deactivated`
restores the full walk and clears exclusions; presets without `--force`, synthesis and the
interview never re-add a denied id and say so; `--preset X --force` clears the exclusions of
the ids X lists and reports them.

## Context

- Plan IC-07; data-model.md §3 (rows for cascade/preset/promotion), §7 (cascade shapes and CLI rendering); research.md D-10 (operator ruling `cascade_walk_through_denied`: stop), D-11; spec US3, US5.4, edge cases (synthesis, interview).
- Builds on WP05 (`PackContext.deactivated_urns`) and WP04 (`manager.activate(..., reinstate=...)`, `deny_delta`, `PromotionOutcome.skipped_denied`).
- Deny writers (operator ruling `deny_writers`): only `charter activate <kind> <id>` (incl. `--only`), cascade `--include-deactivated` and `--preset X --force`. Every other path warns and keeps the exclusion.
- C-007: cascade deactivation's shared-reference skip unchanged (the engine's `DeactivationPlan` is unchanged).
- `activate.py` is owned by this WP only; `_resynthesis_preflight.py` and `_completion_manifest.json` are shared, ordered (from WP06 / WP04).
- Mission order: WP07 of 15 (strictly linear). Transition model D0: tolerant mode is the default. New acceptance tests are ledger-seeded and run strict through `SWEPT_PREFIXES`; the existing cascade, preset and interview tests stay green unchanged.

## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP07 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

T036 writes acceptance tests for US3.1–US3.3, US5.4, US1.3 (interview/synthesis/promotion keep D
excluded) and the synthesis "first creation" edge case. Commit before implementation; record the
red summary.

## Subtasks

### Subtask T036: Failing acceptance tests

**Steps**:
1. `tests/charter/test_cascade_stop_at_denied.py` (engine-level, synthetic graph):
   - edges `directive:P -requires-> tactic:C -requires-> procedure:G`, deny C → `activated` lacks C and G; `skipped_deactivated["tactic"] == [ReferencedArtifact(..., via_requires=True, required_by=("directive:P",))]`; `unreached_behind_deactivated["procedure"] == ["G"]`;
   - a second path `P -suggests-> G` avoiding C → G is activated, not unreached;
   - a denied node outside scope lands in `skipped_by_scope` (scope decided before deny);
   - `include_deactivated=True` → full walk, C and G in `activated`;
   - partition invariant: every node of the full walk lands in exactly one bucket (`activated`, `skipped_by_scope`, `skipped_deactivated`, `unreached_behind_deactivated`, `not_cascaded_kind_filtered`), parametrised over a few random DAGs (seeded).
2. `tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py` (CLI): headings "Skipped (out of scope)", "Skipped, deactivated" (with "(required by directive:… — the parent no longer has this requirement)"), "Unreached (behind a deactivated artifact)", and the hint "Run with --include-deactivated …"; with `--include-deactivated` C is active and its deny entry gone; `--include-deactivated` without `--cascade` is refused (exit 2 usage error).
3. Preset tests (extend `tests/specify_cli/cli/commands/charter/test_activate_preset.py`): deny D listed by preset `default` → without `--force` D stays denied and subtracted, warning names D; with `--force` D's exclusion is cleared and the output names it.
4. Mission-type seeding (US1.3, F17): `charter activate mission-type software-dev` whose default seeding lists denied D → D stays denied and the output names it (`test_mission_type_seeding_keeps_denied_cli` in `test_activate_include_deactivated.py`).
5. Interview / synthesis: extend `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` and `tests/charter/synthesizer/test_reach_only_delivery.py` — a denied id is not re-added; output prints "kept deactivated: <id>"; synthesis never adds a denied tactic even on first creation.

### Subtask T037: Cascade engine (`cascade.py`)

**Steps**:
1. `_reference_adjacency` (`:275-281`) keeps the `Relation` on each edge.
2. `_forward_reference_closure` (`:253-272`) gains `blocked: frozenset[str]`: a blocked node is recorded and not expanded (its `REQUIRES` and other edges are not followed).
3. `ReferencedArtifact` (`:328-337`) gains `via_requires: bool = False` and `required_by: tuple[str, ...] = ()`; reuse it for the skipped bucket (R10).
4. `CascadeActivationResult` (`:346-368`) gains `skipped_deactivated` and `unreached_behind_deactivated` (default empty; existing 37 tests in `tests/charter/test_cascade.py` keep passing with empty buckets).
5. `cascade_activation_targets(graph, source_urn, scope, *, deactivated_urns=frozenset(), include_deactivated=False)` (`:371-412`): compute the full walk once and the blocked walk once; derive `unreached = full − blocked_reach − denied − scope_skips`. Keep complexity ≤ 15 by extracting `_classify_nodes(...)`.
6. `NoCascadeReport` / `referenced_but_not_cascaded` (`:421-500`) list denied nodes as deactivated.

### Subtask T038: Activate CLI (`activate.py`)

**Steps**:
1. Add `--include-deactivated` next to `--cascade` (`:866-910`); refuse it without `--cascade`.
2. `_render_cascade_activation` (`:237-341`): pass `pack_context.deactivated_urns` into the engine at `:268`; call `manager.activate(..., reinstate=DenyListChoice.CASCADE_INCLUDE_DEACTIVATED)` at `:280` when the opt-in is set; print the "reinstated" line from `deny_delta`.
3. Render the two new headings beside "Skipped (out of scope)" (`:300-308`); update the zero-target summary (`:337-341`) and `_render_no_cascade_warning` (`:386`).
4. Help text for `--include-deactivated` and for `--force` (now two effects: overwrite + clear listed exclusions). Regenerate `src/specify_cli/_completion_manifest.json` with `.venv/bin/python -m specify_cli.completion --regenerate` and run `tests/architectural/test_completion_manifest_freshness.py` (F14).

**T038 extension: mission type as a cascade source (FR-022, operator ruling
`mission_type_cascade_source`, added after WP07's first implementation).**
Today `_source_urn` (`activate.py:154`) returns `None` for `mission-type`, so
`charter activate mission-type X --cascade <scope>` silently cascades nothing,
although AGENTS.md documents it.

Steps:
1. Make the mission type a cascade source: resolve its DRG node
   (`mission_type:<id>`, `NodeKind.MISSION_TYPE`).
2. Feed it to the same `_render_cascade_activation` / `cascade_activation_targets`
   walk. The engine already follows the action hop for mission-type nodes
   (`cascade.py:89-96`: `requires` to action-sequence steps, `scope` to type-wide
   governance, `instantiates` to templates).
3. Apply the same rules as an artifact source: scope, skip-and-report, stop at a
   denied node, `--include-deactivated` and the no-cascade warning.
4. The direct activation of the mission type itself (`mission_type_activations`)
   is unchanged. Mission types get no deny list.
5. `charter deactivate mission-type X --cascade` follows the deactivation-side
   rules: only the named mission type is removed from `mission_type_activations`,
   with no deny entry for children, plus the C-005 shared-reference skip and the
   required-children skip.
6. Red-first acceptance:
   - `activate mission-type software-dev --cascade all` reaches a denied child C,
     reports it under "Skipped, deactivated", and leaves it excluded.
   - Positive control on the same fixture: a non-denied child is activated.
   - With `--include-deactivated`, C is reinstated.

Also fix the AGENTS.md / CLAUDE.md example only if its text is now wrong. WP15
owns those files, so leave a carry-forward note instead of editing them.

### Subtask T039: Resynthesis preflight

**Steps**: `_resynthesis_preflight.py:80` passes `deactivated_urns` into the cascade call. Add a focused test in `tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_flags.py` or the nearest existing resynthesis-preflight test.

### Subtask T040: Presets (`preset_application.py`)

**Steps**:
1. `_target_state` (`:482-494`) partitions preset-listed ids into kept and denied (effective deny).
2. Without `--force`: denied ids are left out of the allow lists; `PresetPlan.denied_listed` carries them for the warning.
3. With `--force`: `apply_preset_plan` (`:594-607`) clears them via `prepare_activation_write(..., deny_change=DenyListChoice.PRESET_FORCE)` and keeps them in the allow lists; the cleared list comes from `deny_delta`.
4. `GOVERNED_KEYS` (`:106`) stays allow-only (a preset never names a deny key).
5. CLI rendering at `activate.py:790-855`; `restamp_bundle_hash` after the write.

### Subtask T041: Synthesis (`synthesizer/reach_only.py`)

**Steps**: `append_synthesized_tactic_activations` (`:115-165`) returns the skipped-denied tactics and never re-adds a denied tactic, even when the tactic was just created. The created-tactics record `.kittify/charter/synthesized-tactics.yaml` is unchanged and is not an activation surface. Its two callers, `cli/commands/charter/synthesize.py:532-536` and `resynthesize.py:202-204`, already print the returned `activation_warnings`; return one warning per skipped tactic ("kept deactivated: tactic <id>") so no caller change is needed beyond a test, and touch the callers only if the output needs a separate heading.

### Subtask T042: Interview (`interview.py`)

**Steps**: `interview.py:100-199`: after `promote_activations` (`:187`), print "kept deactivated: <kind> <ids>" from `PromotionOutcome.skipped_denied`; the interview never passes a `deny_change`.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q tests/charter/test_cascade_stop_at_denied.py tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py
.venv/bin/python -m pytest -q tests/charter/test_cascade.py tests/charter/test_kind_cascade_exhaustive.py tests/charter/presets tests/charter/synthesizer/test_reach_only_delivery.py tests/charter/activation/test_preset_application.py tests/charter/activation/test_default_preset_provisioning.py
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_flags.py tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py tests/specify_cli/cli/commands/charter/test_activate_preset.py tests/specify_cli/cli/commands/charter/test_activate_only_6408.py tests/specify_cli/cli/commands/charter/test_org_cascade_chain.py tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py tests/specify_cli/cli/commands/test_charter_interview_promotion.py
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering tests/specify_cli/cli/commands/charter
.venv/bin/python -m pytest -q tests/architectural/test_charter_kind_vocabulary_single_authority.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_completion_manifest_freshness.py
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy src/charter/activation/cascade.py src/charter/activation/preset_application.py src/charter/activation/synthesizer/reach_only.py src/specify_cli/cli/commands/charter/activate.py src/specify_cli/cli/commands/charter/interview.py src/specify_cli/cli/commands/charter/_resynthesis_preflight.py
```

NFR-003: `tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py` must stay green; also time one cascade activation on this repository.

## Standing orders

- python-pedro; complexity ≤ 15 (the cascade classifier and `_render_cascade_activation` are the hot spots — extract helpers and unit-test them); ruff/format(`--force-exclude`)/mypy clean; no suppressions; literals used ≥ 3 times (headings) become constants.
- Append dated entries to the Mission's `traces/*.md`.
- Do not edit shipped migrations.

## Definition of Done

- Stop-at-denied walk with the unreached bucket and the partition invariant test.
- `--include-deactivated` works only with `--cascade` and clears exclusions.
- Presets/synthesis/interview keep exclusions and warn; `--force` clears listed ones and reports.
- Gates green; subtasks marked done.

## Risks

- Existing cascade output tests snapshot headings: update them deliberately; do not loosen assertions.
- `--force` semantics broaden: help text and the changelog (WP15) must say both effects.

## Reviewer Guidance

- Check a node reachable over a second, non-denied path is still activated.
- Check that only the explicit choices pass a non-`None` `deny_change`: `DenyListChoice.ACTIVATE` (`charter activate <kind> <id>`, incl. `--only`), `CASCADE_INCLUDE_DEACTIVATED` (cascade `--include-deactivated`), `PRESET_FORCE` (`--preset X --force`), and `DEACTIVATE` (`charter deactivate`, which adds). No migration, preset without `--force`, interview or synthesis passes one.

## Test-mode rules (analyze pass 2, binding)

- **New test files run strict through `SWEPT_PREFIXES`.** Every new test file this WP adds is
  appended, by exact path, to `SWEPT_PREFIXES` in `tests/conftest.py`, in the same commit as the
  file. The edit is append-only; this WP co-owns `tests/conftest.py`, dependency-ordered.
- **How strict mode is set (M1).** A `pytest_runtest_setup(item)` hookimpl (`tryfirst=True`) in
  `tests/conftest.py` sets or clears `os.environ["SPEC_KITTY_ACTIVATION_STRICT"]` from the
  item's path **before any fixture of that item is set up**, so function- and module-scoped
  fixtures see the item's mode. `test` means strict, and a stray legacy key raises. A matching
  `pytest_runtest_teardown` restores the previous value.
- **Session-scoped activation-seeding fixtures must be mode-independent (L1).** A session fixture
  is set up once, by its first user, in that item's mode. No such fixture exists today (grep).
  Any future one must be function-scoped, or go through the
  WP11 step-0 helpers or `tests/_factories/activation_ledger.py`, which work in both modes.
- **No test file references `SPEC_KITTY_ACTIVATION_STRICT`.** That covers `setenv`, `delenv`
  and string mentions. There are two exceptions: the kernel resolver test
  `tests/kernel/test_activation_ledger_store.py` (WP02 creates it, WP14 rewrites it), and the
  swept-prefix fixture in `tests/conftest.py` itself (WP02 creates it, WP14 deletes it).
- **No new tolerant-mode-only test.** Tolerant behaviour is pinned only by the existing tests,
  which stay unchanged until their sweep WP, and by the kernel resolver test. An existing test
  file this WP modifies must stay correct in tolerant mode. Tests for new behaviour go in new,
  ledger-seeded files.
