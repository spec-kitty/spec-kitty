Goal: take the named issues on `spec-kitty/spec-kitty` through a full governed Mission to a pull request that is green and flipped from draft to ready for review. The operator is the maintainer who invoked this skill; the canonical remote is the git remote that points at `spec-kitty/spec-kitty` (find it with `git remote -v`).

Input: the issue numbers the user names (parameter `issues`), optionally followed by guidance (parameter `guidance`). If no issue is named, ask which to run. Record the guidance in the Mission spec. Scale the review effort to the work: a small fix needs a couple of reviewers per round; a contract or API-surface change needs the full adversarial treatment.

## Steps

Follow the `issue-to-mission-delivery` procedure. It carries the rules and the commands; this list is the order:

1. Start from the current `main` of the canonical remote (fast-forward only, push nothing). Read the charter.
2. Ground the issues: confirm each still reproduces on current main and was not superseded, and set the Mission boundary.
3. Claim every issue (comment, assign the operator, add `status:claimed` and `taken-by-human`) and verify it before any planning artifact exists.
4. Specify, plan and tasks through the canonical commands; fill the issue matrix; keep the tracer files.
5. Survey the existing code, then implement red-first with `spec-kitty next --agent <name> --mission <slug>`.
6. Run the `mission-wrap-up-sequence` procedure: accept, issue verdicts, aggregate review, consolidate, compact, rebase.
7. Review the integrated diff and fix every finding, except one that is highly impactful, takes significant effort, or needs a significant operator decision. Name each exception in the PR body with its reason.
8. Update the changelog and docs.
9. Open the PR as a draft, follow CI to green, then flip it to ready for review and label it `ready-for-squad`.

Every subagent you dispatch first loads its profile with `spec-kitty agent profile show <id>`. Use the cheaper model tier for implementation and the stronger tier for review.

## Stop and ask the operator when

- every issue is resolved or superseded (stop and report), or only some are (drop them and confirm the remaining scope);
- an issue is already assigned to someone active on it, or a claim fails;
- `main` cannot fast-forward or the working tree is not clean;
- a work package is rejected twice or blocked.

## Hand-off

The flip from draft to ready for review is the hand-off to the maintainers. Never flip a PR that is red or still being changed. Report the PR link, the issues it closes, what each review round changed, and every check still failing with the reason it is not caused by this PR. Then stop. Do not merge, and do not arm auto-merge, on your own initiative.
