# Contextive Toolguide

## What is Contextive?

Contextive is a language server and IDE extension suite that surfaces
ubiquitous language definitions directly in the developer workflow. By
maintaining a YAML glossary file in the repository, Contextive provides:

- **Hover definitions** -- hover over a term in code, comments, config, or
  markdown to see its definition and usage examples
- **Auto-complete** -- glossary terms appear in auto-complete suggestions in
  any file type, with smart casing (camelCase, PascalCase, snake_case,
  UPPER_CASE)
- **Compound word recognition** -- terms are detected inside compound
  identifiers (e.g. `PolicyEntity`, `cargo_id`, `LegMagnitudePolicy`)
- **Plural/singular detection** -- a term defined as `Policy` is recognised
  when used as `Policies`
- **Multi-context support** -- separate glossary files per bounded context,
  with cross-context term disambiguation

## Installation

Contextive supports multiple IDEs via the Language Server Protocol:

| IDE | Installation |
|---|---|
| **VS Code** | Install `contextive` from the VS Code marketplace |
| **IntelliJ IDEs** | Install from the JetBrains plugin marketplace |
| **Visual Studio 2022** | Install from the Visual Studio marketplace |
| **Neovim** | Configure via LSP client (see Contextive docs) |
| **Helix** | Configure via LSP settings (see Contextive docs) |

Full installation instructions: https://docs.contextive.tech/community/guides/installation/

## Glossary File Setup

### Single-context repository

Place the glossary at `.contextive/definitions.yml` in the repository root:

```yaml
contexts:
  - name: MyContext
    domainVisionStatement: >
      One to three sentences describing the context's purpose.
    terms:
      - name: Cargo
        definition: >
          A unit of transportation that needs moving and delivery
          to its delivery location.
        examples:
          - "Multiple customers are involved with a cargo."
        aliases:
          - unit
        meta:
          "Status:": "Canonical"
```

### Multi-context repository (monorepo)

Use one glossary file per module/context:

```
repo-root/
  billing-module/
    billing.glossary.yml
  shipping-module/
    shipping.glossary.yml
  .contextive/
    definitions.yml          # shared / cross-cutting terms
```

Each file follows the same `contexts:` structure. Contextive will detect
which context applies based on file path.

## Term Definition Syntax

### Required fields

Only `name` is strictly required:

```yaml
- name: Policy
```

This creates a placeholder that prompts you to add a definition.

### Recommended fields

```yaml
- name: Policy
  definition: >
    A set of actuarial rules applied to premium calculation
    based on risk factors and customer history.
  examples:
    - "The policy determines the base rate for this risk class."
    - "We need to configure the set of policies for this customer."
  aliases:
    - rule
  meta:
    "Status:": "Canonical"
```

### Multi-word terms

Define compound terms in natural language. Contextive will match them in
any casing convention:

```yaml
- name: Leg Magnitude Policy
  definition: >
    A policy that helps the routing engine select the legs
    with the lowest magnitude.
```

This matches `LegMagnitudePolicy`, `legMagnitudePolicy`,
`leg_magnitude_policy`, and `leg-magnitude-policy` in code.

### Aliases

Use aliases for acronyms or alternative names:

```yaml
- name: Anti-Corruption Layer
  aliases:
    - ACL
```

Hovering over `ACL` in code will show the full definition.

### Metadata

Add arbitrary key-value metadata displayed in hover panels:

```yaml
meta:
  "Owner:": "[Team A](https://wiki/teams/TeamA)"
  "Ref:": "[Glossary Wiki](https://wiki/glossary/policy)"
  "Status:": "Canonical"
```

Keys and values support markdown and emoji.

## Integration with Spec Kitty Workflows

### Glossary curation

The [glossary-curation-interview](../tactics/communication/glossary-curation-interview.tactic.yaml)
tactic defines the process for systematically expanding a living glossary.
Terms curated through that process should be captured in Contextive format
so they are immediately enforceable in the IDE.

### Bounded Context Canvas

Section 7 (Ubiquitous Language) of the
[Bounded Context Canvas](../../../src/charter/offering/templates/architecture/bounded-context-canvas-template.md)
should be backed by a Contextive glossary file. This ensures the canvas
is not just documentation but an active, enforceable artifact.

### Glossary writing styleguide

Follow the [kitty-glossary-writing](../styleguides/writing/kitty-glossary-writing.styleguide.yaml)
styleguide when authoring definitions. Key rules:

- Definitions must be self-contained (no undefined foundational terms)
- Use domain language, not implementation language
- Include at least one usage example per term

### Term lifecycle

| Status | Meaning |
|---|---|
| **Candidate** | Proposed during curation; awaiting HiC approval |
| **Canonical** | Approved; enforced in code and documentation |
| **Deprecated** | Superseded; retained with deprecation notice |

Track status via the `meta` field:

```yaml
meta:
  "Status:": "Deprecated - replaced by 'Premium Calculation Rule'"
```

## Multiline YAML Tips

Contextive renders definitions as markdown. Use YAML block scalars for
longer definitions:

```yaml
# Literal block (|) preserves newlines
definition: |
  First paragraph of the definition.

  Second paragraph with more detail.

# Folded block (>) joins lines (use for flowing prose)
definition: >
  A single paragraph that is easier to read in the YAML source
  because it wraps across multiple lines.
```

For line breaks within a paragraph (not new paragraphs), end the line
with two spaces before the newline.

## References

- Contextive repository: https://github.com/dev-cycles/contextive
- Documentation: https://docs.contextive.tech/community
- Defining terminology: https://docs.contextive.tech/community/guides/defining-terminology/
- Setting up glossaries: https://docs.contextive.tech/community/guides/setting-up-glossaries/
- Spec Kitty glossary skill: see `spk-charter-glossary` skill
