# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · pi-b1 · 2026-11-02 · pi · The discovery prompt's 'Mission directory' names the coord worktree while the runtime resolves meta.json/mission type only from the primary checkout: moving the specify scaffold into the coord worktree made 'next' return blocked with 'Mission template not found: mission.yaml'. Restored the scaffold to kitty-specs/<slug>/ in the primary and next advanced normally.

2026-11-02 · pi-b1 · 2026-11-02 · pi · The dogfood for_review move runs the INSTALLED CLI (v4.0.0rc8 built from main), so it exercised the OLD gate code: it reported 'effective budget=300s' and passed only because the host was idle enough. A lane-local fix to the gate cannot be dogfooded by move-task in the same WP; the review/ship proof has to come from the lane's pytest suites plus the post-merge release.

2026-11-02 · pi-b1 · 2026-11-02 · pi · Pre-existing red family seen by the gate's own baseline at the lane merge-base: tests/cli/commands/test_retrospect.py::{TestMaybeAutoCommit,TestCreateHarness,TestBackfillHarness} 'protected target warns and commits nothing' compare commit SHAs and fail only inside the parallel fast-tier run (each passes standalone in both the primary and the lane). The baseline captured all three and the head run reported no new failures, so this diff is clean; recorded for the PR's pre-existing-red note.
