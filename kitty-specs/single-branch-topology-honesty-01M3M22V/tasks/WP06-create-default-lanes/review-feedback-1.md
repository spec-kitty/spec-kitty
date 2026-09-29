# WP06 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** Two blast-radius misses. The flip itself is correct and well tested (see "Verified").

## Blocking

**Issue 1: `tests/specify_cli/test_specify_topology_flag.py::test_specify_omitted_topology_on_non_primary_branch_derives_single_branch` is now red. It is green on base 7f623086.**

- **What the test pins.** The pre-WP06 behaviour: `spec-kitty specify` (the `lifecycle.py` entry point, not `agent mission create`) with no `--topology` on a non-primary branch writes `topology: single_branch`. It goes through the same `_resolve_default_topology_phase`, so it now gets `lanes`.
- **Evidence.** I ran the same 16 blast-radius files on both commits: base shows 195 passed and 0 failed; HEAD shows 202 passed and 1 failed (this test). The implementer's grep missed this entry point.
- **Required fix.**
  - Re-pin it the same way as the other two edits: rename it `…derives_lanes`, assert `meta["topology"] == "lanes"`, and keep the no-`coordination_branch` assertion.
  - Update its docstring to cite #2602 and the #5100 binding decision.

**Issue 2: the `spec-kitty specify --topology` help text (`src/specify_cli/cli/commands/lifecycle.py:178-180`) still says "single_branch on a non-primary feature branch".**

- That is now false, user-facing text on a sibling command that shares the same derivation.
- **Required fix.** Mirror the new `mission_create.py` help text: "…coord on the primary branch or with --pr-bound when coordination is reachable; lanes otherwise. single_branch only when requested explicitly (or via --owned-checkout)." This is an out-of-map edit; add a one-line rationale in the Activity Log.

## Non-blocking

**Nit 3: `--owned-checkout` is a behaviour change, not preservation. Say so, and pin it at the CLI.**

- **Probe.** I cloned `tests/agent/test_agent_feature.py::test_owned_checkout_creates_mission_in_real_linked_worktree` and dropped `--topology single_branch`. That is a real `agent mission create --owned-checkout <linked> --json` through CliRunner.
  - On **base** it writes `topology: coord`.
  - On **HEAD** it writes `topology: single_branch`.
- **So the new `owned_checkout` parameter is justified.** Owned mode is single_branch-only (ADR 2026-09-03-1), so HEAD's behaviour is the right one. But the premise "previously got single_branch implicitly via the non-primary arm" does not hold for this fixture; it minted coord.
- **Required follow-up.**
  - Correct the matrix test's docstring and the Activity Log.
  - Add that CLI-level case as a pinned test (no `--topology` + `--owned-checkout` → `meta.json` `topology: single_branch`), so the short-circuit is protected end to end and not only at the unit level.
  - The unit row's red is a TypeError because the parameter is new; that is acceptable given the CLI-level behaviour red above.

## Verified

- **Red→green.** At 6b8c0b01 the two LANES matrix rows fail on assertions (`SINGLE_BRANCH == LANES`). The owned row fails with a TypeError (a new parameter; see Nit 3). Both `test_coord_topology_no_strand` tests and the `test_mission_create` feature-branch test fail on `'single_branch' == 'lanes'`. All pass at HEAD.
- **Other arms unchanged.** The matrix rows for primary → COORD, pr-bound reachable → COORD, unresolvable repo → COORD, and explicit single_branch / lanes all pass at both commits.
- **Pinned-test edits are legitimate.** `test_coord_topology_no_strand.py` now positively asserts `payload["topology"] == "lanes"`; it did not merely lose an assertion. The no-coord-branch assertions are kept. `test_mission_create.py` adds a stored-`meta.json` check.
- **Help text and docstring.** `mission_create.py`'s help and docstring carry no generic `main`.
- **Mutation.** Removing the `owned_checkout` short-circuit is caught by the `owned_checkout_no_topology` matrix row.
- **Blast radius.** 16 named files were run on HEAD and base. The only new red is Issue 1.
  - Files: the matrix, no_strand, mission_create, specify_topology_flag, mission_creation_placement, make_mission_parity, issue_2684, research_templates, issue_matrix_partition, issue_4888, mission_create_phases, json_remediation, golden_contract, test_agent_feature, checkout_restore, selector_resolution.
