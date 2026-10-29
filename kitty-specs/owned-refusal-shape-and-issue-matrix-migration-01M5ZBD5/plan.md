# Implementation Plan: Owned-checkout issue-verdict cleanup

**Branch**: `issue-6354-owned-issue-verdict-cleanup` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/spec.md`

Planning questions are answered and recorded as Decision Moments
(`spec-kitty agent decision verify` is clean); the Engineering Alignment below was
confirmed by the operator on 2026-10-27.

## Summary

Two follow-ups from the owned-checkout work:

1. **Migration placement.** `migrate_issue_matrix_to_json` gains a keyword-only `owned`
   parameter and forwards it to `write_issue_matrix(..., owned=owned)`;
   `issue_verdict._migrate_if_needed` passes the validated owned fact through. An owned
   legacy-`.md` migration then lands in the owned checkout.
2. **One owned refusal shape.** The shared renderer in
   `src/specify_cli/cli/commands/_owned_checkout.py` stops accepting a per-command
   `envelope` builder and always renders the C2 core from `json_contract.json_error`,
   plus an optional `context` object and an optional top-level `spec_kitty_version`
   stamp. The four builders are deleted, so a different owned shape cannot be built
   through the renderer. The four owned refusals that bypass the renderer use the same
   payload builder. orchestrator-api reads the new host shape and its contract goes to
   1.19.0. An ADR records the rule and supersedes the earlier owned-checkout contract line.

## Engineering Alignment (confirmed)

1. Renderer by construction: `emit_owned_refusal(exc, *, json_output, context=None,
   stamp_version=False)` and `resolve_owned_or_refuse(..., json_output, context=None,
   stamp_version=False)`. The core is `json_error(code, message)`. A public
   non-validating builder `owned_refusal_payload(code, message, *, context=None,
   stamp_version=False)` is the single builder; `emit_owned_refusal` = registry check +
   builder + print.
2. Redundant keys are dropped: `result: "error"` and `success: false` are replaced by
   `ok: false`. Facts move under `context`.
3. The mark-status in-command owned failure (see #3865) uses the same C2 + `context`
   shape as its owned refusal (one builder for both).
4. The move-task owned catch-all keeps accepting any `ActionContextError` code through
   the non-validating builder (unchanged validation posture).
5. Human mode (`Error: [<CODE>] <message>` on stderr, exit 1) is unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing); no dependency added, upgraded or removed
**Storage**: files in git checkouts (`kitty-specs/<mission>/issue-matrix.json`); no schema change
**Testing**: pytest -- red-first integration tests through the CLI entry points (typer `CliRunner`), re-pinned unit tests for the renderer, a parametrized cross-command shape test, the existing C2 enumeration gate
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single (CLI)
**Performance Goals**: no measurable change; refusal rendering stays O(1)
**Constraints**: strict C2 core; `error.code` registered (renderer path); no write on refusal; non-owned payloads byte-identical; complexity <= 15; diff coverage >= 90%; no new suppressions
**Scale/Scope**: ~25 owned refusal sites across ~22 command modules, 2 orchestrator-api modules, 1 migration module, 1 ADR, ~12 test modules re-pinned

**Supply chain**: no dependency decision in this mission; DIRECTIVE_051 controls not triggered.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | The C2 core comes from `json_contract.json_error`; four competing builders are deleted; ownership validation stays in `_owned_checkout.py` (G2 gate unchanged). |
| Architectural alignment | PASS | No layer or package change; ADR 2026-10-22-1 / 2026-10-26-1 unaffected (research §2). |
| ATDD-first / red-first | PASS (planned) | Each WP starts with a failing acceptance test through the CLI entry point; both defects already reproduced red (research §1). |
| Gate non-vacuity | PASS (planned) | Shape fixed by construction (no `envelope` argument); the cross-command test drives every site and pairs with a same-fixture success control. |
| Terminology canon | PASS | Mission, never feature, in new text. |
| No hosted surface | PASS | None touched. |
| Tidy-first | PASS | No preparatory refactor needed (research §5). |
| Versioned contract discipline | PASS (planned) | orchestrator-api 1.18.0 → 1.19.0, documented. |
| No full heavy suites in mission | PASS (planned) | Targeted + blast radius + `make test-fast` only. |

Post-design re-check: PASS. The design adds no authority, keeps the G2 gate's empty
allowlist, and changes only rendering.

## Project Structure

### Documentation (this mission)

```
kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/
├── spec.md
├── plan.md                         # this file
├── research.md                     # Phase 0 grounding + caller inventory
├── data-model.md                   # owned refusal payload, context per command
├── quickstart.md                   # how to verify both fixes by hand
├── contracts/
│   └── owned-refusal-envelope.md   # the C2 owned refusal contract
├── tracer-approach.md
├── tracer-design-decisions.md
├── tracer-tooling-friction.md
└── tasks.md                        # /spec-kitty.tasks output (not created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── tasks/issue_matrix_migration.py                 # IC-01
├── cli/commands/
│   ├── _owned_checkout.py                          # IC-02 (renderer + builder)
│   ├── agent/issue_verdict.py                      # IC-01, IC-02
│   ├── agent/{acceptance_verdict,context,mission_setup_plan,mission_finalize,
│   │          mission_check_prerequisites,mission_record_analysis,tasks,
│   │          tasks_status_cmd,workflow}.py        # IC-02
│   ├── {next_cmd,accept,spec_commit_cmd,research,dispatch,
│   │    invocations_cmd,profile_invocation}.py     # IC-02
│   ├── charter/generate.py                         # IC-02
│   ├── decision.py                                 # IC-02 (repair-runtime-lock), IC-03 (verbs)
│   ├── agent/mission_create.py                     # IC-03
│   ├── agent/tasks_move_task.py                    # IC-03
│   └── agent/tasks_mark_status.py                  # IC-02 (edge refusal), IC-03 (in-command failure)
└── orchestrator_api/{design_phase,runtime_next,envelope}.py   # IC-04
docs/adr/4.x/2026-10-27-1-owned-refusals-use-the-c2-error-contract.md   # IC-02
docs/api/orchestrator-api.md                       # IC-04
docs/changelog/CHANGELOG.md                        # IC-05
tests/                                             # per IC
```

**Structure Decision**: single CLI project; every change lands in existing modules.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — Owned-aware legacy issue-matrix migration

- **Purpose**: write an owned Mission's migrated structured issue matrix into its owned checkout.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-004, C-003
- **Affected surfaces**: `src/specify_cli/tasks/issue_matrix_migration.py` (`migrate_issue_matrix_to_json` gains keyword-only `owned`), `src/specify_cli/cli/commands/agent/issue_verdict.py` (`_migrate_if_needed` forwards it); tests in `tests/integration/` (owned legacy-`.md` flag + flagless + non-owned control) and `tests/specify_cli/tasks/test_issue_matrix_structured.py` (forwarding unit test).
- **Sequencing/depends-on**: none (independent of IC-02..IC-05; touches `issue_verdict.py` in a different function than IC-02).
- **Risks**: the bulk `issue-matrix migrate` command must keep `owned=None` (repository root by design). The terminality tests (see #6653) must stay green.

### IC-02 — C2 owned refusal renderer and every renderer caller

- **Purpose**: make the shared renderer produce exactly the C2 owned refusal and move all its callers onto it.
- **Relevant requirements**: FR-004, FR-005, FR-007, FR-008, FR-010, FR-011, FR-014, C-001, C-002, C-004
- **Affected surfaces**: `_owned_checkout.py` (new `owned_refusal_payload`, changed `emit_owned_refusal` / `resolve_owned_or_refuse` / `resolve_owned_op_record_root`, deleted builders, docstring envelope rule rewritten); research rows 1-21 call sites; `agent/context.py::_emit_context_error` inlines its non-owned dict (it reused `success_false_envelope`); ADR `docs/adr/4.x/2026-10-27-1-...` superseding the line in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/cli-owned-checkout-surface.md:21`; re-pinned tests (research §1.4).
- **Sequencing/depends-on**: none.
- **Risks**: largest diff. Every renderer signature change must land in one WP (an intermediate state would not import). Shape-agnostic tests reading `["error_code"]` must move to `["error"]["code"]`. `mark-status`'s edge refusal shares `_ms_failure_payload` with IC-03, so the builder change lands here.

### IC-03 — Owned refusals outside the renderer

- **Purpose**: give the four off-renderer owned refusal paths the same C2 shape.
- **Relevant requirements**: FR-006, FR-007, FR-009, FR-010, FR-011
- **Affected surfaces**: `agent/mission_create.py:509-530` (C2 + version stamp via `_emit_json`); `agent/tasks_move_task.py:1726-1740` (non-validating builder); `agent/tasks_mark_status.py::_ms_report_owned_failure` (C2 + context); `decision.py` verbs (owned resolution routed through the renderer → stdout C2; non-owned `_handle_action_context_error` unchanged on stderr).
- **Sequencing/depends-on**: IC-02 (uses `owned_refusal_payload`).
- **Risks**: decision verbs currently catch owned and non-owned `ActionContextError` in one handler. The owned refusal must be told apart at the resolution call, not by code, so non-owned errors keep stderr. `tests/agent/test_agent_feature.py:725` re-pinned.

### IC-04 — orchestrator-api reads the new host shape

- **Purpose**: keep orchestrator classification correct and signal the payload change.
- **Relevant requirements**: FR-012, FR-013
- **Affected surfaces**: `orchestrator_api/design_phase.py::_classify_check_prerequisites_error` (read `error.code` / `error.message` when `error` is a mapping; keep the `MISSION_CONTEXT_UNRESOLVED` → `MISSION_NOT_FOUND` translation); `runtime_next.py::_fail_native_refusal` (message stays generic; the embedded payload changes); `envelope.py` `CONTRACT_VERSION = "1.19.0"`; `docs/api/orchestrator-api.md` version + change note; orchestrator tests.
- **Sequencing/depends-on**: IC-02.
- **Risks**: other orchestrator tests may assert `contract_version == "1.18.0"`; grep and update. `upstream_contract.json` is unaffected (codes unchanged).

### IC-05 — Cross-command pin, C2 gate entries, changelog

- **Purpose**: pin every owned refusal path to the contract so it cannot drift, and record the change.
- **Relevant requirements**: FR-015, SC-002, SC-004, NFR-001
- **Affected surfaces**: a parametrized test (`tests/integration/test_owned_refusal_c2_shape.py`) driving one owned refusal per in-scope `--json` command with a same-fixture success control; `tests/architectural/test_json_contract_enumeration.py` (owned refusal cases recorded as adopted where the gate's structure allows, else the cross-command test is the pin); `docs/changelog/CHANGELOG.md` `[Unreleased]`.
- **Sequencing/depends-on**: IC-02, IC-03, IC-04.
- **Risks**: the owned-checkout fixture is slow (~170 s setup). Share one module-scoped fixture across parameters.

## Test plan (blast radius)

- Targeted: every new or re-pinned test file named above.
- Blast radius: `tests/specify_cli/cli/commands/test_owned_checkout_helper.py`,
  `tests/specify_cli/cli/commands/` owned tests, `tests/integration/test_owned_*.py`,
  `tests/integration/test_owned_lifecycle_acceptance_e2e.py`,
  `tests/integration/test_explicit_checkout_commands.py`,
  `tests/specify_cli/tasks/test_issue_matrix*.py`, issue-verdict tests
  (`tests/integration/test_issue_verdict_*.py`, `test_p0_repro_6320_owned_issue_verdict.py`),
  `tests/policy`, `tests/specify_cli/orchestrator_api/`, `tests/agent/test_agent_feature.py`.
- Named architectural gates: `test_owned_checkout_single_authority.py`,
  `test_json_contract_enumeration.py`, `test_no_legacy_terminology.py`.
- Baseline: `make test-fast`.
- Static: `ruff check`, `ruff format --check --force-exclude <files>`, `mypy` on touched files.
