---
work_package_id: WP02
title: No Mission-scoped occurrence map in docs tooling
dependencies:
- WP01
requirement_refs:
- FR-007
- NFR-003
- SC-003
planning_base_branch: issue-6927-url-baseline-moves-ledger
merge_target_branch: issue-6927-url-baseline-moves-ledger
branch_strategy: Planning artifacts for this mission were generated on issue-6927-url-baseline-moves-ledger. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6927-url-baseline-moves-ledger unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
phase: 'Phase 2 - #2358 for every script'
history:
- at: '2026-11-01T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- tests/docs/test_docs_tooling_defaults.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/rename_reconcile.py
- scripts/docs/bulk_ref_rewrite.py
- scripts/docs/relative_link_fixer.py
- tests/docs/test_docs_tooling_defaults.py
- tests/docs/test_bulk_ref_rewrite.py
- tests/docs/test_relative_link_fixer.py
- tests/docs/test_touched_set_gates.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – No Mission-scoped occurrence map in docs tooling

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- No module under `scripts/docs/` has a default (module constant, argparse default or env fallback) naming a path under `kitty-specs/` (FR-007, SC-003).
- `rename_reconcile.py` checks renames and deletions against `site/moves.yaml` and checks the forward rule (every ledger `from` is a committed map key).
- `bulk_ref_rewrite.py` and `relative_link_fixer.py` default to `site/moves.yaml` (via `moves_ledger.source_pairs`). An explicit `--occurrence-map` with a legacy-shape map keeps working, so their fixture tests pass.

## Context & Constraints

- Depends on WP01's `scripts/docs/moves_ledger.py`.
- ADR D-6: these scripts are "keep for the README rename, then drop"; their binding "is replaced by `site/moves.yaml`".
- `touched_set_gates.py` reads no occurrence map (grounding §1); it is listed only because its tests import `rename_reconcile` (`tests/docs/test_touched_set_gates.py:456`).

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: issue-6927-url-baseline-moves-ledger
- **Merge target branch**: issue-6927-url-baseline-moves-ledger

Implementation command: `spec-kitty agent action implement WP02 --agent claude --mission docsite-url-ledgers-01M6BRMR`

## Subtasks & Detailed Guidance

### Subtask T007 – Acceptance test (red)

- **File**: `tests/docs/test_docs_tooling_defaults.py` (new).
- `test_no_docs_script_default_names_kitty_specs`: for every `scripts/docs/*.py`, parse it with `ast` and collect string constants that are module-level assignments, `add_argument(..., default=...)` values or `os.environ.get(..., <fallback>)` fallbacks. Assert none contains `kitty-specs/`. Docstrings and comments are not defaults and are skipped.
- **Positive control**: the same collector run on a synthetic source string with `DEFAULT = "kitty-specs/x/occurrence_map.yaml"` returns that constant, so the gate is non-vacuous. Add a floor: the collector examined ≥ 10 modules.
- `test_tooling_defaults_point_at_the_standing_ledger`: `rename_reconcile.DEFAULT_MOVES_LEDGER`, `bulk_ref_rewrite.DEFAULT_OCCURRENCE_MAP` (or its renamed successor) resolve to `site/moves.yaml`.
- Red today: `rename_reconcile.py` and `bulk_ref_rewrite.py` name the Mission maps.

### Subtask T008 – `rename_reconcile.py`

- `DEFAULT_MOVES_LEDGER = "site/moves.yaml"` replaces `DEFAULT_OCCURRENCE_MAP`; `--moves` replaces `--occurrence-map`; update `__all__`.
- Load with `moves_ledger.load_moves`. If the file is absent, report 0 moves examined (keep the existing C-010 no-op behaviour).
- Reverse gate: a renamed or deleted path is in scope iff `source_to_route(path)` is in `site/url-baseline.txt` (a published route was removed). It is covered iff that route is a ledger `from`. Non-page files and never-published pages are out of scope; say so in the docstring.
- Forward gate: every ledger `from` (slash-less) is a key in the committed `redirect_map.yaml` (detects a stale map). Keep the rule ids `rename_reconcile` / `occurrence_subset_redirect`, since downstream reports name them.
- Use `sys.path` bootstrap + `from scripts.docs.moves_ledger import ...`. ruamel stays for the redirect map read, or switch to the shared loader; pick the smaller diff.

### Subtask T009 – `bulk_ref_rewrite.py` / `relative_link_fixer.py`

- `DEFAULT_OCCURRENCE_MAP` becomes the ledger path (`site/moves.yaml`); keep the `SPEC_KITTY_OCCURRENCE_MAP` env override; the docstring and comment say a Mission's own map is passed explicitly.
- `load_moves(path)`: when the YAML has `kind: docs-moves-ledger`, return `moves_ledger.source_pairs(...)`. Otherwise keep the legacy `moves:` parse (explicit maps and fixtures).
- `relative_link_fixer.py` imports the default from `bulk_ref_rewrite`, so no constant change is needed; update its docstring and help text that name the closed Mission.

### Subtask T010 – Re-pin tests

- `tests/docs/test_touched_set_gates.py` (around line 456) and any `rename_reconcile` tests: pass a ledger fixture (`kind`/`version`/`moves`) and a baseline fixture. Keep their assertions on rule ids and counts.
- `tests/docs/test_bulk_ref_rewrite.py` / `test_relative_link_fixer.py`: add one case that loads a ledger-shaped file through `load_moves` and gets `docs/` source pairs. Existing fixture-map tests stay.
- Architectural gates that name these test files: run `tests/architectural/test_gate_remedy_presence.py` and `tests/architectural/test_no_dead_doctrine_paths.py`.

## Test Strategy

- `uv run --frozen pytest tests/docs/test_docs_tooling_defaults.py tests/docs/test_touched_set_gates.py tests/docs/test_bulk_ref_rewrite.py tests/docs/test_relative_link_fixer.py -q`
- `uv run --frozen pytest tests/architectural/test_gate_remedy_presence.py tests/architectural/test_no_dead_doctrine_paths.py -q`
- mypy, ruff, `ruff format --check --force-exclude` on the changed files.
- Run `python3 scripts/docs/rename_reconcile.py --base HEAD~1 --strict` on the branch and record the output.

## Risks & Mitigations

- The rewrite tools are reused for the README rename (#6939). Keep the legacy `moves:` parse so a Mission can still pass its own map explicitly.

## Review Guidance

- The new defaults test fails on the base and has a positive control.
- No `kitty-specs/` default survives: `grep -n "kitty-specs" scripts/docs/*.py` shows only docstring prose, if anything.

## Progress & Status

Use `spec-kitty agent tasks add-history WP02 --note "..."`.
