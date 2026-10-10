---
title: Parallel Implementation Tracking
description: Track several agents implementing a roadmap in parallel and give leadership continuous visibility through Spec Kitty status views and the WP status event log.
doc_status: active
updated: '2026-10-10'
type: how-to
audience: docs/context/audience/external/architect-evaluator.md
---

# Parallel Implementation Tracking

Use this recipe when multiple agents implement a roadmap in parallel and leadership needs continuous visibility.

## Setup
- Project: Priivacy Rust recognizers
- Active worktree: `.worktrees/001-systematic-recognizer-enhancement`

## Steps
1. **Check status** – Run `spec-kitty agent tasks status` to see the lane-based board for the Mission.

2. **Snapshot lane counts** – The status output shows items in `planned`, `in_progress`, `for_review`, `done`. Capture `spec-kitty agent tasks status --json` for hourly reports.

3. **Move prompts via workflow commands** – Always use `spec-kitty agent action implement/review` so the status log stays accurate:
   ```bash
   spec-kitty agent action implement WP01
   ```

4. **Record history notes** – Lane moves are recorded automatically in the Mission's `status.events.jsonl`. Agents add free-form notes to the same event log for auditability:
   ```bash
   spec-kitty agent tasks add-history WP01 --note "Resumed after dependency install"
   ```
   Read notes back with `spec-kitty agent tasks status`.

5. **Monitor task completion** – Review `kitty-specs/<feature>/tasks.md` checklist to ensure all subtasks are checked before merge.

6. **Automate alerts** (Optional) – Poll machine-readable status for monitoring:
   - `spec-kitty orchestrator-api mission-state --mission <slug>` - Mission state and WP lanes as JSON
   - `spec-kitty agent tasks status --json` - Lane-based status for the current Mission
   - Build custom alerts when tasks spend >4 hours in `in_progress` lane

## Reporting
- Export `tasks.md` and `spec-kitty agent tasks status` output at daily stand-up
- Summarize agent throughput using the lane events and history notes in `status.events.jsonl`
- Identify bottlenecks by checking lane distribution in the status output
- Use `/spec-kitty.accept --mode checklist` to generate readiness report
- Use `/spec-kitty.merge --dry-run` to produce merge preview for executives

The bundled local web dashboard has been removed. A read-only Mission Status Read API ([#5528](https://github.com/spec-kitty/spec-kitty/issues/5528)) is planned as the contract for a replacement UI, which will live in its own repository.
