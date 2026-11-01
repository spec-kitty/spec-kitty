---
title: Roo Cline (deprecated)
description: Roo Code shut down on 2026-05-15 and is no longer a supported Spec Kitty harness.
doc_status: active
updated: '2026-06-15'
type: how-to
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
---
# Roo Cline (deprecated)

> **Roo Code shut down on 2026-05-15 and is no longer supported.**

`spec-kitty init --ai roo` is rejected — Roo Cline can no longer be targeted as a
new harness. This page is retained only so existing links keep resolving.

## Existing projects with a `.roo/` directory

Projects that already contain a `.roo/` directory will receive a deprecation
notice during `spec-kitty upgrade`. The `.roo/` directory is **preserved** and is
not deleted automatically. To remove Roo from your project configuration, run:

```bash
spec-kitty agent config remove roo
```

## See also

- [Supported AI Agents](../../../api/supported-agents.md) — the authoritative
  list of currently supported harnesses, including the Roo Code deprecation notice.
