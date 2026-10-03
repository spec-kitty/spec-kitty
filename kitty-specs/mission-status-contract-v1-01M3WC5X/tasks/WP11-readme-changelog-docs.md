---
work_package_id: WP11
title: README final, CHANGELOG entries and docs section (IC-10, part a)
dependencies:
- WP10
requirement_refs:
- FR-001
- FR-024
- NFR-006
- C-008
- C-011
- SC-001
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T069
- T070
- T071
- T072
- T073
history: []
agent_profile: curator-carla
authoritative_surface: contracts/README.md
create_intent:
- contracts/README.md
- contracts/mission-status/CHANGELOG.md
execution_mode: code_change
model: sonnet
owned_files:
- contracts/README.md
- contracts/mission-status/CHANGELOG.md
- docs/changelog/CHANGELOG.md
- docs/development/reference/ci-gate-mechanics.md
- docs/development/docs-retrieval-index.yaml
role: curator
tags: []
tracker_refs: []
---

# WP11 - README final, CHANGELOG entries and docs section (IC-10, part a)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the final `contracts/README.md`, finish the module `CHANGELOG.md`, add the `[Unreleased]` changelog entry and the short contracts-gates section in the gate-mechanics reference, and regenerate the docs index if a heading was added. No new behaviour.

## Context

- First half of plan concern **IC-10** (second half, WP12, is the `kitty-specs/` evidence record; **split reason**: a `code_change` WP may not own `kitty-specs/` paths). **Single writer of the README final.** Depends on WP10 so every command and floor it documents exists.
- This WP is `code_change` because it owns `contracts/` paths; it owns no `kitty-specs/` path.
- **Open-PR overlap check (2026-10-02, `gh pr list` plus `gh pr diff --name-only` per PR)**: this WP is the only one that overlaps open pull requests. #5540 and #5326 both edit `docs/changelog/CHANGELOG.md`; #5540 also edits `docs/development/docs-retrieval-index.yaml`. This is a textual merge-conflict risk, not an ownership conflict (the PRs are outside this Mission). Mitigation: write a minimal single `[Unreleased]` entry, rebase last (orchestrator action), and regenerate the index with its script after the rebase rather than hand-resolving it. Re-run the overlap check at start and before hand-off and record the result. No open PR touches `contracts/` or the gate-mechanics reference.
- Binding rules:
  - **README (FR-001, NFR-006)**: one heading per required topic, each with one example: layout; path-file naming rule; relative `$ref` rules (no URL, absolute or `~1`; canonical spelling for brace-named files as recorded in `research.md` R-3 after WP02 and applied by WP04, or by WP09's re-sweep if it ran); `_shared/` admission criteria; per-module `info.version` and the `/api/v1` prefix; the `x-source`, `x-derived` and `x-provisional` extensions; status lane versus code lane and repo-root lane (execution lane only as the umbrella phrase tied to `docs/architecture/execution-lanes.md`); workflow phase (contract field `phases`) versus glossary `phase`, and `phaseLabel`; that the `Topology` enum is the stored `meta.json` shape and is unrelated to `MissionStatus.topology` in the status aggregate; that the bundle is a build product and is never committed; the one documented local command for validate and bundle with its prerequisite (a JDK and network access; NFR-006); that markdown lint of these files is advisory (the router's `markdownlint` job ends in `|| true`); the one-line collision note with `src/specify_cli/contracts/`; the board-column mapping as a consumer convention; the versioning rule (breaking moves major, additive minor, documentation-only patch; a bundle change with no version change fails the breaking-change job); the residual-risk statement on handle-shaped strings (R-6); the reader-author warning with the one-line local command `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py` (reader edits and `tests/contract/**`-only edits select no job, accepted risks R-14, P-10); the preview tag namespace `preview/mission-status/p<N>` and what each point promises (p0 unvalidated, p1 stable marker, p2 pin-grade) in two sentences. Headings must satisfy `contracts/tools/structure_check.py` (WP07): read its required list and match it.
  - **Module CHANGELOG (FR-024)**: headings for added, changed, removed, provisional and the current `info.version` (`1.0.0`) with the initial entry; any `Pre-release shape change` lines WP10 logged stay.
  - **`docs/changelog/CHANGELOG.md`**: the root `CHANGELOG.md` is a **symlink** to this file. Edit the target **in place** with the Edit tool; never through a tool that replaces the symlink with a regular file. One `## [Unreleased]` entry, **American spelling** and the house entry shape that `docs-lint` checks (`python -m scripts.docs.check_spelling`, `python -m scripts.docs.check_changelog_style`). No CLI version number appears (C-008).
  - **`docs/development/reference/ci-gate-mechanics.md`**: a short section on the contracts gates (what runs where, tier 1/2/3, that `contracts/**` selects `tests-corpus`, the post-merge-only observability of the fleet verdict). Bump the frontmatter `updated`. If a new `##` heading is added, regenerate `docs/development/docs-retrieval-index.yaml` with `python -m scripts.docs.docs_index --write` (never by hand) and run `tests/docs/test_docs_index_freshness.py`; alternatively add the content under an existing heading and leave the index alone.
  - No ADR is authored (C-011); the open ADR amendment on placement and transport is a separate decision on #5528.
- Terminology: Mission, never feature; no absolute host path, e-mail address or private-discussion reference (C-006).

### Test surface, gates and baseline

- Targeted: `tests/contract/test_structure_check.py`, `.venv/bin/python contracts/tools/structure_check.py --root contracts` and `.venv/bin/python contracts/tools/leak_scan.py --root contracts` (exit 0), `.venv/bin/python -m scripts.docs.check_spelling`, `.venv/bin/python -m scripts.docs.check_changelog_style`.
- Named docs files: `tests/docs/test_docs_index_freshness.py tests/docs/test_docs_index.py tests/docs/test_docs_freshness_invariant.py tests/docs/test_changelog_style.py tests/docs/test_check_spelling.py`. Baseline for them is WP01's baseline hand-off (`research.md` R-8). No full docs sweep. Also `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py` (the Mission's new prose lands in `docs/` and `contracts/`).
- README topic equality is mechanical and owned by WP07: `tests/contract/test_structure_check.py` plants the removal of each heading, and `structure_check.py` (heading constant copied from WP01's T007 list, the single authority) run over the final README is the equality check. This WP adds no test; T069 runs `structure_check` on the final README and the README must keep every T007 heading.
- Red-first (charter): the red-first evidence for README headings is WP07's planted-removal test (one planted removal per heading in `structure_check`'s own tests); WP01's README skeleton already holds every heading, so at this WP `structure_check` is green from the start and WP11 adds no test and claims no red state for it: it only confirms `structure_check` is green on the final README text. The docs-lint commands are red on a deliberately British-spelled draft line before the fix is applied (an uncommitted demonstration run).

## Subtasks

### Subtask T069: README final

**Purpose**: FR-001, NFR-006.
**Steps**: replace the WP01 skeleton with full text per the list above, with one example per topic; verify every command shown by running it (record exit codes); keep prose Mission-canonical.
**Files**: `contracts/README.md` (~300 lines).
**Validation**: `structure_check` and `leak_scan` exit 0.

### Subtask T070: Module CHANGELOG

**Purpose**: FR-024.
**Steps**: complete the headings and the initial `1.0.0` entry; keep WP10's shape-change lines; American spelling.
**Files**: `contracts/mission-status/CHANGELOG.md` (~60 lines).
**Validation**: `structure_check` exit 0.

### Subtask T071: Repository changelog entry

**Purpose**: house-style entry.
**Steps**: one `## [Unreleased]` entry in `docs/changelog/CHANGELOG.md` edited in place; run both docs-lint commands and the changelog-style test; confirm `ls -l CHANGELOG.md` still shows a symlink.
**Files**: `docs/changelog/CHANGELOG.md` (edited in place; the root `CHANGELOG.md` is a symlink to it).
**Validation**: both commands exit 0; symlink intact.

### Subtask T072: Gate-mechanics section and index

**Purpose**: place the new workflow family in the reference.
**Steps**: add the section (content: job list and tiers, router glob, no-pytest rule, early-start tag namespace pointer to the README, the post-merge verification list); bump `updated`; regenerate the index with its script if a heading was added; run the freshness tests.
**Files**: `docs/development/reference/ci-gate-mechanics.md` (new section), `docs/development/docs-retrieval-index.yaml` (regenerated by script only if a heading was added).
**Validation**: named docs files green.

### Subtask T073: Overlap re-check and final runs

**Purpose**: record the only open-PR overlap.
**Steps**: re-run `gh pr list --repo spec-kitty/spec-kitty --state open --json number,files` and `gh pr diff <n> --name-only` for each result touching this WP's files; record PR numbers and files; run the targeted commands, ruff, and (read-only) `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py` and `uv lock --check`; record counts and results for `close-out.md`.
**Files**: none in this WP's diff (hand-off record only; WP12 T075 records it in `close-out.md`).
**Validation**: results recorded in the hand-off for WP12; terminology guard green, `uv lock --check` exits 0.

## Definition of Done

- README, module CHANGELOG, repository changelog entry and gate-mechanics section are final; every required topic has a heading and an example; the one local command works as written.
- `structure_check`, `leak_scan`, docs-lint and the named docs tests are green; root `CHANGELOG.md` is still a symlink.
- Index regenerated by script iff a heading was added.
- Overlap re-check recorded (PRs and files).
- Terminology guard re-run green and `uv lock --check` exits 0, both recorded for `close-out.md`; `structure_check` exits 0 on the final README (every WP01 T007 heading present; WP07's planted-removal test is the mechanical check).
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Conflict with #5540 or #5326 on the changelog or index at rebase: single minimal entry; regenerate, do not hand-merge the index.
- Replacing the symlink: edit in place only.
- American-spelling lint failure on prose copied from the plan (which is British): rewrite.

## Reviewer Guidance

Check every README command runs; check headings against `structure_check`; check no CLI version number or host path; check the changelog entry shape and the symlink; check the index diff is script output.

Implementation command: `spec-kitty agent action implement WP11 --agent claude`
