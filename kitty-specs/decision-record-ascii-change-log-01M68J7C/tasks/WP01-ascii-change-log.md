---
work_package_id: WP01
title: Render the DM change log with an ASCII separator and pin the byte-safe invariant
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6579-decision-record-ascii
merge_target_branch: issue-6579-decision-record-ascii
branch_strategy: Planning artifacts for this mission were generated on issue-6579-decision-record-ascii. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6579-decision-record-ascii unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decision-record-ascii-change-log-01M68J7C
created_at: '2026-10-31T08:50:00.000000+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- event: created
  at: '2026-10-31T08:50:00Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/decisions/store.py
- tests/specify_cli/decisions/test_store.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Render the DM change log with an ASCII separator and pin the byte-safe invariant

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## Objective

Make a written Decision Moment (DM) record byte-safe by construction. `store._render_artifact`
renders the `## Change log` bullets with a literal U+2014 em dash; the record lands in
`kitty-specs/<slug>/decisions/DM-<id>.md`, so `spec-kitty validate-encoding --mission <slug>`
refuses the file the tool just wrote (issue spec-kitty/spec-kitty#6579). Replace the glyph with an
ASCII separator in the writer, leave the encoding validator untouched, and pin the invariant with a
regression test that drives the public `write_artifact` entry point.

## Context

**Mission**: `decision-record-ascii-change-log-01M68J7C` (issue #6579, `domain:decisions`,
`priority:P2`).

Read `spec.md` and `plan.md` in the mission dir first. Verified facts:

- Reproduction on `main` at `35318ef51c`: rendering a resolved `IndexEntry` through
  `write_artifact` produces 6 non-ASCII bytes (two U+2014 sequences) on the two change-log lines;
  `max(path.read_bytes()) == 0xE2`. The artifact text lines are
  `` - `<created_at>` — opened `` and `` - `<resolved_at>` — resolved (final_answer="…") ``.
- `src/specify_cli/decisions/store.py::_render_artifact` is the only DM markdown renderer in the
  package: `emit.py` writes JSONL events; `service.py`, `fork.py`, `index_fold.py` and `verify.py`
  read or mutate the ledger and call `store` for artifact output. There is no template that mirrors
  the bullet.
- The gate's detector is `specify_cli.text_sanitization.detect_problematic_characters`
  (`PROBLEMATIC_CHARS` maps `"\u2014"` to `"---"`). It is correct and must not change.
- Repository convention: markdown/JSON/YAML that *tooling* writes must stay byte-safe ASCII, so the
  strict encoding gate keeps its meaning for author-written content.

## Subtasks

### T001 — Survey the decisions package for render paths

**Purpose**: Prove the fix has exactly one home (FR-004) before touching anything.

**Steps**:
1. Read `src/specify_cli/decisions/store.py`, `emit.py`, `service.py`, `fork.py`, `verify.py`,
   `index_fold.py`, `models.py`, `__init__.py`.
2. Grep the package for `"## Change log"`, `lines.append`, and non-ASCII literals in rendered
   output. Confirm `_render_artifact` is the sole producer of the change-log bullet and that the
   other em dashes in the package are docstrings/error messages (not artifact content).
3. Append the finding to `traces/approach.md` (created during planning) with
   `spec-kitty agent tracer-append --mission decision-record-ascii-change-log-01M68J7C --category approach --entry "<text>"`.

**Files**: read-only over `src/specify_cli/decisions/`; writes the tracer entry.

### T002 — Red-first pin through `write_artifact`

**Purpose**: A failing test through the pre-existing entry point, before the fix (FR-005, SC-003).

**Steps**:
1. In `tests/specify_cli/decisions/test_store.py`, inside the existing `TestWriteArtifact` class, add
   `test_artifact_is_ascii_for_every_status`.
2. Parametrize or loop over the four rendered shapes: `open`; `resolved` with `final_answer`;
   `resolved` without `final_answer`; `deferred`/`canceled` with `final_answer`. Use the module's
   existing `_entry()` helper and `T0`/`T1` timestamps.
3. For each, call `write_artifact(tmp_path, e)` and assert:
   - `max(path.read_bytes()) <= 0x7F` (NFR-001), with a message naming the offending line;
   - `detect_problematic_characters(path.read_text(encoding="utf-8")) == []` — the gate's own
     detector, imported from `specify_cli.text_sanitization`, not a re-implemented scan.
4. Run it and capture the failure:
   `uv run pytest tests/specify_cli/decisions/test_store.py -k ascii -q`. Expected: fails with
   `0xE2`/`0xe2` on the change-log lines. Record the red output in `traces/design-decisions.md`.

**Files**: `tests/specify_cli/decisions/test_store.py`.

### T003 — Replace the em dash with an ASCII separator constant

**Purpose**: Make the record scaffold ASCII by construction, with one named home for the invariant
(FR-001, FR-002, FR-003, C-001, C-002).

**Steps**:
1. In `src/specify_cli/decisions/store.py`, add a module-level constant next to the other
   module-level names:
   ```python
   # ASCII only: a DM record is a generated file under kitty-specs/ and must pass
   # `spec-kitty validate-encoding` (#6579). Never render U+2014 here.
   _CHANGE_LOG_SEPARATOR = "-"
   ```
2. Use it in both change-log bullets in `_render_artifact`, keeping the line shape and the
   `(final_answer="...")` suffix unchanged:
   `f"- \`{entry.created_at.isoformat()}\` {_CHANGE_LOG_SEPARATOR} opened"` and the terminal form.
3. Do not touch `validate_encoding`, `text_sanitization`, the record's headings, field order, or any
   user-authored field rendering (question/options/rationale/final_answer stay verbatim).

**Files**: `src/specify_cli/decisions/store.py`.

### T004 — Green, blast radius and static checks

**Purpose**: Prove the fix and prove nothing else moved (SC-004, NFR-002, NFR-003).

**Steps**:
1. `uv run pytest tests/specify_cli/decisions/test_store.py -q` and
   `uv run pytest tests/specify_cli/decisions -q` — all green.
2. `uv run pytest tests/specify_cli/cli/commands -q -k "encoding"` (or the owning file
   `tests/specify_cli/cli/commands/test_validate_encoding.py` if present) — green, unchanged.
3. `uv run pytest tests/specify_cli/decisions/test_store.py -q -k ascii` on a stashed (pre-fix)
   tree, or re-run the captured T002 command, to record the red→green pair for the PR.
4. `uv run ruff check src/specify_cli/decisions/store.py tests/specify_cli/decisions/test_store.py`,
   `uv run ruff format --check` on the same, and `uv run mypy src/specify_cli/decisions/store.py`.
5. Record the green results in `traces/design-decisions.md`.

**Files**: none (verification only).

## Branch Strategy

Planning artifacts were generated on `main` (the primary partition for this topology). Execution
worktrees are allocated per computed lane from `lanes.json`; the mission's code lands on the
coordination/mission branch and consolidates into `main` locally. Completed changes must merge back
into `main` unless the human explicitly redirects the landing branch. Never push `main`.

## Definition of Done

- The em dash is gone from the rendered change log; both bullets use the ASCII separator constant.
- `test_artifact_is_ascii_for_every_status` exists, fails on the pre-fix renderer (captured red) and
  passes after the fix, asserting both `max(bytes) <= 0x7F` and the gate detector's empty result.
- `pytest tests/specify_cli/decisions` green; the `validate-encoding` tests green and untouched.
- `ruff check`, `ruff format --check` and `mypy` clean on the two touched files.
- No change to `validate_encoding`, `text_sanitization.PROBLEMATIC_CHARS`, or the record's schema.

## Risks and Reviewer Guidance

- A pin that only re-reads `_CHANGE_LOG_SEPARATOR` is vacuous: reviewers must confirm it writes a
  real record and asserts on the file's bytes and the gate's detector.
- A separator change must not disturb the `(final_answer="...")` suffix or the escaped inline code
  around timestamps; reviewers should read the diff for exact line shape.
- The fix must not "solve" the issue by relaxing the validator, stripping author prose, or making
  `write_artifact` transliterate arbitrary text (C-001, C-002).
- Existing `test_artifact_*` tests that assert headings/fields must pass unchanged (NFR-003).
