---
title: How-to (contributor & maintainer tasks)
description: Task-oriented runbooks for contributors and maintainers — landing PRs, review gates, overrides, the issue tracker, contract pinning, and authoring doctrine and pack skills.
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/index.md
- docs/development/getting-started/index.md
- docs/development/reference/index.md
---
# How-to (contributor & maintainer tasks)

Step-by-step runbooks for the recurring tasks of contributing to and maintaining
Spec Kitty. Each page is scoped to one job you can pick up and finish.

- [Landing contributor PRs](pr-landing.md) — the claim → isolate → rebase → classify → fold → squad → hand-off maintainer runbook.
- [Review gates: pre-PR / pre-review checklist](review-gates.md) — the hygiene steps to run locally before requesting review.
- [Local overrides for cross-package development](local-overrides.md) — dev-only editable installs across `spec-kitty-cli`/`-events`/`-tracker` that must never be committed.
- [Managing the issue tracker](manage-issue-tracker.md) — epics vs. meta-trackers, native sub-issue parenting, and triage conventions.
- [Contract pinning workflow](contract-pinning.md) — pinning the `spec-kitty-events` envelope contract in tests.
- [Cut-over guard: fail-closed pre-merge gate](cutover-guard.md) — what `spec-kitty cutover-guard` checks, how it is wired into CI, and how to register it as a required status check.
- [Create a doctrine artifact](create-a-doctrine-artifact.md) — author a new doctrine artifact end to end, including the loose-contract asset kind.
- [Create and activate a pack skill](create-a-pack-skill.md) — author a shared `skill`, set its namespace, activate it into each configured tool, and check it with `doctor skills`.
- [Add an exemption to an architectural gate](add-architectural-gate-exemption.md) — exempt a site by content (descriptor or `CensusKey`), never by line number.
- [Compress mission history](compress-mission-history.md) — the path-bucket recipe for compressing a noisy mission branch into a clean, reviewable history (not a default landing step).

## See also

- [Development home](../index.md)
- [Contributing to Spec Kitty](../contributing.md)
