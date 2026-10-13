---
title: 'Tracer: tooling friction'
updated: 2026-10-13
type: explanation
mission: declaration-first-repo-root-resolution-01M4TB21
---

# Tooling-friction tracer

Friction notes captured during the run (feeds the next mission).

- Cloud checkout is shallow: local `git log --since=90.days` reports ~1 commit/file, so
  per-file churn must be read from the issue history rather than git locally. Not a
  blocker; noted so the next agent does not mistake it for a quiet file.
- `spec-kitty charter context --action specify` emits a `CharterCatalogMissWarning` for
  `toolguide:typescript-mutation-tools` (scope_filtered to java/python). Pre-existing,
  unrelated to this mission; ignored.
