---
work_package_id: WP02
title: Tracer-append fails closed on unmaterialised coord read (#4959)
dependencies:
- WP01
requirement_refs:
- C-003
- FR-002
- NFR-001
planning_base_branch: fix/coord-read-fail-closed
merge_target_branch: fix/coord-read-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/coord-read-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/coord-read-fail-closed unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
history:
- event: created
  at: '2026-09-24T05:45:24Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/specify_cli/retrospective/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/retrospective/tracer_writer.py
- tests/specify_cli/retrospective/test_tracer_writer.py
- tests/specify_cli/retrospective/test_tracer_writer_coord_e2e.py
role: implementer
tags: []
tracker_refs:
- '#4959'
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro` before anything else.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objective
Stop `agent tracer-append` from clobbering a real `traces/<cat>.md` when the coordination surface is unmaterialised. With WP01 making the seam raise, `tracer_writer._read_current_coord_content` must **propagate** that raise (fail closed) instead of swallowing it into `""` (which the writer turns into a from-scratch header at the write site). Also refuse on an undecodable byte. **Read `contracts/reader-partition-contract.md` first.**

## Key context (verified on main)
- `src/specify_cli/retrospective/tracer_writer.py::_read_current_coord_content` (~144-170): catches `_NO_EXISTING_CONTENT_EXCEPTIONS` (`ActionContextError, StatusReadPathNotFound, FileNotFoundError`, ~86-90) → returns `""`; also `if not category_path.is_file(): return ""` (~165) and `except (OSError, UnicodeDecodeError): return ""` (~167). Consumer `append_tracer_finding` (~251): `base_content = current_content or _default_header(category)` → the clobber.
- WP01 adds `CoordinationWorktreeUnmaterialized(StatusReadPathNotFound)` — so today's `except StatusReadPathNotFound` would SWALLOW it. That is the bug to flip.

## Subtasks

### T006 — Red-first
In `tests/specify_cli/retrospective/test_tracer_writer.py`, build a coord mission with an UNMATERIALIZED coord surface and a populated `traces/<cat>.md`; run the tracer-append path; assert the file is **unchanged** (0 findings lost) and the command fails closed. Confirm it FAILS pre-fix (file clobbered to header+entry). Add a second red-first: an existing file with a non-UTF-8 byte → refuse (not `""`). Paste failures.

### T007 — Narrow the catch → propagate + refuse
In `_read_current_coord_content`: distinguish "resolved-but-empty" (OK) from "could-not-resolve / unmaterialised" (propagate) and "undecodable byte on an existing file" (refuse). Concretely: do NOT catch `CoordinationWorktreeUnmaterialized` (and, per the contract, the unresolved-coord read generally) into `""` — let it propagate so the write is refused; on `UnicodeDecodeError` for an existing file, raise/refuse rather than returning `""`. Keep `FileNotFoundError`/genuinely-absent-on-resolved-surface → `""` (legitimate first write). Update the module's exception-tuple + comments naming #4959.

### T008 — Regression
Assert: (a) resolved coord surface + absent file → empty, first append works (no regression); (b) materialised coord surface + present file → normal append; (c) the fail-closed path leaves the file byte-intact. Run `tests/specify_cli/retrospective/` (your two files) and paste counts.

## Branch Strategy
Base + target `fix/coord-read-fail-closed`; worktree per `lanes.json`.

## Definition of Done
- Unmaterialised-coord tracer-append leaves a populated file byte-intact + fails closed (FR-002, NFR-001, red-first green); undecodable byte refuses; resolved-absent + materialised-present unchanged (C-003, no regression).
- `ruff`/`mypy` clean on owned files.

## Reviewer guidance
Confirm the narrowed catch still lets a genuine first-write (resolved, absent file) return empty. Re-run the red-first swap (file clobbered pre-fix, intact post-fix).
