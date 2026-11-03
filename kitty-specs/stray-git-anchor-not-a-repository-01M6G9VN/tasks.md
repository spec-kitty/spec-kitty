# Tasks: a stray `.git` that is not a repository is not an anchor

Mission: `stray-git-anchor-not-a-repository-01M6G9VN` · Branch: `issue-7093-stray-git-anchor-not-a-repository` (plans and lands here; it reaches `main` through a PR) · Topology: `single_branch` (one WP, so one lane in the write checkout)

## WP01 — Anchor on a repository, not a `.git` name (code_change)

Prompt: [tasks/WP01-anchor-on-a-repository.md](tasks/WP01-anchor-on-a-repository.md) · Requirements: FR-001..FR-005, NFR-001..NFR-003, C-001..C-004, SC-001..SC-005

Summary: `specify_cli.mission_metadata._has_no_git_anchor` counts any `.git` entry above a
Mission folder as a repository anchor, so a `.git` directory that is not a repository (no
`HEAD`) turns git's "not a git repository" into the `TrackedMeta(unavailable=True)` refusal.
`build_baseline_feature_meta` then refuses a Mission it could repair, and the frozen `2.0.6`
sweep reports a baseline write it never makes (`tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py::test_apply_repairs_feature_state_and_legacy_prompt_refs`).
The fix narrows the anchor to a `.git` pointer file or a `.git` directory that holds `HEAD`,
keeping every existing refusal (dangling pointer, index-only, corrupt, staged-differs,
dubious ownership) intact.

- T001 Red-first: a unit test in `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py` that builds an ancestor `.git` directory with `hooks/` and no `HEAD` above a Mission folder, asserts `read_tracked_meta` returns `TrackedMeta(None, unavailable=False)` and `build_baseline_feature_meta` returns a payload, and — on the same fixture, after swapping that directory for a `.git` pointer file — asserts the refusal is back (`unavailable=True`). RED on the base.
- T002 Red-first: an integration test in `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` that puts the same stray non-repository `.git` above a project with a Mission folder and asserts the sweep leaves a `meta.json` behind (the reported symptom, made environment-independent). RED on the base.
- T003 Fix `_has_no_git_anchor` in `src/specify_cli/mission_metadata.py`: an anchor is a `.git` file (pointer) or a `.git` directory holding `HEAD`; an unreadable anchor fails closed; the walk continues past a non-repository `.git` and stops at the first anchor. Update the docstrings of `_has_no_git_anchor` and `read_tracked_meta` to say what an anchor is.
- T004 Verify: the reported test and `test_nothing_tracked_is_not_a_refusal` go green on this host with their assertions byte-identical to `origin/main`; the whole two test modules pass; the same two pass with a clean basetemp outside `/tmp` (proving both environment directions); ruff and mypy clean on the changed files.
