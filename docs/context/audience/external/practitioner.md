---
title: 'Stakeholder Persona: Practitioner'
description: 'External practitioner persona: installs the Spec Kitty CLI and runs Missions day to day, from specify to consolidate, and needs commands that work and clear recovery.'
doc_status: active
kind: Explanation
updated: '2026-11-16T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Check that this profile still describes a real reader before pages are written for it.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this profile before drafting a page for this reader; match its vocabulary and the questions it brings.
---
# Stakeholder Persona: Practitioner

| Field | Value |
|---|---|
| **Category** | `EXTERNAL Stakeholder` |
| **Actor Type** | `human` |
| **Primary Goal** | Get a change from intent to a reviewed, landed result with the Spec Kitty CLI, without fighting the tool. |
| **Persona ID** | `aud-ext-practitioner` |
| **Created / Updated** | `2026-11-16` / `2026-11-16` |
| **Domain / Context** | Spec Kitty 4.x |
| **Status** | canonical |

---

## Overview

- **Role Focus**: Hands-on use of the CLI in their own project.
- **Primary Function**: Installs Spec Kitty (`uv tool install spec-kitty-cli`, `pipx install spec-kitty-cli` or `python -m pip install spec-kitty-cli`), runs `spec-kitty init` in a repository, and drives Missions through `/spec-kitty.specify`, `/spec-kitty.plan`, `/spec-kitty.tasks`, implementation, review, `spec-kitty accept` and `spec-kitty consolidate`, usually with an AI coding agent doing the work.
- **Environment / Context**: A developer or small-team lead working in their own repository, new to Spec Kitty or using it every day. They are not a Spec Kitty contributor and do not read its source.

---

## Core Motivations

- **Professional Drivers**: Ship the change they set out to make, with a spec and a review behind it, in less time than doing it by hand.
- **Emotional or Cognitive Drivers**: Confidence that the next command is the right one and that a refusal can be recovered from.
- **Systemic Positioning**: Runs the workflow; does not set governance policy (the [Project Owner](project-owner.md) does) or decide adoption (the evaluators do).

---

## Desiderata

| Category | Expectation / Need | Description |
|---|---|---|
| Information | The next step, always | Wants to know where a Mission stands and what to run next: `spec-kitty agent tasks status`, `spec-kitty next --agent <name> --mission <slug>`. |
| Interaction | Copy-paste commands | Expects every command on a page to run as printed on the current release, with the flags it really takes. |
| Support | Recovery recipes | Needs a named remedy for each refusal code a command prints, and the recovery commands (`spec-kitty doctor`, `spec-kitty consolidate --resume` / `--abort`, `spec-kitty upgrade`). |
| Governance | Light, visible gates | Accepts the discovery interview and review gates when they say why they block and what answers they need. |
| Decision Authority | Their own Missions | Decides scope inside a Mission, approves or rejects work packages, and chooses when to consolidate and open a pull request. |

---

## Frustrations and Constraints

- **Pain Points**: Commands or flags in the docs that the installed CLI does not have; a refusal code with no remedy; wording that mixes senses of "lane", "merge" or "primary"; pages written for evaluators or contributors when they need a task done.
- **Trade-Off Awareness**: Accepts the interview and review steps if they catch real problems early.
- **Environmental Constraints**: Limited time per session, work that spans several sessions, and an agent that follows the docs literally.

---

## Behavioral Cues

| Situation | Typical Behavior | Interpretation |
|---|---|---|
| Stable / Routine | Runs the command sequence from memory or a tutorial | Trusts the workflow while it behaves as documented. |
| Change / Uncertainty | Searches the docs for the error code or command they just saw | Needs reference and how-to pages keyed to codes and commands. |
| Under Pressure | Reaches for `--force` or hand edits of `.kittify/` files | Needs the safe recovery path to be easier to find than the shortcut. |

---

## Collaboration Preferences

- **Decision Style**: Pragmatic; picks the path that gets the Mission moving again.
- **Communication Style**: Short steps, exact commands, expected output.
- **Feedback Expectations**: Errors that name the cause and the next command to run.

---

## Design Impact

- **Affected By**: Tutorials, task how-tos, CLI reference pages, refusal messages and the commands agents print.
- **Needs From Design**: A first Mission that works end to end on the current release, and a recovery path for every refusal.
- **Risk If Ignored**: Abandoned Missions, hand-edited state, and loss of trust in the tool.
- **Acceptance Signal**: A new user completes a first Mission from `spec-kitty init` to `spec-kitty consolidate` without asking for help.

---

## Measures of Success

| Dimension | Indicator | Type |
|---|---|---|
| Performance | Time from installation to the first consolidated Mission | Quantitative |
| Quality | Share of documented commands that run as printed on the current release | Quantitative |
| Growth | Confidence recovering from a refusal without hand-editing state | Qualitative |

---

## Narrative Summary

The Practitioner installs Spec Kitty and uses it to get their own work done. They run the
commands, answer the interviews, review what their agent produced and consolidate the
result. They read tutorials and how-tos, not architecture pages, and they judge the docs by
one test: does the command on the page work, and when it refuses, does the page say what to
do next.

---
