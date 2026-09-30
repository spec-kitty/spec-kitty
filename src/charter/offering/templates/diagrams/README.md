# Diagram Templates

Diagram-as-code templates for Mermaid and PlantUML, aligned with Spec Kitty
documentation conventions.

## Structure

```
diagrams/
  mermaid/
    themes/        Mermaid theme snippets (copy-paste init blocks)
    examples/      Mermaid diagram templates by modeling intent
  plantuml/
    themes/        PlantUML theme documentation templates
    examples/      PlantUML diagram templates by modeling intent
```

## Mermaid Templates

Mermaid is the default for diagrams embedded in Markdown. See
[mermaid/README.md](mermaid/README.md) for the full listing.

### Theme Snippets

- [mermaid-theme-common-template.md](mermaid/themes/mermaid-theme-common-template.md) -- Neutral baseline for architecture and ADR diagrams.
- [mermaid-theme-bluegray-conversation-template.md](mermaid/themes/mermaid-theme-bluegray-conversation-template.md) -- Interaction-heavy sequence diagrams.

### Example Templates

- [causal-map-mermaid-template.md](mermaid/examples/causal-map-mermaid-template.md) -- Cause-effect feedback loops.
- [content-map-mermaid-template.md](mermaid/examples/content-map-mermaid-template.md) -- Content inventory and governance.
- [frontend-architecture-mermaid-template.md](mermaid/examples/frontend-architecture-mermaid-template.md) -- Component-level front-end overview.
- [repo-content-graph-mermaid-template.md](mermaid/examples/repo-content-graph-mermaid-template.md) -- Artifacts-to-audiences mapping.
- [request-lifecycle-sequence-mermaid-template.md](mermaid/examples/request-lifecycle-sequence-mermaid-template.md) -- Request flow through system components.
- [structure-meta-model-mermaid-template.md](mermaid/examples/structure-meta-model-mermaid-template.md) -- Conceptual meta model.
- [system-map-mermaid-template.md](mermaid/examples/system-map-mermaid-template.md) -- High-level system context map.

## PlantUML Templates

PlantUML is used for standalone diagram files, workshop visuals, and diagrams
needing the stickies/causal DSL. See
[plantuml/README.md](plantuml/README.md) for the full listing.

### Theme Documentation

- [plantuml-theme-common-template.md](plantuml/themes/plantuml-theme-common-template.md) -- Minimal shared conventions.
- [plantuml-theme-bluegray-conversation-template.md](plantuml/themes/plantuml-theme-bluegray-conversation-template.md) -- Blue-gray conversation theme.
- [plantuml-theme-stickies-template.md](plantuml/themes/plantuml-theme-stickies-template.md) -- Sticky note workshop theme with causal macros.

### Example Templates

- [causal-map-plantuml-template.md](plantuml/examples/causal-map-plantuml-template.md) -- Cause-effect relationships with sticky macros.
- [content-map-plantuml-template.md](plantuml/examples/content-map-plantuml-template.md) -- Content inventory and dependencies.
- [frontend-architecture-plantuml-template.md](plantuml/examples/frontend-architecture-plantuml-template.md) -- Component-level front-end overview.
- [repo-content-graph-plantuml-template.md](plantuml/examples/repo-content-graph-plantuml-template.md) -- Artifacts-to-audiences mapping.
- [request-lifecycle-plantuml-template.md](plantuml/examples/request-lifecycle-plantuml-template.md) -- Request flow sequence diagram.
- [structure-meta-model-plantuml-template.md](plantuml/examples/structure-meta-model-plantuml-template.md) -- C4-based conceptual meta model.
- [system-map-plantuml-template.md](plantuml/examples/system-map-plantuml-template.md) -- High-level system context map with stickies.
- [event-storming-plantuml-template.md](plantuml/examples/event-storming-plantuml-template.md) -- DDD event storming board.

## C4 and 2.x Cross-Reference

| Diagram Template | C4 Template Alignment | 2.x Architecture Alignment |
|---|---|---|
| System Map | [C4 Context](../architecture/c4-context-mermaid-template.md) | [`docs/architecture/diagrams/01_context/README.md`](../../../../../docs/architecture/diagrams/01_context/README.md) |
| Frontend Architecture | [C4 Containers](../architecture/c4-container-mermaid-template.md), [C4 Components](../architecture/c4-component-mermaid-template.md) | [`docs/architecture/diagrams/02_containers/README.md`](../../../../../docs/architecture/diagrams/02_containers/README.md), [`docs/architecture/diagrams/03_components/README.md`](../../../../../docs/architecture/diagrams/03_components/README.md) |
| Request Lifecycle | [C4 Components](../architecture/c4-component-mermaid-template.md) | [`docs/architecture/diagrams/02_containers/runtime-execution-domain.md`](../../../../../docs/architecture/diagrams/02_containers/runtime-execution-domain.md) |
| Structure Meta Model | [C4 Context](../architecture/c4-context-mermaid-template.md) | [`docs/architecture/diagrams/01_context/README.md`](../../../../../docs/architecture/diagrams/01_context/README.md) |
| Causal Map | [C4 Context](../architecture/c4-context-mermaid-template.md) | [`docs/architecture/diagrams/01_context/README.md`](../../../../../docs/architecture/diagrams/01_context/README.md) |
| Content Map | [C4 Context](../architecture/c4-context-mermaid-template.md) | [`docs/architecture/README.md`](../../../../docs/architecture/README.md) |
| Repo Content Graph | [C4 Context](../architecture/c4-context-mermaid-template.md) | [`docs/architecture/README.md`](../../../../docs/architecture/README.md) |

## Choosing Between Mermaid and PlantUML

| Criterion | Mermaid | PlantUML |
|---|---|---|
| Inline Markdown rendering | Native (GitHub, GitLab, VS Code) | Requires proxy or pre-rendering |
| Dependencies | None (browser-based) | Java, Graphviz |
| Theme includes | Copy-paste init blocks | `!include` file system |
| Workshop macros (stickies, causal) | Not available | Full DSL via stickies theme |
| Layout control | Limited | More configurable |
| C4 support | Experimental | Mature (plantuml-stdlib) |

## Toolguides

For full tool usage guidance, see:

- [PlantUML Diagramming Toolguide](../../../../packs/built-in/toolguides/PLANTUML_DIAGRAMMING.md)
- [Mermaid Diagramming Toolguide](../../../../packs/built-in/toolguides/MERMAID_DIAGRAMMING.md)

## Notes

1. Mermaid does not support PlantUML-style include files in markdown contexts.
   Theme files in `mermaid/themes/` are copy-paste snippets.
2. Keep architecture docs Mermaid-first. PlantUML references are input lineage
   only.
3. PlantUML themes in `plantuml/themes/` are documentation templates. The
   actual `.puml` theme source files live in the reference repositories and
   should be included via relative paths when rendering.
