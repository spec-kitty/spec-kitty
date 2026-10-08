---
affected_files: []
cycle_number: 1
mission_slug: upgrade-migration-commit-scope-01M4AKVE
reproduction_command:
reviewed_at: '2026-10-07T14:58:26Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

# WP03 review feedback, cycle 1 (reviewer-renata)

Verdict: **changes requested**. The `config.yaml` part of #5673 is fixed and well tested: red-first is real, and all 12 mutants I planted were killed. But the fix drops a path the claim itself writes, and that breaks claims on lanes and coord topologies.

## MAJOR 1: the claim writes the WP prompt on lanes and coord topologies, and the fix stops committing it

On base `d3b1b0679`, workspace allocation during `spec-kitty implement` stamps `base_branch`, `base_commit` and `created_at` into the claimed WP's frontmatter. See `src/specify_cli/frontmatter.py:331-334`: "Only `base_branch`/`base_commit`/`planning_base_branch` are still genuinely written, and only once, at workspace-creation time." This is the claim's own write. The "0 runtime bytes" statement in the WP prompt is true only for the `shell_pid` claim triple. On `single_branch`, the repo-root lane, no stamp is written, which is why the WP's CLI cases (single_branch only) never saw it.

`claim_commit_paths` (`implement_claim.py:168-180`) now leaves that write out. I measured this on real git with the `_implement_fixtures` lanes mission, comparing base and fix:

| scenario (lanes) | base | eb20dc7d1 |
|---|---|---|
| first `implement WP01` | claim commit = meta + status pair + `tasks/WP01-test.md`; tree clean | claim commit = meta + status pair; **`tasks/WP01-test.md` left modified** |
| then `implement WP02` | claim commit includes WP02's stamp; clean | an extra `chore: planning artifacts` commit sweeps WP01's stamp; WP02's stamp is left dirty |
| `--no-auto-commit` | all 4 staged, nothing unstaged | WP01 prompt **unstaged**, so "changes staged only" is false (#3471 contract) |

Tests outside the owned files that go red at `eb20dc7d1` and are green at `d3b1b0679`:

- `tests/specify_cli/cli/commands/test_implement_no_auto_commit_consecutive_claims.py::test_the_claims_own_writes_are_staged_as_the_message_says`
- `tests/specify_cli/cli/commands/test_implement_no_auto_commit_consecutive_claims.py::test_an_ignored_claim_file_is_staged_with_the_rest_like_the_auto_commit_would_commit_it`
- `tests/specify_cli/cli/commands/agent/test_workflow.py::TestImplementReceiptsNameRealBranch::test_coordination_mission_receipts_all_carry_a_contained_sha`
- `tests/specify_cli/cli/commands/agent/test_workflow.py::TestImplementReceiptsNameRealBranch::test_target_branch_receipt_names_the_target_branch_not_coordination`
- `tests/characterization/test_trio_json_envelope.py::TestAgentActionImplementTextEnvelope::test_coord_mission_prompt_skeleton`
- `tests/specify_cli/cli/commands/agent/test_issue_2508.py::TestIssue2508IdentityReadAnchorsOnPrimary::test_claim_succeeds_through_coordination_transaction_despite_drifted_coord_husk`

The four coord failures are user-visible. `spec-kitty agent action implement WP01` on a coord mission now exits 1 with `Failed to record planned -> claimed for WP01 via BookkeepingTransaction: safe_commit ... refusing to stage path under .worktrees/: .worktrees/<slug>-coord/kitty-specs/<slug>/tasks.md`. The coord claim commit is now skipped or meta-only, so the stamped primary WP prompt stays dirty, and the workflow executor's follow-up transaction then trips the #3784 guard.

Proof of cause: in a scratch copy of `eb20dc7d1` I appended the claimed WP's prompt to the list in `_commit_wp_claim_status`. With that change all six tests and the full #3471 module pass (18 passed).

The WP's own Risks section says to escalate rather than silently drop a claim-written path. Deviation (f) instead edited `destroy_lane` (`test_implement_characterization.py:613-616`) to commit "the fixture's WP prompt edit". That edit is the product's own stamp, so the fixture change hides the regression. Revert it.

**Fix direction (needs a planner/spec decision first, because FR-009 and US4 literally say "never the WP prompt"):** the rule should be "exactly what the claim wrote". Thread a third fact from `allocate`, alongside the `meta.json` pair: whether workspace creation stamped the claimed WP's prompt in this run, and whether that file was clean before. Include the prompt only when the claim wrote it and it was clean. Escalate the FR-009 wording to the planner. Then add CLI-level cases on a **lanes** mission (first claim: exact set includes the stamped prompt and the tree is clean afterwards; `--no-auto-commit`: nothing unstaged), and run the six tests above.

## MINOR 2: case 2 docstring says it is red on base; it is green

`test_implement_claim_scope_5673.py:113-114` says "Red on the base too: the WP file is in today's bundle." At `c3b85ede5` this case passes, because on single_branch the WP file is unchanged and adds nothing to the commit. Only cases 1, 3, 4 and 5 are red (RED is otherwise genuine: content assertions, exit 0). Fix the docstring. A positive control being green on base is fine.

## MINOR 3: no CLI coverage off `single_branch`

Every CLI-level case runs on `single_branch`, the one topology where the claim writes no WP stamp. This is why MAJOR 1 got through. Add at least one lanes CLI case, and one coord case if the coord harness (`tests/characterization/test_trio_json_envelope.py::_build_mission_repo(coord=True, materialize_coord=True)`) allows it.

## NOTE 4: from the user's view, the fix only fully holds for `config.yaml`

In the same `spec-kitty implement` run, `commit_planning_artifacts` (out of scope, C-003) still commits operator edits to `tasks.md`, other WP prompts and `meta.json`, as a separate `chore: planning artifacts for <mission>` commit before the claim. This happens on both base and fix, staged or unstaged. So the new "meta.json dirty before claim" warning cannot be reached from the CLI: the planning commit makes `meta.json` clean before the probe runs. Record this in the Activity Log and the follow-up issue. It is not a blocker for this WP.

## Deviations (a)–(h)

- (a) dead `wp_file` param: acceptable, because an external caller passes it (`test_issue_610:103,148`). It may become live again under MAJOR 1.
- (b) passing the raw flags and combining them in `_commit_wp_claim_status`: accepted. The warning needs the raw `meta_written`.
- (c) case 1 covers only the config: accepted. Unrelated staged or untracked work is covered at the seam (case 4).
- (d) integration/git_repo marks: accepted, because the module-level `pytestmark` forces them.
- (e) skipping an empty `git add`: accepted.
- (f) `destroy_lane` change: **rejected**; see MAJOR 1.
- (g) the leaked-path change in `test_claim_commit_reraises_path_policy_error`: accepted. It still drives the real guard.
- (h) `tasks.md` bytes: I verified them myself. They are unchanged by a real first claim on both lanes and single_branch.
