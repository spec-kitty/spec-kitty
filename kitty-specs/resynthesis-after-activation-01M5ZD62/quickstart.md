# Quickstart: verify the fix

1. In a git repo: `spec-kitty init --ai claude --non-interactive`, `spec-kitty charter interview --defaults`, `spec-kitty charter generate`, then commit.
2. Author `.kittify/charter/generated/directives/001-project-intent-directive.directive.yaml` (`id: PROJECT_001`) and the tactics/styleguides synthesis names. Run `spec-kitty charter synthesize`; expect exit 0. Commit.
3. Run `spec-kitty charter activate directive 003-decision-documentation-requirement`. `activation.yaml` now lists `001-project-intent-directive`.
4. Run `spec-kitty charter synthesize` and expect exit 0. On base it exits 1 with `colliding_urn='directive:PROJECT_001'`.
5. Run `spec-kitty charter resynthesize --topic directive:PROJECT_001`; expect exit 0.
6. Run `spec-kitty charter context --action implement` and expect the project directive's rule text in the output.
7. `git diff -- .kittify/charter/activation.yaml` shows no change from steps 4–5.
