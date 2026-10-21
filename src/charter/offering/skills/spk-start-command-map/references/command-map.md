# Command Map

| User intent | Command | Operating skill |
|---|---|---|
| Start or revise a specification | `/spec-kitty.specify` | `spk-mission-specify` |
| Capture discovery findings before specification | `/spec-kitty.research` | `spk-mission-research` |
| Create an implementation plan | `/spec-kitty.plan` | `spk-mission-plan` |
| Create tasks or work packages | `/spec-kitty.tasks*` | `spk-mission-tasks` |
| Implement assigned work | `/spec-kitty.implement` or `next` output | `spk-run-next` |
| Review a work package | `/spec-kitty.review` or review lane output | `spk-run-review-wp` |
| Accept completed mission | `/spec-kitty.accept` | `spk-gate-accept` |
| Consolidate mission work | `/spec-kitty.consolidate` | `spk-gate-consolidate` |
| Inspect current state | `spec-kitty agent tasks status` or `spec-kitty agent status ...` | `spk-run-next` |
| Charter/governance work | `/spec-kitty.charter` | `spk-charter-governance` |

Generated slash-command files and generated Agent Skills are separate command
surfaces. Slash-command files use `/spec-kitty.<command>`; command skills are
named `spec-kitty-<command>` under `.agents/skills/` (`$spec-kitty-<command>` in
Codex, `/skill:spec-kitty-<command>` in Pi, `/spec-kitty-<command>` in Vibe,
Letta and Antigravity). Operating skills are named `spk-*` for user discovery.
