---
work_package_id: WP04
title: Evidence, docs and the cross-cutting guards
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-009
- NFR-001
- NFR-002
- NFR-004
- SC-003
planning_base_branch: issue-6767-synthesis-ownership-single-reader
merge_target_branch: issue-6767-synthesis-ownership-single-reader
branch_strategy: Planning artifacts for this mission were generated on issue-6767-synthesis-ownership-single-reader. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6767-synthesis-ownership-single-reader unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 3 - Evidence
history: []
agent_profile: python-pedro
authoritative_surface: docs/changelog/CHANGELOG.md
create_intent:
- tests/architectural/test_single_synthesis_ownership_reader.py
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
- tests/architectural/test_single_synthesis_ownership_reader.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Evidence, docs and the cross-cutting guards

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

Closes #6767's documentation and drift-prevention half (FR-009, SC-001..SC-004, NFR-001..NFR-004).

- An architectural guard test pins the convergence: one ownership reader, one sidecar parser, one
  coded error, and the retired names absent from `src/`.
- An `[Unreleased]` changelog entry states the change for an operator, impact-first, with the issue
  reference, before/after, and the one documented code.
- The docs freshness check reports `errors=0`.
- The touched suites plus ruff/mypy are green at the tip.

## Context & Constraints

- Spec: `.../spec.md` FR-009, SC-001..SC-004, NFR-001..NFR-004; plan IC-04.
- Changelog rules: `docs/changelog/CHANGELOG.md` (`CHANGELOG.md` at the root is a symlink); the entry
  goes under `[Unreleased]`, is a bold impact-first lead ending in `(#6767)`, then before/after,
  under 1,200 characters.
- Do **not** regenerate the whole `docs/api/cli-commands.md` reference: this host runs many agents on
  one global asset cache and a full rebuild reads it concurrently. Regenerate only what this diff
  actually changes, then verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`).
- Guard-test placement: `tests/architectural/` holds repo-shape guards; check the suite's conventions
  (`pytest.mark.fast`? a shared helper for AST parsing?) before writing.

## Branch Strategy

- **Planning base branch**: `issue-6767-synthesis-ownership-single-reader`
- **Merge target branch**: `issue-6767-synthesis-ownership-single-reader`

```bash
spec-kitty agent action implement WP04 --agent python-pedro --mission synthesis-ownership-single-reader-01M68ZJM
```

## Subtasks & Detailed Guidance

### Subtask T016 – The drift guard

- **File**: `tests/architectural/test_single_synthesis_ownership_reader.py` (new).
- Assertions, each with the file path in the failure message:
  1. `src/charter/activation/synthesizer/manifest.py` defines `synthesized_urns` exactly once; no
     other module under `src/` defines a function that parses `synthesis-manifest.yaml` (AST: a
     `def` whose body references `MANIFEST_PATH` and is not in the record module). Keep it simple and
     tolerant: scan for `def <name>` whose body contains a call to `load_yml`/`load_yaml` on
     `MANIFEST_PATH` — a small allowlist of the record module is fine if the general rule is noisy.
  2. No module under `src/` outside the record module calls `ruamel.yaml.YAML`/`yaml.safe_load` on a
     `provenance` path or on `artifact_urn`. Practical form: `artifact_urn` string literals may only
     appear in the record module, the provenance model and the CLI display wrapper's *docstring*.
  3. `SYNTHESIS_MEMBERSHIP_UNREADABLE` is constructed in exactly one place under `src/`.
  4. The retired names (`_synthesized_urns`, `_SynthesisOwnershipUnreadableError`,
     `_extract_artifact_id_from_provenance`) appear nowhere under `src/`.
- Each guard must fail if the property is broken: verify by temporarily reverting one line locally
  and recording the red output in the history note (do not commit the revert).

### Subtask T017 – Changelog

- **File**: `docs/changelog/CHANGELOG.md`, under `[Unreleased]`.
- Shape (adapt, keep under 1,200 characters):
  "**The synthesis ownership record now has one reader and one `unreadable record` error** (#6767).
  **Before:** three paths answered 'what did synthesis create?' from different sources — the
  reach-only reader fell back to `.kittify/charter/synthesized-artifacts.yaml`, the directive
  ownership reader refused with an uncoded private error, and the `charter synthesize --json`
  envelope parsed the provenance sidecar itself. One damaged file could refuse delivery that the
  record could still answer, and two errors meant two catch sites. **After:** one reader serves both
  questions, with one fallback and one documented code, `SYNTHESIS_MEMBERSHIP_UNREADABLE`; the JSON
  envelope wraps the strict sidecar reader, so an unreadable sidecar costs the envelope its
  `artifact_id`, not its shape. A manifest entry whose sidecar records `project-direct-write` is a
  registration, not synthesis ownership, so a hand-authored artifact is never gated as synthesized."
- Check it renders correctly in context (surrounding entries' style) and that the code is spelled
  exactly.

### Subtask T018 – Docs and terminology

- `grep -rn "SYNTHESIS_MEMBERSHIP_UNREADABLE\|synthesized-artifacts" docs/ | head` and update any
  page that names the two readers or the retired error (today only the changelog mentions the code).
- If `docs/context/` carries a glossary term for the synthesis record, add the ownership reader's
  authority line there; if it does not, do not invent a term (terminology canon: no new domain term).
- Run `uv run python -m scripts.docs.check_docs_freshness --ci` and record `errors=0`, and
  `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`.

### Subtask T019 – Final verification

- Record the full sweep with its output:
  ```bash
  uv run --frozen pytest tests/charter/synthesizer/ -q
  uv run --frozen pytest tests/architectural/test_single_synthesis_ownership_reader.py -q
  uv run --frozen pytest tests/cli/test_charter_context_coded_error_6454.py -q
  uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q
  uv run --frozen ruff check src/ tests/architectural/test_single_synthesis_ownership_reader.py
  uv run --frozen ruff format --check --force-exclude <touched files>
  uv run --frozen mypy <touched files>
  ```
- Diff coverage: the new/changed lines are covered by the WP01–WP03 tests; confirm the new module's
  branches each have a case (the matrix in WP01 T001 is the map).

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/ -q -k "ownership or terminology or docs"
uv run python -m scripts.docs.check_docs_freshness --ci
```

## Risks & Mitigations

- A guard test that greps for text is brittle; prefer AST where it is cheap, and put the exact file
  path in every failure message so a future refactor can find it.
- Do not touch `docs/api/cli-commands.md` unless this diff changes a command surface (it does not).

## Review Guidance

- Read the changelog entry as an operator: does it say what changes for them, and name the one code?
- Confirm each guard test fails when its property is broken (history note records one red run).
