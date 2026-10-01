---
title: Multi-Agent Mission Development
description: Orchestrate a multi-agent team of Claude, Gemini, and Cursor to deliver a complex mission end to end with Spec Kitty work packages and human review.
doc_status: active
updated: '2026-08-10'
type: how-to
audience: docs/context/audience/external/architect-evaluator.md
---

# Multi-Agent Mission Development

A lead architect coordinates several AI agents — each playing to its strength — to deliver one complex mission through Spec Kitty. This walkthrough shows the hand-offs from specification to merge and where the human reviewer stays in the loop.

**At a glance:** one mission, four contributors (Claude, Gemini, Cursor, and a human reviewer), eight work packages, and a two-week window — driven by the standard `/spec-kitty.*` command sequence.

## Context

| Dimension | Value |
|-----------|-------|
| Mission | `001-cross-platform-chat-upgrade` |
| Agents | Claude (spec/plan), Gemini (data modeling), Cursor (implementation), human reviewer |
| Goal | Ship a cross-platform chat upgrade (web + mobile) with improved reliability in two weeks |

## Playbook

1. **Specify the mission.** The lead runs `/spec-kitty.specify` with the stakeholder brief. Discovery gates confirm scope, users, and success metrics.

2. **Plan and research.** Claude executes `/spec-kitty.plan` to capture architecture; Gemini runs `/spec-kitty.research` to gather literature benchmarks.

3. **Generate work packages.** `/spec-kitty.tasks` produces eight prompts across API, UI, and infrastructure. `[P]` flags highlight parallel-safe work such as documentation updates and telemetry instrumentation.

4. **Assign agents.**
   - Claude handles plan updates and reviews.
   - Gemini owns `data-model.md` updates and research prompts.
   - Cursor implements the chat service changes.
   - The human reviewer tracks `tasks/for_review/`.

5. **Run the orchestration loop.**
   - Manual mode: `spec-kitty agent action implement WP##` per assigned work package.
   - Automated mode: `spec-kitty-orchestrator orchestrate --mission 001-cross-platform-chat-upgrade`.

6. **Review completed work.** The human reviewer processes `for_review` prompts via `/spec-kitty.review`, giving feedback or approving work to move to `done`.

7. **Accept and merge.** Once every work package is in `done/`:
   ```text
   /spec-kitty.accept   # Validates mission readiness, records metadata
   /spec-kitty.merge    # Consolidates lane branches into local main and cleans up worktrees
   ```

## Outcome

- Web and mobile chat surfaces upgraded with consistent reliability guarantees.
- Zero merge conflicts — agents respected prompt-file boundaries.
- `spec-kitty agent tasks status --json` snapshot exported for the sprint report.
