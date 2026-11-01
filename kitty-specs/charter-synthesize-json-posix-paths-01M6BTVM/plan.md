# Implementation Plan: Charter synthesize JSON reports POSIX paths on every OS

**Branch**: `issue-6277-charter-synthesize-json-posix-paths` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/spec.md`
**Input**: Mission specification from `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/spec.md`

## Summary

`charter synthesize --json` renders repository-relative paths with
`str(Path.relative_to(...))`, so Windows reports `\` where Linux/macOS report `/`. Two
sites produce that spelling: the fresh-seed helpers in
`src/specify_cli/cli/commands/charter/_fresh_project_layer.py` (which feed
`files_written`, `files_planned`, `planned_deletes`, `written_artifacts[].path`) and the
write pipeline's `ManifestArtifactEntry.path`
(`src/charter/activation/synthesizer/write_pipeline.py`), whose recorded value the real-run
envelope projects verbatim.

The approach is one spelling rule rather than per-field patching: a small shared helper in
`src/kernel/charter_pack_paths.py` turns `(path, repo_root)` into a repo-relative POSIX
string; every emitting site calls it, and the manifest projection normalises the string it
reads so an older Windows-written manifest cannot re-leak a backslash. A Windows-simulated
regression test (patch `Path.relative_to` to return a Windows-flavoured path) proves the
defect red-first on POSIX CI, and the acceptance scenario returns to asserting the full
`.kittify/...` paths that #6266 relaxed.

## Technical Context

**Language/Version**: Python 3.11 (project `requires-python >= 3.11`)
**Primary Dependencies**: stdlib `pathlib` only — no new dependency; `typer` CLI surface unchanged
**Storage**: files under `.kittify/` (JSON envelope on stdout; `synthesis-manifest.yaml` on disk)
**Testing**: pytest (`uv run pytest`), unit tier `tests/specify_cli/cli/commands/charter/` + `tests/charter_pack_synthesizer/`; acceptance scenarios via the repo's BDD runner for `tests/scenarios/charter/charter.feature`
**Target Platform**: cross-platform CLI (Linux, macOS, Windows)
**Project Type**: single project — `src/specify_cli/cli/commands/` (CLI surface) + `src/charter/activation/synthesizer/` (synthesis pipeline) + `src/kernel/` (shared path helpers)
**Performance Goals**: no measurable cost — normalisation is `PurePath.as_posix()` on values already computed; no extra I/O in the JSON path
**Constraints**: envelope schema (`contracts/synthesis-envelope.schema.json`) unchanged; POSIX output byte-identical to today; no new OS-detection seam
**Scale/Scope**: 3 source files (2 changed, 1 helper added) + 1 CLI projection, 2 test modules, 1 acceptance feature file, 1 changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — PASS: the fix removes a split (fresh-seed `str()` vs
  direct-write `as_posix()`), converging both on one helper. It creates no second source of
  truth.
- **ATDD-first / red-first (DIRECTIVE_034)** — PASS: a failing regression test is written
  and demonstrated red against the unfixed code before the fix, through the pre-existing
  CLI entry point.
- **`change-apply-smallest-viable-diff` + DIRECTIVE_024 locality** — PASS: five call sites
  and one projection, no unrelated refactoring; the helper is additive.
- **DIRECTIVE_041 test value** — PASS: one focused regression module + the restored
  acceptance assertion; no characterization scaffolding, no per-WP shape tests.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — PASS: only the targeted charter-synthesis test
  selection runs locally; CI owns the full sweep.
- **Pre-existing Failure Reporting Rule** — applies if any local gate is red for reasons
  outside the diff; recorded in the PR `## Deferred` section, never skipped.
- **Changelog obligation** — PASS: user-facing envelope change ⇒ `[Unreleased]` entry under
  `docs/changelog/CHANGELOG.md`.

No violations; `Complexity Tracking` is therefore empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── kernel/
│   └── charter_pack_paths.py                      # add one repo-relative POSIX helper
├── charter/activation/synthesizer/
│   └── write_pipeline.py                          # record ManifestArtifactEntry.path POSIX
└── specify_cli/cli/commands/charter/
    ├── _fresh_project_layer.py                    # fresh-seed reported paths POSIX
    └── _synthesis.py                              # manifest projection normalises on read

tests/
├── unit/                                          # (n/a — this repo's tiers below)
├── charter/                                       # existing synthesis pipeline tests
└── specify_cli/cli/commands/charter/              # CLI-level regression test (new)

tests/scenarios/charter/charter.feature            # restore full-path assertions
docs/changelog/CHANGELOG.md                        # [Unreleased] entry
tests/scenarios/absorption-ledger.json             # note the restored assertion
```

**Structure Decision**: Single project. The change is confined to the charter synthesis
reporting path (`src/specify_cli/cli/commands/charter/`), the pipeline that persists the
recorded path (`src/charter/activation/synthesizer/write_pipeline.py`), and the shared path
helper module the charter pack already uses for path arithmetic
(`src/kernel/charter_pack_paths.py`). Tests follow the repo's existing tiers rather than a
new layout.

## Complexity Tracking

No charter-check violations; nothing to justify.

## Implementation Concern Map

### IC-01 — One repo-relative POSIX spelling

- **Purpose**: Give the charter surface a single function that turns a `Path` plus a repo
  root into the repo-relative POSIX string the envelope and the manifest both promise, so
  the spelling cannot drift between the fresh-seed, direct-write and manifest-projection
  paths.
- **Relevant requirements**: FR-001, FR-002, FR-004, C-001, C-002
- **Affected surfaces**: `src/kernel/charter_pack_paths.py` (new helper),
  `src/specify_cli/cli/commands/charter/_fresh_project_layer.py` (three call sites),
  `src/charter/activation/synthesizer/write_pipeline.py` (`rel_content`)
- **Sequencing/depends-on**: none
- **Risks**: the helper must preserve the current POSIX-host output byte for byte (a
  changed string would break committed fixtures); it must not accept an already-relative
  string and silently produce a doubled path.

### IC-02 — The envelope never leaks what an old manifest recorded

- **Purpose**: Normalise the manifest projection on read, so a `synthesis-manifest.yaml`
  written by an earlier Windows run (or hand-edited) still yields POSIX
  `written_artifacts[].path` in the real-run envelope.
- **Relevant requirements**: FR-003, C-001
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/_synthesis.py`
  (`_load_written_artifacts_from_manifest`)
- **Sequencing/depends-on**: IC-01 (same spelling rule; reads the helper for consistency)
- **Risks**: the four-field `WrittenArtifact` shape and the `[]`-on-absent-manifest
  behaviour must not change; the function must stay non-raising.

### IC-03 — Prove it red, then guard it end to end

- **Purpose**: Make the Windows spelling observable and gated on a POSIX-only CI: a
  simulated-Windows regression test at the CLI boundary (with a non-vacuity control), and
  the acceptance scenario restored to assert the full forward-slash paths.
- **Relevant requirements**: FR-005, FR-006, NFR-001, NFR-003, SC-001…SC-005
- **Affected surfaces**: `tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py`
  (new), `tests/scenarios/charter/charter.feature`, `tests/scenarios/absorption-ledger.json`
- **Sequencing/depends-on**: IC-01, IC-02 (the test must be red before them and green after)
- **Risks**: the simulation must patch rendering, not `os.name` (which flips `pathlib`
  mid-run and crashes pytest — `tests/kernel/test_is_windows_seam.py`); the control
  assertion must show the harness genuinely produces backslashes pre-fix.

### IC-04 — Tell the user

- **Purpose**: Record the behaviour change where consumers of the CLI look for it.
- **Relevant requirements**: spec "Changelog obligation"; SC-005
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]`)
- **Sequencing/depends-on**: IC-01
- **Risks**: keep the entry under 1,200 characters, bold impact-first lead with `(#6277)`,
  before/after.
