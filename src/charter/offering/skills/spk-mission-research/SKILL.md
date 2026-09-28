---
name: spk-mission-research
description: "Operate pre-spec or in-mission research workflows while keeping findings tied to mission decisions."
---

# spk-mission-research

Use this skill when a mission needs discovery, external facts, design precedent,
technical investigation, or decision support.

## Flow

1. Use `/spec-kitty.research` for pre-spec discovery, before a spec or plan
   exists: capture decisions, evidence, and open questions directly in
   `research.md` (create or extend it; never truncate it).
2. On a mission type that ships research templates (today: the `research`
   mission type), once that mission's plan is filled in you can additionally
   run `spec-kitty research --mission <handle>` to scaffold `research.md`,
   `data-model.md`, and the CSV stubs from the shipped templates. Other
   mission types, including `software-dev`, have no such scaffold — the
   command creates nothing for them.
3. Write findings as decision-ready evidence, not a loose reading list.
4. Record assumptions, source quality, and unresolved questions.
5. Return findings to `spk-mission-specify` or `spk-mission-plan`.

## Rule

Research is not a substitute for a spec. It should narrow uncertainty enough for
the next mission phase.
