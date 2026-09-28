# Mission Specification: specify_cli out-of-matrix nightly drift reds

**Mission Branch**: `issue-5258-nightly-drift-reds`
**Created**: 2026-09-28
**Status**: Draft
**Input**: #5258 (nightly `specify-cli-out-of-matrix` leg red, 21 failures in job 108835722806 / run 36393904544; main run 36374561241 also red), folding the overlapping reds of #4916 and #5187.

## Context

The nightly `specify-cli-out-of-matrix` leg runs every `tests/specify_cli/**` tree that no module-matrix row claims. Because nothing gates those trees per-PR, intentional product changes on `main` left their oracles behind. Pre-spec triage (three read-only lenses, one per red group) gave each red a DIRECTIVE_041 verdict with commit evidence. The result: 17 reds are stale tests, 1 is a doctrine defect, 1 is a data (dogfood-corpus) defect, and 5 are an environment dependence (ANSI colour on GitHub runners). One more red outside the leg, `tests/migration/test_verdict_provenance_backfill.py`, has no tracker issue.

### Per-red verdicts (the mission's contract)

| # | Test | Verdict | Cause (evidence) |
|---|------|---------|------------------|
| R1 | `test_doctor_cli_surface_golden::test_registered_command_names_match_frozen_subcommands` | RE-PIN | `doctor decisions` added on purpose (`ed6d34e75`, #4757) |
| R2 | `…::test_subcommand_help_snapshot[coordination]` | RE-PIN | merge→consolidate help wording (`cf295c58a`, #3080) |
| R3 | `…::test_subcommand_help_snapshot[provenance]` | RE-PIN | provenance help rewritten (`e8186a911`) |
| R4 | `test_doctor_coordination::test_apply_missing_worktree_fix_generic_refusal_without_coord_branch_extra` | FIX-PRODUCT + re-pin + new generic case | The `--fix` fallback arm (`_coordination_doctor.py::_apply_missing_worktree_fix`) reclassifies remote-only only when the finding carries a `coord_branch` extra. Without it, the arm relays the exception's text "fetch, then `doctor coordination --fix`", which loops the operator back to the command that just refused and omits `git branch <b> origin/<b>`. This is the loop #5113 exists to prevent. Fix: reclassify on `exc.coordination_branch`. The genuinely generic local-head refusal gets its own test (post-spec squad finding 1). |
| R5 | `test_decision_command_shape_consistency::test_agent_decision_subgroup_has_canonical_visible_subcommands` | RE-PIN | `decision list` added on purpose (`989667221`, #3951) |
| R6 | `…::test_no_non_canonical_decision_command_shape_in_repo_text` + #5187 `test_terminology_guards::test_no_feature_flag_in_live_first_party_docs` | EXEMPT `docs/reports/` (test-side) | Dated report snapshots quote the retired shapes they describe. Rewording them would falsify the record. `docs/reports/` is already classified as immutable snapshots (`ARCHIVE_PATH_PREFIXES`). |
| R7 | `charter_lint/checks/test_orphan::test_orphaned_directive_findings_exact_set` | FIX-PRODUCT (doctrine) | DIRECTIVE_052 (`77bb57e68`) has only outgoing edges, so `charter lint` reports it as orphaned on every consumer install. Its author measured "orphan sets unchanged" against the extractor's pure-orphan notion, not the lint `OrphanChecker`. Fix: a curated `procedure:disciplined-defect-diagnosis --suggests--> DIRECTIVE_052` edge, following the DISCIPLINED_REFACTORING precedent. It stays advisory, pulls in no cascade, and leaves the `requires` histogram unchanged. |
| R8 | `bulk_edit/test_occurrence_map_field_paths::test_governance_occurrences_and_files_match_sc011` | RE-PIN | +1 governance (planner-priti→053, `3e3bcb4da`) (R7 adds a DRG edge, not a profile directive-reference, so it does not move this count: final 101); −2 raw material (final 19) (#5203, `414bbe89b`) |
| R9 | `migration/test_dogfood_corpus_backfilled::test_all_eligible_missions_snapshot_non_empty_and_verify_ok` | FIX-DATA via canonical migration | Two dogfood dossiers were imported un-flipped (`60fffe824`, `52bd6048f`) |
| R10–R14 | `test_mission_close_guard` ×5 | FIX HARNESS | Typer freezes `FORCE_TERMINAL=True` at import when `GITHUB_ACTIONS` is set. The autouse plain-console seam never reached Typer's own console. |
| R15 | `test_mission_type_current_fallback_signal::…prints_loud_cli_warning` | RE-PIN to fail-closed | The warn-and-substitute fallback was removed on purpose (`7a9c35728`, #3831) |
| R16 | `…::test_signal_survives_default_warning_filters` | DELETE (+ campsite) | Guards the retired fallback only. The dead `"using software-dev as default"` print branch in `mission_type.py` is removed with it. R15 gains a repeat invocation, which keeps the "deterministic across repeats" half. |
| R17 | `…::test_unrelated_warning_is_reemitted_while_fallback_still_prints` | RE-PIN (resolvable type) | The re-emit loop is still live |
| R18–R19 | `skills/test_installer::test_coordinated_skill_installation_exact_delta_and_project_precheck[*]` | RE-PIN | The canonical `machine_file_lock` (`c206e7d2d`, #4714) touches the lock file's mtime only |
| R20 | `skills/test_installer_global_reassess_convergence::…without_rebuild_a_concurrent_peer_still_crashes_the_loser` | RE-PIN (+ spy) | Replay without rebuild is now idempotent, so the loser converges too; the causing commit is bisected in the WP. Deleting the test would leave nothing proving the rebuild seam is used, so the with-rebuild test gains a call-count spy. |
| R21 | `test_audit_tail_readers::test_decision_open_corrupt_events_log_json_envelope_names_the_typed_kind` | RE-PIN (stderr + `code`) | `cmd_open` owns the error via the decision-family stderr handler (`dd808bc4b`) |
| R22 | `invocation/cli/test_dispatch::test_dispatch_non_git_project_json_envelope_is_parseable` | RE-PIN | Adopted `json_error()` contract (`45303ca90`) |
| R23 | `tests/migration/test_verdict_provenance_backfill::…historical_rejection_then_later_real_approval_resolves_approved` | RE-PIN fixture (add the causal rework hops) + positive pin (#5279) | events 10.4.0 (#4990) correctly drops a stale concurrent approval that has no rework. The old scenario becomes an explicit contract test. A corpus probe injected the backfill rollback into 85 real approved/done WPs whose last review was a rejection: 0 were demoted. |

Also in scope: the stale "features" wording in `src/specify_cli/missions/documentation/templates/task-prompt-template.md:137`, versus canonical `packs/built-in/missions/documentation/templates/task-prompt-template.md:163` ("missions"). The 3.13 shard-6 byte-parity red came from `tests/cross_cutting/test_kittify_override_parity.py`, which `main` already deleted in #5128. That red was a branch-run artefact (#5276) and needs no action here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nightly out-of-matrix leg reports only honest reds (Priority: P1)

As a maintainer reading the nightly, I want the `specify-cli-out-of-matrix` leg to go green on `main`, so that a red there signals a real regression and not oracle drift.

**Why this priority**: #5258 is a P0 escalation. The release gate is red CI == no release (charter standing order 9).

**Independent Test**: Run every R-test file with `.venv/bin/python -m pytest <files> -p no:randomly`. All pass.

**Acceptance Scenarios**:

1. **Given** the mission branch, **When** the SC-001 files run, **Then** 0 fail and no test is skipped, xfailed or quarantined to get there.
2. **Given** a re-pinned test, **When** a reviewer reads the PR, **Then** a one-line verdict names the causing commit.

### User Story 2 - CLI help/usage assertions are colour-independent (Priority: P1)

As a contributor, I want in-process CLI output assertions to behave identically locally and on GitHub runners.

**Independent Test**: `GITHUB_ACTIONS=true .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_mission_close_guard.py -p no:randomly` passes. It fails before the fix.

**Acceptance Scenarios**:

1. **Given** `GITHUB_ACTIONS=true` (or `FORCE_COLOR=1`), **When** the mission-close guard tests run, **Then** all 7 pass.
2. **Given** no colour env, **Then** they still pass.

### User Story 3 - Consumer doctrine has no unreachable directive (Priority: P2)

As a consumer of the built-in pack, I want DIRECTIVE_052 reachable from the built-in graph through an incoming edge, as its author intended.

**Independent Test**: The orphan exact-set test passes with the original `{DIRECTIVE_035, DIRECTIVE_039}` set.

### Edge Cases

- A per-test colour helper (`force_wide_help_console`, `strip_ansi`) still works when the harness has already disabled colour, because monkeypatch undo is LIFO-safe.
- The dogfood cutover rewrites archive-frozen `meta.json`/`status.events.jsonl` bytes. That needs a dated archive-correction entry, per the #4972/#4957 precedents, and the operator must sanction it explicitly; the agent does not self-sanction. **Operator sanction: granted by stijn-dejongh on 2026-09-28, during this mission's spec phase.** Excluding these missions is not an option: both guards scan all of `kitty-specs/`, so the dogfood guard would become vacuous. Root cause: both missions were born on a long-lived branch (2026-07-16/22), before the birth-cutover seam landed (`71a1bba98`, 2026-07-27), and were merged 2026-09-15.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Harness-level colour neutralisation | As a contributor, I want the autouse plain-console seam to also disable Typer's own rich console colour so that help/usage assertions are runner-independent. | High | Open | [build] | no — `GITHUB_ACTIONS=true` run of `test_mission_close_guard.py` is red before, green after |
| FR-002 | Re-pin stale CLI-surface oracles | As a maintainer, I want R4's `--fix` loop fixed in the product, and R1–R5, R15–R17 and R21–R22 re-pinned (or deleted where verdict says so) to the intentional product contract so that the leg is green. | High | Open | [ratchet] | no — each test is red on the base |
| FR-003 | Exempt dated report snapshots | As a maintainer, I want `docs/reports/` exempt from the decision-shape and `--feature` literal guards, aligned with the existing archive classification, and guarded so the exemption fails loudly if reports are ever published (docfx content globs), so that historical findings are not rewritten. | Medium | Open | [build] | no — both guards red on base |
| FR-004 | De-orphan DIRECTIVE_052 | As a consumer, I want an incoming advisory `suggests` edge to DIRECTIVE_052 so that the directive is reachable. | Medium | Open | [build] | no — orphan exact-set red on base |
| FR-005 | Re-pin SC-011 corpus counts | As a maintainer, I want the bulk-edit inventory counts re-pinned to the current pack (after FR-004). | Medium | Open | [ratchet] | no |
| FR-006 | Cut over the two dogfood missions | As a maintainer, I want the two un-flipped dogfood missions cut over with the canonical `migrate backfill-runtime-state` so that the corpus invariant holds. | Medium | Open | [build] | no |
| FR-007 | Re-pin installer and verdict-backfill oracles | As a maintainer, I want R18–R20 and R23 re-pinned/deleted per verdict. | High | Open | [ratchet] | no |
| FR-008 | Canonical wording in the documentation task-prompt template | As a user, I want the src documentation template to say "missions" like canon. | Low | Open | [folded] | yes — no test pins it (parity gate retired in #5128) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Targeted-only validation | Only the touched test files and named gate files are run; no full `tests/architectural/` or `make test-full` sweep. | Process | High | Open |
| NFR-002 | Lint/format/type | Changed files pass `ruff check`, `ruff format --check` with 0 issues. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Sibling ownership | Do not edit `consolidation/*`, `tests/integration/**`, `ci-nightly.yml`, `scripts/ci/nightly_escalation.py`, `tests/charter/test_consistency_check.py`. | Technical | High | Open |
| C-002 | No green-washing | No skip/xfail/quarantine/retry; DELETE only where the test pins retired behaviour. | Process | High | Open |
| C-003 | Claimed-elsewhere issues | #4919/#4998/#4900/#4933/#4940/#4964/#5202 are not fixed here. | Process | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: These 15 files pass locally with 0 failed: `test_doctor_cli_surface_golden.py`, `test_doctor_coordination.py`, `test_decision_command_shape_consistency.py`, `test_orphan.py`, `test_occurrence_map_field_paths.py`, `test_dogfood_corpus_backfilled.py`, `test_mission_close_guard.py`, `test_mission_type_current_fallback_signal.py`, `test_installer.py`, `test_installer_global_reassess_convergence.py`, `test_audit_tail_readers.py`, `test_dispatch.py`, `tests/migration/test_verdict_provenance_backfill.py`, `tests/contract/test_terminology_guards.py`, `test_extractor_projection.py` — [ratchet] · no-op passable: no
- **SC-002**: `test_mission_close_guard.py` passes under `GITHUB_ACTIONS=true` and under `FORCE_COLOR=1` — [build] · no-op passable: no
- **SC-003**: Every re-pin or delete has a one-line verdict with a commit sha in the PR — [folded] · no-op passable: no
- **SC-004**: `grep -rn "large features" src packs` returns 0 hits — [folded] · no-op passable: no
