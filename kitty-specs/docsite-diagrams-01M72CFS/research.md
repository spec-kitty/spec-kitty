# Research: Docsite diagrams

Grounding: [research/code-grounding.md](research/code-grounding.md).

## R-1: @startyaml
- **Decision:** keep the 5 `@startyaml` blocks as they are.
- **Evidence (2026-11-10):** the pinned PlantUML 1.2025.4 jar (sha256 `26518e14…`) renders all 5 to error-free SVGs. So does doc-kitty v0.7.0's exact transform (`injectSkinparam` preamble, then astro-plantuml's `@startuml`/`@enduml` wrap): the output is byte-identical to the plain render.
- **Cosmetic gap:** the theme preamble does not reach `@startyaml`, so those diagrams render in default colours. This is a low-priority upstream suggestion.
- **Operator rule:** if a block were invalid, it would be rewritten as `@startjson`. That rule does not apply.

## R-2: Service container on GitHub runners
- **Decision:** follow doc-kitty's own CI (`5acb83c:.github/workflows/ci.yml:258-264`).
  - `--service-container "${{ job.services.plantuml.id }}"`.
  - `--canary-host` comes from the service network gateway, read with `docker inspect`.
- doc-kitty #287 (non-container services) is not needed.

## R-3: Image
- `plantuml/plantuml-server:jetty-v1.2026.9@sha256:065c66adc6728ba6dd353a29d4ada73f8358b68549a0f710c4bf46b43c103618` (doc-kitty `docs/guides/consumer-setup.md:1159`, operator decision).
- Security profile `SANDBOX`. No external includes (ruling of 2026-11-01).

## R-4: Render mode
- `DK_DIAGRAM_BUILD_RENDER=build` and `DK_PLANTUML_SERVER_URL` are read only from the process environment.
- Build mode needs Playwright Chromium.
- `playwright` gets an exact pin in `site/`. `make docs-site-bump` does not track it, so this is noted in the PR.

## Supply chain
New inputs are the PlantUML server image, pinned by digest, and `playwright`, pinned exactly. No credentials are involved.
