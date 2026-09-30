---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T06:28:47Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review, cycle 2: CHANGES REQUESTED

## What I verified and accept
- **HIGH-1: accepted.** The divergence row in e203e0adb builds `<P>/.kittify/overrides/mission-steps/software-dev/specify/step.yaml` and has both sanity pins. Per the orchestrator's ruling, the red proof is the reviewer's cc6230ede run. The "NOT implemented" note is gone.
- **HIGH-2: red-first verified.** At 2bafdfbe3 two tests fail (symlink and mismatch); at b28dffaec both pass. The owned arm now takes `owned_create_root.repository_root` and fails closed on a mismatch.
  - `MissionCreationError` is the appropriate surface here. The mismatch cannot happen from the CLI, because it mints from the same located root. It is a contract violation by a programmatic caller: the same surface as the existing "Could not locate project root", rendered by the existing `MissionCreationError` envelope branch.
  - It is NOT a claim refusal. A foreign checkout is already refused as `OWNERSHIP_FOREIGN` inside `resolve_owned_create_root`.
- **HIGH-3: red-first verified.** At 131f043ea the test fails; at 962e8defa it passes.
- **HIGH-4: accepted.** The #1067 (both), #3474 (both) and #3673/FR-001 comments are restored next to their code.
- **MEDIUM-5, 6, 7 and 8: accepted.**
  - The dead arm is deleted.
  - `_run_create_core_phase` is now at complexity 4, and `_emit_create_core_error_and_exit` at 11.
  - The CLI pin for `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` is in place.
  - Nine helper unit tests were added.
- **LOW-10 and LOW-12: accepted.**
- **LOW-11:** the history is not rewritten, so declare the format campsite in the PR body.

## Required fixes

1. **[HIGH] A real fail-open (formerly ADVISORY-13; now in scope for WP10).** `src/specify_cli/cli/commands/agent/mission_create.py` `create_mission` computes `command_checkout = owned_checkout.resolve()` from the RAW claim. It then runs `_rollback_start_branch_on_failure`, `_resolve_start_branch_phase` (which calls `_mission._switch_to_start_branch`), `get_current_branch` and `_resolve_default_topology_phase` on it, all BEFORE `resolve_owned_create_root` validates it.
   - Reviewer probe: CliRunner, `create probe --owned-checkout <X> --start-branch side --target-branch side --json`, with `_switch_to_start_branch` spied.
     - For X = R, the branch is switched in R, then refused with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`.
     - For X = an unrelated repository, the branch is switched in the FOREIGN repository, then refused with `OWNERSHIP_FOREIGN`.
   - This is a git mutation of a checkout that the validator refuses. It folds the claim back into bare-`Path` parameters (`repo_root=command_checkout`). The WP says "Nothing is owed to WP18 for this file", so it is fixed here.
   - Fix: mint the fact once, at the top of `create_mission`, before any git operation.
     ```python
     repo_root = _mission.locate_project_root()
     owned_create_root = _mint_owned_create_root(repo_root, owned_checkout, mission_slug=..., json_output=...)
     # None when no claim was given. When a claim was given and repo_root is None: fail closed
     # (the HIGH-3 MissionCreationError). Otherwise: resolve_owned_create_root(repo_root, owned_checkout).
     # Any exception is routed through _emit_create_core_error_and_exit, so the envelopes stay identical.
     command_checkout = owned_create_root.checkout if owned_create_root is not None else repo_root
     ```
     Then change `_run_create_core_phase` to take `owned_create_root: OwnedCreateRoot | None` (keyword-only) instead of the raw `owned_checkout`. Delete the in-funnel mint and the HIGH-3 guard there, since they move up, and move/re-point the HIGH-3 test accordingly. `create_mission` keeps `owned_checkout: OwnedCheckoutOption` as the only raw-claim carrier.
   - Red-first test: commit it before the fix, in `test_mission_create_phases.py` (declared out-of-map, like the HIGH-3 test). Use the probe above, parametrised over X = R and X = a foreign repository.
     - Assert that `_switch_to_start_branch` is never called: patch it to record or raise.
     - Assert that the foreign repository's `HEAD` branch is unchanged.
     - Assert that `error_code` is `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` or `OWNERSHIP_FOREIGN` respectively.
2. **[MEDIUM] A bare `assert` in production code** (22bebeb91, `mission_create.py`: `assert repo_root is not None  # narrowed by the guard above`). `python -O` strips it; this is the same standard WP08 was rejected on. Fix 1 removes it, because minting now lives in an explicit `if repo_root is None: raise ... else: mint` structure. Do not reintroduce any `assert` for narrowing in `src/`.
3. **[MEDIUM] MEDIUM-9 built a parallel NFR-001 oracle, with an unjustified suppression.** `tests/core/test_mission_creation_owned_charter.py::_snapshot_repository_root` reimplements the R snapshot. It is also WEAKER than NFR-001: it skips `.git`, so it never covers the shared lock root (`<common-dir>/spec-kitty-locks`) or `SPEC_KITTY_HOME`. It also carries `# noqa: TID251` with no justification, which `pyproject.toml` forbids for raw sha256 in tests.
   - Fix: delete the helper and use the canonical oracle. `tests/_owned_fixtures.py` is a plain, importable module, and its docstring sanctions a direct import; there is no need to move the test to `tests/integration/`.
     ```python
     from tests._owned_fixtures import RSnapshotter
     home = Path(os.environ["SPEC_KITTY_HOME"]) if os.environ.get("SPEC_KITTY_HOME") else None  # same source as integration's _home_for_snapshot
     snap = RSnapshotter(repository_root, owned, home)
     before = snap.take(); result = create_mission_core(...); after = snap.take()
     snap.assert_unchanged(before, after, tolerate_status_mutex_for=result.feature_dir.name)
     ```
   - Evidence: with the canonical `RSnapshotter`, an owned create adds exactly one key to the lock root: `<mission-dir>.status.lock`. HEAD, index and files are otherwise unchanged. That key is exactly NFR-001's single named tolerance (an empty per-mission status mutex).
   - Dependency: the `tolerate_status_mutex_for` parameter is WP06's canonical tolerance (530bc56b5, on lane-e). It is NOT yet on the mission branch or lane-i. Pick it up either by merging the mission branch into lane-i once WP06 is integrated (preferred; the orchestrator will say which), or by a declared out-of-map `git cherry-pick -x 530bc56b5`. Never re-implement the tolerance locally.

## Tests to run after the fix
The same targeted set as cycle 2: 460 passed at the current head. Also run the new red-first test for fix 1: red before the fix, green after.
