---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T10:04:16Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review cycle 1: changes requested (reviewer-renata)

## Blocking

**Issue 1: O4 (and so O6) is wrongly excluded for worktree-only removals.** Two places say that because the branch is never deleted, "O3, O4 and O6 do not arise":
- `docs/adr/3.x/2026-04-03-1-...md`, Amendment 2026-11-06, "Releasing commits or refuses" bullet ("O1, O2, O5, O7 and O8 apply as written. A release never deletes the lane branch, so O3, O4 and O6 do not arise.");
- `docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md`, D-9 step 4 ("The coordination branch is never deleted by this migration, so O3, O4 and O6 do not arise.").

ADR 2026-11-06-1 (PR #7275, `origin/issue-7211-safe-landed-prune`) defines O4 as: "A commit that only the **worktree `HEAD` reflog** or the branch reflog still reaches would be lost when those reflogs go." `git worktree remove` drops that worktree's HEAD reflog even when the branch survives. A commit made in the checkout and then orphaned (`commit --amend`, `reset`, an aborted rebase) is reachable only from that reflog, and removing the checkout loses it. O6 is the proof that may leave such a commit unrecorded, so it applies whenever O4 does. As written, these records exempt the short-lived-checkout release and the coordination-worktree drain from the obligation that protects exactly that work. That contradicts ruling 5 ("releasing a checkout commits or refuses", meaning it never discards) and ruling 7 / C-005 (the #7264 proof list is the single authority and is not re-scoped here).

**Fix:** in both places, say that O1, O2, O4 (with O6), O5, O7 and O8 apply, and that only O3 does not arise because no branch is deleted. Also check the S3 Confirmation bullet and C-1's drain-migration test bullet, so that the follow-up tests cover "a reflog-only commit in the checkout is recorded under `refs/spec-kitty/discarded/reflog/` before removal".

## Non-blocking (fix while you are there)

1. C-1 calls spec-kitty-events #215 a "draft pull request". It is open and not a draft (head ab8ebe57). Say "pull request".
2. C-1 D-9 step 2: "committed onto the coordination branch by the last use of the old writer, before the cut". Steps 4 and 4a ship together (D-10), and step 4 deletes the Python appenders, so name what commits the drained rows: a plain git commit of bytes already in the worktree file, made by the migration, not an event writer under D-5. Otherwise it reads as a Python fallback writer.
3. FR-084's spec text ("drafts ... delivered as files in this Mission") and C-003 still describe the events ADRs as Mission deliverables. plan.md and the WP prompt make them sibling-owned and linked only. Record the drift in traces, or flag it for a spec fix, so the FR-084 coverage claim stays honest.

## Verified OK

- Every D-6 bullet is quoted verbatim and maps to exactly one record (SC-010).
- The retired five codes, the three new codes, mission-write 1.0.1-SNAPSHOT, the coordination_ref_commit and checkout_append narrowing, destinationRef as required (amending 2026-10-27-1 D-3), steps 4 and 4a in one release with the #7266 artefact rule, oracle-fallback parity (C-3 D-3, matching ADR-0008 D-1), and the CAS-only fence with an emptied core.hooksPath and SERVICE_BUSY / COORDINATION_BRANCH_DELETED / COORDINATION_REF_MOVED all match events ADR-0007/0008 at ab8ebe57.
- The S10 citation matches PR #7274's amendment text. The amendment draft's `guarded_landed_removal` / `LandedRemoval` binding target matches #7275's code.
- Amendments are appended only, every record is Proposed, relative links resolve, the terminology guard passes (98), and the description-length check passes.
