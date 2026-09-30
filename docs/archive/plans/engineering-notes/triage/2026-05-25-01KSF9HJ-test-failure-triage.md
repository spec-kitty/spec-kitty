---
title: Mission 01KSF9HJ — Test Triage (WP01)
description: 'Test triage (WP01, 2026-05-25) for mission 01KSF9HJ: root-cause clustering of the full pytest-suite failures against main HEAD.'
doc_status: deprecated
updated: '2026-05-29'
---
# Mission 01KSF9HJ — Test Triage (WP01)

**Triaged:** 2026-05-25 (this WP)
**Baseline:** `main` @ HEAD, full pytest suite (`pytest tests/`)
**Source artifacts:** `/tmp/01KSF9HJ-baseline.xml` (junit), `/tmp/01KSF9HJ-baseline.txt` (raw output)
**Totals:** 249 failed · 19,375 passed · 71 skipped · 18 xfailed · 1 xpassed (924s / 15m24s)

This document is the canonical triage referenced by FR-001 / FR-002 of mission
`test-stabilization-and-debt-pass-01KSF9HJ`. It buckets every failing test by
**root cause cluster**, names the owning WP, and flags items that DIR-013 says
must be filed as separate GitHub issues (pre-existing failures that this
mission will not fix).

---

## Cluster summary

| Cluster | Count | Root cause | Owner WP | DIR-013 issue? |
|---|---:|---|---|---|
| **C1 – Shared-package events drift** | **98** | Installed `spec_kitty_events==5.0.0` is missing modules (`project_lifecycle`, `build_lifecycle`, symbols `MissionOriginBoundPayload`, `LOCAL_ONLY_EVENT_TYPES`) that the codebase imports. The package boundary cutover landed code that targets a newer events package than what `uv.lock` currently pins. | WP02 (sync events fix) | Yes — file once for the umbrella drift |
| **C2 – Snapshot / lockfile drift** | 4 | `tests/contract/snapshots/spec-kitty-events-5.2.0` snapshot missing; `__version__` 5.0.0 vs uv.lock 5.2.0 — same root cause as C1 (events package mismatch). | WP02 | (Same issue as C1) |
| **C3 – Cascade `JSONDecodeError`** | 21 | CLI subcommands fail to start because of C1, so their stdout never produces JSON. Cascade; resolving C1/C2 will eliminate these. | WP02 (verifies after fix) | No |
| **C4 – `.pytest_cache` ENOENT** | 12 | Tests that probe `.pytest_cache/...` directories that aren't pre-created when the fixture runs in isolation. Local flake, ordering-sensitive. | WP03 (surgical fixes) | No |
| **C5 – `src/specify_cli/missions/software-dev/command-templates/checklist.md` missing** | 9 | Template file deleted but `test_command_template_cleanliness` and the codex skill renderer still expect it. Two co-symptoms: cleanliness test + no-checklist-surface guard. | WP03 | No |
| **C6 – File-name-too-long OSError** | 2 | `.pytest_cache/.kittify_update_idempotent_…` filenames exceed OS limit on Linux ext4 in CI fixtures. | WP03 | No |
| **C7 – `charter_source missing` cascade** | 7 | Multiple CLI integration tests call `charter sync` paths without first running `charter sync`; harness change reveals stricter ordering. | WP03 | No |
| **C8 – Stray `click.Exit: 1`** | 4 | Mostly C1 cascade (CLI fails to import → returns 1). | WP02 | No |
| **C9 – `_SYMBOL_ALLOWLIST` stale entries** | 1 | New callers found for symbols previously listed as orphans — guard test wants them removed from allowlist. | WP03 (1-liner) | No |
| **C10 – Legacy agent profiles path** | 1 | `src/charter/extractor.py` still references the pre-rename hyphenated agent profiles directory. | WP03 | No |
| **C11 – Pytest marker convention** | 1 | One test file declares the wrong marker per the marker convention guard. | WP03 | No |
| **C12 – `lanes.json is required`** | 1 | Bulk-edit planning test expects a warning in CLI output that's no longer emitted. | WP03 | Yes — file (deferred; expected-message drift) |
| **C99 – Genuine pre-existing failures** | **90** | See breakdown below. These are NOT cascades of C1; many predate this mission and are owned by other features. | mixed | **Yes — DIR-013 batch** |

**Total: 249 failures** accounted for across 13 clusters.

---

## C99 sub-clusters (90 genuine pre-existing failures)

These are NOT environment cascades. They surface real product/code state and
fall into the following sub-buckets. Per **DIR-013**, every C99 entry MUST get
a GitHub issue (one issue per sub-cluster, not per testcase).

### C99-a — Twelve-agent parity drift (24 failures)

`tests/specify_cli/regression/test_twelve_agent_parity.py` — every
`implement-<agent>` and `tasks-finalize-<agent>` snapshot diverges from the
rendered command file. Cause: `src/specify_cli/missions/software-dev/command-templates/implement.md`
or `tasks-finalize.md` has changed since the last snapshot refresh, but the
parity test was not re-baselined.

- **Status:** Pre-existing (template was edited multiple times across the
  recent missions without snapshot refresh).
- **Owner:** WP03 (snapshot refresh) **OR** file as a single issue per
  DIR-013 if WP03 decides the refresh is out of scope. **Recommended:**
  WP03 will refresh — these are not external bugs, they are snapshot
  bookkeeping.

### C99-b — Twelve-agent parity TOML syntax (2 failures)

`test_toml_command_output_is_parseable[implement-gemini]` and `[implement-qwen]`
— rendered TOML at line 146 col 68 has an unescaped backslash. Real bug,
introduced by a recent template edit.

- **DIR-013 issue:** **YES** — file separate from C99-a (real bug, not
  cosmetic snapshot drift).

### C99-c — `finalize-tasks` bootstrap regressions (7 failures)

`tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap.*` —
typed frontmatter migration, ownership manifest, bootstrap-stats JSON, and
WP01 regression coverage all failing.

- **Status:** These appear to be tests for a half-landed change. Linked to
  WP12 (FR-015 fix-locks for finalize-tasks).
- **Owner:** Already in scope of **WP12** which is **already APPROVED**;
  these tests will be revisited as part of WP12's lockdown.
- **Action:** Re-run after WP02/WP03 land. If they still fail, file an
  issue under WP12's umbrella.

### C99-d — Charter synthesizer hash mismatch (5 failures)

`tests.charter.synthesizer.test_bundle_validate_extension`,
`test_manifest`, `test_path_guard`, `test_chokepoint_coverage`,
`test_bundle_validate_cli` — synthesizer manifest hashes drift (stored vs
computed), direct write primitives leaking outside `path_guard.py`, and
chokepoint coverage gap.

- **Status:** Real charter-context bug. Manifest hash mismatch implies
  generator output is non-deterministic OR fixtures are stale.
- **DIR-013 issue:** **YES**. Owned by the charter context maintainers,
  not by 01KSF9HJ.

### C99-e — Doctrine / glossary integrity (4 failures)

- `tests.doctrine.test_glossary_link_integrity` × 2 — missing anchors
  `doctrine-pack`, `platform-darwin--platform-linux` in glossary contexts.
- `tests.doctrine.test_tactic_compliance` × 2 — `five-paradigm-parallel-debugging`
  tactic schema invalid + unresolved refs.

- **DIR-013 issue:** **YES**. Pure doctrine debt; file one issue.

### C99-f — `next` command exit-code regressions (4 failures)

`tests.next.test_next_command_integration.test_blocked_result_exit_code`,
`test_terminal_state_exit_code_zero`, `test_advancing_mode_with_result_…`,
`tests.next.test_query_mode_unit.test_result_success_calls_decide_not_query`.

Pattern: `assert 1 == 0` — the `next` CLI is returning 1 in scenarios that
previously returned 0, and `decide_next` mocks are no longer invoked.

- **DIR-013 issue:** **YES**. This is real `next` behaviour drift,
  separate from anything in scope.

### C99-g — Status / lifecycle event drift (varies; merged into C1 above for the events package failures, but ~6 here are NOT C1)

- `tests.git_ops.test_atomic_status_commits_unit` — status artifacts left dirty after move_task (real bug in atomic commit flow).
- `tests.specify_cli.core.test_mission_creation_specify_started` × 2 — `SpecifyStarted` event not emitted at mission-create (#1067 regression).
- `tests.tasks.test_move_task_git_validation_unit.test_move_for_review_from_worktree_does_not_mirror_commit_to_lane_branch` — wrong commit message bubbled up to lane branch.
- `tests.integration.test_status_emit_on_alloc_failure` — implement does not block when alloc fails.

- **DIR-013 issue:** **YES**. Real status/lifecycle drift; file one issue for the cluster.

### C99-h — Charter integration / runtime walk (6 failures)

- `tests.integration.test_charter_lint_lints_all_layers` — org-layer source name missing in lint output.
- `tests.integration.test_charter_synthesize_fresh::test_synthesize_without_charter_md_fails_actionably` — wrong error class surfaced.
- `tests.integration.test_documentation_runtime_walk::test_full_advancement_through_six_actions` — `discover` action blocks despite `spec.md` being authored.
- `tests.integration.test_implement_review_retrospect_smoke::test_reject_fix_next_retrospect_smoke` — smoke fails.
- `tests.integration.test_rejection_cycle::test_implement_uses_review_cycle_artifact_after_review_claim` — wrong branch reported in handoff.
- `tests.integration.test_specify_plan_commit_boundary::test_setup_plan_commits_substantive_plan` — substantive plan not auto-committed.

- **DIR-013 issue:** **YES**. Integration suite has real failures.

### C99-i — Sync daemon / origin / contract (8 failures)

- `tests.sync.test_daemon_intent_gate::test_no_unauthorized_daemon_call_sites` — `src/specify_cli/sync/restart.py` is an unauthorised caller; needs allowlist + WP04 audit row.
- `tests.sync.test_lifecycle_readiness::test_init_emits_project_init_event_offline` — `BuildRegistered` not queued at init.
- `tests.sync.tracker.test_origin_integration.test_event_queued_when_no_websocket` — `MissionOriginBound` not queued.
- `tests.contract.test_cross_repo_consumers::test_spec_kitty_events_module_version_matches_resolved_pin` — version drift (C1/C2 dup).
- `tests.contract.test_events_envelope_matches_resolved_version::test_resolved_version_snapshot_exists` — missing snapshot dir for 5.2.0 (C1/C2 dup).
- `tests.contract.test_handoff_fixtures::test_fixture_payload_passes_emitter_rules[WPCreated:01JMBYA1B2C3]` — WPCreated payload missing `actor` / `wp_title`.
- `tests.contract.test_packaging_no_vendored_events::test_vendored_events_tree_does_not_exist_on_disk` — vendored events tree reintroduced under `src/specify_cli/spec_kitty_events`.
- `tests.contract.test_example_round_trip::test_contract_example_round_trip[...check_docs_freshness.md::block-MISSING_FRONTMATTER]` — YAML codeblock missing `# pydantic_model:` frontmatter.

- **DIR-013 issue:** **YES** — sync-related ones tie back to WP02 scope.
- **Owner:** Items mentioning `_SYMBOL_ALLOWLIST`, daemon callers, and
  payload schemas are in **WP02** scope. Items about vendored events tree
  and contract snapshots flag a regression of the shared-package boundary
  cutover; file a DIR-013 issue.

### C99-j — Auth / invocation / docs / minor (30 failures)

The remainder spreads across:

- `tests.auth.integration.test_refresh_through_transport` — auth exit code 2.
- `tests.specify_cli.invocation.cli.test_do`, `test_profiles`, `test_record` — invocation tests fail because of `logged_out_on_connected_teamspace` noise leaking into JSON output.
- `tests.specify_cli.docs.test_readme_governance` × 4 — README missing the `## Governance layer` section.
- `tests.specify_cli.docs.test_trail_model_doc::test_changelog_unreleased_has_both_tranches` — CHANGELOG missing `## [Unreleased - 3.2.0]` block.
- `tests.specify_cli.migration.test_schema_version` — error message wording drift.
- `tests.specify_cli.cli.test_doctrine_cli_removed::test_doctrine_parent_group_is_unregistered` — `assert 0 != 0`; doctrine group still registered.
- `tests.specify_cli.test_codebase_sweep::test_no_direct_meta_json_writes_outside_feature_metadata` — direct `meta.json` writes leaking outside chokepoint.
- `tests.specify_cli.test_lane_regression_guard[src/specify_cli/audit/classifiers/wp_files.py]` — frontmatter `lane` access in audit classifier (pre-060 regression).
- `tests.specify_cli.status.test_wp_metadata::test_all_kitty_specs_wp_files_validate` — 6 WP files in legacy kitty-specs fail Pydantic validation.
- `tests.specify_cli.test_cli.test_map_requirements::test_frontmatter_takes_priority_over_stale_tasks_md` — finalize-tasks refuses to run (already addressed in WP12).
- `tests.init.test_init_minimal_integration::test_init_creates_agents_skills_for_codex` — missing `spec-kitty.checklist` skill package (same root as C5).
- `tests.cross_cutting.test_mypy_strict_mission_step_contracts::test_mission_step_contracts_executor_is_mypy_strict_clean` — mypy --strict failure.
- `tests.architectural.*` and `tests.cli.commands.test_implement_base_flag` and `tests.cli.test_implement_bulk_edit_planning` — base-flag plumbing, bulk-edit warning emission.
- `tests.missions.test_mission_switching_integration` × 2 — switching across mission types blocked.

- **DIR-013 issues:** **YES**. File **per failing sub-area** (auth, docs/CHANGELOG, doctrine-group, codebase-sweep chokepoint, lane regression, WP metadata, mission switching, mypy strict). Recommend **5–7 issues** grouped by feature area, not 30.

---

## DIR-013 issue plan

The orchestrator will file these after WP02/WP03 land (so the issue list
isn't contaminated by C1 cascade noise that will disappear). One issue per
sub-cluster below; total **≈10 issues**:

1. **C2 / C99-i (umbrella):** Shared-package events drift — installed
   `spec_kitty_events 5.0.0` vs uv.lock 5.2.0, missing modules, missing
   snapshot dir, vendored tree reintroduced. (Critical, blocks 101+ tests.)
2. **C99-b:** TOML rendering escape bug — gemini/qwen `implement` TOML
   has unescaped backslash at line 146 col 68.
3. **C99-d:** Charter synthesizer non-determinism — manifest hash mismatch,
   direct writes outside path_guard.
4. **C99-e:** Doctrine / glossary anchor drift + five-paradigm tactic
   schema invalid.
5. **C99-f:** `next` CLI exit-code regressions — blocked/terminal/advancing
   modes all returning 1 instead of expected codes.
6. **C99-g:** Status / lifecycle event drift — `SpecifyStarted` missing at
   `mission create`, atomic commit leaves dirty artifacts, move_task
   commit-message bubbles up wrong message.
7. **C99-h:** Charter integration suite — lint output drift, synthesize
   error class, documentation runtime walk blocked on `discover`, smoke
   tests broken.
8. **C99-j docs:** README missing `## Governance layer`, CHANGELOG missing
   `## [Unreleased - 3.2.0]`.
9. **C99-j chokepoints:** Direct `meta.json` writes outside
   `mission_metadata.py`; frontmatter `lane` access in
   `audit/classifiers/wp_files.py`.
10. **C99-j misc:** auth exit-code, invocation logout noise leaking into
    JSON, `doctrine_parent_group` still registered, mypy --strict failure
    on `mission_step_contracts/executor.py`, mission switching blocked.

---

## Mission-scope action

The triage assigns work as follows:

| WP | Scope after triage |
|---|---|
| **WP02** (sync events fix) | Resolves C1 (98) + C2 (4) + C3 cascade (21) + C8 cascade (4) + sub-items of C99-i marked as in-scope. **Expected delta: ~130 failures green.** |
| **WP03** (surgical fixes) | Resolves C4 (12) + C5 (9) + C6 (2) + C7 (7) + C9 (1) + C10 (1) + C11 (1) + C99-a (24 snapshot refresh). **Expected delta: ~57 failures green.** |
| **DIR-013 issues** | Everything in C99 not absorbed by WP02/WP03. **Remaining open: ~60 failures, filed as ~10 issues.** |
| **WP04** (Wave T closeout) | Confirms post-WP02/WP03 baseline is `≤60` failures and matches the DIR-013 issue plan above. |

Acceptance criterion FR-001 / FR-002: `triage.md` exists and assigns every
one of the 249 baseline failures to a cluster, an owner, and (where
applicable) a DIR-013 issue. ✅ This document satisfies that criterion.
