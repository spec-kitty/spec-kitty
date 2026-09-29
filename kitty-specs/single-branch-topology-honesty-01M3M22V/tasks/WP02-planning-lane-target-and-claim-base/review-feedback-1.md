# WP02 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The core design is sound. The naming split, the claim-base module, the lane-keyed routing and the architectural gate are all correct. Red to green is proven, and the targeted suite is green (204 passed). Two problems block approval:

- The new claim-base wiring has no test at its production call sites.
- One out-of-map edit introduced a crash.

## Blocking

**Issue 1: the claim-base wiring is untested at every production call site (anti-pattern #4 FR coverage; Sonar new-code / diff-cover ≥90%).**

`tests/lanes/test_issue_5100_planning_lane_ref.py` records the claim base with a raw `git update-ref`. `tests/lanes/test_claim_base.py` only unit-tests the module. As a result, you can delete any of the following and no test fails:

- `lanes/implement_support.py:147`, the `record_claim_base(...)` call in the planning arm of `create_lane_workspace`;
- the `record_claim_base(...)` call in the repo-root arm of `orchestrator_api/commands.py::_resolve_start_workspace` (~:1373);
- the three `_clear_claim_base_on_terminal(...)` calls in `coordination/status_transition.py`, at :544 (primary fallback), :577 (coord fallback) and :1587 (transactional).

Add focused tests that drive the real seams:

- **(a) Implement records the claim base.** `create_lane_workspace` for a planning-lane WP records `refs/spec-kitty/wp-base/<slug>/<WP>` at write-checkout HEAD. A second call does not move it.
- **(b) The orchestrator records the claim base.** `_resolve_start_workspace` for a planning-lane WP returns `workspace_path == repo_root` and records the ref. `_resolve_existing_workspace` does NOT record it.
- **(c) Terminal transitions clear the ref.** An `emit_status_transition_transactional` (or fallback) transition to `done` clears the ref. So does a transition to `canceled`. A non-terminal transition, for example to `for_review`, leaves it intact. Cover at least the primary-fallback arm and the transactional arm.
- **(d) The missing-ref fallback refuses.** When the claim-base ref is absent, `evaluate_for_review_gate` REFUSES even with a qualifying implementation commit on HEAD. The WP's own Risks section says "a test pins it", and none does today. See `for_review_gate.py:181`.
- **(e) The allocator and predictor refuse the planning lane.** `predict_lane_worktree(..., PLANNING_LANE_ID)` and `allocate_lane_worktree` for a planning-lane WP raise `ValueError("repo-root lane has no worktree")` (`worktree_allocator.py:551`).

**Issue 2: `git/sparse_checkout.py:232` regression, where `code_lane_branch_name` crashes on a `<slug>-lane-planning` worktree dir.**

- **Cause.** `_ManagedLanePolicy.expected_branch_for` passes whatever `lane_id_for_worktree_dir` parses. `_LANE_ID_RE = lane-[a-z]+` matches `lane-planning`, so a registered, sparse-active `.worktrees/<slug>-lane-planning` directory now raises `ValueError`. That directory is exactly the phantom path #5100 is about. Before this change the method returned `"main"`, so the state was classified `UNKNOWN`.
- **Reproduction.** `_ManagedLanePolicy('demo-01KZZTES', frozenset()).expected_branch_for(Path('.worktrees/demo-01KZZTES-lane-planning'))` raises `ValueError`.
- **Impact.** This path feeds `scan_repo` / `require_no_sparse_checkout` / `warn_if_sparse_once`, which 17 production call sites use as a preflight. A preflight must not crash with a raw `ValueError`.
- **Required fix.** Return `None` (which classifies the state as UNKNOWN) when the parsed lane id is the planning lane, via `is_planning_lane` / the lane-id check. Add a regression test. This edit was supposed to be mechanical, so it must not change behaviour into a crash.

## Non-blocking (nits; fix if cheap, otherwise note in the Activity Log)

**Nit 3.** `_clear_claim_base_on_terminal` in the transactional arm (`status_transition.py:1587`) and the coord-fallback arm runs BEFORE the coord commit lands. If the commit fails and the event is rolled back, the ref is already deleted. `_tombstone_lane_workspace_context_on_cancel` has the same ordering, so this is consistent with precedent. Either:

- accept it and add a one-line comment, or
- move the call post-commit, for example into the deferred fan-out.

**Nit 4.** `_fallback_emit_batch` and `emit_status_transition_batch_transactional` do not call the terminal hook. Today the batch door is used only for claim→in_progress (`work_package_lifecycle.py`), so no terminal transition reaches it. Add a one-line comment at the batch door so WP07 does not miss it if a terminal batch is ever introduced.

**Nit 5.** `predict_lane_worktree` compares `lane_id == PLANNING_LANE_ID`, and `branch_naming` duplicates the literal as `_PLANNING_LANE_ID`. The duplication is justified by a circular import and is acceptable. Still, WP03's `is_repo_root_lane` rename must update both spots, so flag it in WP03's prompt/notes.

**Nit 6.** The ruff-format drift in `context/resolver.py` and 4 test files predates this WP: I confirmed the base versions are also unformatted under the repo config. It is not a WP02 defect, but CI runs `ruff format --check .` over the whole repo. Consider a separate campsite commit.

## Verified OK

- Red→green: at c14a48f9 there are 3 failures, all on assertions (predict_lane_worktree asked for the planning lane; a `branch 'main' does not resolve` WARNING; no TypeError). At HEAD, 3/3 pass.
- `lane_branch_name(..., *, target_branch)` is required. Every src caller passes a manifest/meta-derived target, and none passes a guessed `"main"`.
- `code_lane_branch_name` raises for the planning lane.
- The gate counts only non-status paths and never passes when the ref is missing (code-verified; see Issue 1(d) for the missing test).
- Routing is lane-keyed, not WP-kind keyed.
- No topology or single_branch leakage.
- The architectural gate has a floor of 5, a self-mutation test and no allowlist.
- The out-of-map edits are mechanical keyword renames except for sparse_checkout (Issue 2). That covers `consolidation.py`, `core/worktree_topology.py`, `context/resolver.py`, `compute.py` and 26 test files.
- The recovery.py rationale (commit b0457d89) is accepted.
- The implementer's pre-existing failure claim is confirmed: the same 10 failures occur on the base and on the lane, tracked by #5044 except test_handle_equivalence_matrix, which has no tracking issue.
