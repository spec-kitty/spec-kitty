---
title: Orchestrator Quickstart
description: Learn how Spec Kitty and spec-kitty-orchestrator work together to run a small mission through implementation and review.
doc_status: active
updated: '2026-08-11'
audience: docs/context/audience/external/project-owner.md
type: tutorial
related:
- docs/guides/tutorials/your-first-mission.md
---
# Orchestrator Quickstart

This tutorial shows the external orchestration model end to end:

- `spec-kitty` owns mission state and lane transitions.
- `spec-kitty-orchestrator` runs agents and calls `spec-kitty orchestrator-api`.
- Implementation and review happen in git worktrees, not on protected `main`.

By the end, you will know how to check the host contract, run the reference
orchestrator, watch mission state, and recover from a stopped run.

## Prerequisites

You need:

- a git repository initialized with Spec Kitty
- `spec-kitty` on `PATH`
- a host-compatible `spec-kitty-orchestrator` build on `PATH`
- at least one agent CLI supported by the orchestrator, such as Claude Code,
  Codex, or OpenCode
- a mission with at least one `tasks/WP*.md` file

If you do not have a mission yet, finish [Your First Mission](your-first-mission.md)
first.

![Orchestrator quickstart - Mission Kitty splash](../../assets/images/orchestrator-quickstart-mission-kitty.png)

_Stylized splash — the conductor's podium is decorative. Host contract, orchestrator run, and recovery steps are in the sections below._

## Version compatibility

The orchestrator is published on
[PyPI as `spec-kitty-orchestrator`](https://pypi.org/project/spec-kitty-orchestrator/).
Install the latest compatible package from PyPI, then verify the host contract
before running a mission.

## 1. Install the orchestrator

Use `pipx` for an isolated command-line install:

```bash
pipx install spec-kitty-orchestrator
```

If you already have it installed:

```bash
pipx upgrade spec-kitty-orchestrator
```

If you prefer `uv` tool management:

```bash
uv tool install spec-kitty-orchestrator
```

Or upgrade an existing uv-managed install:

```bash
uv tool upgrade spec-kitty-orchestrator
```

Confirm the CLI is now available:

```bash
spec-kitty-orchestrator --help
spec-kitty-orchestrator orchestrate --help
```

If either command is missing, check that the Python environment where you
installed the package is on `PATH`.

The source repository is
[`spec-kitty/spec-kitty-orchestrator`](https://github.com/spec-kitty/spec-kitty-orchestrator)
if you want to inspect code, issues, or release history. Do not install from
GitHub unless you are intentionally testing unreleased provider changes.

Return to your Spec Kitty project root before continuing.

## 2. Confirm the host API works

Run this from the project root:

```bash
spec-kitty orchestrator-api contract-version
```

The output is a JSON envelope. For a compatible host it includes:

```json
{
  "success": true,
  "data": {
    "api_version": "1.0.0"
  }
}
```

The orchestrator performs this check at startup too, but running it yourself
confirms that the host CLI is installed and that JSON output is available.

## 3. Find your mission slug

Use the dashboard, `kitty-specs/`, or the mission commands to identify the
mission slug:

```bash
ls kitty-specs
```

Examples look like:

```text
034-payment-retry-flow
099-orchestrator-e2e
```

The orchestrator API selector is always `--mission`, even when the selector is
a slug, mission id, or short mission id.

## 4. Inspect ready work

```bash
spec-kitty orchestrator-api list-ready --mission 034-payment-retry-flow
```

Ready work packages are WPs in `planned` whose dependencies are already `done`.
If no WPs are ready, inspect the whole mission:

```bash
spec-kitty orchestrator-api mission-state --mission 034-payment-retry-flow
```

## 5. Dry-run the orchestrator

```bash
spec-kitty-orchestrator orchestrate \
  --mission 034-payment-retry-flow \
  --impl-agent claude-code \
  --review-agent codex \
  --max-concurrent 1 \
  --dry-run
```

Use `--dry-run` before the first real run. It validates configuration without
moving WP lanes.

## 6. Run implementation and review

```bash
spec-kitty-orchestrator orchestrate \
  --mission 034-payment-retry-flow \
  --impl-agent claude-code \
  --review-agent codex \
  --max-concurrent 1
```

With a host-compatible provider build, the orchestrator loop will:

1. call `list-ready`
2. call `start-implementation` for a ready WP
3. prepare a usable WP worktree and run the implementation agent there
4. transition the WP to `for_review`
5. run the review agent
6. claim `in_review` before completing approved review
7. transition to `done` with the required review evidence when the review passes
8. move rejected work back to `in_progress` for rework

The orchestrator writes its local run state under `.kittify/` and agent logs
under `.kittify/logs/`.

## 7. Check progress

In another terminal:

```bash
spec-kitty-orchestrator status
spec-kitty orchestrator-api mission-state --mission 034-payment-retry-flow
```

Use `mission-state` as the source of truth for WP lanes. Use
`spec-kitty-orchestrator status` for provider-local details such as retry
counts and the last agent log path.

## 8. Resume or abort

If the process is interrupted:

```bash
spec-kitty-orchestrator resume
```

If you need to stop tracking the run state:

```bash
spec-kitty-orchestrator abort --cleanup-worktrees
```

`abort --cleanup-worktrees` removes provider-local state. It does not rewrite
authoritative mission lane history.

## What to read next

- [Run the External Orchestrator](../how-to/collaboration/run-external-orchestrator.md) for
  operational commands and troubleshooting.
- [Build a Custom Orchestrator](../how-to/collaboration/build-custom-orchestrator.md) if you
  want to write your own provider loop.
- [Orchestrator API Reference](../../api/orchestrator-api.md) for command
  flags and JSON payloads.
- [Multi-Agent Orchestration](../../architecture/multi-agent-orchestration.md) for
  the host/provider model.
