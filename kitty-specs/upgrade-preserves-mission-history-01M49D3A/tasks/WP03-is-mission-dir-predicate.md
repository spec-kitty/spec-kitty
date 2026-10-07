---
work_package_id: WP03
title: One is-a-Mission predicate (#5812)
dependencies:
- WP02
requirement_refs:
- FR-006
planning_base_branch: issue-5811-upgrade-preserves-mission-history
merge_target_branch: issue-5811-upgrade-preserves-mission-history
branch_strategy: Planning artifacts for this mission were generated on issue-5811-upgrade-preserves-mission-history. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5811-upgrade-preserves-mission-history unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-preserves-mission-history-01M49D3A
base_commit: 58288463762665d251fd16b80db786d382b6e3d6
created_at: '2026-10-07T05:26:00.092402+00:00'
subtasks:
- T012
- T013
- T014
- T015
- T016
phase: Phase 2 - Fixes
history:
- at: '2026-10-07T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/context/
create_intent:
- tests/context/test_is_mission_dir.py
- tests/audit/test_residue_directory_finding.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/context/mission_resolver.py
- src/specify_cli/audit/engine.py
- tests/context/test_is_mission_dir.py
- tests/audit/test_residue_directory_finding.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03: One is-a-Mission predicate (#5812)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ Review Feedback

If this WP came back from review, read the `review_ref` in the event log first (`.venv/bin/spec-kitty agent tasks status --mission 01M49D3A`). Every feedback item is part of your work.

## Objective

A directory under `kitty-specs/` that holds only untracked or gitignored residue is not a Mission. One shared predicate decides this for both the mission-state audit and the repair. Residue produces a non-blocking finding and is never written into.

Spec references: FR-006, FR-008 (identity backfill), User Story 3.

## Branch Strategy

- Planning base and final merge target: `issue-5811-upgrade-preserves-mission-history`.
- WP03 is in WP02's lane, because both edit `src/specify_cli/migration/mission_state.py`. Prepare with `.venv/bin/spec-kitty agent action implement WP03 --agent claude`.

## Seam Map (brownfield scout; re-check lines)

- `src/specify_cli/context/mission_resolver.py:221`: `_iter_mission_dirs` yields every directory under `kitty-specs/` in sorted order. Its docstring says it is the **single enumeration primitive**, enforced by `tests/architectural/test_mission_resolver_walker_gate.py`. **Do not add a second directory scan.** The predicate is a per-directory test that callers apply to what the walker yields. The existing population rule is "`spec.md` or `meta.json`" (~:279).
- `src/specify_cli/migration/mission_state.py:2517`: `_select_mission_dirs` (also used ~:667) treats every directory as a Mission. It is out of your owned files; edit it here with a one-line rationale ("WP03 owns the selection rule; WP02 owned the rest of this file and has landed in this lane").
- `src/specify_cli/audit/engine.py`: find where it enumerates Mission directories and where the `IDENTITY_MISSING` finding is emitted (`audit/classifiers/meta.py:92`, `audit/identity_adapter.py:84`).
- `kernel.git.listing.is_tracked(cwd, path)` (`src/kernel/git/listing.py:457`) returns a bool and raises `GitCommandError` on other failures. `tracked_paths` (:439) is a batch alternative; prefer it if you check many directories, to avoid one subprocess per Mission on about 650 Missions.

## Subtasks

### T012: Public `is_mission_dir` predicate

1. Add `is_mission_dir(path: Path, *, repo_root: Path, tracked: frozenset[str] | None = None) -> bool` to `context/mission_resolver.py`. It is True when `spec.md` or `meta.json` under `path` is git-tracked. `tracked` is an optional precomputed set of tracked repo-relative paths, for batch use with `tracked_paths`.
2. **A genuine Mission that is not yet committed must still count.** A fresh `mission create` writes `meta.json` before anything is committed. So also return True when `meta.json` exists on disk and parses with a non-empty `mission_id`. Residue never has a valid identity-bearing `meta.json`, which keeps #5812 closed. State this rule in the docstring.
3. If the repository is not a git repository, or git is unavailable, fall back to the existing population rule ("`spec.md` or `meta.json` exists"). Never error out of enumeration for a non-git scan root; the doctor `scan_root` fixtures may not be git repositories, so check `_mission_state_doctor.py:275` usage.
4. Tests in `tests/context/test_is_mission_dir.py`:
   - tracked `spec.md`, tracked `meta.json`, untracked `meta.json` with `mission_id` → True;
   - a gitignored lock file only, or an untracked `meta.json` without `mission_id` → False;
   - non-git fallback → existence rule.

### T013: The repair selection uses the predicate

1. `_select_mission_dirs` (when `mission is None`) keeps only directories for which `is_mission_dir` is True. Return or record the rejected ones as residue, so the repair report lists them as non-blocking.
2. The repair must create nothing inside a residue directory: no meta backfill, no status files.
3. An explicit `mission=` selection keeps today's behaviour (an operator naming a directory is a deliberate act), but still refuse to mint identity into a directory with no Mission artifacts at all. Pick the smallest safe rule and document it.

### T014: The audit uses the predicate; non-blocking `RESIDUE_DIRECTORY` finding

1. Where the audit enumerates Mission directories, apply `is_mission_dir`. For rejected directories, emit a finding code `RESIDUE_DIRECTORY` with a **non-blocking** severity: it must not count toward TeamSpace readiness `blocked`. Follow the existing finding-code registry and severity model in `audit/`; find where codes such as `IDENTITY_MISSING` are declared and add the new one there, and only there.
2. Make sure readiness (`check_teamspace_mission_state_readiness`, or whatever the gate reads) ignores non-blocking findings.
3. Test in `tests/audit/test_residue_directory_finding.py`: a residue directory yields exactly one `RESIDUE_DIRECTORY` finding, zero `IDENTITY_MISSING` and readiness not blocked; a real Mission without `mission_id` still yields `IDENTITY_MISSING` (positive control).

### T015: Identity backfill still runs for real legacy Missions

Confirm with the existing tests (`grep -rl _canonicalize_meta tests/`) that a real legacy Mission (tracked `spec.md`, tasks or event log, with no `mission_id`) still gets its identity backfilled by `doctor mission-state --fix`. If no test covers it, add one case to `tests/audit/test_residue_directory_finding.py` or the nearest existing repair test (out-of-map; give a one-line reason).

### T016: Turn the #5812 repro into a regular test

In `tests/integration/migration/test_residue_dir_not_mission_5812.py` (WP01's file; out-of-map with the reason "fix WP removes the p0_repro marker per ADR 2026-07-17-1"):
- remove `@pytest.mark.p0_repro(issue=5812)` and `@pytest.mark.regression`;
- confirm green in a default run;
- keep it as a functional test.

## Constraints

- No second walker; respect `test_mission_resolver_walker_gate.py`. Run it.
- Complexity at most 15; ruff, format and mypy clean.
- `tests/architectural/mission_type_reader_allowlist.yaml:77` lists `mission_state.py`. If you add a reader of `meta.json` mission fields in a new module, check that gate (`grep -rl mission_type_reader_allowlist tests/architectural`) and run it.
- Mission terminology only (`RESIDUE_DIRECTORY`, not "orphan feature").

## Tests to Run

```bash
.venv/bin/python -m pytest tests/context/ tests/audit/ tests/migration/ tests/integration/migration/ -q
.venv/bin/python -m pytest tests/architectural/test_mission_resolver_walker_gate.py tests/migration/test_repair_row_parity_5811.py -q
make test-fast
```

## Definition of Done

- One predicate, used by both the audit and the repair selection.
- The #5812 repro is green as a regular test.
- A residue finding is non-blocking.
- Legacy backfill is intact, and the walker gate is green.

## Reviewer Guidance

- Grep for any other new "is this a Mission" logic added in this WP; there must be exactly one.
- Check the untracked-but-genuine Mission case: a fresh scaffold must not become residue.
