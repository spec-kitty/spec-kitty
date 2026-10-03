# Tasks: Upgrade and Windows drift

**Mission**: `upgrade-windows-drift-01M40959` · **Planning base / consolidation target**: `kitty/upgrade-windows-drift`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: unattended upgrade with canonical bytes and an old recorded hash exits 0 (#5574) | WP01 | |
| T002 | Red-first unit: installer treats canonical bytes as fresh and refreshes the recorded hash | WP01 | |
| T003 | Installer: `preserve()` lets canonical bytes through; adopt-only refreshes an existing entry's hash | WP01 | |
| T004 | Installer: a `consent_required` path named in `consent.overwrite_paths` is overwritten | WP01 | |
| T005 | Ratchet: unattended upgrade leaves a real edit byte-identical and still reports it | WP01 | |
| T006 | Red-first: `doctor tool-surfaces --fix` replaces a real command-skill edit (#5575) | WP02 | |
| T007 | Provider `repair` passes drifted paths as `ApplyConsent.overwrite_paths` | WP02 | |
| T008 | Drift finding names `spec-kitty doctor tool-surfaces --fix`; probe reports canonical bytes as present | WP02 | |
| T009 | Guard: unattended paths never hand drifted command skills to `repair` | WP02 | |
| T010 | Red-first: Git-clean CRLF checkout yields an empty staging plan (#5576) | WP03 | [P] |
| T011 | Ratchet: a real token change saved with CRLF is still staged, alone | WP03 | [P] |
| T012 | `GitPort.changed_vs_ref` object-id compare (batched, fail closed) | WP03 | [P] |
| T013 | Route `_files_changed_vs_ref` through it; re-pin the trio seam gate; update both fake ports | WP03 | [P] |
| T014 | Entry-point check: `implement --no-auto-commit` no longer refuses on a Git-clean CRLF checkout | WP03 | [P] |

## WP01 — Command-skill installer: canonical bytes are fresh, consent is honored

**Prompt**: [tasks/WP01-installer-canonical-fresh-and-consent.md](tasks/WP01-installer-canonical-fresh-and-consent.md) · **Priority**: P1 · **Estimated prompt**: ~260 lines
**Goal**: closes #5574 at the owner; adds the installer half of #5575's consent.
**Independent test**: `spec-kitty upgrade --yes` on a project whose command skills equal today's rendering but carry an older recorded hash exits 0 and records the canonical hash.

- [ ] T001 Red-first: unattended upgrade with canonical bytes and an old recorded hash exits 0 (#5574) (WP01)
- [ ] T002 Red-first unit: installer treats canonical bytes as fresh and refreshes the recorded hash (WP01)
- [ ] T003 Installer: `preserve()` lets canonical bytes through; adopt-only refreshes an existing entry's hash (WP01)
- [ ] T004 Installer: a `consent_required` path named in `consent.overwrite_paths` is overwritten (WP01)
- [ ] T005 Ratchet: unattended upgrade leaves a real edit byte-identical and still reports it (WP01)

Dependencies: none. Risks: `install_command` is near the complexity ceiling; extract a helper. The adopt-only pass must still refuse unknown bytes.

## WP02 — Command-skill repair: the explicit repair replaces a real edit

**Prompt**: [tasks/WP02-command-skill-repair-consent.md](tasks/WP02-command-skill-repair-consent.md) · **Priority**: P1 · **Estimated prompt**: ~220 lines
**Goal**: closes #5575 — `doctor tool-surfaces --fix` overwrites a drifted command skill, as it does for agent profiles; guidance names it.
**Independent test**: after a real edit, `doctor tool-surfaces --kind command-skill --fix --json` exits 0, the file equals the canonical rendering, and a second run reports no findings.

- [ ] T006 Red-first: `doctor tool-surfaces --fix` replaces a real command-skill edit (#5575) (WP02)
- [ ] T007 Provider `repair` passes drifted paths as `ApplyConsent.overwrite_paths` (WP02)
- [ ] T008 Drift finding names `spec-kitty doctor tool-surfaces --fix`; probe reports canonical bytes as present (WP02)
- [ ] T009 Guard: unattended paths never hand drifted command skills to `repair` (WP02)

Dependencies: Depends on WP01 (installer honors `overwrite_paths`). Risks: never populate `overwrite_paths` from non-drifted statuses.

## WP03 — Planning-artifact staging uses Git's clean view

**Prompt**: [tasks/WP03-planning-staging-git-object-ids.md](tasks/WP03-planning-staging-git-object-ids.md) · **Priority**: P1 · **Estimated prompt**: ~240 lines
**Goal**: closes #5576 — a Git-clean CRLF checkout neither blocks `implement --no-auto-commit` nor makes an empty commit; a real edit is still staged.
**Independent test**: real-git repository with `* text=auto eol=crlf`; `resolve_planning_artifact_staging(..., auto_commit=False)` returns an empty `files_to_commit`.

- [ ] T010 Red-first: Git-clean CRLF checkout yields an empty staging plan (#5576) (WP03)
- [ ] T011 Ratchet: a real token change saved with CRLF is still staged, alone (WP03)
- [ ] T012 `GitPort.changed_vs_ref` object-id compare (batched, fail closed) (WP03)
- [ ] T013 Route `_files_changed_vs_ref` through it; re-pin the trio seam gate; update both fake ports (WP03)
- [ ] T014 Entry-point check: `implement --no-auto-commit` no longer refuses on a Git-clean CRLF checkout (WP03)

Dependencies: none. Parallel with WP01/WP02.

## Sequencing

WP01 → WP02 (shared consent seam); WP03 in parallel. MVP: WP01 (unblocks unattended upgrade).
