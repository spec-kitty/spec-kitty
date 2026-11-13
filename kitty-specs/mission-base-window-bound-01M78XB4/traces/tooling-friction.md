# Tooling friction — mission-base-window-bound-01M78XB4

- **[2026-11-12][research] Shallow clone hides history.** The checkout is grafted at `497c356a93`, so 90-day churn for the post-rc8 extractions (`reconciliation_closed_world.py`, `claim_inputs.py`) shows one commit each. Workaround: diffed functions at `bcd2afa03` and `1d1a0c04c` after fetching them.
- **[2026-11-12][research] Container restart dropped a subagent result.** The challenger's report was recovered from its transcript file. Disposition: workaround, no tracker item (harness, not Spec Kitty).
- **[2026-11-12][specify] `mission create` commits are untrailered.** CLI-made commits carry no `Co-Authored-By`; history cleanup at closeout adds the required trailer. Disposition: workaround.
- **[2026-11-12][review] Bare `--agent claude` cannot prove review independence.** WP01's approval refused `REVIEW_NOT_INDEPENDENT`: implementer and reviewer both recorded `claude::`. Fix: reopen to `in_progress` and resubmit as `claude::python-pedro`, approve as `claude::reviewer-renata`; later WPs use profile-qualified identities from the claim. The model segment is left empty (no model ids in committed artifacts). Candidate gap: `implement --agent` could default the profile from the WP's `agent_profile`.
- **[2026-11-12][implement] `check-prerequisites` reports `branch_matches_target: false` on a default topic branch** while `setup-plan` reports true for the same state. Candidate gap.
- **[2026-11-12][implement] `move-task --to for_review` runs the fast tier twice** (baseline + candidate), several minutes per submission.
- **[2026-11-13][implement] `safe-commit` with an absolute coordination-worktree path from the repo root commits nothing** ("no changed files"); a relative path from inside the coordination worktree works. Candidate gap.
- **[2026-11-13][implement] Container restart stopped the WP04 implementer mid-run**; resumed from its transcript, nothing was committed in between.
