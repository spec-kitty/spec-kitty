Goal: bring one pull request on `spec-kitty/spec-kitty` to a state the operator can merge. You rebase it, fix what blocks it, review it, update its description, changelog and docs, and hand it off with evidence. The operator is the maintainer who invoked this skill; the canonical remote is the git remote that points at `spec-kitty/spec-kitty` (find it with `git remote -v`).

Input: the PR the user names (parameter `pr`). If none is named, ask for it.

## Step 1: Check the PR is not a draft, and ask about auto-merge

Run `gh pr view <N> --repo spec-kitty/spec-kitty --json isDraft,author,statusCheckRollup` before anything else.

If `isDraft` is true, STOP before you touch the branch. Your reply must start with a prominent warning: "WARNING: PR #<N> is still a DRAFT. It has not been handed off for landing." Give its author and its CI state, and ask whether to land it anyway. Do not rebase, push or comment on a draft PR without an explicit go-ahead. A draft is handed off when its author flips it to ready for review.

Whether the PR is ready for review or you were told to land a draft, ask the operator one question before the landing work begins: "Arm auto-merge when this PR is merge-ready, or hand off for a manual merge?" The default is to hand off. If there is no answer, do not arm it.

## Step 2: Run the landing procedure

Follow the `landing-contributor-prs` procedure from its second step onward. It carries the rules and the commands; this list is the order:

1. Decide whether the PR is worth landing: the full check for an old or substantive PR, the short check for a recent mechanical one. Stop and report the recommendation (LAND, RESCOPE or CLOSE) unless it is LAND.
2. Claim the PR with a comment and assign it to the operator.
3. Work in a separate worktree; rebase onto the canonical remote's `main`; regenerate what the rebase made stale.
4. Classify every red check, and file an issue for each pre-existing red that has none.
5. Fix what blocks the PR, one landing fix per commit, delegated to subagents. Apply the test economy rule in every brief. Read CI before running anything locally; never run a full heavy suite. For a bugfix PR, verify the red-first proof.
6. Run an independent review of the integrated diff and fix every finding, except one that is highly impactful, takes significant effort, or needs a significant operator decision. Name each exception in the PR body with its reason.
7. Tidy the commit history only when needed. The merge bar is the PR head, not each commit. Before a force-push, the rebuilt tree must be byte-identical to the old head.
8. Vet the tests the landing added with a reviewer who is not the implementer.
9. Update the PR body, changelog and docs.
10. Push (SSH is the preferred transport), then post the remediation summary.
11. File a tracked issue for every deferred item and leave the landing queue readable (the procedure's follow-up hygiene step).

## Stop and ask the operator when

- the PR is a draft (step 1);
- the recommendation is RESCOPE or CLOSE;
- you cannot attribute a red check;
- a permission prompt or safety classifier refuses a push (hand the push to the operator).

## Hand-off

Post the remediation summary on the PR. Then stop: the operator merges. Arm auto-merge only if the operator said yes when asked in step 1, only once the PR is merge-ready and complete, and as the procedure's hand-off step describes; confirm it armed without merging at once. Never merge by another route, never push to `main`, and arm nothing while the PR still needs commits. Afterwards, follow the "After the PR is merged" step.
