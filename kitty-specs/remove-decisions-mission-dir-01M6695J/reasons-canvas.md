# REASONS Canvas — remove-decisions-mission-dir-01M6695J

Source of truth for scope and acceptance: `spec.md` in this directory. This
canvas captures intent only; where it and `spec.md` disagree, `spec.md` wins.

## Requirements

**Summary:** Remove the caller-less read-side `decisions/service.py::_mission_dir`
(left dead by #6762) without touching behaviour, and pin the surviving
read/write split so it cannot silently regress.

- **Problem statement.** PR #6762 moved the decisions opened-row check onto the
  pre-resolved write-side `events_path` and removed the read-side
  `_events_path`; the read-side `_mission_dir` it also used is now dead in
  `src/`, exercised only by two tests that pin the dead helper itself. Dead
  seam helpers invite future callers onto a read path the module no longer
  owns (#6766).
- **Acceptance criteria.** See `spec.md` FR-001..FR-004 and SC-001..SC-004:
  symbol gone, orphaned tests removed, stale docstrings re-pointed, a guard
  test that is red on the planning base (read-side `read_dir(STATUS_STATE)`
  present) and green on the mission head, with the architectural gates named
  by the issue staying green.
- **Definition of done.** Mission head passes `tests/decisions/`,
  `tests/specify_cli/decisions/`, `tests/specify_cli/test_read_seam_leniency.py`,
  the three architectural gates, ruff/mypy on touched files, and the diff-cover
  ≥90% CI gate; changelog entry present; PR green and ready for review.
- **Must (Safeguards).** `decisions/emit.py::_mission_dir` (live, census-named)
  must not change; no gate suppression; PR-only delivery, operator merges.
- **Should (Norms).** Smallest viable diff — only `service.py`, the leniency
  test file, the new guard test, and the changelog.
- **May (Approach options).** The two orphaned tests may be deleted (chosen) or
  re-pointed at a surviving read-seam behaviour if review finds one they still
  guard.

## Entities

**Summary:** One aggregate changes — the decisions service's STATUS_STATE
access path — plus its test seam.

- **Decisions service (STATUS_STATE access)**: decision events live at
  `kitty-specs/<mission>/status.events.jsonl`; since #4848/#6762 every access
  in `service.py` is a write-side pre-resolution
  (`_write_mission_dir` / `_write_events_path`). The read-side `_mission_dir`
  is the dead half of the former read/write split.
- **Read-seam leniency pins** (`tests/specify_cli/test_read_seam_leniency.py`):
  behavioural pins for migrated (fail-loud) and stay-lenient read-seam sites;
  two pins exercise only the dead helper and leave with it.
- **Placement seam (`read_dir`/`write_dir`)**: the topology-aware artifact
  placement API (`mission_runtime.placement_seam`); the mission deletes one
  `read_dir(STATUS_STATE)` call and adds no new seam surface.

## Deviations

- None.
