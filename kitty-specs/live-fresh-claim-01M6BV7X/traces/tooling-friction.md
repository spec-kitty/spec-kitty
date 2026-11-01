# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude:opus-5.5:python-pedro:implementer · spec-kitty specify in a fresh non-interactive project scaffolds topology=coord by default; the reporter's topology (lanes) needs --topology lanes. Also, a lanes mission whose meta target_branch is a protected branch refuses bookkeeping (PROTECTED_BRANCH_REFUSED), so reproduction fixtures must set target_branch to the topic branch.

2026-11-01 · claude:opus-5.5:python-pedro:implementer · Pre-review regression gate cannot complete on this host: three consecutive for_review attempts timed out at its 300s budget (phase=candidate_head), and an independent make-test-fast run in a pristine origin/main worktree exceeded 9 minutes under load average 105-357 on 40 cores. Not attributable to the diff: this branch changes no production file (git diff --stat origin/main..HEAD -- src/ is empty). Upstream already tracks this: open #3046 (advisory gate blocks on its own timeout; 300s structurally insufficient) and #6865 (empty derived scope falls back to full make test-fast). Used the documented --skip-pre-review-gate escape for the single for_review transition, disclosed in the PR Deferred section; the gate never produced a verdict, so nothing was turned green.
