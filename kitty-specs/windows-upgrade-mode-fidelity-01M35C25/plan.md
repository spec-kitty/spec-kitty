# Implementation Plan: Windows upgrade POSIX-mode fidelity

**Branch**: `fix/windows-upgrade-mode-fidelity` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/windows-upgrade-mode-fidelity-01M35C25/spec.md`

## Summary

Two Windows-only `upgrade` defects share one root: Windows filesystems cannot carry POSIX
file modes, so managed command/skill surface effects always show a mode divergence. This
plan (a) makes every `follow_symlinks=False` chmod/utime call-site in the skill installer
host-safe through the **existing** `kernel.no_follow` authority, closing the crash class
(#4923) and guarding it with a precisely-scoped architectural gate; and (b) extends the
host-aware mode-divergence relaxation to file/symlink kinds so the project-skill projection
stops emitting phantom `chmod` effects on Windows (#4927), threading the same relaxation
through the completion-recheck seams. Both are verified on Linux CI via the
`kernel.paths.is_windows` mock seam with a repro that *raises* on the unsupported flag.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib `os`/`stat`/`pathlib`; internal `kernel.no_follow`, `kernel.paths`, `specify_cli.skills.installer`, `specify_cli.skills.command_installer`, `specify_cli.tool_surface.providers.managed_skills`
**Storage**: N/A (filesystem effects on managed command/skill surfaces)
**Testing**: pytest; host simulation via monkeypatching `kernel.paths.is_windows` and forcing `os.utime`/`Path.chmod` to reject `follow_symlinks` (or patching `os.supports_follow_symlinks`)
**Target Platform**: Windows (defect surface) + POSIX (regression-protected); Linux CI is the test host
**Project Type**: single (library/CLI — `src/specify_cli`, `src/kernel`)
**Performance Goals**: N/A (correctness fix; no perf-sensitive path changed)
**Constraints**: POSIX behavior byte-identical before/after (NFR-002); no second no-follow authority (C-001); extend not fork the divergence relaxation (C-002); red-first per ADR 2026-07-17-1 (C-004); complexity ≤ 15, ruff/format/mypy clean, tests-with-branches (NFR-004)
**Scale/Scope**: 2 defects, ~5 call-sites + 1 planner branch + 2 recheck seams + 1 arch gate; ~2 work packages

### Supply-Chain Security

No dependency is added, upgraded, or removed. The `supply_chain_security_check` step has
nothing to examine for this mission; recorded here as examined-and-N/A, not skipped.

## Constitution Check (Charter)

*GATE: passes before Phase 0; re-checked after design.*

- **Single canonical authority (DIRECTIVE_044)**: PASS — the host-safe primitive lands in the
  existing `kernel.no_follow`; the file/symlink relaxation extends the existing
  `windows_dir_mode_only_divergence` authority rather than forking a parallel one.
- **Architectural gate discipline (Standing Order #5)**: PASS — a non-vacuous, shrink-only
  gate scoped to chmod/utime `follow_symlinks=False` in the managed-skill apply surface,
  built on the existing `test_os_detection_ban.py` / `_os_detection_scan.py` / `_exemptions/`
  pattern, with a self-mutation proof.
- **ATDD / red-first (DIRECTIVE_041, ADR 2026-07-17-1)**: PASS — each defect lands an
  issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry
  point *and raises for the right reason* before the fix.
- **Tiered rigour / locality (DIRECTIVE_024/025)**: PASS — edits are local to the installer /
  tool-surface seams; opportunistic cleanup stays inside the touched file set.
- **Terminology canon**: PASS — no `feature`/`sync` vocabulary introduced.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/windows-upgrade-mode-fidelity-01M35C25/
├── plan.md              # This file
├── research.md          # Phase 0: decisions + adversarial evidence
├── spec.md              # Requirements (committed)
├── tracer-*.md          # Mission tracers
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

data-model.md and contracts/ are **not applicable**: this is a behavior fix over existing
filesystem-effect code with no new domain entities and no API/event surface. Omitted
deliberately (the plan exit gate requires only a substantive Technical Context).

### Source Code (repository root)

```
src/kernel/
├── no_follow.py                    # WP01: add host-safe utime + path chmod helpers (canonical authority)
└── paths.py                        # is_windows() host-detection seam (consumed, unchanged)

src/specify_cli/skills/
├── installer.py                    # WP01: sweep sites {172,174,963,969,981} to kernel.no_follow
│                                   # WP02: project-skill projection — suppress phantom file/symlink chmod (write ~592-593, _expected_project_entries ~725, canonical/unchanged ~785-814); recheck seam ~507
└── command_installer.py            # WP02: generalize windows_dir_mode_only_divergence to file/symlink (or coordinated sibling)

src/specify_cli/tool_surface/providers/
└── managed_skills.py               # WP02: thread relaxation through _recheck_command_completion ~181

tests/
├── specify_cli/skills/test_installer.py                                  # WP01 repro + unit
├── specify_cli/tool_surface/providers/test_managed_skills_host_aware.py  # WP02 repro + update pinned dir-only assertion
└── architectural/                                                        # WP01 non-vacuous follow_symlinks gate (+ _exemptions floor)
```

**Structure Decision**: Single project. Fix lands in `src/kernel/no_follow.py` (authority),
`src/specify_cli/skills/{installer,command_installer}.py`, and
`src/specify_cli/tool_surface/providers/managed_skills.py`; gate under `tests/architectural/`.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (#4923: close the crash class)
  - add host-safe utime + path-chmod helpers to kernel.no_follow
  - migrate installer.py sites {172,174,963,969,981} to the helpers
  - add the non-vacuous, shrink-only follow_symlinks arch gate + self-mutation proof
  - red-first repro that RAISES on follow_symlinks=False (backup-restore/symlink vector)
        │
        ▼  (sequential — WP02 edits the same installer.py region; and once WP02
           suppresses the file chmod, FR-001's :963 vector stops firing, so WP01
           must land its crash repro on a still-live vector first — F7)
WP02 (#4927: suppress phantom mode divergence)
  - extend host-aware file/symlink mode-divergence relaxation (command_installer.py)
  - apply at the installer.py project-skill projection (write chmod branch + canonical/unchanged detection)
  - thread through recheck/receipt seams (installer.py:507, managed_skills.py:181)
  - update the pinned dir-only assertion (delete-the-assertion-not-the-test)
  - red-first repro: converged simulated-Windows project → dry-run "184→0", matches doctor tool-surfaces
```

### Work Distribution

- **Sequential**: WP01 → WP02. They share `installer.py`; sequencing avoids whack-a-field
  conflict and preserves a live crash-repro vector for WP01 (F7). This is a small mission,
  so a single implementer executes both WPs in order rather than parallel lanes.
- **Coordination**: WP02 rebases on WP01. No cross-mission coordination branch needed.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
