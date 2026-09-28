# Spec HALT ruling — operator, 2026-09-27

**Findings ruled on:** SPEC-FRESH3-001 (severity 4) and SPEC-FRESH3-002 (severity 3), both in
`spec-fresh-3.yaml` at `c00c97591`. Root cause shared by both: the spec left the choice of
recapture-PR marker (label / branch-name prefix / bot commit-author) open for the plan, and
FR-010 tried to constrain an unchosen marker with a "consistent with, never contradicting"
clause.

**Ruling: the marker is a single fixed head branch, pinned in the spec.**

1. The scheduled recapture job always pushes to ONE constant head branch (the spec names it;
   e.g. `ci/recapture-charter-shard-timings`). GitHub permits only one open PR per head branch
   into a given base, so a duplicate recapture PR is structurally impossible.
2. FR-007 detection is "an open PR exists with head = that branch and base = `main`". When one
   exists, the job **updates that PR's branch** with the fresh capture (force-update), rather
   than skipping. When none exists, it opens one. An unrelated PR that also touches
   `.github/ci-shard-timings.json` is never matched, because its head branch differs.
3. The label, branch-prefix and commit-author alternatives are removed from FR-007 and Key
   Entities.
4. FR-010 no longer carries any identity-matching / "consistent with" clause. It only requires
   the PR body and commit message to state plainly that the change is an automated recapture
   (single-purpose, by the scheduled workflow), falsifiable by inspection of the fixed text.
5. SPEC-FRESH3-002's false mechanism claim ("FR-010 can only ever produce a bot-commit-author
   identity/PR-body") is deleted, not reworded.

**This ruling REPLACES the acceptance bar for SPEC-FRESH3-001 and SPEC-FRESH3-002.** A verifier
must judge them resolved iff the spec implements points 1–5 above; the original "identical
marker" / "consistent with" bars no longer apply. Any new consequences of the ruling (e.g. what
force-updating an open PR does to reviews already on it, C-006 concurrency interplay) are fair
game for the fresh sweep.

---

# Spec HALT ruling 2 — operator, 2026-09-27

**Findings ruled on:** SPEC-FRESH5-001 (severity 4), SPEC-FRESH5-002 (severity 2),
SPEC-FRESH5-003 (severity 3), all in `spec-fresh-5.yaml`. Root cause: ruling 1's
"force-update the open PR" clause, which spawned FR-011 (lease-guarded force push), FR-012
(approval state after a force push) and a stale-review-thread edge case. FR-012's option (a)
("dismiss stale reviews on push") is infeasible on this repository in any scope: it has no
branch protection (the API returns 404, not offered).

**Ruling: skip if open. Ruling 1 point 2 is amended; points 1, 3, 4, 5 stand.**

1. The fixed head branch stays (ruling 1 point 1).
2. If an open PR with head = that branch and base = `main` exists, the job **does not push,
   force-push, comment or open anything**. It writes one line to the job summary naming the
   open PR's number and exits successfully. The job never force-pushes, in any case.
3. When no such PR is open, the job pushes the fresh capture to the fixed branch and opens the PR.
   If the fixed branch exists with no open PR (e.g. a previously closed PR), the plan decides
   how that stale branch is replaced; that is not a force-update of a PR under review.
4. FR-011 (lease-guarded force push), FR-012 (review-state after force-update), the
   stale-review-thread edge case and SC-007 are **deleted** — they have no subject under this
   ruling. Every cross-reference to them (Charter Tension items, ranges such as "FR-005–FR-012",
   acceptance scenarios, success criteria) is swept.
5. The accepted cost is stated in the spec: an unmerged recapture PR's capture can go stale
   relative to `main`; this is tolerable because the per-PR check is now a warning only, and
   closing a stale PR lets the next scheduled run open a fresh one.

**Dispositions:** SPEC-FRESH5-001 and SPEC-FRESH5-003 are resolved iff FR-012 and the
stale-thread edge case are gone and nothing in the spec still implies a force-update.
SPEC-FRESH5-002 is resolved iff the Charter Tension FR ranges match the surviving FR set.
**This ruling REPLACES the acceptance bar for all three.** New consequences of the ruling are
fair game for the fresh sweep.
