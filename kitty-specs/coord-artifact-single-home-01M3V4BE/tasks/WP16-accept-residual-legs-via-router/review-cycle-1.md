---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T04:50:22Z'
reviewer_agent: claude
wp_id: WP16
---

# WP16 review (reviewer-renata, cycle 1): CHANGES REQUESTED

Lane head reviewed: `e650f071fd` (base `7f8e73218f`).

The coordination half is correct and is a real fix. In a probe with a MATERIALIZED `coord` Mission on `topic`:
- **Base:** raw-committed the stale root `status.events.jsonl` onto `topic` (R7). On a coord Mission whose target is protected `main`, it raw-committed `meta.json` plus the stale status log onto protected `main`.
- **HEAD:** neither happens. The coordination-only dirt still lands on the coordination branch.

Also correct:
- The gate and the committer now share one predicate. `partition_for_mission_path` is exactly the old `is_coord_residue_churn(path, mission_slug=...)` call, and it stays gated by `_mission_routes_through_coordination`, so verdicts for `lanes`/`single_branch` are unchanged.
- Diff coverage is 100% (60/60).

The PRIMARY leg, however, changes behaviour for non-coordination Missions and breaks 7 existing accept tests that are green at base.

## Blocking

### B1. Regression: the PRIMARY residual leg now commits to `meta.target_branch` instead of where accept's own meta commit lands (C-008; 7 tests red, all green at `7f8e73218f`)

Red on the lane, green at base:
- `tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_command_reports_approved_wps_without_closing`
- `tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_does_not_require_done_evidence_for_approved_wp`
- `tests/specify_cli/acceptance/test_accept_idempotency.py::test_accept_converges_on_unchanged_tree[commit]`
- `tests/specify_cli/cli/commands/test_accept_merge_commit.py::test_accept_pr_mode_records_verified_merge_as_baseline`
- `tests/specify_cli/cli/commands/test_accept_merge_commit.py::test_accept_single_parent_landing_needs_attestation`
- `tests/specify_cli/cli/commands/test_accept_normalize_encoding.py::test_normalize_encoding_real_commit_mode_ignores_own_backup`
- `tests/specify_cli/cli/test_accept_birth_cutover.py::test_squash_merge_after_accept_lands_cut_over_corpus`

**Shape.** All 7 share the shape of the 4 fixtures you re-pinned: HEAD = `kitty/mission-<slug>` and `meta.target_branch` = `main`. The failure is either `✗ primary (main): refused — …meta.json: PROTECTED_BRANCH_REFUSED` or `…meta.json: error`. The second one is `SafeCommitHeadMismatch`.

**Mechanism.**
- `perform_acceptance` (`acceptance/__init__.py` ≈L1734-1770) still raw-commits the accept `meta.json` on the current HEAD whenever HEAD is unprotected.
- The new `_run_residual_acceptance_commit` sends the PRIMARY residuals through `commit_for_mission`, which targets `get_feature_target_branch` = `meta.target_branch`.

**Effect.** For a `lanes` Mission (no coordination surface) run from a branch other than its `target_branch`, the result is:
- the acceptance commit lands on HEAD;
- the residual commit is refused;
- accept exits 1 with a split state.

At base both commits landed on HEAD. Reviewer probe E (`lanes`, target `topic`, HEAD `other`): base `created=True` on `other`; HEAD raises `TaskCliError`.

**The re-pins.** The design-decisions entry calls these 4 re-pins "latent fixture bugs". But 11 fixtures across 6 files model this exact flow, and the meta commit still honours it. This is a supported flow being changed, not latent fixture drift. Choose one, and get it ruled if needed:
- **(a)** The PRIMARY group commits where accept's meta commit commits (HEAD when unprotected; protected primary keeps the router's refusal), so `lanes`/`single_branch` behave as before (C-008).
- **(b)** Obtain an operator ruling that accept must run on `target_branch`. Then add an explicit up-front preflight refusal before any commit, with an actionable message, so there is no split state. Move the meta commit onto the same rule, and re-pin all 11 fixtures under that ruling, citing it.

The current state matches neither option.

### B2. The residual refusal drops the actionable diagnostic (rule d)

`_run_residual_acceptance_commit` builds its error text with `"; ".join(render_commit_outcome(result)) or result.diagnostic`. For an `error` surface with named paths, `render_commit_outcome` prints only `path: error`. So the message the operator sees is:

`✗ primary (topic): refused — kitty-specs/<m>/meta.json: error`

The real diagnostic is lost:

`safe_commit: … HEAD is 'other', expected 'topic'. Run git -C … checkout topic first.`

The reviewer probe shows the diagnostic is present on `result.surfaces[0].diagnostic`.

Fix:
- Append each refused/error surface's `diagnostic` to the `TaskCliError` text.
- Add a test with a HEAD-mismatch error surface that asserts the checkout instruction appears.

### B3. The refusal arm prints rendered outcome text through Rich markup, and its JSON loses structured surfaces (rule c)

- The `TaskCliError` text, which contains `render_commit_outcome` lines and diagnostics, reaches `_report_error` (`accept.py` ≈L825-837). That prints `f"[red]Error:[/red] {message}"` and `tracker.error(step, message)` with markup enabled.
- Reviewer probe: `_report_error(False, "… git said [/red]")` raises `rich.errors.MarkupError`.
- Fix: `escape()` the message in both the console line and the tracker. WP10 cycle 2 established this pattern.
- On `--json`, the failure arm prints `{"error": message}`. The per-surface outcome is only flattened into that string. Carry `residual_commit.surfaces` (via `commit_outcome_payload`) on the failure arm too. For example, raise a small exception that carries the `CommitRouterResult` and let `_raise_on_finalize_errors` add the payload.
- Add tests for both.

### B4. The `write_seam.py:55` docstring still names `_commit_coord_residuals` as "the canonical example" caller

That function no longer exists, and accept no longer calls the write seam at all. This was a declared, binding out-of-map edit for this WP. Make the one-line fix: drop the accept example, or name the remaining real callers.

## Non-blocking
- **N1. Red-first.** `a2dd6c1365` is red at base only because of the collection-time `ImportError`. With the import removed, the 3 R-tests still fail at base only with a `NameError` on `_run_residual_acceptance_commit`. So the committed tests never ran red behaviourally at base. My probe G (R7, a stale root status log landing on the target) and probe H (a raw commit onto protected `main`) confirm the real base defects. Record this as a process finding.
- **N2.** `CoordinationBranchDeleted` (a `StatusReadPathNotFound`, not an `ActionContextError`) still escapes `_stamp_step`'s except tuple, which runs inside a `finally`. Accept then crashes with a traceback and the residual commit is skipped. This is unchanged from base, which raised the same error from `resolve_artifact_surface`/`_coord_dirty_paths`, and it is the pinned fail-loud contract. It is acceptable here; it is a candidate for WP21/WP20 to turn into a structured refusal.
- **N3.** The protected-target behaviour change itself is consistent:
  - For a protected primary, `perform_acceptance` already routes the meta commit through the router, where the PRIMARY_METADATA rule 3 refuses, so accept already exited 1 at base.
  - WP16 only stops the follow-up raw commit onto protected `main`.
  - The `single_branch` minted-mission-branch flow and the `--commit-to-target` flow both commit exactly as at base (probes A/B).

## Verified OK
- **Gates and dead-symbol:** `partition_for_mission_path` is in `__all__` with a cross-module caller; the dead-symbol gate reports only `COORD_SEED_TRAILER`.
- **Mutation:** removing the `_run_residual_acceptance_commit` raise is caught by 2 tests.
- **Gate/committer predicate:** C-008-neutral (same predicate as before, still topology-gated).
- **`_coord_status_feature_dir` switched to `write_dir`:** reached only on the commit-required path, so `--no-commit`/`--diagnose` stay read-only.
- **Ledger:** the ledger test is real work under every topology.
- **Static checks:** ruff and format are clean. C901 ≤ 15. mypy shows 4 errors, the same as base.
