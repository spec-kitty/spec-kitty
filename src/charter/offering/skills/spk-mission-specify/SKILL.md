---
name: spk-mission-specify
description: "Operate the Spec Kitty specify phase: turn user intent into a mission spec while preserving scope, ambiguity, and acceptance criteria."
---

# spk-mission-specify

Use this skill when creating or revising a mission specification.

## Flow

1. Run or invoke `/spec-kitty.specify` for the feature.
2. Capture the user's concrete goal, constraints, non-goals, and success
   criteria.
3. Keep unresolved product decisions explicit instead of hiding them in plan
   details.
4. If terminology matters, route to `spk-charter-glossary`.
5. If governance affects scope, route to `spk-charter-governance`.
6. When a non-trivial user flow, domain lifecycle, rule, or concept boundary is
   clearer visually, load `spk-practice-show-me` and add the smallest useful
   diagram. Keep implementation choices out of the specification.

## Output Standard

The spec should be good enough for `/spec-kitty.plan` to derive architecture
and implementation strategy without inventing product intent. Work packages are
authored by `/spec-kitty.tasks`.
