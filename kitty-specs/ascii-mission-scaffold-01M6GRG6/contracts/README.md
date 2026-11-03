# Contracts -- ascii-mission-scaffold-01M6GRG6

**No new or changed external contract ships from this mission.** There is no wire format,
CLI flag, API schema or event payload in the diff: the change is scaffold text inside
`src/specify_cli/core/`, and two tests.

This directory exists because the `software-dev` path convention expects it, and because
there *is* one interface this mission constrains -- a text one, recorded here so it is not
lost:

## The scaffold text contract

| Surface | Guarantee | Enforced by |
| --- | --- | --- |
| `render_tasks_readme_content(planning_branch)` | Returns text whose every byte is `< 0x80`, for any ASCII branch name; interpolates only `planning_branch` | `tests/core/test_tasks_readme_scaffold_ascii.py` |
| The same text written to `kitty-specs/<mission>/tasks/README.md` | `detect_problematic_characters()` (the detector `spec-kitty validate-encoding` uses) finds nothing | same module, plus `tests/git_ops/test_worktree.py::test_tasks_readme_comes_from_the_canonical_renderer` |
| The renderer's behaviour | Formats; never sanitises. Authored non-ASCII passes through unchanged | `test_renderer_formats_it_does_not_sanitise`, `test_scaffold_module_never_sanitises` |
| Ownership | Exactly one module holds the text | `tests/git_ops/test_worktree.py::test_no_second_copy_of_the_tasks_readme_scaffold` |

The stabilised tokens in that text are the WP-frontmatter keys and the CLI commands it
documents (`spec-kitty agent tasks move-task`, `mark-status`). The `history:` example's field
names mirror `packs/built-in/missions/software-dev/templates/task-prompt-template.md`, which
remains the canonical source; a drift there must be corrected upstream, not here.
