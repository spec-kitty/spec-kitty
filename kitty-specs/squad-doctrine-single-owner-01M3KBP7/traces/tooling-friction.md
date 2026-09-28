# Tooling friction — squad-doctrine-single-owner-01M3KBP7

- 2026-09-28: Tooling touched: `spec-kitty doctrine regenerate-graph`, the pack-manifest regen gate, the DRG golden ledgers (`test_extractor_projection.py`, `test_reachability.py`) and the upgrade-migration registry.
- 2026-09-28: `pip install -e .` failed on the Debian-installed PyJWT (no RECORD file). It needed `--ignore-installed PyJWT`.
- 2026-09-28: The grounding brief path `/mnt/project-files/mission-grounding/...` did not exist in the container, so I worked from the operator's inline summary.
- 2026-09-28: The WP prompts told implementers to append the Activity Log to the WP file, but `move-task` refuses kitty-specs/ commits on a lane branch. WP02 hit this and self-remediated with the guard's prescribed restore. Fix applied: Activity Logs go in commit bodies and the orchestrator records them on the planning branch. The task-prompt template should say so.
- 2026-09-28: `spec-kitty agent action implement` for three WPs exceeded 120 s (worktree allocation), so it had to be backgrounded.
- 2026-09-28: `implement` is gated on `/spec-kitty.analyze` (`analysis_report_required`), which the skill flow does not mention.
- 2026-09-28: Re-claiming a rejected WP (`agent action implement`) auto-merged the coordination branch into the lane (`0b13ee60`, "auto-rebase … R-COORDINATION-ARTIFACT-THEIRS"). That put kitty-specs/ status, the issue matrix and review files on the lane, so `move-task --to for_review` refused its own merge result. The sandbox classifier blocked the prescribed restore for the subagent. The operator approved it and the orchestrator ran it. This looks like an upstream defect: the re-claim path contaminates lanes with coordination artifacts.
- 2026-09-28: The safe-commit refusal text (`commit_helpers.py:325-329`) and `REMEDY_PROTECTED_PRIMARY` recommend `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`, which this repo's charter forbids agents to use (charter.md:424). Follow-up issue to be filed.
- 2026-09-28: Wave-2 allocation (`agent action implement WP04..WP08`) failed with "cannot auto-merge dependency lane 'lane-b'". The only conflict was the derived `status.json`, which lane-b's kitty-specs cleanup had diverged. The lanes use sparse checkout (kitty-specs/ excluded), so `git add` could not stage the resolution, and the merges were left in progress. Resolved at index level:
  - took only lane-b's code (28 files);
  - reset kitty-specs/ to the lane's own HEAD;
  - committed, then re-ran the claims.

  Root cause: two conflicting mechanisms. Lane allocation and re-claim merge coordination/planning artifacts INTO lanes (FR-009, auto-rebase), yet `move-task` refuses lanes that carry kitty-specs/ changes. Upstream defect candidate.
