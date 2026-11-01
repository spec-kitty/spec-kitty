---
title: Review Spec Kitty Artifacts with PlanBridge
description: 'How to review spec kitty artifacts with planbridge with Spec Kitty 3.2: Review Spec Kitty Artifacts with PlanBridge.'
doc_status: active
updated: '2026-06-03T00:00:00Z'
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/missions/create-plan.md
- docs/guides/how-to/missions/create-specification.md
- docs/guides/how-to/missions/generate-tasks.md
- docs/guides/how-to/missions/review-work-package.md
kind: How-To
---
# Review Spec Kitty Artifacts with PlanBridge

Use this guide when you want inline browser comments on the `spec.md`, `plan.md`, and `tasks.md` files that Spec Kitty creates before implementation begins.

## Overview

[PlanBridge](https://plan.contextbridge.ai/) opens agent plans or local markdown files in a local browser review UI. You highlight text, add comments, approve or request changes, and the feedback returns to your coding harness so the agent can revise the artifact.

Spec Kitty writes planning artifacts under `kitty-specs/<feature>/`:

- `kitty-specs/<feature>/spec.md` after `/spec-kitty.specify`
- `kitty-specs/<feature>/plan.md` after `/spec-kitty.plan`
- `kitty-specs/<feature>/tasks.md` after `/spec-kitty.tasks`

Spec Kitty already has `/spec-kitty.review` for completed code. PlanBridge complements that upstream by reviewing the spec, plan, and task markdown before code is written.

## Install

Install PlanBridge from [plan.contextbridge.ai](https://plan.contextbridge.ai/install/) or from the [contextbridge/planbridge GitHub repository](https://github.com/contextbridge/planbridge).

The shortest install path is:

```bash
/bin/sh -c "$(curl -fsSL https://downloads.contextbridge.ai/cli/install.sh)"
```

For a manual install with Homebrew:

```bash
brew install contextbridge/tap/cli
contextbridge install
```

Verify the install:

```bash
contextbridge --version
contextbridge install status
```

Codex CLI users may need to trust newly installed hooks before PlanBridge can open inside Codex. Follow the PlanBridge Codex setup notes after `contextbridge install`.

## Manual

After `/spec-kitty.specify`, open the generated spec for review.

Claude Code:

```text
/planbridge-open the spec you just wrote
```

Codex CLI:

```text
$planbridge-open the spec you just wrote
```

The agent resolves the path under `kitty-specs/<feature>/`, sends the markdown to PlanBridge, and revises from your inline comments.

Do the same after `/spec-kitty.plan` and `/spec-kitty.tasks`.

Claude Code:

```text
/planbridge-open kitty-specs/my-feature/plan.md
/planbridge-open kitty-specs/my-feature/tasks.md
```

Codex CLI:

```text
$planbridge-open kitty-specs/my-feature/plan.md
$planbridge-open kitty-specs/my-feature/tasks.md
```

## Automatic

To review each artifact without asking, append a snippet to your global agent instructions.

Claude Code:

```bash
cat <<'EOF' >> ~/.claude/CLAUDE.md

## Spec Kitty + PlanBridge
When `/spec-kitty.specify`, `/spec-kitty.plan`, or `/spec-kitty.tasks` creates a file in `kitty-specs/<feature>/`, open that file with `/planbridge-open`. Use the returned annotations as review feedback, revise the artifact, and only then continue to the next Spec Kitty phase.

EOF
```

Codex CLI:

```bash
cat <<'EOF' >> ~/.codex/AGENTS.md

## Spec Kitty + PlanBridge
When `/spec-kitty.specify`, `/spec-kitty.plan`, or `/spec-kitty.tasks` creates a file in `kitty-specs/<feature>/`, open that file with `$planbridge-open`. Use the returned annotations as review feedback, revise the artifact, and only then continue to the next Spec Kitty phase.

EOF
```

## See Also

- [Create a Specification](create-specification.md)
- [Create a Plan](create-plan.md)
- [Generate Tasks](generate-tasks.md)
- [Review Work Packages](review-work-package.md)
- [PlanBridge Spec Kitty recipe](https://plan.contextbridge.ai/recipes/spec-kitty/)
