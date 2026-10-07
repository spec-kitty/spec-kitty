# Tasks: Cutover guard exempts pre-accept Missions

**Mission**: `cutover-guard-pre-accept-exemption-01M49DF4` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Branch**: planning base and merge target `fix/cutover-guard-pre-accept-exemption` (PR to upstream `main`).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first #5835 repro through `evaluate_touched_missions` (real WP-template frontmatter, claim event, no stamp) | WP01 | |
| T002 | Red-first #5300 repro through `assert_birth_invariant_holds` on a synthetic corpus | WP01 | |
| T003 | `LegacyWPRuntime.has_frontmatter_runtime()` + unit tests | WP01 | [P] |
| T004 | `pre_accept_exemption(mission_dir)` fail-closed helper (terminal evidence, phase well-formedness, legacy read) | WP01 | |
| T005 | Wire the helper into `is_cut_over` (PASS + note / reason-specific FAIL) and `eligible_runtime_missions` | WP01 | |
| T006 | Verdict matrix in `tests/status/test_cutover_eligibility.py`; convert repros to focused tests | WP01 | |
| T007 | Guard report: exempt Missions listed with note; per-reason remedy; additive JSON payload fields | WP02 | |
| T008 | Guard CLI tests for report text and JSON payload | WP02 | |
| T009 | `docs/development/how-to/cutover-guard.md`: exemption, conditions, residual | WP02 | [P] |
| T010 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry (#5835, #5300) | WP02 | [P] |

## WP01 — Shared pre-accept exemption in the cut-over predicate (P1)

**Goal**: one fail-closed exemption decision consumed by both `is_cut_over` (CI guard) and `eligible_runtime_missions` (dogfood corpus test). **Independent test**: the #5835 and #5300 repros are red on the base and green after; the strict cells of the matrix stay red.
**Prompt**: [tasks/WP01-shared-pre-accept-exemption.md](tasks/WP01-shared-pre-accept-exemption.md) (~300 lines)

T001 Red-first #5835 repro through `evaluate_touched_missions` (WP01)
T002 Red-first #5300 repro through `assert_birth_invariant_holds` (WP01)
T003 `LegacyWPRuntime.has_frontmatter_runtime()` (WP01)
T004 `pre_accept_exemption()` helper (WP01)
T005 Wire into `is_cut_over` and `eligible_runtime_missions` (WP01)
T006 Verdict matrix + repro conversion (WP01)

**Dependencies**: none. **Risks**: making the exemption too broad (mitigated by the paired strict fixtures); complexity of `is_cut_over` (extract the helper).

## WP02 — Actionable guard output and docs (P2)

**Goal**: the guard report names exempt Missions with their note, gives a per-reason remedy for each remaining failure, and the behaviour is documented. **Independent test**: CLI output and JSON payload assertions per reason.
**Prompt**: [tasks/WP02-guard-output-and-docs.md](tasks/WP02-guard-output-and-docs.md) (~220 lines)

T007 Guard report + payload (WP02)
T008 Guard CLI tests (WP02)
T009 Cutover-guard doc (WP02)
T010 Changelog entry (WP02)

**Dependencies**: Depends on WP01 (reason vocabulary and the note on `CutOverVerdict`).

## Parallelisation

WP02 follows WP01. Within WP02, T009/T010 are independent of T007/T008. MVP: WP01 alone clears the P0.
