---
name: spk-start-here
description: "Start here for Spec Kitty. Orient CLI users and supported agent-harness users; choose the right command, skill family, and recovery path."
---

# spk-start-here

Orient the user by where they are working: command line or supported agent
harness.

## Access Model

- Command-line users run `spec-kitty` CLI commands. `spk-*` skills are not CLI
  commands.
- Agent-harness users invoke installed command surfaces:
  `/spec-kitty.*` in slash-command hosts, `$spec-kitty.<command>` in Codex, or
  the host's skill syntax for skill hosts.
- Public `spk-*` skills are agent operating guides. Use them by name in a
  skill-aware harness or let natural-language intent trigger them.
- If commands or skills are missing, route to `spk-admin-setup-doctor`.

## Operating Model

Spec Kitty has three visible layers:

1. Commands: `/spec-kitty.*` slash commands and CLI commands that create or
   advance mission artifacts.
2. Skills: `spk-*` operating guides that teach an agent how to use the product.
3. Doctrine: charter, glossary, profiles, directives, and tactics loaded on
   demand by the runtime or by specialist skills.

Do not turn this into a full tutorial. Identify entry mode first, then route to
the smallest useful workflow.

## First Route

- New project or broken install: use `spk-admin-setup-doctor`.
- New feature from scratch: use `spk-start-first-feature`.
- User wants a command list: use `spk-start-command-map`.
- User asks "will this work in Codex or Claude?": use `spk-start-agent-surface`.
- Existing mission needs advancement: use `spk-run-next`.
- Multi-mission or multi-repo program: use `spk-run-program-orchestrate`.
- Review or approval work: use `spk-run-review-wp`, then `spk-gate-accept`.
- Team, SaaS, tracker, or sync concern: use `spk-team-sync` or `spk-team-tracker`.
- Charter or governance concern: use the `spk-charter-*` family.
- Engineering practice (bulk edit, visuals, code reduction): use the `spk-practice-*` family.
- Visual explanation or diagram request: use `spk-practice-show-me`.
- Unsure which skill applies: use `spk-meta-skill-map`.

## Agent Behavior

State the route, load only the routed skill, and continue. Prefer commands and
runtime outputs over guessing from files. If the user asks for a plan, give the
shortest workflow that gets them to the next concrete Spec Kitty action.
