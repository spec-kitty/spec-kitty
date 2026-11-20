---
affected_files: []
cycle_number: 2
mission_slug: remote-only-branch-remedy-01M7X5Z5
reproduction_command:
reviewed_at: '2026-11-20T21:03:16Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review, cycle 2: changes requested (reviewer: claude::reviewer-renata)

The B1 fix is correct, and so are N1, N2 and N3. One gate is red, so this cycle is a rejection. The fix is one line.

## Blocking

### B2 (gate). `ruff check .` fails on a line the fix commit added
`tests/mission_runtime/test_coord_remedy.py:43`: E501, line too long (177 > 164). Commit 5415660b added it.
It is the only error in the whole repository (`ruff check . --output-format concise` gives 1 error), so the CI
lint step (`ci-router.yml`: `.venv/bin/ruff check .`) goes red. `ruff format` does not wrap a long f-string, so
the format check passes. Fix: split the expected string, for example two adjacent f-string literals inside the
parentheses. Then re-run `ruff check .` and `ruff format --check --force-exclude` on the file.

## Non-blocking (fix if cheap, or note in the tracer)

- N4 (low). The `CoordinationWorktreeUnmaterialized` class docstring (`surface_resolver.py` ~line 327) still says
  the guidance "leads with ``git fetch origin <branch>``". The text it describes is now the canonical
  `coord_remedy` form, with the resolved remote and an explicit destination.
- N5 (info). The local-head arm's manual fallback `materialize_cmd` (`git -C {repo_root} worktree add ...`) is
  still unquoted. This is not the builder's text and was already true before this WP, but a root with spaces
  breaks it the same way N1 did.
- N6 (info). Branch names are not quoted. Git refnames cannot contain spaces, and Mission branches are generated
  slugs, so this is acceptable. Note it only if you touch the builder again.

## Verified (PASS)
- B1: I ran the printed git steps, using the real builder with `shlex.split`, in 9 setups. Every one ended with
  `refs/heads/<b>` present:
  - a single-branch clone and a shallow `--depth 1` clone: fetch, then branch;
  - a normal clone with the tracking ref present: branch only;
  - a normal clone with the tracking ref pruned;
  - a multi-remote clone (`-o upstream` plus `fork`): branch only, through the upstream tracking ref;
  - a single-branch clone with `origin` plus `fork`;
  - a root with spaces in a single-branch clone;
  - a slash branch `other/feat` under that root;
  - an apostrophe root (`it's`) in a shallow clone.
- Red before the fix: on 24a89285 (in a detached worktree, with that commit's `src` first on the path),
  `test_single_branch_clone_remote_only_coord_branch_is_not_deleted` gives 1 failed.
- No other site prints the old form. All three sites (doctor, unmaterialized refusal, write refusal) delegate to
  `remote_only_steps`. The remaining `origin` literals in `src/` are the out-of-scope ones listed in cycle 1.
- Remote-contact owner rule: the builder reads only local config and refs. `test_remote_contact_owner.py` passes.
- `ruff check --select C901` passes on the touched files (complexity at most 15). mypy passes on the 4 source
  files. `ruff format --check --force-exclude` passes on the touched files.
- CI reach: the B1 proof (`tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py`, core_misc) and
  the unit tests (`tests/mission_runtime`, execution_context) run per PR. The 5113 round trip
  (`tests/specify_cli/cli/commands/test_coordination_remedy_5113.py`) is in `out_of_matrix_test_dirs` and runs
  only in the nightly. B1 is still proven per PR by the 4979 test.

## Commands
- 7 files, `pytest -n 4 --dist loadfile`: coord_remedy, 5287, 4979, 5113, test_doctor_coordination,
  test_layer_rules, test_remote_contact_owner: 183 passed.
- Red check on 24a89285, 4979 `-k single_branch_clone`: 1 failed (as expected).
- Adversarial clone script (9 setups): 9/9 left a local branch.
- `ruff check .`: 1 error (B2).
