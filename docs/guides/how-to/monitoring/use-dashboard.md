---
title: The Bundled Dashboard Was Removed
description: The spec-kitty dashboard command and its local web UI were removed in 4.0.0rc5; check mission status from the CLI instead.
doc_status: deprecated
updated: '2026-10-01'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/monitoring/index.md
---
# The Bundled Dashboard Was Removed

The `spec-kitty dashboard` command, the `/spec-kitty.dashboard` slash command and the local web dashboard were removed in 4.0.0rc5 ([#5530](https://github.com/spec-kitty/spec-kitty/issues/5530)). `spec-kitty upgrade` removes the leftover command files and stops a dashboard server that is still running.

To see where every work package stands, run:

```bash
spec-kitty agent tasks status --mission <handle>
```

Add `--json` for machine-readable output.
External tools can use `spec-kitty orchestrator-api mission-state`, which prints JSON by default. A read-only Mission Status Read API ([#5528](https://github.com/spec-kitty/spec-kitty/issues/5528)) is planned, with a replacement UI in its own repository.

See [Status & History](index.md) for the other monitoring guides.
