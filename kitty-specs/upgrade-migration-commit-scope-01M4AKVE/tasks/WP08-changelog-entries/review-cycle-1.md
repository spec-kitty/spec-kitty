---
affected_files: []
cycle_number: 1
mission_slug: upgrade-migration-commit-scope-01M4AKVE
reproduction_command:
reviewed_at: '2026-10-07T22:30:11Z'
reviewer_agent: reviewer-renata
wp_id: WP08
---

# WP08 review, cycle 1: changes requested (reviewer-renata)

Merge b37820a6f is correct and the other 8 bullets are accurate. Three bullets claim more than the code on the lane does. Only `docs/changelog/CHANGELOG.md` changes. Each replacement below passes `python -m scripts.docs.check_changelog_style` with 0 errors and the same 15 warnings as origin/main 6d45d8fcc.

## Issue 1 (blocking): the #5673 bullet's `--no-auto-commit` sentence is false

The bullet says: "With `--no-auto-commit`, a `meta.json` or prompt you had already modified is left unstaged, with a warning naming it."

In `implement`, `commit_planning_artifacts` runs before the claim. Under `--no-auto-commit`, `implement_planning_commit._ensure_planning_artifacts_committed_git` refuses when a Mission-folder file has an ordinary edit. It prints "Planning artifacts not committed: …" and "Auto-commit disabled. Commit planning artifacts first", then exits 1. The claim never runs, so nothing is "left unstaged with a warning".

WP03's own test says the same. The docstring of `test_an_operator_edited_wp_prompt_is_not_staged_and_a_warning_names_it` reads: "the only edit that reaches the claim dirty is one the planning guard tolerates: a legacy runtime frontmatter key". The `meta.json` warning is in practice unreachable from the CLI: a `meta.json` that only differs by the VCS lock means the claim writes no lock, so `meta_written` is False.

A probe on the lane tip with a flat lanes Mission:
- operator edit to `meta.json`, `--no-auto-commit`: exit 1, refused as above, nothing staged;
- body edit to the WP01 prompt, `--no-auto-commit`: exit 1, refused the same way;
- the same edits with `--auto-commit`: "chore: planning artifacts for …" commits the edited file before the claim commit. The orchestrator's sentence ("with auto-commit, `implement`'s separate planning-artifacts commit still records such edits") is correct.

The Before line ("so your own pending edits went in with it") also overstates. Under auto-commit, edits to `meta.json` and the prompt were already swept by the planning commit, so the claim commit's real overreach was `.kittify/config.yaml`.

Replace the bullet with:

- **`spec-kitty implement`'s claim commit carries only what the claim wrote** (#5673). **Before:** the claim commit took `.kittify/config.yaml`, the Mission's `meta.json` and the claimed work package's prompt whether or not the claim had changed them, so a pending `config.yaml` edit went in with it; `--no-auto-commit` staged that `meta.json` and prompt the same way. **After:** the claim carries only the status files, `meta.json` when the first claim's VCS lock changed it, and the prompt's workspace stamp. Your other edits in the Mission folder are handled as before: with auto-commit, `implement`'s planning-artifacts commit still records them, and with `--no-auto-commit` they still refuse the claim.

## Issue 2 (blocking): the first Internal bullet claims more than the gate does

"A new architectural gate … refuses any sweeping, pathspec-less or hook-bypassing commit in `src/`". The gate (`tests/architectural/test_commit_scope_owner.py` over `_commit_scope_census.py`) is an AST census of literal argument lists and known runner calls. Its docstring lists what it does not cover: argument lists built across statements (`+=`, `.append`), `shlex.split`, `shell=True` / `os.system`, function-local constants, clustered short options, rebase/pull/am, and plumbing commits (`commit-tree` + `update-ref`). "Any" is therefore wrong.

Replace the bullet with:

- **Every merge, revert and squash conclusion goes through one owner, and a gate keeps it that way** (#5443). Consolidation, auto-rebase, lane allocation and the coordination rollbacks conclude through it: it never skips hooks, never commits without a merge, revert, cherry-pick or squash in progress, and concludes a squash only in a proven-clean worktree. Restoring target-newer planning files no longer sweeps another staged file into the squash commit. A new architectural gate with an empty allowlist reports every sweeping, pathspec-less or hook-bypassing `git` call it can read from a literal argument list in `src/` outside `safe_commit` and that owner; argument lists built across statements, shell strings and plumbing commits (`commit-tree`) are outside its reach.

## Issue 3 (fix with the others): the removed-helpers bullet simplifies `GitVCS.commit`

The old `GitVCS.commit` ran `git add <path>` for each given path, and `git add -A` only when called with no paths (`git show 6d45d8fcc:src/specify_cli/core/vcs/git.py`, around lines 631-640). Replace the bullet with:

- **The unused sweeping commit helpers are removed, for maintainers** (#5443). `GitVCS.commit` and `VCSProtocol.commit` (`git add -A` when given no paths, then a pathspec-less commit) and `specify_cli.core.git_ops.init_git_repo` (`git add .`, then a pathspec-less commit) are gone, with the `specify_cli.core` re-export and its `__all__` entry. They had no product callers; code that commits uses the path-scoped `safe_commit`.

## Notes (non-blocking; for the orchestrator)

- The WP prompt says WP08 "never adds, edits or moves the #5443 bullet". d8c810e28 rewrites that bullet's last sentence for FR-022. The new sentence is accurate: `autocommit.migration_index_untracks` feeds `safe_commit(index_deletions=…)`, the file stays on disk, and the old "left as a staged removal" sentence would now be false. The edit was made at the orchestrator's direction. Record that decision in the Activity Log.
- Review Guidance limits #5443 to the orchestrator's bullet or as the umbrella of the bake bullet. The skills bullet and both Internal bullets also cite (#5443). That is defensible, since they are mission-umbrella work with no dedicated issue, but it departs from the prompt's wording. Either keep it and note the decision, or adjust the refs.
- The merge (b37820a6f) and the lane-guard merge (b18632c4f, no src/tests/docs change) are fine; see the review report.
