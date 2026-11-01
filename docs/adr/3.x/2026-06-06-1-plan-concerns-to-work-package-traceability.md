---
title: 'ADR: Plan Concerns To Work Package Traceability'
description: 'Plans carry `IC-##` Implementation Concerns, and `wps.yaml` alone records the many-to-many concern-to-work-package mapping — never work-package prompt frontmatter.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-06'
---

## Context

The software-development planning flow used to describe plan-level slices with
work-package-shaped language such as "Parallel Work Analysis", "Work
Distribution", and "Agent assignments". That made plan sections look
executable, even though implementation and review machinery only operates on
`WP##` work packages generated later by `/spec-kitty.tasks`.

The result was a vocabulary gap. A reviewer could see architectural intent in
`plan.md` and executable WPs in `tasks.md`, but there was no durable,
machine-readable link explaining how the task workflow translated one into the
other.

## Decision

1. `plan.md` uses an **Implementation Concern Map** for plan-level units of
   intent. Concern IDs use the `IC-##` shape.

2. Implementation concerns are not executable units. They capture purpose,
   relevant requirements, affected surfaces, sequencing, and risks. The tasks
   workflow translates them into executable `WP##` work packages.

3. `wps.yaml` is the only machine-readable place that records concern-to-WP
   traceability. Each work package may list `plan_concern_refs`, and each value
   must match `IC-##`.

4. The mapping is many-to-many. One concern may produce several WPs, and one WP
   may cover several concerns.

5. Cross-cutting infrastructure WPs may use `cross_cutting: true` instead of
   concern refs. This is an advisory marker used to avoid false-positive
   coverage warnings.

6. WP prompt frontmatter must not include `plan_concern_refs`. WP prompt
   frontmatter is parsed by `WPMetadata` with unknown fields forbidden; concern
   traceability belongs in `wps.yaml`.

7. Legacy manifests without `plan_concern_refs` or `cross_cutting` remain quiet.
   They must parse and finalize without new warning noise. Once a manifest opts
   into concern traceability by using either new field, `finalize-tasks` warns
   for any WP missing both.

## Consequences

- Reviewers can trace plan intent to executable work by reading generated
  `tasks.md` and the source `wps.yaml`.
- The plan phase no longer creates pseudo-WP vocabulary that competes with the
  real WP lifecycle.
- Existing missions keep backward-compatible finalization behavior.
- The warning check is advisory. It guides newly authored manifests but does
  not block historical missions or strict migration windows.

## Rejected Alternatives

1. **Put `plan_concern_refs` in WP prompt frontmatter.** This was rejected
   because WP prompt frontmatter is a different schema with `extra="forbid"`.
   Adding concern refs there would make `finalize-tasks --validate-only` reject
   agent-generated WP files.

2. **Require a one-to-one concern-to-WP mapping.** This was rejected because
   architectural concerns and executable work units have different granularity.
   Large concerns often need several WPs, while small concerns may safely merge
   into one implementation WP.

3. **Warn on every legacy manifest missing concern refs.** This was rejected
   because it violates backward compatibility. The new warning only applies
   after a manifest opts into concern traceability.

## References

- Issue: [#1730](https://github.com/Priivacy-ai/spec-kitty/issues/1730)
- User guide: [`docs/guides/use-wps-yaml-manifest.md`](../../guides/how-to/missions/use-wps-yaml-manifest.md)
- Plan guide: [`docs/guides/create-plan.md`](../../guides/how-to/missions/create-plan.md)
- Task guide: [`docs/guides/generate-tasks.md`](../../guides/how-to/missions/generate-tasks.md)
- Manifest model: [`src/specify_cli/core/wps_manifest.py`](../../../src/specify_cli/core/wps_manifest.py)
