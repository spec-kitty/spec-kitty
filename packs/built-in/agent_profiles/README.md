# Shipped Agent Profiles

Reference agent profiles included in the `doctrine` package distribution. These
define the core roles with their specialization, collaboration contracts, directive
references, and initialization declarations. Language-specialist profiles (prefixed
with the language name) extend the base `implementer-ivan` role for polyglot projects.

| File | Profile ID | Primary Role |
|------|------------|------|
| `architect-alphonso.agent.yaml` | `architect-alphonso` | architect |
| `curator-carla.agent.yaml` | `curator-carla` | curator |
| `debugger-debbie.agent.yaml` | `debugger-debbie` | investigator |
| `designer-dagmar.agent.yaml` | `designer-dagmar` | designer |
| `doctrine-daphne.agent.yaml` | `doctrine-daphne` | curator / onboarding-guide |
| `drupalling-dries.agent.yaml` | `drupalling-dries` | implementer (Drupal specialist) |
| `frontend-freddy.agent.yaml` | `frontend-freddy` | implementer |
| `generic-agent.agent.yaml` | `generic-agent` | implementer |
| `human-in-charge.agent.yaml` | `human-in-charge` | human-in-charge |
| `implementer-ivan.agent.yaml` | `implementer-ivan` | implementer |
| `java-jenny.agent.yaml` | `java-jenny` | implementer (Java specialist) |
| `node-norris.agent.yaml` | `node-norris` | implementer |
| `paula-patterns.agent.yaml` | `paula-patterns` | architecture-scout |
| `planner-priti.agent.yaml` | `planner-priti` | planner |
| `python-pedro.agent.yaml` | `python-pedro` | implementer (Python specialist) |
| `randy-reducer.agent.yaml` | `randy-reducer` | implementer (semantic compression specialist) |
| `researcher-robbie.agent.yaml` | `researcher-robbie` | researcher |
| `retrospective-facilitator.agent.yaml` | `retrospective-facilitator` | facilitator |
| `reviewer-renata.agent.yaml` | `reviewer-renata` | reviewer |
| `analyst-annie.agent.yaml` | `analyst-annie` | analyst |
| `comms-cleo.agent.yaml` | `comms-cleo` | communicator |
| `diagram-daisy.agent.yaml` | `diagram-daisy` | diagram-author |
| `lexical-larry.agent.yaml` | `lexical-larry` | semantic-analyst |
| `minutes-mahad.agent.yaml` | `minutes-mahad` | documentarian |
| `scribe-sally.agent.yaml` | `scribe-sally` | documentarian |
| `synthesizer-sam.agent.yaml` | `synthesizer-sam` | synthesizer |

Shipped profiles are read-only at the package level. Project-level overrides in
`.kittify/charter/agents/` can customize any profile by matching `profile-id`.
