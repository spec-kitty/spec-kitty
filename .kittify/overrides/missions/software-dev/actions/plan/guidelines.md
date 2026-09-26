# Plan Action — Governance Guidelines

These guidelines govern the quality and correctness standards for implementation planning work in the software-dev mission. They were extracted from the command template and are injected at runtime via the charter context bootstrap.

---

## Core Authorship Rules

- Use absolute paths when referencing files and directories.
- ERROR on gate failures or unresolved clarifications — do not silently proceed past blockers.
- Mark `[NEEDS CLARIFICATION: …]` only when the user deliberately postpones a decision; resolve every other ambiguity before generating design artifacts.

---

## Charter Compliance

- If a charter exists, fill the Charter Check section from it and challenge any conflicts directly with the user.
- If no charter exists, mark the Charter Check section as skipped.
- Re-evaluate Charter Check after Phase 1 design and resolve new gaps before reporting completion.

---

## Phase Discipline

- Phase 0 must fully resolve all `NEEDS CLARIFICATION` items before Phase 1 begins.
- Phase 1 design artifacts (data-model.md, contracts/, quickstart.md) must derive from confirmed planning answers — not from raw user input.
- This command ends after Phase 1. Do NOT proceed to task generation.
