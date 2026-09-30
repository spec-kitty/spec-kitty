# Implementation Plan: Docs lint: codespell and changelog Unreleased guard

**Branch**: `issue-5426-docs-lint` (stacked on PR #5420) | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docs-lint-codespell-changelog-guard-01M3RFGJ/spec.md`

Planning questions were answered by the operator's steer (issue #5426 body is the source of truth), two grounding scouts, and the post-spec adversarial squad (findings and dispositions: the `design-decisions` tracer on the coordination branch; summary in [research.md](research.md)). No open planning questions remain.

## Summary

Add two blocking docs checks:

1. **Spelling.** A pinned `codespell` runs through one entry point, `scripts/docs/check_spelling.py`, in three passes:
   - a typo pass over `docs/**/*.md`, `README.md` and `packs/built-in/**/*.md`;
   - an en-GB→en-US pass over `docs/guides/` and `docs/context/`;
   - the same US pass over the changelog's `## [Unreleased]` section only.

   Dictionary, skip list and ignore list live in `[tool.codespell]` in `pyproject.toml`.
2. **Changelog Unreleased style guard.** `scripts/docs/check_changelog_style.py` holds the heading, entry-shape, banned-token and length rules. Planted-violation tests live in `tests/docs/`.

Both checks locate the Unreleased section through one extractor added beside the existing changelog heading grammar in `scripts/release/validate_release.py`. A new always-on, unmasked `docs-lint` CI job runs both scripts with `python -m` (never pytest), and `make docs-lint` runs the same two commands. The mission also fixes the measured in-scope typos and UK spellings. It renames three UK glossary headings with legacy anchors, and writes contributor guidance under `docs/development/`.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor). CI uses Python 3.12 via `astral-sh/setup-uv`.
**Primary Dependencies**: `codespell==2.4.3` (new, dev dependency group only; GPL-2.0-only, never shipped: `scripts/` and dev groups are outside the wheel). The two new modules otherwise use only the standard library (`re`, `subprocess`, `dataclasses`, `argparse`, `pathlib`, `tempfile`).
**Storage**: N/A (reads repository files; planted tests use `tmp_path`).
**Testing**: pytest in `tests/docs/`, marked `pytest.mark.unit` + `pytest.mark.fast`, following the `tests/docs/test_tracker_egress_upgrade_note_3108.py` pattern: text-in checker, one run on the real file, planted mutants. Tests call the production entry points (`main(argv)` and one `python -m` subprocess per script), not only helpers.
**Target Platform**: Linux CI (`ubuntu-24.04`) and developer machines (Linux/macOS/Windows; no shell-specific constructs in the scripts).
**Project Type**: single. Repo tooling under `scripts/docs/`, `scripts/release/`, `tests/docs/`, `.github/workflows/`, `Makefile`.
**Performance Goals**: both spelling passes finish in under 5 s. Measured: about 0.35 s for the typo pass, 0.08 s for the US pass, 0.02 s for the Unreleased US pass. The guard's test module finishes in under 2 s.
**Constraints**: no pytest in any new always-on job (`tests/architectural/test_no_duplicate_suite_execution.py`). Released changelog sections are only typo-corrected. `kitty-specs/`, `kitty-ops/` and `docs/archive/` stay untouched (archive-freeze). ruff, ruff format and mypy stay clean. Complexity is ≤ 15 per function. New code has ≥ 90% coverage.
**Scale/Scope**: about 670 markdown files in the typo scope; the Unreleased section has 224 entries; 4 typo fixes, about 62 US-spelling prose fixes, and 3 glossary heading renames.

### Supply-chain check (DIRECTIVE_051), codespell 2.4.3

| Control | Result |
|---|---|
| Registry authenticity | pypi.org `codespell`, project `codespell-project/codespell` on GitHub. Resolved through `uv.lock` from the default index; no mirror or extra index. |
| Freshness | First published 2016-06-09. 2.4.3 uploaded 2026-07-15 (wheel `sha256:af2505b3…`), about 11 weeks before adoption. Latest release, not yanked. |
| Lifecycle scripts | Pure `py3-none-any` wheel with no install hooks and no runtime dependencies on Python ≥ 3.11 (`chardet` and `tomli` are optional extras we do not enable). |
| Lockfile-driven install | Pinned exactly in `[dependency-groups].dev`, with `uv.lock` regenerated in the same commit. CI installs with `uv sync --frozen`, and the `uv-lock` job enforces `uv lock --check`. |
| Incident / IoC posture | No known incident advisory for codespell. It is invoked as a subprocess (`python -m codespell_lib`), so its GPL code is never imported into repository modules, and it makes no network calls at run time. |

Adversarial evidence: the dependency decision was operator-fixed (issue #5426 tool choice) and challenged by the post-spec squad, which found no contested finding on the dependency itself. The license and subprocess decision is recorded in research.md (R-2).

## Charter Check

| Charter rule | Status |
|---|---|
| Single canonical authority | Pass. One Unreleased extractor, placed beside the existing `parse_changelog_heading` grammar. One dictionary config (`[tool.codespell]`). Scope roots are named constants in one script. CI YAML and the Makefile carry no codespell arguments. |
| Architectural alignment / pack tiers | Pass. Repo tooling only. Nothing goes into `packs/built-in` (it would ship to consumers) and nothing goes into doctrine. `packs/built-in/**/*.md` is only a spell-check input. |
| ATDD-first / red-first | Pass. Each work package opens with its failing tests: planted violations, and a live-tree test that is red on the base where fixes are due. |
| Non-vacuous gates (DIRECTIVE_043) | Pass. Every rule has a planted red test plus a same-fixture positive control. The pre-rewrite Unreleased section is a real-world red control. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass. Only named gate files run: `test_pyproject_shape.py`, `test_dual_mode_contract.py`, `test_no_duplicate_suite_execution.py`, `test_ci_module_wiring.py`, `test_workflow_script_import_guard.py`, `test_no_legacy_terminology.py`. |
| Terminology canon | Pass. The guard bans the retired `spec-kitty merge` outside its rename context. No "feature" wording is added. The renamed glossary term keeps its UK form as an alias. |
| Campsite (Standing Order 2) | Scoped. The duplicate heading regex in `scripts/release/extract_changelog.py` and the terminology guard's private extractor are left alone for locality (migrating the guard would shrink what it scans). They are noted in the PR body. |
| Sonar / complexity | Rules are small, pure functions: one function per rule, each returning findings. |

No violations; Complexity Tracking not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docs-lint-codespell-changelog-guard-01M3RFGJ/
├── spec.md
├── plan.md              # this file
├── research.md          # grounding + squad synthesis, decisions R-1..R-8
├── data-model.md        # Unreleased section / Entry / Finding shapes
├── quickstart.md        # contributor-facing local usage (seed for the docs page)
├── contracts/
│   └── check-cli.md     # CLI contract of the two scripts
└── tasks.md             # /spec-kitty.tasks output
```

### Source Code (repository root)

```
pyproject.toml                         # [dependency-groups].dev += codespell==2.4.3; [tool.codespell]
uv.lock                                # regenerated
scripts/release/validate_release.py    # + unreleased_section(text) extractor (reuses CHANGELOG_HEADING_RE)
scripts/docs/check_changelog_style.py  # new: heading / shape / banned-token / length rules, main(argv)
scripts/docs/check_spelling.py         # new: three codespell passes via subprocess, main(argv)
tests/docs/test_changelog_style.py     # new: planted violations, live-text pass, pre-rewrite red control
tests/docs/test_check_spelling.py      # new: fixture-tree planted typos / UK words / skip-tree pairs
tests/docs/test_docs_spelling_live.py  # new: live tree is clean under all three passes
.github/workflows/ci-router.yml        # + always-on `docs-lint` job; + router-gate needs
tests/ci/test_ci_module_wiring.py      # + docs-lint in _ALWAYS_ON_JOB_NAMES
Makefile                               # + docs-lint target (no pytest)
docs/changelog/CHANGELOG.md            # 2 Changed-entry defects fixed, 1 Internal entry added, 2 released-section typos
docs/guides/**, docs/context/**, docs/adr/3.x/ (2 files)  # typo + US-spelling prose fixes, glossary renames
src/specify_cli/.contextive/execution.yml                 # regenerated after the glossary rename
docs/development/how-to/review-gates.md, docs/development/reference/ci-gate-mechanics.md  # contributor guidance
docs/development/3-2-page-inventory.yaml, docs/development/3-2-docs-retrieval-index.yaml  # regenerated
```

**Structure Decision**: repository tooling in `scripts/docs/`, which the `docs` path group already routes, so script edits re-run `tests-docs`. The rules live in importable modules with a `main()`, so the always-on CI job and `make docs-lint` run them without pytest, and the tests exercise the same entry points.

## Implementation Concern Map

### IC-01 — Canonical Unreleased extractor and changelog style guard

- **Purpose**: stop the Unreleased section drifting back into maintainer prose; give both checks one definition of "the Unreleased section".
- **Relevant requirements**: FR-008, FR-009, FR-010, FR-011, FR-012, FR-016; SC-002, SC-005; C-002, C-003.
- **Affected surfaces**: `scripts/release/validate_release.py`, `scripts/docs/check_changelog_style.py`, `tests/docs/test_changelog_style.py`. In `docs/changelog/CHANGELOG.md`: the two Changed entries named in C-003, plus one Internal entry for this change.
- **Sequencing/depends-on**: none.
- **Risks**:
  - Rule calibration against 224 real entries; the exact thresholds are in research.md R-4.
  - The two Changed-entry fixes need the true before-behavior from their PR/issue (#5100), not an invented one.
  - The extractor must ignore `## [` inside fenced blocks.

### IC-02 — Spelling check tooling

- **Purpose**: a pinned, config-driven typo pass and a scoped US-spelling pass, one entry point.
- **Relevant requirements**: FR-001, FR-002, FR-004, FR-005, FR-013 (entry point), FR-014; NFR-001, NFR-002, NFR-003.
- **Affected surfaces**: `pyproject.toml`, `uv.lock`, `scripts/docs/check_spelling.py`, `tests/docs/test_check_spelling.py`.
- **Sequencing/depends-on**: IC-01 (extractor).
- **Risks**:
  - Skip-glob semantics differ between directory walks and explicit file arguments (use the `*dir,*dir/*` pair from research R-3).
  - The code-span and anchor ignore-regex must apply only to the US passes.
  - Planted tests must run over a fixture tree that reproduces the skip paths, with the real config.

### IC-03 — Content fixes and the live-tree gate

- **Purpose**: make the real tree green without ignoring real errors.
- **Relevant requirements**: FR-003, FR-006, FR-007; SC-001.
- **Affected surfaces**:
  - 4 typo fixes: 2 in released changelog sections, 2 in ADRs.
  - About 62 prose fixes in `docs/guides/` and `docs/context/`.
  - Glossary renames: `docs/context/charter.md` (Organisation Tier, plus 7 in-page links), `docs/context/execution.md` (communication artefact, kept as an alias), and `docs/guides/gstack-glossary-observations.md` (Trail Behaviour).
  - Regenerated derived files: contextive YAML and the retrieval index.
  - New `tests/docs/test_docs_spelling_live.py`.
- **Sequencing/depends-on**: IC-02.
- **Risks**:
  - Quoted literals such as the CLI message `recognised` and identifiers such as `behaviour-driven-development` go in code spans; they are not respelled.
  - The `src/specify_cli/.contextive/` edit triggers a run-all CI.
  - Docs edits require the inventory and index regeneration.

### IC-04 — CI and local wiring

- **Purpose**: make both checks blocking on every PR, with one local command that mirrors CI.
- **Relevant requirements**: FR-013, FR-014; SC-003; C-005.
- **Affected surfaces**:
  - `.github/workflows/ci-router.yml`: a new `docs-lint` job, also added to the router-gate `needs`.
  - `tests/ci/test_ci_module_wiring.py`: `_ALWAYS_ON_JOB_NAMES`.
  - `Makefile`: the `docs-lint` target and its `.PHONY` entry.
- **Sequencing/depends-on**: IC-01 and IC-02 (the scripts must exist). It can run in parallel with IC-03.
- **Risks**: the router-gate `needs` set-equality check (`test_dual_mode_contract.py`), the duplicate-suite ledger, and the workflow-script import guard. The job must not call `make` or pytest.

### IC-05 — Contributor guidance

- **Purpose**: contributors can run both checks locally, add an ignore word, and exempt a quoted literal.
- **Relevant requirements**: FR-015; SC-004.
- **Affected surfaces**: `docs/development/how-to/review-gates.md` ("Changelog update and style" section); `docs/development/reference/ci-gate-mechanics.md` (new `docs-lint` entry); the regenerated page inventory and retrieval index.
- **Sequencing/depends-on**: IC-03 and IC-04 (it documents the final commands; it shares the regenerated index file with IC-03).
- **Risks**: frontmatter `updated:` dates and the 50–180 character description gate; the doc must warn that bare `codespell` scans the whole repository.
