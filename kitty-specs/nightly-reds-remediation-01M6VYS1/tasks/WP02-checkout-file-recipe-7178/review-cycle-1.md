---
affected_files: []
cycle_number: 1
mission_slug: nightly-reds-remediation-01M6VYS1
reproduction_command: spec-kitty agent tasks move-task WP02 --to approved --mission nightly-reds-remediation-01M6VYS1 --agent claude-opus-reviewer
reviewed_at: '2026-11-07T22:45:45Z'
reviewer_agent: claude-opus-reviewer
wp_id: WP02
---

Approved by claude-opus-reviewer: approval:WP02

# WP02 review (reviewer-renata, claude-opus-reviewer): APPROVED

Commit e219dafeb4.

- `_git_remedies.py:49-127`: `checkout_file_recipe(paths)` renders `git checkout -- <paths>` (index to working tree) and shares `_file_scoped_path_args` with `restore_recipe`. The `restore_recipe` error messages stay byte-identical (`renderer="restore_recipe"`). It does NOT use `restore_recipe`, and the docstring records why: the staged_differs edit is kept, and `--source HEAD` would fail for `index_only`.
- `tracked_meta_notice.py:23-32`: `_RESTORE` is removed and `_restore_command` uses a deferred import, with the cycle rationale documented. All five sites route through it. Byte identity verified: the old `_RESTORE.format(path=p)` equals `_restore_command(p)` for `kitty-specs/<slug>/meta.json` and for an absolute POSIX path. `_restore_notice`'s concatenated f-string was joined without any text change.
- Gate: `test_git_remedies.py` changes only add renderer tests. The scanner, `_RENDERER_MODULE` and the empty allowlist are untouched. Five focused tests cover the exact line, not being the restore form, quoting, directory refusal and empty refusal.
- Low (not blocking, observation): `shlex.quote` changes the text only for a path with shell-special characters. That can only happen through `_display_path`'s absolute-path fallback, for example a checkout under `/home/a b/`. In that one case the notice quotes the checkout command, while `git restore --staged {path}` and `git show HEAD:{path}` in the same staged_differs/corrupt notices stay unquoted. That is pre-existing inline text, out of scope for this WP, but worth a follow-up if absolute paths with spaces matter.

Evidence (reviewer, foreground): test_git_remedies + test_read_tracked_meta_6673 + test_backfill_identity_tracked_absent_6673 + integration test_upgrade_tracked_meta_identity_6673 + architectural test_destructive_op_routing: 139 passed. Gate node green. ruff, format and mypy (2 src files) clean.
