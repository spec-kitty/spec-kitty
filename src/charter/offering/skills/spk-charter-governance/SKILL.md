---
name: spk-charter-governance
description: >-
  Run Spec Kitty charter interview, generation, context loading, and
  synchronization workflows for project governance. Access charter artifacts
  programmatically via ActiveCharterService. Resolve agent profiles. Load
  action-scoped governance context iteratively, not all at once.
  Triggers: "interview for charter", "generate charter",
  "sync charter", "use doctrine", "set up governance",
  "charter status", "extract governance config", "load doctrine",
  "agent profile", "ActiveCharterService", "action index".
  Does NOT handle: generic spec writing not tied to governance, direct runtime
  loop advancement, setup/repair diagnostics, or editorial glossary maintenance.
---

# spk-charter-governance

Use this skill for project governance, charter creation, charter sync, or
charter context questions.

`.kittify/charter/charter.yaml` is the runtime governance source for a
project; `.kittify/charter/charter.md` is a human-readable companion the
runtime never parses. The charter offering (`src/charter/offering/`) supplies
the reusable directives, tactics, paradigms, styleguides, toolguides,
procedures, agent profiles, and step contracts the charter references.

## Invariant

spec-kitty never calls an LLM. The harness running this skill is the
inference engine: when asked to synthesize charter artifacts, author them
yourself, then let the CLI validate and promote them.

## Flow

1. Invoke `/spec-kitty.charter` or the relevant charter command.
2. Check the current state:

   ```bash
   spec-kitty charter status --json
   ```

3. Discover the change in chat, write
   `.kittify/charter/interview/answers.yaml`, then generate:

   ```bash
   spec-kitty charter generate --from-interview --json
   ```

4. Keep governance decisions explicit and versioned; edit `charter.yaml`
   directly for policy changes.
5. Load charter context on demand, scoped to the active action:

   ```bash
   spec-kitty charter context --action <action> --json
   ```

6. Use the `spk-charter-glossary` and `spk-charter-spdd-reasons` skills when
   the charter selects those practices; load profiles with
   `spk-charter-profile-load`.

## References

- `references/charter-governance-workflow.md` -- Full workflow: agent-driven
  synthesis, the charter model and data flow, artifact kinds,
  `ActiveCharterService` access, profile resolution, and common pitfalls.
- `references/charter-command-map.md` -- Full CLI command reference with all
  flags and output fields.
- `references/charter-artifact-structure.md` -- File layout, authority
  classes, and data flow.
