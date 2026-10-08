---
name: spk-charter-glossary
description: >-
  Curate and apply Spec Kitty glossary terminology, aliases, conflicts,
  semantic drift checks, and domain-model pressure-tests across missions.
  Triggers: "update the glossary", "use canonical terms", "check terminology",
  "add a term", "fix term drift", "glossary conflicts", "resolve ambiguity",
  "review terminology consistency", "shape a domain model's terms",
  "validate domain language against code".
  Does NOT handle: runtime loop advancement, setup or repair requests,
  agent configuration, or direct code implementation tasks.
---

# spk-charter-glossary

Maintain semantic integrity by curating the project glossary, detecting term
drift, and ensuring that all mission artifacts use canonical terminology.

Use this skill when the user asks about canonical terms, glossary updates,
terminology drift, or domain language consistency. Do not use it for purely
operational tasks like advancing the runtime loop or repairing an
installation.

## Flow

1. Locate active glossary context.
2. Check conflicts and strictness before changing anything.
3. Classify the change: new term, alias, conflict, drift, or usage correction.
4. When shaping a domain model or resolving a contested term, pressure-test the
   model before recording it: cross-check code evidence, challenge the term
   with a concrete edge case, and apply the ADR gate.
5. Update or apply terminology without rewriting unrelated docs.
6. Feed domain language back into spec, plan, and documentation skills.

## References

- `references/glossary-workflow.md` -- The glossary runtime (scopes,
  middleware pipeline, events), and the detailed steps for locating context,
  resolving conflicts, pressure-testing terms, and preventing drift.
- `references/glossary-field-guide.md` -- Seed file schema, scope precedence,
  status lifecycle, event-sourcing mechanics, and CLI quick reference.
- `references/semantic-drift-examples.md` -- Concrete drift patterns with
  detection and correction strategies.
