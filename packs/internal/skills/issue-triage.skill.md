Goal: triage a set of open issues on `spec-kitty/spec-kitty` so each is typed, prioritised, labelled by domain, parented, linked to its blockers and (when obvious) given a milestone, and so stale, duplicate or clustered issues are reported rather than mis-triaged. You are the orchestrator: you dispatch triage subagents and aggregate their reports; you do not triage inline. The operator is the maintainer who invoked this skill; the canonical remote is the git remote that points at `spec-kitty/spec-kitty`.

Input: the issues the user selects (parameter `scope`). With no scope, use every open issue created in the last 7 days.

## Steps

Follow the `issue-triage-pass` procedure. It carries the rules and the commands; this list is the order:

1. Read `docs/development/how-to/manage-issue-tracker.md` in full and treat it as binding. Apply the `tracker-organisation-workflow` procedure and the `spec-kitty-tracker-labels` styleguide.
2. Record the start time. Resolve the work list, the milestones and the functional epics. Fetch the canonical remote's `main` and pass `<canonical-remote>/main` to every subagent as the ref for code-state checks. If the scope selects nothing, report "no issues in scope" and stop.
3. Dispatch the triage subagents in parallel (3 to 5 issues each, at most 4 at once, further rounds for a larger scope). Each loads the `planner-priti` profile first and discloses what it loaded. They re-read each issue's state immediately before every write.
4. Re-check issue states and merged PRs, then write one consolidated report.
5. Put every flagged item to the operator, apply each ruling yourself, and report the final state.

## Two rules to repeat in every brief

- Never set `priority:P0` yourself. Name the criterion the issue meets and flag it for the operator.
- Flag rather than guess. Never touch `status:*`, `squad:*` or `needs:*` labels; they belong to the agent fleet.

## Stop and ask the operator when

- an item is flagged (P0 candidate, unclear parent or milestone, deprecated or superseded content, suspected duplicate, emerging cluster);
- a subagent fails or a write is refused (retry once, then list the issues as "not triaged" with the error).

## Hand-off

Give the operator the consolidated report: a table of what changed per issue, the "Needs an operator decision" section, each subagent's doctrine disclosure, the baseline ref (with a note if `origin` lags it) and the counts. Do not call the pass complete while flagged items are unresolved.
