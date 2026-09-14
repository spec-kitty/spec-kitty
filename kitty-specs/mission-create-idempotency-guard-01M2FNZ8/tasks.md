# Tasks: Mission-create idempotency guard

**Mission**: mission-create-idempotency-guard-01M2FNZ8 · **Issue**: #4033
**Branch**: fix/mission-create-idempotency-4033 → PR targets `main`

One cohesive WP (the guard, the abandonment classifier, the flag threading, tests).

## Subtask Index
| ID | Description | WP |
|----|-------------|----|
| T001 | Abandonment classifier: for prior same-slug+same-type missions, read meta.json + reduced status event log → live vs abandoned (fail-closed on unreadable) | WP01 |
| T002 | Idempotency guard in `_create_mission_core_impl`, before scaffold/branch write: refuse a live same-key match unless overridden, with an actionable error naming the mission + `--allow-duplicate` | WP01 |
| T003 | Thread `allow_duplicate: bool=False` through `create_mission_core`; expose `--allow-duplicate` on `agent mission create` (+ specify pass-through); factory passes it | WP01 |
| T004 | Red-first `@pytest.mark.regression` repro (create-twice → 2 missions today) + unit tests: guard fires, abandonment auto-allow, flag override, same-slug/diff-type allowed, no orphan scaffold on refusal | WP01 |
| T005 | Verify no-behavior-change (tests/core green) + ruff/format/mypy clean, complexity ≤15 | WP01 |

## Work Packages

### WP01 — Idempotency guard + abandonment-aware auto-allow + escape hatch (#4033)
- **Goal**: refuse a duplicate mission create (same slug+type, live) fail-closed before scaffold write, with abandonment auto-allow and an explicit `--allow-duplicate` override.
- **Priority**: P1
- **Independent test**: create twice → one mission + `MissionCreationError`; cancel+re-create → succeeds; `--allow-duplicate` → second mission.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002
- **Included subtasks**: T001 T002 T003 T004 T005
- **Prompt**: `tasks/WP01-idempotency-guard.md`
- **Dependencies**: none
