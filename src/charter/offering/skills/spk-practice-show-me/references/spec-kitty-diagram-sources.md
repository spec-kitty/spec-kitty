# Spec Kitty diagram sources

Load only the on-demand artifact summary needed for the visual. Run one include
per command:

```bash
spec-kitty charter context --include toolguide:mermaid-diagramming
spec-kitty charter context --include toolguide:plantuml-diagramming
spec-kitty charter context --include directive:USE_C4_MODEL_TECHNIQUES
spec-kitty charter context --include tactic:architecture-diagram-review-checklist
```

An included artifact is canonical guidance, but inclusion alone does not
activate it as binding governance. First load the current action context:

```bash
spec-kitty charter context --action <action> --mission-type <type> --json
```

Treat guidance as binding only when that action context or the project charter
activates it. Otherwise use it as optional advice.

The toolguide summaries report canonical `guide_path` values. Project-installed
skills cannot assume those checkout-relative paths exist, so full byte-pinned
copies ship with this skill:

- `assets/MERMAID_DIAGRAMMING.md`
- `assets/PLANTUML_DIAGRAMMING.md`

In the Spec Kitty source repository, their authorities and templates are:

- `packs/built-in/toolguides/MERMAID_DIAGRAMMING.md`
- `packs/built-in/toolguides/PLANTUML_DIAGRAMMING.md`
- `src/charter/offering/templates/diagrams/`

Use this skill's portable `assets/mermaid-theme-common-template.md` or
`assets/mermaid-theme-bluegray-conversation-template.md` as optional visual
baselines. The bundled guides and themes mirror canonical Spec Kitty sources;
repository parity tests prevent silent drift.
