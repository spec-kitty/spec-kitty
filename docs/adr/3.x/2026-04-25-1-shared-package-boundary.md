---
title: 'ADR: Shared Package Boundary Cutover'
description: 'Retires the standalone runtime package by internalizing the surface the CLI needs, with an import-graph test forbidding production imports of the retired package.'
status: Accepted
date: '2026-04-25'
updated: '2026-10-29'
---

## Context

The Spec Kitty product surface includes three Python packages:
`spec-kitty-cli`, `spec-kitty-events`, `spec-kitty-tracker`, plus the
retiring `spec-kitty-runtime`. Pre-cutover, the CLI consumed a hybrid
mix:

- vendored events code under `src/specify_cli/spec_kitty_events/` in the
  CLI's production paths (~23 kLoC);
- production imports of `spec_kitty_runtime` from CLI code, even though
  `pyproject.toml` did not list `spec-kitty-runtime` as a dependency;
- an editable `[tool.uv.sources]` entry pointing at a sibling
  `../spec-kitty-events` checkout, which masked the missing dependency in
  local development;
- a `constraints.txt` file that papered over the transitive
  `spec-kitty-events<4.0` pin in `spec-kitty-runtime` 0.4.x.

This state failed in two predictable ways. (1) Clean-install CI did not
exist, so a fresh `pip install spec-kitty-cli` would `ImportError` on
the first `spec-kitty next` invocation. (2) Cross-package releases had to
land in lockstep, because any contract change in events or tracker
required a coordinated CLI release.

[PR #779](https://github.com/Priivacy-ai/spec-kitty/pull/779) attempted a
partial cutover that moved runtime-shaped code into the CLI tree but kept
`spec_kitty_runtime` production imports alive. That PR was rejected
because the resulting hybrid state was structurally identical to the
pre-cutover state from a clean-install perspective and re-imposed
cross-package release lockstep.

## Decision

The mission `shared-package-boundary-cutover-01KQ22DS` lands the cutover
in 10 work packages. Concretely:

1. The CLI internalizes the runtime surface it needs from
   `spec-kitty-runtime` into
   `src/specify_cli/next/_internal_runtime/`. Production code paths
   import only from the internalized module. The standalone
   `spec-kitty-runtime` PyPI package is retired and is not a CLI
   dependency. (WP01, WP02)
2. The architectural test
   `tests/architectural/test_shared_package_boundary.py` enforces R1 / C-001:
   no production module under `src/` may import `spec_kitty_runtime`
   (top-level, sub-module, or lazy). The rule is enforced by `pytestarch`
   (import-graph) and an AST-walk fallback. (WP03)
3. CLI consumes events through the public PyPI package
   (`spec_kitty_events`); the vendored copy at
   `src/specify_cli/spec_kitty_events/` is deleted in its entirety.
   (WP04, WP05)
4. The wheel-shape and filesystem assertions in
   `tests/contract/test_packaging_no_vendored_events.py` lock the
   deletion: PRs that re-introduce the directory or ship vendored paths
   in the wheel fail CI. (WP06)
5. CLI consumes tracker through the public PyPI package
   (`spec_kitty_tracker`); CLI-internal `specify_cli.tracker.*`
   adapters do not re-export tracker public surface. Consumer-test
   contracts under
   `tests/contract/spec_kitty_events_consumer/` and
   `tests/contract/spec_kitty_tracker_consumer/` pin the subset of the
   public surfaces CLI uses; upstream contract changes break these tests
   explicitly. (WP07)
6. `pyproject.toml` lists events / tracker via compatibility ranges
   (`>=4.0.0,<5.0.0` and `>=0.4,<0.5` respectively); exact pins live
   only in `uv.lock`. (WP08)
7. `[tool.uv.sources]` does not contain editable / path entries for any
   shared package on the committed configuration path. Developer
   overrides live in dev-only configuration documented in
   [`docs/development/local-overrides.md`](../../development/how-to/local-overrides.md).
   (WP08)
8. `constraints.txt` is removed; its only purpose (papering over the
   `spec-kitty-runtime` transitive `spec-kitty-events<4.0` pin
   conflict) is gone. (WP08)
9. CI runs a `clean-install-verification` job that proves
   `spec-kitty next` works in a fresh venv after only
   `pip install spec-kitty-cli`. The job builds the wheel, creates a
   clean Python venv, installs the wheel, asserts
   `spec-kitty-runtime` is not installed, asserts `import specify_cli`
   does not pull `spec_kitty_runtime` into `sys.modules`, and runs
   `spec-kitty next --json` against a fixture mission. (WP09)
10. Operator-facing documentation (`CHANGELOG.md`, `README.md`,
    `CLAUDE.md`, `docs/development/*`, `docs/migration/*`,
    `docs/host-surface-parity.md`) is updated to describe the new
    boundary, and the closing PR formally supersedes PR #779. (WP10)

## Consequences

- Cross-package release lockstep is dissolved: events / tracker can ship
  within their compatibility windows without forcing a CLI release; the
  consumer-test contracts in WP07 catch breaking changes explicitly.
- Operators install only `spec-kitty-cli` from PyPI. The retired
  `spec-kitty-runtime` package is unused; existing installs can leave it
  installed (it is harmless) or remove it via `pip uninstall`.
- The CLI codebase grows by ~3 kLoC (the internalized runtime).
- The CLI codebase shrinks by ~23 kLoC (the deleted vendored events
  tree).
- Cross-package contract changes (events / tracker public surface) break
  the CLI's consumer-test suite explicitly, forcing CLI to react in a
  controlled PR rather than fail at runtime in a customer environment.
- The hybrid state (runtime-shaped code in the CLI tree alongside live
  `spec_kitty_runtime` production imports) is mechanically forbidden by
  the architectural and packaging tests.

## Alternatives considered

- **Re-publish `spec-kitty-runtime` as a stable library**: rejected. The
  runtime API is CLI-specific; it has no other consumers. Maintaining a
  standalone PyPI package added cross-package release coordination cost
  without delivering external value.
- **Keep events vendored**: rejected. Vendoring forks the contract;
  consumers see two events surfaces that may diverge. Worse, the
  vendored copy was already drifting from PyPI's
  `spec-kitty-events==4.0.0`.
- **Land the cutover in two PRs (runtime first, events second)**:
  rejected. Constraint C-007 of the mission spec explicitly forbids
  partial cutovers; PR #779 was the cautionary example.

## References

- Mission spec: `kitty-specs/shared-package-boundary-cutover-01KQ22DS/spec.md`
- Migration runbook: [`docs/migration/shared-package-boundary-cutover.md`](../../migrations/shared-package-boundary-cutover.md)
- Local-overrides dev doc: [`docs/development/local-overrides.md`](../../development/how-to/local-overrides.md)
- Architectural enforcement:
  - [`tests/architectural/test_shared_package_boundary.py`](../../../tests/architectural/test_shared_package_boundary.py)
  - [`tests/architectural/test_pyproject_shape.py`](../../../tests/architectural/test_pyproject_shape.py)
  - [`tests/architectural/test_events_tracker_public_imports.py`](../../../tests/architectural/test_events_tracker_public_imports.py) (public symbols only; see Amendment 2026-10-22)
- Consumer contracts:
  - [`tests/contract/spec_kitty_events_consumer/`](../../../tests/contract/spec_kitty_events_consumer/)
  - [`tests/contract/spec_kitty_tracker_consumer/`](../../../tests/contract/spec_kitty_tracker_consumer/)
- Packaging assertions:
  - [`tests/contract/test_packaging_no_vendored_events.py`](../../../tests/contract/test_packaging_no_vendored_events.py)
- Clean-install verification:
  - `.github/workflows/ci-quality.yml`'s `clean-install-verification` job (deleted per PROGRAM.md §2 / planning#57 — this repo runs no GitHub Actions)
  - [`tests/integration/test_clean_install_next.py`](../../../tests/integration/test_clean_install_next.py)
- PR #779 (rejected, superseded): <https://github.com/Priivacy-ai/spec-kitty/pull/779>

## Amendment 2026-10-22: the boundary covers public symbols, not only the public package (#6607)

The boundary now means public **symbols**. A production import of a `_`-prefixed module segment or a `_`-prefixed imported name from `spec_kitty_events` or `spec_kitty_tracker` is a violation, even when the package itself is the permitted public one. Core's last such import, `spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL`, was deleted together with the dead hosted lifecycle builder that used it.

`tests/architectural/test_events_tracker_public_imports.py` enforces this over all six production roots (`src/kernel`, `src/charter`, `src/glossary`, `src/runtime`, `src/mission_runtime`, `src/specify_cli`). It checks the imported name (`alias.name`) as well as the module path, and has no allowlist. It joins the enforcement references of this ADR beside `test_shared_package_boundary.py`.

## Amendment 2026-10-29 (Accepted): the events services live in spec-kitty-events

[ADR 2026-10-29-1](../4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) records the operator and CEO ruling of 2026-10-29 that the events domain's Java services and contracts move to `spec-kitty-events`, and that core consumes a released, pinned build.

- **What `spec-kitty-events` is to core.** Core now consumes two artifact kinds from `spec-kitty-events`: the PyPI package (a SemVer range plus `uv.lock`, unchanged) and pinned service builds (`pins/<service>.source.yaml`, holding a `service-v*` tag, the commit and a sha256 per asset). A pin is the release record for a binary, just as `uv.lock` is for the package. No editable, path or moving-branch reference is allowed for either.

Nothing else in this record changes.
