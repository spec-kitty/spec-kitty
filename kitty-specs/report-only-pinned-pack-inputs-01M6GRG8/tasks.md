# Work Packages: `--report-only` treats a pin-verified pack tree as clean input

**Inputs**: Design documents from `kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, quickstart.md
**Governing issue**: [#7128](https://github.com/spec-kitty/spec-kitty/issues/7128)

**Organization**: Two work packages. WP01 is the red-first production change (the exemption
predicate, the preflight filter, and the end-to-end plus unit proof); WP02 is the operator-facing
documentation and the per-PR changelog fragment.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files/components).
- Subtasks are reference rows; completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The pin-verified pack tree exemption (Priority: P0)

**Goal**: `record-analysis --report-only` commits the report in a clone whose gitignored
`packs/<name>/` tree matches the digests in its tracked, clean `packs/<name>.source.yaml` — and
still refuses, naming the path, when the tree no longer matches, when the pin is uncommitted, or
when the untracked material input is not under a verified pack tree.
**Independent Test**: `uv run --frozen pytest
tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py -q` — the new positive case
fails on `main` with `DIRTY_ANALYSIS_INPUT` and passes after the change, with the three negative
controls and every pre-existing case unedited.
**Prompt**: `tasks/WP01-pin-verified-pack-exemption.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

- T001 Red-first: build the pin-backed pack fixture and add the four end-to-end cases to
  `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`; run them against the
  current preflight and record the failure (the positive case must fail with
  `DIRTY_ANALYSIS_INPUT` naming `packs/internal/...`)
- T002 `pinned_pack_tree_roots(repo_root)` in `src/specify_cli/analysis_inputs.py`: return the
  repo-relative roots whose sibling `<root>.source.yaml` is tracked and clean, whose `pin.subtree`
  names that root, and whose tree verifies with `charter.offering.packs.pack_pin.verify_pack_pin`
- T003 `src/specify_cli/git/report_transaction.py`: subtract those roots (component-wise prefix) from
  the untracked-material dirty set only; leave the three other dirty rules untouched
- T004 Fast unit cases in `tests/specify_cli/test_analysis_inputs_pinned_packs.py`: subtree mismatch,
  missing pin, unverifiable pin (no `snapshot_sha256`), pack root outside the repository, sibling
  `packs/intern` not matching `packs/internal`
- T005 Targeted suites, `ruff check`, `ruff format --check`, and `mypy` for the touched modules

### Implementation Notes

- The predicate returns *roots*, not a boolean verdict, so no caller can turn the exemption into
  "ignored paths are clean" (FR-004).
- Fail closed: every error arm (unreadable/malformed pin, unknown digest algorithm, digest mismatch,
  symlink, bad `pack.yaml`, root outside the repo) yields "not exempt" and never escapes the
  preflight (NFR-002).
- Reuse `load_pack_pin` and `verify_pack_pin`; no second pin parser, no second digest (C-002).
  Prove "committed pin" with `kernel.git.tracked_paths` + `kernel.git.status_entries`, not a
  `git show HEAD:` blob reader.
- Generalise over `load_pack_registry(repo_root).packs` → `effective_root(repo_root)`; do not
  hard-code `packs/internal`.
- Verification runs only when the untracked-material set is non-empty, so a clean clone pays nothing.
- No existing test may be edited, skipped or xfailed; the `ignored_input` case is the ratchet.

### Parallel Opportunities

- T004 touches only the new unit module and can follow T002 independently of T003.

### Dependencies

- None (starting package). WP02 depends on this.

### Risks & Mitigations

- Exemption accidentally covering a sibling pack → the prefix check is component-wise, pinned by a
  T004 case.
- Fixture and production drifting apart → the fixture writes its pin with the same
  `clean_tree_digest`/`full_tree_digest` helpers `make sync-packs --check` uses, never a literal.
- Slow preflight → measured 8 ms for the real 67-file tree; verify only on demand (research D3).

---

## Work Package WP02: Operator docs and the per-PR changelog fragment (Priority: P1)

**Goal**: Tell an operator that a fetched, pin-verified pack tree no longer blocks `--report-only`,
and record the change as the per-PR changelog fragment.
**Independent Test**: `docs/development/analysis-report-transactions.md` states the exemption and its
four refusals; `docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md` passes
`scripts.docs.check_changelog_style` and `scripts.docs.check_spelling --pass unreleased`, and
`scripts.docs.check_docs_freshness --ci` reports errors=0.
**Prompt**: `tasks/WP02-operator-docs-and-fragment.md`
**Requirement Refs**: FR-001, FR-004, FR-006, NFR-003, C-004, SC-001, SC-002
**Dependencies**: WP01

### Included Subtasks

- T006 Under "Material inputs" in `docs/development/analysis-report-transactions.md`, one short
  paragraph: a fetched `packs/<name>/` tree that matches the pin in its tracked
  `packs/<name>.source.yaml` is a material input with committed state, so it does not block the
  transaction; any other untracked or ignored material input still does, and a modified tree or a
  dirty pin still refuses
- T007 `docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md`: impact-first lead
  with `(#7128)`, before/after, under 1,200 characters, US spelling
- T008 Changelog style, spelling and docs-freshness checks for the touched surface

### Implementation Notes

- The changelog is a **per-PR fragment** under `docs/changelog/unreleased/`, never an edit to
  `docs/changelog/CHANGELOG.md`. Name it by issue + branch slug now; rename it to `<pr>.fixed.md`
  once the pull request number exists.
- Do not regenerate the CLI reference or the docs index: this diff changes no command surface and no
  indexed page inventory. Verify with `check_docs_freshness --ci` (errors=0).
- No machine-local path or personal data in the doc, the fragment, or a commit.

### Parallel Opportunities

- T006 and T007 are independent files.

### Dependencies

- Depends on WP01: the docs must describe the shipped behaviour, not the planned one.

### Risks & Mitigations

- A docs rebuild reads the host's shared CLI asset cache, which other agents write concurrently →
  touch no generated index; verify freshness instead of rebuilding.
