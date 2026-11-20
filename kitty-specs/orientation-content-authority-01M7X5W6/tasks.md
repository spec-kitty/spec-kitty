# Tasks: One authority for committed orientation content

**Mission**: orientation-content-authority-01M7X5W6 · **Branch**: fix/5215-orientation-content-authority (single_branch)
**Inputs**: spec.md, plan.md, research.md, data-model.md

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests: slug fallback, deterministic committed health, hook/file slug agreement | WP01 | |
| T002 | Extract `slug_from_git_remote` from `derive_project_slug` | WP01 | |
| T003 | New `session_presence/projection.py`: `resolve_project_slug`, `expected_orientation`, `orientation_writer` | WP01 | |
| T004 | Manager: `_build_content` delegates to the authority; new `live_content`; install/update via `orientation_writer`; dry-run variant gone | WP01 | |
| T005 | session-start calls `live_content`; re-pin stale manager/session-start tests | WP01 | |
| T006 | Red-first acceptance tests S1, S3, S4 and upgrade/`--fix` convergence | WP02 | |
| T007 | `projection.orientation_drift` + provider probe uses it; drop version-only helpers | WP02 | |
| T008 | Provider `_orientation_content` and `_prepare` applicability use the authority | WP02 | |
| T009 | Writer `prepare` unchanged only on full block equality | WP02 | |
| T010 | Delete `local_presence_content`; re-pin stale provider/writer tests; dead-symbol gate | WP02 | |

## WP01 — Content authority, identity fallback, manager and hook (P1)

**Prompt**: [tasks/WP01-content-authority.md](tasks/WP01-content-authority.md)
**Goal**: one module decides the committed orientation content (identity slug, deterministic health); the hook keeps live health with the same slug.
**Independent test**: `pytest tests/specify_cli/session_presence/test_orientation_projection_5215.py tests/specify_cli/identity/`.

T001 Red-first tests: slug fallback, deterministic committed health, hook/file slug agreement (WP01)
T002 Extract `slug_from_git_remote` from `derive_project_slug` (WP01)
T003 New projection module (WP01)
T004 Manager delegates to the authority; `live_content` (WP01)
T005 session-start uses `live_content`; re-pin stale tests (WP01)

Dependencies: none. Risk: tests pinning live health via `_build_content` are stale pins and move to `live_content`.

## WP02 — Provider and writer consume the authority; S1/S3/S4 repaired (P1)

**Prompt**: [tasks/WP02-provider-writer-convergence.md](tasks/WP02-provider-writer-convergence.md)
**Goal**: the probe reports a wrong block as stale, and upgrade repair and `doctor --fix` write identical identity-slug bytes.
**Independent test**: `pytest tests/specify_cli/tool_surface/providers/test_session_presence_orientation_5215.py`.

T006 Red-first acceptance tests S1, S3, S4 and convergence (WP02)
T007 `orientation_drift` + probe (WP02)
T008 Provider content and applicability via the authority (WP02)
T009 Writer full-equality check (WP02)
T010 Delete `local_presence_content`; re-pin; dead-symbol gate (WP02)

Dependencies: WP01. Risk: blocks with live health / legacy glyphs at the current version now converge once (intended).
