# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi/deepseek-v4.1 · spec-kitty validate-encoding --mission <freshly created mission> already reports two Needs Fix files before any authoring: spec.md (6x U+2014) and tasks/README.md (U+2013). Recorded as the live red-first repro; the tasks/README.md half is fixable in core, the spec.md half is not. Also hit a shared-machine race: tracer-append failed with 'Global asset input changed: ~/.kittify/cache/agent-commands-freshness.lock', which the brief documents as an unsafe-to-race global cache.
