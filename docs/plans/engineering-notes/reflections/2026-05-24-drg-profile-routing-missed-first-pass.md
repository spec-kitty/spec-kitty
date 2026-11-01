---
title: DRG profile routing not applied on first tasks generation
description: 'Reflection: DRG profile routing was not applied on the first /spec-kitty.tasks run for mission 01KSAF14, so Python WPs were misassigned; what happened and why.'
doc_status: draft
updated: '2026-05-26T00:00:00Z'
kind: Planning
---
# DRG profile routing not applied on first tasks generation

When I ran `/spec-kitty.tasks` for mission `charter-ux-and-org-pack-vocabulary-01KSAF14`, every Python-implementation work package was assigned the generic `implementer-ivan` profile. The HiC had to ask explicitly for "proper assignment based on dynamic DRG routing and task context" before the more-specific `python-pedro` (routing priority 80, with `pydantic / pytest / pathlib / refactor / python` in its action-domain set) was applied to WP01-WP08.

## What happened

- All eight Python-implementation WPs got `agent_profile: implementer-ivan` on first pass (priority 50, generic implementer).
- WP09 correctly got `curator-carla` (documentation/glossary work).
- WP10 correctly got `reviewer-renata` (acceptance/sign-off framing).
- The remaining mismatch on WP01-WP08 was caught by a second-pass HiC nudge, not by the routing logic itself.

## What should have happened

The `/spec-kitty.tasks` skill explicitly instructs the agent (Step 8a) to "review all available doctrine-provided and user-created agent profiles and assign the most relevant profile to each work package" using `task_type`, `authoritative_surface`, `owned_files`, and subtask content. With `python-pedro.routing-priority = 80` vs `implementer-ivan.routing-priority = 50`, and with every owned-file path under `src/**/*.py` and every test under `tests/specify_cli/**/*.py` or `tests/integration/**/*.py`, Pedro is the strict overmatch from the DRG signal alone.

## Why the gap

Two compounding causes:

1. **Anchoring on the most generic acceptable profile.** I reached for `implementer-ivan` because it is the literal canonical "implementer" role and trivially correct. That is the default that satisfies the role-fit check but ignores the routing-priority + action-domain overlap. The skill's Step 8a is explicit about doing the routing match; I executed it as a one-line shortcut.
2. **Skill-instruction recency vs. task-pressure inversion.** Step 8a sits late in a long prompt, after seven steps that all emphasised completing the planning artifacts. By the time it fired, the gravitational pull was "land the WPs and finalize-tasks" rather than "run a separate profile-matching pass". The skill's framing rewards completion over precision on this last step.

Neither cause is novel — both are classic LLM failure modes (default-to-generic, step-fatigue near the end of multi-step prompts). The interesting observation is that the DRG routing data needed to do this correctly was sitting one CLI call away (`spec-kitty agent profile list --json`), but I didn't think to invoke it on the first pass.

## Follow-up

- If this recurs, consider tightening Step 8a of the `/spec-kitty.tasks` skill: make the profile-matching call mandatory and require a 1-line justification per WP referencing the matched action-domain. That converts "pick a profile" into a small structured argument that's harder to discharge with a generic default.
- Or expose a CLI helper `spec-kitty agent profile match --wp <id> --json` that resolves the best profile from owned_files + action domains, so the agent doesn't have to reproduce the matching logic in prose.
- For now, the lesson is local to this mission: profile assignment is a separate step that benefits from doing the lookup explicitly, not a "default to ivan" decision.
