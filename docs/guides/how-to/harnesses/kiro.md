---
title: Use Spec Kitty in Kiro
description: 'How to use Spec Kitty in Kiro (partial tier): a bootstrap-only surface in 3.2, to be promoted once the full /spec-kitty.* command set is verified end-to-end.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Kiro

> **Tier:** **partial** — bootstrap-only surface in 3.2. Promote to `supported` once the full `/spec-kitty.*` set is verified end-to-end.
> **Citation (accessed 2026-06-03):** <https://kiro.dev/docs>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai kiro
  ```
- **Kiro installed and configured.** Follow the [Kiro documentation](https://kiro.dev/docs) for installation and authentication.

## Partial-tier note

Kiro is the rebrand-target of Amazon Q. In 3.2 the Spec Kitty installer ships a **bootstrap-only** surface for Kiro — the directory layout is in place, but the full `/spec-kitty.*` command set is not yet integration-tested end-to-end against this harness. Expect feature parity with Amazon Q at the prompt-file level; verify each command before relying on it for production missions.

The promotion criteria (`partial → supported`) are maintained in `docs/development/3-2-harness-research-method.md` §6.

## Plugin-install classification

Kiro is **prompt-only** for Spec Kitty 3.3 plugin-install planning. Current
public Kiro docs describe steering files, hooks, MCP configuration, and prompt
surfaces, but do not document a plugin or Powers bundle primitive that Spec
Kitty can install as a packaged command-skill equivalent.

Spec Kitty therefore keeps Kiro out of #1635 plugin-install scope until an
upstream package primitive is documented and smoke-tested. Continue using the
`.kiro/prompts/` surface for bootstrap coverage.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Kiro uses the prompt-file mechanism. Spec Kitty installs:

- **Directory:** `.kiro/prompts/`
- **Files:** the `spec-kitty.*` prompt set (specify, plan, tasks, implement, review, accept, merge, status, charter, analyze, research).

## Canonical invocation

Inside Kiro, prompts are invoked via the host's prompt-discovery convention. The current best guess (mirroring Amazon Q) is:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

If Kiro's current syntax differs, consult the host docs at <https://kiro.dev/docs> for the canonical prompt invocation.

## Worked example

1. From your project root, launch Kiro.
2. At the prompt, attempt:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. If the prompt is recognized, Spec Kitty's interview prompts appear — answer them inline and pick a kebab-case slug.
4. If it is not recognized, fall back to running Spec Kitty from another configured harness (Claude Code, OpenCode, Cursor, etc.) — the on-disk artifacts under `kitty-specs/` are harness-agnostic.

## Troubleshooting

- **`/spec-kitty.*` prompts do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.kiro/prompts/` from the canonical source templates. Restart Kiro.

- **Profile not loading.**
  Run inside Kiro:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Kiro

Authoritative documentation: <https://kiro.dev/docs> (accessed 2026-06-03).
