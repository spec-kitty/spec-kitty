# Approach: pack-shipped-builtin-override-sanction-01M45WB7

Initial approach (plan.md): `doctor doctrine` reads a pack-root `replaceable-builtins.yaml` in place, scoped to the contributing pack and unioned with the consumer allowlist, through one loader in `override_policy`. The concerns run tidy-first: a parser seam first, then the effective policy, then doctor wiring, then pack validate/assemble, then docs.

- 2026-10-05: The post-specify squad moved the pack-root source from a second registry resolution to the already-loaded fragments. It also added contained reads, per-pack isolation and a decision table.
- 2026-10-05: The post-tasks squad (renata + daphne) changed four things:
  - The old adjudication predicates are retired instead of kept, because the dead-symbol gate checks every public name and keeping them would create a second authority.
  - The doc/gate parity test moved to a new WP02-owned file and became behavioural.
  - The gate merges with `project=None`.
  - The assembler detects sanction conflicts before writing.
