---
affected_files: []
cycle_number: 1
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:10:42Z'
reviewer_agent: reviewer-renata
wp_id: WP07
---

# WP07 review cycle 1: changes requested

Reviewer: reviewer-renata.

1. **Classifier hole with a live witness** (`tests/architectural/test_commit_recipe_strings.py:222`). F-string interpolations are joined as empty text, so `f"git -C {repo_root} commit ..."` collapses to `git -C  commit` and `-C` swallows `commit`. `src/specify_cli/cli/commands/mission_type.py:1040-1043` prints `git -C {repo_root} add {meta_path} && git -C {repo_root} commit -m ...` and is not flagged. Substitute a placeholder for each interpolated part, add scanner-level f-string fixtures for `git -C {d} commit -m` and the add-and-commit form, and convert the `mission_type.py` recipe. Do not allowlist it.
2. **The printed recipe is refused on a protected target** (`src/specify_cli/post_merge/retrospective_terminus.py:325-336`). With `target_branch: main` the rendered `spec-kitty safe-commit ...` returns "refusing to commit to protected branch 'main'". The automatic path commits with the merge-bookkeeping capability; the CLI uses the standard one. It also fails from a working directory outside the checkout. The warning must not print a command that cannot succeed: point at the idempotent re-run (heal path proven by `test_idempotency_heals_a_previously_failed_commit`) and say where to run it.
3. **`--to-branch` branch untested** (`tests/specify_cli/post_merge/test_retrospective_triggering.py:409-416`): the fixture has no `target_branch`. Cover whichever branches remain after item 2.
4. **`mypy --strict` not clean on the changed source file** (`retrospective_terminus.py:319`, `no-any-return`): pre-existing, but the function is touched and the fix is one line.

Also justify or remove the single-fixture carve-out `(?!and/or\b)` at `:169`.

Verified and holding: verbatim move, red-first order, 11 of 11 historical fixtures verbatim and flagged, allowlist 14 to 2 with nothing added, mutation checks red in both directions, per-pull-request selection.
