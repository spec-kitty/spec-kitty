# Tooling friction

Append-only log of friction met while running this Mission (mission-tracer-files procedure).

- 2026-11-11 specify: `mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`; the flag is
  documented only in the specify prompt, not in `--help`'s first screen. Minor.
- 2026-11-11 specify: the first `decision open` wrote `decisions/index.json.lock` beside the decision artifacts. In this
  repository it shows as `!!` only because `.gitignore` carries `*.lock`; a consumer project would see it as `??` (the
  defect this Mission fixes).
- 2026-11-11 specify: the create-time scaffold commit (`Add scaffold for mission …`) is written by the CLI without the
  operator's required `Co-Authored-By` trailer; no flag to add one.
- 2026-11-11 plan: `setup-plan --json` reports `target_branch` as the Mission branch while `meta.json` records
  `fix/7549-doctor-scope-lock-hygiene`; the two "target" senses are easy to confuse.
- 2026-11-11 implement: the first pytest run in a fresh container spends ~90 s building a test venv
  (`.pytest_cache/spec-kitty-test-venv.build-*`), which looks like a hang.
- 2026-11-11 implement: `ls-tree` takes no glob pathspec, so `kernel.git.listing.tree_paths(..., glob=True)` silently
  returns nothing for `kitty-specs/*/meta.json`; listed the directory non-recursively instead.
- 2026-11-11 implement: `materialize_coord_surface_for_write(repo_root, slug)` silently no-ops for a Mission whose
  `meta.json` is on no checkout (it re-reads meta from disk); the doctor now passes the finding's coordination branch
  and mid8 override. Other callers with the same shape would hit the same no-op.
- 2026-11-11 implement: `move-task --to for_review` runs the pre-review gate (fast tier on base and candidate) for
  3–4 minutes with no progress until 30 s; editing source while it runs would skew it.
- 2026-11-11 implement: the terminus harness cannot run from a scratch worktree (`python -m specify_cli consolidate
  --help` fails there), so red-on-base for that pin was proven by restoring the base source files in place.
- 2026-11-11 review: `move-task --to approved` printed 'review-cycle verdict … NOT committed (--no-auto-commit)' although that flag was never passed (reproduces the #7540 smaller-friction note).
- 2026-11-11 consolidate: LANE_MOVED_AFTER_APPROVAL (correct: a test was added after approval). Its printed recovery `move-task <WP> --to in_progress` fails with 'Agent mismatch … assigned to reviewer-renata'; it worked with `--actor reviewer-renata`.
- 2026-11-11 review: recording a reopen (`approved -> in_progress`) with `--actor reviewer-renata` made the reviewer the implementer of record (`latest_implementer_identity` reads the latest implementer claim), so the reviewer's next approval was refused with SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT. Fixed by the reviewer returning the WPs to `planned` and the implementer re-claiming them. The `LANE_MOVED_AFTER_APPROVAL` recovery text could name the actor to use.
