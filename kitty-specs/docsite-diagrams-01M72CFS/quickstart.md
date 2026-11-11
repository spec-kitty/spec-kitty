# Quickstart: Docsite diagrams

## Local build

`make docs-site` needs a PlantUML server running on `localhost:8091`. Start one with the same digest, hardened (the command is in `research/code-grounding.md` §1). The target fails with that command when the server is unreachable.

## In CI

The shared `docs-site-build.yml` job runs these steps in order:

1. Start the `plantuml` service container and wait until it is ready.
2. Install Chromium.
3. Run the canary check.
4. Build the site.
5. Run the built-site check, which now includes the `diagrams` surface.
