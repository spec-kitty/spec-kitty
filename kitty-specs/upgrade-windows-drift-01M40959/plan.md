# Implementation Plan: Upgrade and Windows drift

**Branch**: `kitty/upgrade-windows-drift` (planning base and consolidation target) | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-windows-drift-01M40959/spec.md`

## Summary

Three upgrade-time false alarms, one seam each:

- **#5574** — a command skill whose bytes equal today's canonical rendering is classified as drifted because only the recorded install hash is consulted. The adoption pass that runs before every upgrade refuses any path that already has a manifest entry. Fix at the owner (`command_installer`): canonical bytes are fresh, and the recorded hash is refreshed to the canonical digest.
- **#5575** — a genuine edit to a command skill can never be replaced through the documented repair. `CommandSkillsProvider.repair` grants only automatic consent, so the installer's `consent_required` disposition always wins. Mirror the agent-profile provider: the explicit repair names the drifted paths in `ApplyConsent.overwrite_paths`, and the installer honors them. Unattended upgrade stays report-only.
- **#5576** — on a checkout with CRLF line-ending conversion, planning artifacts that Git reports as clean are classified as changed. The predicate compares raw `git show` blob bytes with raw working-tree bytes. Compare Git object ids after the clean filter instead (`git hash-object --stdin-paths` versus the ref's tree entry).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml; git CLI (no new dependency)
**Storage**: `.agents/skills/` files plus the command-skill manifest (`manifest_store`); git object store
**Testing**: pytest. Red-first per bug through the real entry point; real git repositories for #5576.
**Target Platform**: Linux, macOS, Windows (the CRLF case is reproduced on Linux with `.gitattributes eol=crlf`)
**Project Type**: single project (`src/specify_cli/`)
**Performance Goals**: #5576 adds at most one batched `git hash-object --stdin-paths` and one `git ls-tree` per staging decision, not one subprocess per file
**Constraints**: no new public CLI flag (C-002); never rewrite a real user edit without explicit repair (C-003); never hide a real content change (C-004)
**Scale/Scope**: three issues, three work packages, about 6 source files

## Charter Check

| Gate | Status | Note |
|------|--------|------|
| User Customization Preservation | PASS | Real edits are overwritten only by the explicit repair (`doctor tool-surfaces --fix`, or the interactive upgrade "yes"). Unattended upgrade writes zero bytes to an edited file (NFR-002). |
| ATDD-first / red-first (C-011) | PASS | Each WP opens with a failing test through the real entry point; FR-002 and FR-005 are the paired ratchets that keep a real edit (command or planning file) outstanding. |
| Ownership boundaries for mutating flows | PASS | Classification and consent stay in the command-skill owner (`command_installer`); providers only build consent. No second writer. |
| Canonical sources | PASS | Product code only; no template or `packs/built-in/` change expected. |
| Complexity ≤ 15, no suppressions | PASS (watch) | `install_command` and `_files_changed_vs_ref` are near the ceiling; extract helpers rather than grow them. |
| Terminology canon | PASS | Mission, never feature, in new prose. |

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-windows-drift-01M40959/
├── spec.md
├── research-memo.md     # grounding squad brief
├── plan.md              # this file
├── research.md          # Phase 0 decisions
├── data-model.md        # classification states
├── quickstart.md        # reproduce and verify
├── contracts/
│   ├── command-skill-drift.md
│   └── planning-artifact-staging.md
└── tasks.md             # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/skills/
├── command_installer.py        # preserve(), install_command() adopt path  (#5574, #5575)
└── manifest_store.py           # repair_stale_manifest() drifted report     (#5574)
src/specify_cli/tool_surface/providers/
└── command_skills.py           # repair() consent; probe() finding text       (#5575)
src/specify_cli/cli/commands/
└── implement_cores.py          # _files_changed_vs_ref(), GitPort             (#5576)

tests/specify_cli/skills/test_command_installer.py
tests/specify_cli/skills/test_crlf_skill_render_4998.py
tests/specify_cli/tool_surface/providers/test_command_skills.py
tests/specify_cli/cli/commands/test_upgrade*.py           # entry-point red-first
tests/specify_cli/cli/commands/test_implement_coord_idempotency.py
tests/specify_cli/cli/commands/test_implement_cores.py
tests/architectural/test_trio_seam_only.py                # re-pin token
```

**Structure Decision**: single project; changes stay inside the existing owners named above.

## Implementation Concern Map

### IC-01 — Canonical bytes are fresh

- **Purpose**: stop reporting command skills as drifted when their bytes equal today's canonical rendering, and refresh the recorded hash so later probes agree.
- **Relevant requirements**: FR-001, NFR-001, SC-001
- **Affected surfaces**: `command_installer.py` `preserve` (~715) and `install_command` adopt-only branch (~674-685); `manifest_store.repair_stale_manifest` (~446) drifted list.
- **Sequencing/depends-on**: none
- **Risks**: the `same and existing` branch keeps the old `content_hash`, so a refresh must replace the entry's hash, not only skip the consent check. Adopt-only must still refuse unknown bytes and absent files. Keep `verify()` read-only.

### IC-02 — Explicit repair replaces a real edit

- **Purpose**: let the documented repair overwrite a genuinely edited command skill, as it already does for agent profiles, while unattended upgrade keeps it byte-identical.
- **Relevant requirements**: FR-002, FR-003, NFR-001, NFR-002, C-002, C-003, SC-002
- **Affected surfaces**: `command_installer.py` `preserve` (honor `inputs.consent.overwrite_paths`; `apply_commands` already compares the whole consent); `command_skills.py` `repair` (~364-392) builds `ApplyConsent(automatic=True, overwrite_paths=<drifted rels>)`; `probe` finding names `spec-kitty doctor tool-surfaces --fix` and reports canonical bytes as present (via a read-only `command_installer.canonical_digest`).
- **Sequencing/depends-on**: IC-01 (shares `preserve`; land IC-01 first to avoid a conflict)
- **Risks**: only drifted statuses may populate `overwrite_paths`. `_apply_auto_repairs` passes missing/stale only, which keeps unattended upgrade safe; pin that with a test. An interactive upgrade "yes" already records `drifted_overwritten`; after this change that record becomes true.

### IC-03 — Git's view of clean decides staging

- **Purpose**: classify a planning artifact as changed only when its clean-filtered object id differs from the ref's, so CRLF checkouts neither block `--no-auto-commit` nor make an empty commit.
- **Relevant requirements**: FR-004, FR-005 (ratchet for a real edit), NFR-001, C-004, SC-003, SC-004
- **Affected surfaces**: `implement_cores.py` `_files_changed_vs_ref` (~471-495) and the `GitPort` protocol plus its subprocess adapter; `tests/architectural/test_trio_seam_only.py` pin (~492-501).
- **Sequencing/depends-on**: none
- **Risks**: fail closed (treat a file as changed) on any git error; keep `show_blob` unchanged; batch the calls; update `_FakeGitPort` in tests.

## Branch contract

Current branch at plan start: `kitty/upgrade-windows-drift`. Planning/base branch: `kitty/upgrade-windows-drift`. Completed changes consolidate into `kitty/upgrade-windows-drift`; `branch_matches_target` is true. Publication is a PR from the fork to `spec-kitty/spec-kitty` `main`.
