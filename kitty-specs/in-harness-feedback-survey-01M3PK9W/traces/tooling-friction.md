# Tooling Friction — in-harness-feedback-survey-01M3PK9W

Tooling this mission touches: the command renderer/installer seams (`prepend_agent_upgrade_check` call sites), CLI-driven command shims, `DistributionProfile`, kernel locking/atomic primitives, and the `spec-kitty` specify/plan/decision CLI.

- 2026-09-29 — Specify: the Decision Moment protocol requires `decision open --mission` before each interview question, but no mission exists until `mission create`; the pre-create discovery questions had to be backfilled as decisions after creation.
- 2026-09-29 — Specify: `spec.md` is scaffolded empty; the canonical `spec-template.md` had to be located by hand under `packs/built-in/missions/software-dev/templates/`.
- 2026-09-30 — Plan: `spec-kitty next --mission … --json` reported `mission_state: not_started` / `preview_step: discovery` even though the spec was committed through `/spec-kitty.specify`; the runtime loop does not reflect slash-command-driven phase progress.
- 2026-09-30 — Plan: `spec-kitty charter context --include tactic:<id> --json` returned an empty payload; the tactic YAML had to be read directly.
- 2026-09-30 — Tasks: the installed `spec-kitty.tasks` skill (3.2.5) says to track subtasks with `- [ ]` checkboxes, while the source prompt `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md` and `tasks-template.md` say reference rows tracked via `mark-status`. The source was followed; the installed copy is stale.
- 2026-09-30 — Tasks: `tests/architectural/test_docs_cli_reference_parity.py::test_doctrine_source_snippets_are_registered` scans the retired `src/charter/offering/missions/mission-steps/**` glob, which matches nothing, so the gate is vacuous for the real `packs/built-in/missions/mission-steps/` prompts. Folded into WP07 as T041 (domain-matched campsite), with an issue-and-revert fallback.
- 2026-09-30 — Tasks: the WP prompt template is referenced by the tasks skill but not inlined; it had to be read from `packs/built-in/missions/software-dev/templates/task-prompt-template.md`.
