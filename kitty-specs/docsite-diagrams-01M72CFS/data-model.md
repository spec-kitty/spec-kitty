# Data model: Docsite diagrams

| Element | Source of truth | Consumers |
|---|---|---|
| PlantUML image digest | `docs-site-build.yml` `services.plantuml.image` | CI job; Makefile helper (equality pinned if duplicated) |
| Render mode | job `env:` / Makefile (`DK_DIAGRAM_BUILD_RENDER=build`) | doc-kitty build |
| Server URL | job `env:` / Makefile (`DK_PLANTUML_SERVER_URL`) | doc-kitty build, canary |
| Published diagram blocks | `docs/**` source + `_dockitty_contract` published set | diagram surface (expected count) |
| Rendered figures | `site/dist/**/index.html` | diagram surface (actual count) |
