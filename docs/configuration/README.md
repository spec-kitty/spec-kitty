---
title: Configuration
description: 'Durable configuration and toolchain references for Spec Kitty: library choices and CI linting policy.'
doc_status: active
updated: '2026-06-27'
related:
- docs/configuration/linting-cutoff-policy.md
- docs/configuration/pack-yaml.md
- docs/configuration/yaml-libraries.md
- docs/guides/README.md
- docs/README.md
- docs/operations/README.md
- docs/plans/README.md
---
# Configuration

Durable settings, toolchain, and policy references — pages that document *how
the project is configured* and stay correct across missions. Effort-scoped
tuning notes live under [`../plans/`](../plans/README.md).

## Pages

- [Review test execution budget](review-test-budget.md) — one bounded budget for baseline and candidate tests.

- [YAML library choice: ruamel.yaml vs PyYAML](yaml-libraries.md) — toolchain decision and rationale.
- [Linting cutoff policy](linting-cutoff-policy.md) — commitlint / markdownlint informational-mode policy and cutoff date.
- [`pack.yaml` reference](pack-yaml.md) — Charter Pack descriptor fields, `pack_level` and `requires_core`.

## See also

- [Documentation home](../README.md)
- [Operations](../operations/README.md)
- [Guides](../guides/README.md)
