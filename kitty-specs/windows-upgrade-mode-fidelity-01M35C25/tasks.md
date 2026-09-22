# Tasks: Windows upgrade POSIX-mode fidelity

**Mission**: `windows-upgrade-mode-fidelity-01M35C25`
**Branch**: `fix/windows-upgrade-mode-fidelity` (planning + local merge target); PR → upstream `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

## Overview

Two Windows-only `upgrade` defects (#4923 crash, #4927 phantom repairs) share one root and one
code surface (`skills/installer.py`), so they land as **one sequential work package** with two
phases: first close the `follow_symlinks` crash class, then suppress the phantom mode
divergence. Splitting would force overlapping `owned_files` on `installer.py`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add host-safe `utime` + path-`chmod` helpers to `kernel.no_follow` | WP01 | |
| T002 | Migrate the 5 `follow_symlinks=False` sites in `installer.py` {172,174,963,969,981} to the helpers | WP01 | |
| T003 | Red-first `@pytest.mark.regression` repro for #4923 that RAISES on `follow_symlinks=False` | WP01 | |
| T004 | Non-vacuous, shrink-only arch gate scoped to chmod/utime `follow_symlinks=False` + self-mutation proof + `_exemptions` floor | WP01 | |
| T005 | Extend the host-aware mode-divergence relaxation to file/symlink kinds (`command_installer.py`) | WP01 | |
| T006 | Apply the relaxation at the `installer.py` project-skill projection (`write()` chmod branch ~592-593; canonical/unchanged ~785-814) | WP01 | |
| T007 | Thread the relaxation through the recheck/receipt seams (`installer.py:_command_parent_receipts` ~507, `managed_skills.py:_recheck_command_completion` ~181); update the pinned dir-only assertion | WP01 | |
| T008 | Red-first `@pytest.mark.regression` repro for #4927 (converged simulated-Windows → dry-run "184→0", matches `doctor tool-surfaces`) | WP01 | |
| T009 | De-mark both transitional repros into focused unit tests; run the blast radius (`tests/specify_cli/skills/`, `tests/specify_cli/tool_surface/`, `tests/architectural/`) | WP01 | |

## Work Packages

### WP01 — Host-safe Windows upgrade: close the follow_symlinks crash class + suppress phantom mode divergence

**Goal**: On Windows, `spec-kitty upgrade` completes without crashing and a converged project
reports zero supporting-surface repairs — without weakening POSIX behavior.
**Priority**: P1 (crash on the released wheel; MVP-launch milestone).
**Independent test**: Simulated non-`follow_symlinks` host + simulated Windows mode divergence,
both via the `kernel.paths.is_windows` seam; the crash repro raises pre-fix and passes post-fix,
and the converged dry-run drops 184→0 and matches the auditor.

**Included subtasks**: T001 T002 T003 T004 T005 T006 T007 T008 T009

**Implementation sketch** (two phases, in order — see prompt `WP01-*.md` for full detail):
1. **Phase A — #4923 (close the class)**: T001 helper in `kernel.no_follow`; T002 migrate the
   five sites; T003 red-first crash repro (raises, not no-op); T004 arch gate.
2. **Phase B — #4927 (suppress phantom divergence)**: T005 extend the relaxation; T006 apply at
   the projection; T007 recheck seams + pinned-assertion update; T008 red-first converged repro;
   T009 de-mark repros + blast-radius run.

**Dependencies**: none (foundation WP).
**Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, NFR-004.
**Risks**: (a) mocking too coarsely so a repro passes for the wrong reason — mitigated by the
raise-not-noop rule (NFR-001); (b) FR-004 removing the :963 file-chmod vector before the #4923
repro is pinned — mitigated by Phase A landing first on a still-live vector (:172/:969) (F7);
(c) inverting a pinned dir-only test assertion — handled explicitly in T007
(delete-the-assertion-not-the-test).
**Estimated prompt size**: ~500 lines (9 subtasks).
**Prompt**: [tasks/WP01-host-safe-windows-upgrade.md](./tasks/WP01-host-safe-windows-upgrade.md)

## MVP scope

WP01 is the entire mission; it is the MVP.
