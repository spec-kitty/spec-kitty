---
affected_files: []
cycle_number: 1
mission_slug: ascii-mission-scaffold-01M6GRG6
reproduction_command:
reviewed_at: '2026-11-03T13:36:28Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# Review feedback: WP01 (round 1)

**Reviewer**: reviewer-renata
**Base**: `15ce7e8537`
**Verdict**: REJECT - 1 MEDIUM, 1 LOW. The core fix is correct and the pin is genuinely
non-vacuous; both findings are about the gate's durability and the rendered text's audience.

## What is right (do not change it)

- The fix is by construction: the glyphs are gone from the source text, and no
  `sanitize_markdown_text` call was added anywhere. That is the #6579 shape, applied to the
  right surface.
- The pin is non-vacuous in the way DIRECTIVE_043 asks for: `test_pin_fails_when_a_glyph_is_injected`
  mutates the *shipped* constant through `monkeypatch.setattr` and renders through the
  *shipped* renderer, so it goes red if someone later re-pins against a literal copy of the
  output. The positive control in the same test is a nice touch.
- `test_gate_detector_finds_nothing` asks `detect_problematic_characters` rather than
  restating `PROBLEMATIC_CHARS` - single canonical authority, honoured.
- `test_renderer_formats_it_does_not_sanitise` is the guard rail that keeps a future
  contributor from "fixing" the pin by sanitising authored prose.
- The `history:` example now matches `task-prompt-template.md` (`at:`/`actor:`), and nothing
  else in the scaffold was reworded. `mypy` and `ruff` are clean.

## FINDING-1 (MEDIUM) - the no-sanitizer guard is a source-substring scan

`test_scaffold_module_never_sanitises` greps the module's source text for
`sanitize_markdown_text`, `sanitize_directory` and `detect_problematic_characters`.

Two problems:

1. **False positive.** A future editor documenting *why* the scaffold does not sanitise
   (exactly the comment this mission's own `plan.md` recommends) would turn the test red and
   be pushed to delete either the explanation or the test. That is a gate that punishes its
   own documentation.
2. **It cannot tell importing from mentioning.** A module that imported the sanitizer under
   a different name, or reached it as `text_sanitization.sanitize_markdown_text`, would sail
   past the string scan if the identifier appeared only via an alias.

**Required**: rewrite it as an AST check over the module - assert that no `Import`/
`ImportFrom` names anything from `specify_cli.text_sanitization`, and that no
`Attribute`/`Name`/`Call` node refers to a `sanitize_*` callable. Keep the failure message
naming what it found. The repo already has AST-census precedent (#7108,
`tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py`).

**Self-mutation**: add the matching proof - a planted counter-example (a small source string
that *does* import the sanitizer) that the check rejects, so the reviewer can see it can
fail. Without it this becomes the same screenshot in a different shape.

## FINDING-2 (LOW) - the rendered comment names a path the reader does not have

The new HTML comment is rendered into every mission's `kitty-specs/<slug>/tasks/README.md`.
It ends by naming `packs/built-in/missions/software-dev/templates/task-prompt-template.md`,
which is a **spec-kitty source-tree** path. In a consumer project (someone running
spec-kitty against their own repo) that path does not exist, so the README points the reader
at a file they cannot resolve - and `tasks/README.md` is a document they are meant to act on.

**Required**: split the audience.

- The **rendered** comment keeps only what the reader can use: that the file lands in
  `kitty-specs/`, that `spec-kitty validate-encoding` scans it, and therefore that the text
  must stay ASCII.
- The **pack-provenance** sentence (why the `history:` example uses `at:`/`actor:`, and that
  the pack is the canonical source) moves to a Python `#` comment above
  `TASKS_README_TEMPLATE`, where the maintainer who edits the constant will read it.

Keep both ASCII (NFR-001 applies to the comment too).

## Anti-pattern checklist

| # | Item | Verdict |
| --- | --- | --- |
| 1 | Dead code: no new public symbol | PASS (no new production symbol; the constant and renderer keep their names) |
| 2 | Synthetic-fixture test | PASS - the pin calls the shipped renderer and reads the shipped constant; delete the implementation and every assertion breaks |
| 3 | Silent empty return | N/A - no new branch returns a default |
| 4 | FR coverage | PASS with note - FR-001..FR-004 and FR-007 each have an assertion; FR-005 is `[folded]` and is satisfied at wrap-up (upstream issue + PR citation), not by a test here |
| 5 | Frozen surface | PASS - `packs/built-in/` untouched (`git log --oneline 15ce7e8537..HEAD -- packs/` is empty) |
| 6 | Locked decision | PASS - NFR-001 holds (no sanitizer on the path); C-001 holds (no pack edit) |
| 7 | Shared-file ownership | PASS - WP01 owns `mission_creation_scaffold.py` + the new test module; WP02 owns `worktree.py` + `test_worktree.py`, no overlap |
| 8 | Production fragility | N/A - no new `raise` |

## Evidence requested with the next submission

- The new AST check's planted counter-example failing, with the output pasted.
- `uv run pytest tests/core/test_tasks_readme_scaffold_ascii.py -q --durations=0` (the module
  must stay under the NFR-002 one-second budget).
- `uv run mypy` and `uv run ruff check` on both touched files.
