---
title: Status & History
description: "Check mission progress from the CLI and review your git operation history."
doc_status: active
updated: '2026-10-01'
type: explanation
---

# Status & History

Check mission progress from the CLI and review your git operation history.

To see where every work package stands, run `spec-kitty agent tasks status` (add `--json` for machine-readable output).
External tools can use `spec-kitty orchestrator-api mission-state`, which prints JSON by default. The bundled local web dashboard has been removed; a read-only Mission Status Read API ([#5528](https://github.com/spec-kitty/spec-kitty/issues/5528)) is planned, with a replacement UI to live in its own repository.

- [Use Operation History](use-operation-history.md) — How to use operation history with Spec Kitty 3.2: The spec-kitty ops command group provides read-only access to your git operation history via git reflog.
