---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T19:53:46Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (cycle 1): changes requested

**Reviewer:** reviewer-renata, independent of the implementer.
**Commits reviewed:** 4c3dd3a3b, d9487b1ea, efddfa9c8, dc410753c. The lane tip was 1842288ba.

Most of the WP is in good shape and needs no rework. Everything under "What already passes" stays as it is. The required changes below are small and mechanical. Please do not widen scope beyond them.

## Required changes (blocking)

### 1. Refusal codes must come from `OwnedRefusalCode` (a DoD item that was missed)

The DoD says: "new refusal codes come from WP01's `OwnedRefusalCode` (no repeated literals); the existing literal sites in `owned_mission.py` are converted to it here."

What the code does today:
- `src/specify_cli/core/owned_mission.py` still holds **10** string-literal code sites:
  - `"OWNED_TOPOLOGY_UNSUPPORTED"` ×3 (this alone is S1192, which asks for a constant at 3 or more repeats)
  - `"OWNED_BRANCH_REFUSED"` ×2
  - `"FEATURE_CONTEXT_UNRESOLVED"` ×2
  - `"OWNED_MISSION_PATH_REFUSED"`, `"OWNED_INDEX_REFUSED"` and `"MISSION_CONTEXT_CONFLICT"`
- `src/specify_cli/core/checkout_ownership.py` defines `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` and `OWNED_CHECKOUT_IS_MISSION_WORKTREE` as independent plain strings. That makes a second code authority next to `mission_runtime.OwnedRefusalCode`, which already has both members. It conflicts with the charter's single-canonical-authority rule. WP08's `emit_owned_refusal` validates against the registered set, so the two copies can drift.

Fix:
- Convert every registered code site in `owned_mission.py` to `OwnedRefusalCode.<MEMBER>`. The member values equal the names, so the `logs_telemetry: do_not_change` strings are unchanged.
- Keep the exported names in `checkout_ownership.py`, since T007 asks for them to be exported, but bind them to the enum, for example `OWNED_CHECKOUT_IS_REPOSITORY_ROOT: Final = OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT`. One authority remains.
- Two codes are not in the registry:
  - `FEATURE_CONTEXT_UNRESOLVED`
  - `MISSION_CONTEXT_CONFLICT`

  Hoist each one to a module constant so the `FEATURE_CONTEXT_UNRESOLVED` duplicate goes away. Either note in the Activity Log that they sit outside the owned registry, or escalate to the orchestrator to add them. Do not invent enum members silently.

### 2. Add the test rows the WP prompt specifies

Each of these is listed explicitly in the prompt and is missing:

- **Symlinked repository root (T007 edge case).** "Add one test passing `R` through a symlink `link -> R`; it must still refuse." Expect `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`. No symlink test exists in `tests/core/test_owned_mission_minter.py`.
- **`resolve_owned_create_root` foreign repository (T008 step 1).** A foreign repository must give `OWNERSHIP_FOREIGN`. The nested, broken-pointer and repository-root refusals are tested. Foreign is not.
- **`OwnedCreateRoot` resolution (T008 step 5).** Pass a symlinked checkout path and assert that `checkout`, and `repository_root` where applicable, come back resolved.
- **Claim counts on every adoption case (T009 step 4).** The prompt says "each asserts the return value **and** the number of `resolve_ownership_claim` calls". Only 4 of the 10 cases in `tests/core/test_adopt_owned_checkout.py` use `counting_claims`. Add the count to the others:
  - lane worktree: 0 claims
  - mismatched branch: 1
  - foreign repository: 1
  - mission-surface conflict: 0, because the conflict is raised before the minter runs
  - stale copy: 1
  - P under `.worktrees/`: 1

## Non-blocking nits (fix them while you are in these files if they are cheap)

- **Unreachable `except` and a fail-open path in adoption.** `_is_coordination_worktree` swallows `WorktreeRegistryUnavailable` and returns `False`. That makes the `except WorktreeRegistryUnavailable` in `adopt_owned_checkout` unreachable. It also means an unavailable registry reads as "not coordination", which moves toward adoption. The T009 edge case asks for the opposite: fail closed toward today's behaviour. The claim primitive's own registry read is a backstop in practice, since it returns `OWNERSHIP_BROKEN_POINTER` and adoption then returns `None`. Consider letting the exception propagate from the predicate in the adoption path, or dropping the unreachable `except`, and pin the behaviour with a test.
- **`# noqa: N802` on the `OwnedMission` factory.** The prompt says "ruff's `N` rules are not selected, so no suppression is needed; do not add one". The same applies to `# noqa: T201` in `tests/integration/conftest.py`.
- **`# noqa: TID251` in `tests/_owned_tree_hash.py`.** It has no inline rationale. Add one, in the style of `tests/dossier/test_determinism.py`: "file-integrity checksum, not charter freshness hashing".
- **`test_r_snapshot_detects_head_move` does not isolate HEAD.** It also changes `files` and the index, so the test would still pass if the `head` component were dropped from the snapshot. Use `git commit --allow-empty` to make it prove the HEAD component.
- **Placeholder test.** `test_owned_fixtures_selftest_collection_does_not_break_integration_collection` is `assert True`. Delete it, or make it assert something real.
- **Test modules import from conftest.** `test_r_snapshot_detects_another_worktree_change` and `test_r_snapshot_ignores_change_inside_p_under_worktrees` import `RSnapshotter` from `tests.integration.conftest`. The plan's Test Layout says fixtures are never imported from test modules. `r_snapshot` is also bound to the default `sibling` placement, so later WPs cannot snapshot an `under_worktrees` P through the fixture. Consider a factory variant (`make_r_snapshot(checkouts)`).
- **`Any` return types.** `_require_owned_claim` and `_resolve_owned_directory` are typed `-> Any`. `OwnershipClaim`, and `tuple[<mission type>, Path]`, can be named under `TYPE_CHECKING` without breaking the cold-import boundary.

## What already passes (no rework)

- **Red-first.** Checked in a scratch worktree at 4c3dd3a3b, with the new names stubbed so the tests collect:
  - These are genuinely red on the pre-fix minter: `test_returns_validated_fact` (all three handle kinds), `test_next_topologies_accept_lanes_with_coord`, `test_next_topologies_accept_lanes` and `test_repository_root_is_refused`.
  - The controls and pins are green.
- **Topology sets.** `LIFECYCLE_OWNED_TOPOLOGIES = {single_branch}`. `NEXT_OWNED_TOPOLOGIES` contains `single_branch`, `lanes`, `lanes_with_coord` and `coord`. Both directions are tested on the same fixtures.
- **Refusal pins.** `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` and `OWNED_CHECKOUT_IS_MISSION_WORKTREE` (for a lane and for a coordination worktree, with the P-under-`.worktrees/` control) are pinned. So are a missing path and a directory outside any repository, both giving `OWNERSHIP_BROKEN_POINTER`, and `R/docs`, giving `OWNERSHIP_NESTED`.
- **Minting.** `_mint` is called only from `owned_mission.py`: once in `resolve_owned_mission` and once in the sanctioned transitional factory.
- **`OwnedCreateRoot`.** It is frozen, constructed through a private token, and its field names avoid the names gate G5 bans. It makes exactly one claim call.
- **Transitional markers.** `TRANSITIONAL(WP18)` appears 3 times in `owned_mission.py` and 2 times in the minter tests, matching the DoD.
- **Annotation retype.** It is annotation-only. After ruff-formatting the base version, a diff of each of the 10 files shows only the `OwnedMission` → `OwnedCheckout` import and annotation changes. The other churn is the format gate: 6 of those files were unformatted on the base.
- **efddfa9c8.** Every re-pointed fixture keeps its assertions. The `dataclasses.replace` mismatch cases still vary exactly one guarded dimension each (the checkout root or the slug), so the guard stays non-vacuous.
- **Fixtures.** `r_snapshot` covers the working tree including ignored files, HEAD, the index, the lock root and `SPEC_KITTY_HOME`. It excludes exactly P's subtree and requests `canonical_home`. `stale_root_copy` writes a genuinely different `lanes.json` and has the `different_id` and `with_lanes` variants. `hash_tree` prunes `.git` and the excluded subtree.
- **mypy `--strict`.** One invocation over the minter, `checkout_ownership` and the 10 retyped files reports 14 errors. The base at 4c3dd3a3b reports the identical 14 errors, so this WP adds none.
