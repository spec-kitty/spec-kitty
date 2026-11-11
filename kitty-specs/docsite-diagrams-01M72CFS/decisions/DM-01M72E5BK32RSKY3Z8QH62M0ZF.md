# Decision Moment `01M72E5BK32RSKY3Z8QH62M0ZF`

- **Mission:** `docsite-diagrams-01M72CFS`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.startyaml`
- **Input key:** `startyaml_handling`
- **Status:** `resolved`
- **Created:** `2026-11-10T09:55:52.547447+00:00`
- **Resolved:** `2026-11-10T12:11:11.361672+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

If CI confirms doc-kitty v0.7.0 cannot render @startyaml, how are the 5 @startyaml blocks handled: upstream fix then pin bump, convert the blocks, or ship without them for now?

## Options

- upstream fix then pin bump
- convert the 5 blocks
- ship without them for now

## Final answer

Operator rule 2026-11-10: verify @startyaml is valid PlantUML; if valid it is an upstream bug, else rewrite as @startjson. Verified: all 5 blocks render to error-free SVGs with the pinned PlantUML 1.2025.4 jar (sha256-checked), AND through doc-kitty v0.7.0's exact transform (injectSkinparam preamble + astro-plantuml @startuml/@enduml wrap), byte-identical output. No blocker, no rewrite, no upstream bug. Cosmetic: the skinparam theme does not reach @startyaml diagrams (default colours); low-priority upstream suggestion.

## Rationale

_(none)_

## Change log

- `2026-11-10T09:55:52.547447+00:00` - opened
- `2026-11-10T12:11:11.361672+00:00` - resolved (final_answer="Operator rule 2026-11-10: verify @startyaml is valid PlantUML; if valid it is an upstream bug, else rewrite as @startjson. Verified: all 5 blocks render to error-free SVGs with the pinned PlantUML 1.2025.4 jar (sha256-checked), AND through doc-kitty v0.7.0's exact transform (injectSkinparam preamble + astro-plantuml @startuml/@enduml wrap), byte-identical output. No blocker, no rewrite, no upstream bug. Cosmetic: the skinparam theme does not reach @startyaml diagrams (default colours); low-priority upstream suggestion.")
