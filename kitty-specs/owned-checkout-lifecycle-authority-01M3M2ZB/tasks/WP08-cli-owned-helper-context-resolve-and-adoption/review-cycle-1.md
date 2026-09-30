---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T03:08:24Z'
reviewer_agent: claude
wp_id: WP08
---

# WP08 review — cycle 1: CHANGES REQUESTED

Reviewer: reviewer-renata (claude). Base 5ff83a621, head 63aad7ca0 (commits ae17b50a8, 9c228bb4a, 54b87caa1, fb5695a1a).

## What is good (keep it)

- Red-first holds. ae17b50a8 is red on its own tree: 13 failed and 8 passed, each for a real reason (uncaught ValueError, Typer usage error, MissingLanesError traceback, count 0). The fix commits follow it.
- The campsite extraction is its own commit. `resolve_context` and every helper are at complexity ≤ 11.
- The non-owned payload is byte-identical to the base. The reviewer checked this empirically: tasks_outline, implement WP01, implement WP04 and specify, all from cwd = R with an R copy, gave identical output on 5ff83a621 and on the head.
- NFR-002 has three count rows (1 with the flag, 1 adopted, 0 from R). The owned arm passes `owned=` and never `effective_root=`, and the planning re-anchor uses `owned.mission_dir`.
- The explicit-path `WORKTREE_REGISTRY_UNAVAILABLE` test is present and non-vacuous.
- ruff check, ruff format and mypy `--strict` are clean. mypy shows 0 errors on both base and head.
- No `TRANSITIONAL(WP18)` markers, which matches the DoD of 0.

## Required fixes

1. **[HIGH] tests/integration/test_owned_lifecycle_acceptance_context.py:301-338 — the US7-AS2/AS4 lane and coordination controls are vacuous.**
   - The problem: both worktrees are branched from R's HEAD, which does not carry mission M. `adopt_owned_checkout` therefore returns `None` at "mission absent from toplevel", before either exclusion predicate runs. Both payloads are the same `MISSION_NOT_FOUND` error, because R has no copy either.
   - Mutation proof: the reviewer made `_is_lane_worktree_of_mission` return False and removed the `_is_coordination_worktree` early return in `owned_mission.py`. Both tests still pass.
   - Required fix:
     - The lane worktree and the coordination worktree must each hold M. Branch them from `owned_checkouts.target_branch`, or copy the mission dir in. Use the lane id and path that P's `lanes.json` names.
     - Make R resolve successfully, for example with `stale_root_copy()` active, so that "equals cwd = R" compares success payloads.
     - Show in the commit body that the two mutations above now turn these rows red.
2. **[MEDIUM] test_owned_lifecycle_acceptance_context.py:247-276 — the O10 row is disjunctive and uses the wrong shape.**
   - The problem: it accepts "exit 0 and equal to R", **or** "exit 1 with any registered code". The registered set includes `MISSION_NOT_FOUND` and `PROJECT_ROOT_UNRESOLVED`. At the head it takes the exit-1 branch.
   - Required fix:
     - Always assert `_payload(result) == _r_only_payload(...)`, whatever the exit code.
     - Add the spec's O10 row: a **real registered linked checkout on a mismatched branch** that holds M, flagless, with a payload equal to cwd = R. The reviewer confirmed that the head gives the R payload for it, but nothing pins that. The hand-made pointer row can stay as an extra.
3. **[MEDIUM] src/specify_cli/cli/commands/_owned_checkout.py:236 and tests/architectural/test_single_mission_surface_resolver.py:+351-377 — remove the new allowlist entry and use the canonical composer.**
   - The problem: `stale_repository_root_copy` hand-composes `owned.repository_root / KITTY_SPECS_DIR / owned.mission_slug`. That is a parallel path composer, and a canonical one exists: `specify_cli.missions._read_path_resolver.compose_meta_json_path(base, mission_slug)`. It is pure, with no git and no topology probing. It is the public meta.json composer already used by `next_cmd.py:385` and `mission_runtime.resolution.read_dir_for`.
   - Required fix:
     - Use `r_copy_dir = compose_meta_json_path(owned.repository_root, owned.mission_slug).parent` (lazy import).
     - Drop the ContentDescriptor entry, and with it the out-of-map edit to another mission's gate.
     - FR-007 semantics are unchanged: detection only, and the owned run wins.
     - Do **not** route through `placement_seam(...).read_dir` / `resolve_artifact_surface`. They call `get_main_repo_root` and canonicalise handles, which would break R-12's "no git calls" rule.
4. **[MEDIUM] _owned_checkout.py:1-16, 95-96 (and the 54b87caa1 commit body) — the G2 claim is aspirational.**
   - The problem: the docstrings say this is "the ONLY CLI caller" of the minter. Today these files still call `resolve_owned_mission` directly:
     - `accept.py:342,732` (converted by WP14);
     - `mission_finalize.py:3328` (WP13);
     - `tasks_move_task.py:464`, `tasks_mark_status.py:183`, `spec_commit_cmd.py:113`, `mission_check_prerequisites.py:599` (WP16);
     - `coordination/status_transition.py:917` (the `TRANSITIONAL(WP18)` legacy branch, WP07/WP18).
   - Required fix: state the true current state. The module is G2's designated sole CLI caller, the residual direct callers are listed above with their converting WP, and WP18 enforces G2.
   - Also correct the Activity Log. It says "WP09/WP13/WP16/WP19"; the actual converters are WP13, WP14 and WP16.
5. **[MEDIUM] kitty-specs/.../data-model.md "Error code registry" — `emit_owned_refusal` accepts three codes the registry does not list.**
   - The codes: `WORKTREE_REGISTRY_UNAVAILABLE`, `FEATURE_CONTEXT_UNRESOLVED` and `MISSION_CONTEXT_CONFLICT`. The data-model says the function "validates every emitted error_code against this whole table".
   - Required fix: add the three rows (status "existing", pass-through), or escalate to the orchestrator if you may not edit the planning artifact. The code and the registry must agree.
6. **[MEDIUM] tests/specify_cli/cli/commands/test_owned_checkout_helper.py:240,327,358,382,399,412,427,446 and test_owned_lifecycle_acceptance_context.py:52-54,230,351,379 — repeated code literals.**
   - The problem: the WP DoD says no `OWNED_*` literal may be repeated in new tests (S1192).
     - `"OWNED_CHECKOUT_IS_REPOSITORY_ROOT"` appears 4 times, `"OWNED_BRANCH_REFUSED"` 2 times and `"WORKTREE_REGISTRY_UNAVAILABLE"` 3 times.
     - The acceptance registry re-spells `FEATURE_CONTEXT_UNRESOLVED` and `MISSION_CONTEXT_CONFLICT` although they are now public constants.
   - Required fix: use the `OwnedRefusalCode` members, `WorktreeRegistryUnavailable.error_code` and the `owned_mission` constants.
7. **[MEDIUM] _owned_checkout.py:85-115 — `resolve_owned_or_adopt` does not forward `target_override`.**
   - The problem: WP13 (finalize `--target-branch`) and WP16 (`spec-commit`, "confirm WP08 forwards target_override") both need it. Without it they must edit this WP's authoritative surface out of map.
   - Required fix: add `target_override: str | None = None`, forward it on the explicit path, and add one unit test.
8. **[MEDIUM] test_owned_lifecycle_acceptance_context.py:410-424 — control (a) is not the byte-equality pin T038 requires.**
   - The problem: T038 requires the full base payload, captured inline as an expected dict. The test checks 4 keys. The payload is identical today (reviewer-verified), but the test does not pin it.
   - Required fix: capture the full normalised payload and assert equality.
9. **[LOW] test_owned_lifecycle_acceptance_context.py:279-298 — the T041 step 3a variant is missing.**
   - Required fix: add US7-AS1 flagless == flagged **with `stale_root_copy()` active**.
10. **[LOW] test_owned_checkout_helper.py:627-660 — the T043 disposition table is incomplete.**
    - The problem: the table must live in the module docstring. Row 2 ("caller has no mission") is mapped to a cwd = R test, which is a different scenario.
    - Required fix: add `test_no_adoption_when_checkout_lacks_mission`, using a valid linked checkout without M (the fixture's `sibling`), and move the table into the module docstring.
    - Also rename `test_invalid_checkout_with_conflicting_id_is_not_adopted`: it asserts a conflict refusal, not "not adopted".
11. **[LOW] _owned_checkout.py:195 — `assert` guards the registry check.**
    - The problem: under `python -O` the assert is stripped, so the "validates every code" guarantee disappears. When it does fire, it produces an uncaught AssertionError.
    - Required fix: raise an explicit exception (e.g. `RuntimeError`) with the same message, and adjust the test.
12. **[LOW] test_owned_lifecycle_acceptance_context.py:11-17 — the "observed base" record is inaccurate.**
    - The problem: on the base, O3/O4 raise an uncaught `ValueError` ("Work package WP01 was not found under <R>/kitty-specs/..."). They do not return exit 0 with `lane_workspace`.
    - Required fix: record what the base actually does.
13. **[LOW] src/specify_cli/core/owned_mission.py:406-409 — stale docstring.**
    - The problem: it still reads "Deliberately NOT imported from `specify_cli.missions.operation_context` (WP08 deletes that module)". The module is now deleted.
    - Required fix: reword it (you already hold this file as a declared out-of-map edit).
14. **[NIT] agent/context.py `_reanchor_planning_feature_dir` docstring — bare "primary".**
    - The problem: the new docstring says "Re-anchor … to primary". The terminology rule does not allow bare "primary" as a checkout alias.
    - Required fix: say "the repository root checkout's PRIMARY-partition dir".

## Verified OK (no action)

- **The 11 failures in `tests/specify_cli/cli/commands/` + `missions/` are pre-existing.** They come from 5 files: `test_doctor_cli_surface_golden.py` (3), `test_handle_equivalence_matrix.py` (3), `test_doctor_coordination.py` (1), `charter/test_recompile_preserves_mission_4908.py` (1) and `test_mission_type_current_fallback_signal.py` (3). Both 5ff83a621 and the head give the identical set: 11 failed, 171 passed.
- **`operation_context` is gone.** There are no live references in src, tests, docs or templates. The remaining mentions are prose comments in WP08 files, the stale docstring in item 13, and a historical entry in `tests/release/coverage_breadth_baseline.json`, which is a measurement snapshot that no gate reads per file.
