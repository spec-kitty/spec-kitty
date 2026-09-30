---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T05:30:57Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review, cycle 1: CHANGES REQUESTED

Verified good, keep as is:
- T050 → T051 order.
- The characterisation suite is 19/19 green both before and after the decomposition, and it is non-vacuous. I re-ran the mutations:
  - disabling the #4033 guard turns `test_live_duplicate_raises_already_exists` red;
  - disabling the empty-activation gate turns `test_empty_activation_set_raises_and_leaves_no_scaffold` red;
  - reverting FR-016's `governance_root` turns 3 tests red.
- Red-first order. At 4e19601a1 both carried parametrisations fail for the documented reasons. At cc6230ede the marker test is red and FR-017 is green. At cc9adb159 all four pass.
- Provenance:
  - the cherry-pick is byte-identical to a37e9ee39, keeps author Samuel Goff and carries the `-x` trailer;
  - `Co-authored-by: Samuel Goff <samuel@defpix.com>` is on cc9adb159.
- `ruff.toml` lost exactly the `mission_creation.py` line and the two C901 tokens. The repo config gives `max-complexity=15`, and C901 passes on all three files.
- The arch re-pin is narrow, and no allowlist grew.
- mypy `--strict` shows 0 errors on both base and head.
- The charter suites are untouched.
- 445 targeted tests are green.

## Required fixes

1. **[HIGH] T054 step 1b, the mission-type-context divergence row, is missing.** You must build it; this cannot be approved as a gap. The override tier exists, and I verified it empirically. `resolve_mission_type_context(root, ...)` builds `PackContext.from_config(root)`. Its `template_set` slot comes from `MissionStepRepository.resolve_all_for_mission_type(type, pack_context)`, whose **project layer** is
   `<root>/.kittify/overrides/mission-steps/<mission_type>/<step_id>/step.yaml`
   (see `charter/offering/missions/mission_step_repository.py::_project_mission_type_dir` / `_resolve_project_layer`; project beats org beats built-in).
   Shape: copy `packs/built-in/missions/mission-steps/software-dev/specify/step.yaml` verbatim into `P/.kittify/overrides/mission-steps/software-dev/specify/step.yaml`, changing only `template.template_file: spec-template.md` to `owned-spec-template.md`. Then write `P/.kittify/overrides/missions/software-dev/templates/owned-spec-template.md` containing `# OWNED-CONTEXT-MARKER`.
   - Sanity pins: `resolve_mission_type_context(P, mission_type="software-dev").template_set["spec"] == "owned-spec-template.md"` and the same call on R gives `"spec-template.md"`.
   - Assert: an owned create (`resolve_owned_create_root(R, P)`, chdir P, SINGLE_BRANCH) scaffolds a `spec.md` that contains `OWNED-CONTEXT-MARKER`.
   - I ran exactly this: red at cc6230ede and green at head.
   - It is non-redundant. A mutation that reverts only the context read to R is caught by this row, but NOT by the template-marker test.
   - Commit it red before the fix. If you rebase to insert it before cc9adb159, keep the cherry-pick verbatim. Otherwise land it as a test commit and record the red run at cc6230ede as a commit-anchored proof, per the orchestrator's ruling.
   - Remove the "NOT implemented" comment block.
2. **[HIGH] `src/specify_cli/core/mission_creation.py` `_resolve_create_roots`: the owned arm reads the caller's bare `repo_root` instead of the fact (T055 regression).** `elif resolved_root is None: resolved_root = owned_create_root.repository_root` leaves a supplied `repo_root` unresolved. Before this WP it was `.resolve()`d, and it is never cross-checked against `owned_create_root.repository_root`.
   - Repro: pass a symlinked `repo_root`. `result.canonical_repo_root` (serialized in the `--json` payload) is the symlink path at head, and the real path at base b68e58bcd. My probe passes at base and fails at head.
   - Fix: in the owned arm, set `resolved_root = owned_create_root.repository_root` unconditionally. If a supplied `repo_root.resolve()` differs from it, fail closed and never mix roots.
   - Add a test for the symlink case and for the mismatch case.
3. **[HIGH] `src/specify_cli/cli/commands/agent/mission_create.py` `_run_create_core_phase`: an explicit claim is dropped silently.** The code is `resolve_owned_create_root(...) if owned_checkout is not None and repo_root is not None else None`, so `--owned-checkout P` with an unlocatable project root silently becomes an unowned create.
   - Fix: fail closed when `owned_checkout is not None and repo_root is None`, raising the existing "Could not locate project root" `MissionCreationError` inside the funnel.
   - Add a test.
4. **[HIGH] The #1067, #3474 and #3673/FR-001 decision-record comments were dropped in T051**, contrary to step 3. The commit body also claims that #1067 moved.
   - Pre-decomposition locations: `2e86a79c0:src/specify_cli/core/mission_creation.py:985,1062,1177,1245,1281`.
   - What they cover: the mid8 single derivation and meta backfill (#3474); local persistence before SaaS fan-out, and SpecifyStarted visibility (#1067); the "do NOT suppress a hard git failure" rule (FR-001/#3673).
   - Restore each one next to its code, in `_scaffold_mission_dir`/`_build_create_meta`, `_emit_create_events` and `_commit_create_scaffold`.
5. **[MEDIUM] `mission_create.py`: the `except CheckoutOwnershipError` arm is now dead code.** After T053 nothing on the create path raises it: `create_mission_core` no longer calls `error_for_claim`, and `resolve_owned_create_root` converts it to `ActionContextError`. Delete the arm and its import, keeping the single `ActionContextError` arm, which is envelope-identical.
6. **[MEDIUM] `mission_create.py`: `_run_create_core_phase` complexity went from 12 to 14.** T055 step 5 required that, once its body is touched, the error-funnel `except` arms be extracted into a helper in a separate commit, bringing it to ≤ 11.
7. **[MEDIUM] The CLI refusal pin is missing.** The Risks section requires a one-line test that pins `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` through the CLI (`agent mission create --owned-checkout <R> --json` gives `{success: false, error_code: "OWNED_CHECKOUT_IS_REPOSITORY_ROOT", ...}`). This also covers the new `ActionContextError` arm, which currently has no test (Sonar new-code coverage).
8. **[MEDIUM] T051 step 5: no focused unit tests for the extracted helpers.** Examples: `_validate_create_inputs`, and the `_build_create_meta` retention and pr-bound branches. The decomposition test file gained nothing in 75d043417.
9. **[MEDIUM] The T053 checklist's snapshot of the repository root checkout around an owned create was not added.** It should assert that R is unchanged apart from shared refs, modelled on `tests/integration/test_explicit_checkout_commands.py:44`.

## Lower-severity items (fix in the same cycle)

10. **[LOW] `tests/core/test_mission_creation_owned_charter.py`:**
    - T052 step 3 required renaming `primary` to `repository_root` in the carried-test adaptation, and the adaptation belongs in its own commit; it is currently folded into 7302601e6.
    - The new helper `_init_primary_and_owned` and the "Primary + a linked..." docstring break the terminology canon. Rename to repository root checkout / owned checkout.
    - The cc6230ede body says "primary/owned fixture"; use canonical terms in future commit bodies.
11. **[LOW]** 7302601e6 reformats 4 unrelated hunks in `tests/core/test_mission_create_checkout_restore.py`. They were needed because the base file was not format-clean, but the commit body must declare them as a format campsite.
12. **[LOW]** `_run_create_core_phase` gained `json_output: bool = False` only because of the default ordering. Prefer keyword-only (`*,`) over adding defaults to existing parameters.
13. **[ADVISORY]** `create_mission` still runs `_resolve_start_branch_phase` and the topology phase on `owned_checkout.resolve()` before validation, which is pre-existing. The WP allowed minting the fact in `create_mission` itself. Doing so would fail closed before any git mutation of an unvalidated path, so consider it while fixing item 3.
