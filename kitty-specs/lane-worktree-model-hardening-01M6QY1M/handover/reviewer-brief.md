# Common reviewer brief: Mission lane-worktree-model-hardening-01M6QY1M (epic #7276)

- Load the reviewer-renata profile (`spec-kitty profiles show reviewer-renata`). You are independent of the implementer: verify; do not trust the handoff note.
- Read /home/user/spec-kitty/CLAUDE.md and the charter's review rules (.kittify/charter/charter.md, "Governance by Workflow Action > Review").
  Check: every acceptance criterion in the WP prompt; red-first evidence (failing test committed BEFORE the implementation commit; for code WPs verify
  with `git log --oneline` and, where cheap, by running the test at the red commit); live callers for new code (no dead code); no duplicate authority;
  complexity <= 15; no new noqa/type: ignore; scope limited to the WP's owned_files or recorded out-of-map edits; terminology (Mission, not feature;
  consolidate for lanes; name the sense of primary/merge/routing/residue); and consistency with the resolved operator decisions
  (`spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M --json`) and the Mission traces/design-decisions.md.
- Run the WP's declared targeted tests yourself (lane worktree: `PYTHONPATH=$PWD/src /home/user/spec-kitty/.venv/bin/python -m pytest ...`;
  run `make sync-packs` there first if packs/ is missing). Never run make test-full or a bare tests/architectural/ directory.
- Shared repository root checkout: do NOT commit, stash, reset or checkout anything there. Write feedback only to a temp file OUTSIDE the repo,
  under <SCRATCHPAD>/feedback-WPxx-N.md.
- Verdict, exactly one:
    approve: `spec-kitty agent tasks move-task WPxx --to approved --mission lane-worktree-model-hardening-01M6QY1M --agent claude::reviewer-renata --note "Review passed: <summary>"`
    reject:  `spec-kitty agent tasks move-task WPxx --to planned --mission lane-worktree-model-hardening-01M6QY1M --agent claude::reviewer-renata --review-feedback-file <path>`
  Reject only for real defects (acceptance criteria unmet, correctness, data-loss, charter violation); list nits as non-blocking in the approve note.
  If move-task refuses (e.g. REVIEW_NOT_INDEPENDENT, issue-matrix guard), do not use --force: report the refusal text verbatim and stop.
- Every code-WP review MUST run `tests/architectural/test_no_dead_symbols.py` serially (`-p no:xdist`, ~4-5 min, in the background) on the lane; a red there is blocking unless pre-existing on the lane base.
- Final message (<= 200 words): verdict, blocking findings (if any), non-blocking nits, tests you ran with counts, and Friction lines.
- Auto-commit is disabled in this project: your move-task verdict is written but not committed; the orchestrator commits it. Do not commit it yourself.
