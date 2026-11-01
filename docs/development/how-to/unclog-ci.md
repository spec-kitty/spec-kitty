---
title: 'Pull the safety cord: unclog a deadlocked Actions queue'
description: Pause CI on every PR you are not landing with the pr:pause-ci label, drain the Actions queue, and get the PRs you are landing back to a green signal.
doc_status: active
updated: '2026-11-01'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/how-to/pr-landing.md
---
# Pull the safety cord: unclog a deadlocked Actions queue

## When to use this

Use this guide when GitHub Actions runs on `spec-kitty/spec-kitty` stay queued for a long time
and the PRs you are landing cannot get a green signal. On 2026-11-01 about 480 runs were queued
or in progress at the worst point: 391 `pull_request`, 78 `workflow_run`, and a few `push` and
`schedule` runs.

Check the shape of the queue first:

```bash
unset GITHUB_TOKEN   # if gh reports missing scopes
R=spec-kitty/spec-kitty
gh run list --repo $R --status queued --limit 500 \
  --json databaseId,workflowName,event,headBranch \
  | jq -r 'group_by(.workflowName)[] | "\(length)\t\(.[0].workflowName)"' | sort -rn
```

Repeat with `--status in_progress`, and group by `.event` as well. A queue dominated by
`pull_request` runs across many branches is the case this guide covers.

## Steps

The label only works once `.github/workflows/pr-pause-ci.yml` and the label guards are on `main`.
PR runs use the workflows as merged with current `main`, so paused PRs need no rebase.

1. **Decide the keep-set.** List the PRs you are actively landing. Everything else gets paused.
2. **Test the label on one PR.**

   ```bash
   gh pr edit <n> --repo $R --add-label pr:pause-ci
   gh run list --repo $R --workflow pr-pause-ci.yml --limit 5
   ```

   Confirm that the `PR Pause CI` run succeeded and that the PR's three required gates
   (`router gate`, `CI Modules gate`, `Clean install verification`) read `fail`.
3. **Label every other open PR.**

   ```bash
   gh pr list --repo $R --state open --limit 500 --json number,labels \
     | jq -r '.[] | select(all(.labels[]; .name != "pr:pause-ci")) | .number' \
     | grep -vxF -f keep-set.txt \
     | xargs -P 8 -I{} gh pr edit {} --repo $R --add-label pr:pause-ci
   ```

   `keep-set.txt` holds one PR number per line.
4. **Drain the queue if the pause runs are stuck behind it.** Cancel every queued or in-progress
   run except `PR Pause CI`, and repeat about every 20 seconds until the pause runs complete:

   ```bash
   for s in queued in_progress; do
     gh run list --repo $R --status $s --limit 500 --json databaseId,workflowName \
       | jq -r '.[] | select(.workflowName != "PR Pause CI") | .databaseId'
   done | xargs -P 8 -I{} gh run cancel {} --repo $R
   ```

   Expect `CI Aggregate` runs to reappear as you cancel `CI Modules` runs (see below).
5. **Re-run the keep-set's canceled runs.** For each keep-set PR, find the canceled
   `pull_request` runs on its head SHA and re-run them:

   ```bash
   SHA=$(gh pr view <n> --repo $R --json headRefOid -q .headRefOid)
   gh run list --repo $R --commit $SHA --status cancelled --json databaseId \
     -q '.[].databaseId' | xargs -I{} gh run rerun {} --repo $R
   ```

6. **Resume a paused PR when you pick it up for landing.** Remove the label. If the PR was pushed
   while labeled, push again (or close and reopen it).

   ```bash
   gh pr edit <n> --repo $R --remove-label pr:pause-ci
   ```

Verify `gh` flags against `gh <command> --help` before running a loop.

On 2026-11-01 this took the in-flight count from 195 to 35, all from the keep-set, with 83 PRs
paused. A fleet push to a paused PR now costs three quick gate jobs.

## Why each step works

- **Why the queue clogs.** An external contributor fleet rebases and force-pushes dozens of open
  PRs every time `main` moves. Each push queues the full PR matrix: CI Router, CI Modules (about
  60 jobs), CI Quality, Packs, Contracts, ci-windows, Release Readiness and more. Every GitHub PR
  merge to `main` starts a new wave.
- **Why the label stops it.** Under `pr:pause-ci` the root job of each PR workflow skips, so the
  heavy jobs skip. The three required gates still run and fail with a message, so the PR cannot be
  merged on GitHub while paused. On `labeled`, a small `pull_request_target` workflow cancels the
  PR's queued and in-progress runs and posts failing gate checks. On `unlabeled` it re-runs the
  runs it canceled, unless the PR's head moved since (a push already started fresh runs). Details: [Pausing a PR's CI](pr-landing.md#pausing-a-prs-ci-prpause-ci).
- **Why test on one PR first.** A broken guard on 80 PRs is 80 PRs to repair.
- **Why drain.** The pause runs wait in the same queue as everything else. Cancelling the backlog
  lets them start.
- **Why the drain refills.** `ci-aggregate.yml` is triggered by `workflow_run` on CI Modules
  completion, and a canceled run counts as completed. Mass-canceling CI Modules queues one CI
  Aggregate run each (90 of 195 in-flight runs at one point). A single cancel sweep refilled
  within minutes, so loop until the pause runs finish.
- **Why push again after unlabeling.** A run that started while the PR was labeled replays the
  label and pauses again. The workflow cannot push for you: events caused by `GITHUB_TOKEN` start
  no workflow runs.

## What not to do

- **Do not mark PRs draft.** No workflow checks draft status, and undrafting fires
  `ready_for_review`, which queues another full run.
- **Do not add a new skip label in the same crisis.** The change that teaches workflows to honor it
  must itself pass the clogged CI. (The `pr:pause-ci` change, PR #6961, was merged on GitHub by
  operator override because its own CI could not get a runner.)
- **Do not rely on a cancel sweep alone.** The fleet and CI Aggregate refill the queue.
- **Shell pitfalls.** In zsh, `"$BR:refs/..."` eats `:r`; write `"${BR}:refs/..."`. Never
  `pkill -f` a pattern that appears in your own command line.

## Residuals

- The root cause, the fleet's rebase on every move of `main`, is outside our control.
- `ci-aggregate.yml` does not skip canceled or paused sources; a candidate follow-up.
- `scripts/ci/fleet_verdict.py` reads a paused PR as red.
- `mission-status-api.yml` is not guarded by the label.
