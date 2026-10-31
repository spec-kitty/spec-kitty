# Implementation Plan: Plugin bundle directory conformance

**Branch**: `issue-6479-plugin-bundle-directory-conformance` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/plugin-bundle-directory-conformance-01M68ZVP/spec.md`
**Issue**: spec-kitty/spec-kitty#6479

## Summary

Bring every artifact `spec-kitty plugin build` emits into line with the
directory requirements its own issue lists, without touching the staging/write
machinery and without absorbing the three items the operator's triage owns
elsewhere.

Three targets are affected:

- **Claude Code** (`bundles/claude.py`): drop the top-level `bin/` wrapper pair
  (a hard submission refusal), stop redeclaring the host-default
  `hooks/hooks.json`, and add `homepage`/`repository`/`license`.
- **Codex/OpenAI** (`bundles/codex.py`): SemVer `version`, `./skills/`,
  `interface.shortDescription` ≤30 with the guard corrected to 30, the full
  `interface` listing field set with its pinned limits, `requires_local_executor`,
  and the square brand asset the manifest now declares.
- **Copilot/VS Code** (`bundles/projection.py::plugin_manifest_payload`): an
  Agent Plugins 1.0.0 manifest — the pinned `$schema` const, only keys that
  closed schema defines (so `distribution_target` goes), a real SemVer version
  and a real description.

One new helper (`_builder.to_semver`) is the single PEP 440 → SemVer projection.
One new conformance suite drives everything through the real entry points.

Technical approach: keep the existing prepared-then-applied staging model; the
change is confined to *what* is staged and *what the manifest says*, plus one
shipped asset. No new provider, no new CLI flag, no network call at build time.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; CI matrix 3.11–3.13)
**Primary Dependencies**: `typer` (CLI), `packaging` (already a runtime dep — used
for the PEP 440 → SemVer projection), `pytest` for the suite
**Storage**: files only — the bundle staging tree under `--output-dir`
**Testing**: `pytest`; the new suite is a fast unit module that calls
`ClaudeBundleProjector.build`, `CodexBundleProjector.build` and the Copilot/VS
Code projectors, plus unit tests for the SemVer helper
**Target Platform**: cross-platform CLI (POSIX + Windows wrapper deletion is
platform-neutral)
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: no measurable change; the removed wrapper pair is two
files fewer per Claude build
**Constraints**: no network at build time; deterministic/idempotent output;
external field limits pinned as constants and asserted by tests
**Scale/Scope**: 4 source modules (`claude.py`, `codex.py`, `projection.py`,
`_builder.py`), 1 deletion (`claude_wrapper.py` + its test module), 1 asset,
1 new test module, 1 doc page, changelog

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — one SemVer projection (`to_semver`), one
  manifest builder per target, one brand asset. The Agent-Plugins `$schema` and
  every field limit are declared once as named constants next to the manifest
  builder that must honour them, and the suite reads the same constants.
- **Architectural alignment / locality of change** — edits stay inside
  `src/specify_cli/tool_surface/bundles/`; the Copilot/VS Code fix lands in the
  shared `plugin_manifest_payload` that both projectors already call, instead of
  a second manifest source. No provider, registry or CLI surface changes.
- **ATDD-first / red-first** — the conformance suite is written first and run
  against unmodified `main` output to prove it fails for the reported reasons.
- **Terminology** — "plugin bundle", "manifest", "distribution target" keep their
  existing meanings; the mission does not rename a surface.
- **Quality gates** — no gate is weakened; the CI validator pin and the release
  attestation are out of scope by C-002 and named in the PR's `## Deferred`.
- **Campsite rule** — the wrapper module and its test module go with the wrapper
  output they exist to produce (NFR-004); no dead code is left behind.
- **Test economy** — one new module, asserting behaviour that would otherwise be
  unguarded; no test is added for a helper the suite already covers through the
  entry point.

## Project Structure

### Documentation (this mission)

```
kitty-specs/plugin-bundle-directory-conformance-01M68ZVP/
├── plan.md              # this file
├── research.md          # Phase 0 (decisions, pinned values, deferrals)
├── spec.md              # the specification
├── checklists/          # spec quality checklist
└── tasks/               # produced by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/tool_surface/bundles/
├── _builder.py            # + to_semver(); version projection for every target
├── claude.py              # - bin/ staging, - hooks pointer, + links/license
├── claude_wrapper.py      # DELETED (its only consumer was the bin/ staging)
├── codex.py               # SemVer, ./skills/, 30-char guard, listing fields
├── copilot.py             # unchanged layout; inherits the fixed shared manifest
├── projection.py          # plugin_manifest_payload -> Agent Plugins 1.0.0
├── vscode.py              # unchanged (inherits Copilot)
└── assets/logo.png        # NEW: square brand mark declared by the Codex manifest

tests/specify_cli/tool_surface/
├── test_plugin_manifest_directory_conformance.py   # NEW conformance suite
├── test_plugin_build_claude.py                      # updated expectations
├── test_plugin_build_codex.py                       # updated expectations
└── bundles/
    ├── test_claude.py                               # updated expectations
    ├── test_claude_wrapper.py                       # DELETED with the module
    ├── test_copilot.py                              # updated expectations
    └── test_projection.py                           # manifest payload expectations

docs/guides/how-to/installation/install-claude-code-plugin.md  # wrapper section removed
docs/changelog/CHANGELOG.md                                    # [Unreleased] entry
pyproject.toml                                                 # ship the .png artifact
```

## Implementation Concern Map

- **IC-01 Version projection.** `to_semver()` in `_builder.py`: PEP 440 →
  SemVer, never raising; every manifest consumer uses it. Unit-tested directly
  and through each build.
- **IC-02 Claude reduction.** Remove the two wrapper `StagedFile`s and the
  module import; delete `claude_wrapper.py` and its test module; drop the now
  unused `wrapper` branch in `projection.apply_staging` and the `wrapper` field
  in `StagedFile` if nothing else sets it; document the change.
- **IC-03 Shared manifest.** `plugin_manifest_payload` becomes the Agent Plugins
  1.0.0 payload builder (schema const + identity + links), taking the resolved
  version so `0.0.0` disappears. Copilot and VS Code inherit automatically.
- **IC-04 Codex manifest.** Codex-format fields with pinned limits, the brand
  asset staged at `./assets/logo.png`, `requires_local_executor`, and the
  existing forbidden-key guard kept intact.
- **IC-05 Conformance suite.** One module that builds through the production
  entry points and asserts each requirement, every absence assertion paired with
  a same-fixture positive control (tactic
  `acceptance-criteria-non-vacuity`).

## Phases

- **Phase 0 — research** (done): decisions and pinned external values are in
  `research.md`, including the reproduced baseline and the three deferrals.
- **Phase 1 — design**: this plan; no `data-model.md` (no persistent entity),
  no `contracts/` directory (the "contract" is the external manifest schema,
  pinned as constants and asserted by the suite).
- **Phase 2 — tasks**: `/spec-kitty.tasks` slices IC-01..IC-05 into work
  packages; the red test lands before the fixes (WP ordering below).
- **Phase 3 — implementation**: drive each WP with `spec-kitty next`.

### Work-package slicing (input to Phase 2)

- **WP01 — version projection + shared Agent-Plugins manifest** (IC-01, IC-03):
  the suite's version and Copilot/VS Code assertions go red first, then the
  helper and the shared payload land.
- **WP02 — Claude bundle reduction + Codex directory conformance** (IC-02,
  IC-04): the wrapper removal, the hooks-pointer removal, the Codex manifest
  fields and the shipped asset.
- **WP03 — conformance suite completion, docs and changelog** (IC-05): the
  remaining assertions, the how-to update, the `[Unreleased]` entry, and the
  packaging artifact guard for the new asset.

## Risks

- **Snapshot-style tests.** Several existing tests assert the current bundle
  contents (including the `bin/` wrapper). They must be updated deliberately, not
  relaxed: each changed assertion is replaced by one that pins the new required
  shape.
- **Asset shipping.** A manifest that points at an unshipped file is worse than
  no field; `pyproject.toml` must gain the `.png` artifact and the suite asserts
  the artifact glob is present.
- **Scope creep.** The three deferred items are tempting (they are what the issue
  body lists after the defects). The plan keeps them out and the PR names them.
