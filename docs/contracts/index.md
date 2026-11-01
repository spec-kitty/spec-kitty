---
title: Contracts
description: 'Contract-ownership boundary registry for Spec Kitty: the seeded contract manifest and its validation schema, checked by the doctor contracts gate.'
doc_status: active
updated: '2026-08-14'
related:
- api/cli-commands
- ''
- contracts/handoff-packet-v1
---
# Contracts

This section holds the **Contract Registry** for the contract-ownership
boundary (#2441): the single, canonical manifest of ownership contracts that
Spec Kitty enforces, plus the schema that validates it.

It also holds the **handoff packet** payload contract that external
requirements tools use to seed `/spec-kitty.specify` without losing
requirement identity:

- `handoff-packet-v1.md` — optional YAML-frontmatter overlay on a Markdown
  brief. Frontmatter is additive; unknown versions degrade to prose intake.
  Parser: `src/specify_cli/intake/packet.py`.

## Files

- `contract-registry.yaml` — the seeded contract manifest. Each record declares
  a contract's kind, status, enforcement level, owning boundary, semver, and
  tracker references, along with the anchors that pin it to the code or docs it
  governs.
- `contract-registry-schema.yaml` — the schema every registry record is
  validated against: required fields, allowed `kind`/`status`/`enforcement`
  ranges, well-formed semver and tracker references, resolvable anchors, and the
  DIR-041 self-consistency rule that forbids positional `file:line` anchoring.
- `handoff-packet-v1.md` — optional YAML-frontmatter overlay that lets an
  upstream requirements tool seed `/spec-kitty.specify` without losing FR/AC
  identity. Unknown versions degrade to prose intake.

## Validation

The registry is validated by the CLI gate:

```
spec-kitty doctor contracts
```

Structural validation is the only enforcing gate in v1 — a malformed record or a
positional `file:line` anchor exits non-zero. The retirement absence-sweep is
advisory. See `spec-kitty doctor contracts --help` (documented in
`docs/api/cli-commands.md`) for exit codes and options.
