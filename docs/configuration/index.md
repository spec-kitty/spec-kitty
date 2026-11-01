---
title: Configuration
description: 'Durable configuration and toolchain references for Spec Kitty: library choices and CI linting policy.'
doc_status: active
updated: '2026-06-27'
related:
- configuration/linting-cutoff-policy
- configuration/pack-yaml
- configuration/yaml-libraries
- guides
- ''
- operations
- plans
---
# Configuration

Durable settings, toolchain, and policy references — pages that document *how
the project is configured* and stay correct across missions. Effort-scoped
tuning notes live under [`../plans/`](../plans/index.md).

## Pages

- [Review test execution budget](review-test-budget.md) — one bounded budget for baseline and candidate tests.

- [YAML library choice: ruamel.yaml vs PyYAML](yaml-libraries.md) — toolchain decision and rationale.
- [Linting cutoff policy](linting-cutoff-policy.md) — commitlint / markdownlint informational-mode policy and cutoff date.
- [`pack.yaml` reference](pack-yaml.md) — Charter Pack descriptor fields, `pack_level` and `requires_core`.

## See also

- [Documentation home](../index.md)
- [Operations](../operations/index.md)
- [Guides](../guides/index.md)
