---
title: Development
description: The contributor/maintainer zone for Spec Kitty — subdivided into getting-started, how-to runbooks, reference policy, and testing — kept separate from end-user guides.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/getting-started/index.md
- docs/development/how-to/index.md
- docs/development/reference/index.md
- docs/development/testing/index.md
- docs/development/how-to/create-a-doctrine-artifact.md
- docs/guides/index.md
---
# Development

Runbooks and policy for people **contributing to or maintaining the Spec Kitty
project itself** — as opposed to [`../guides/`](../guides/index.md), which
documents *using* Spec Kitty in your own project. The split is strict: no
contributor-only page is reachable from end-user navigation.

The active release cycle is **4.0.0** (release candidates on `main`); see the
[4.0.0 milestone roadmap](../plans/4-0-0-milestone-roadmap.md). The 3.x line is
closed.

This zone is subdivided by concern:

- **[Getting started](getting-started/index.md)** — [onboarding a co-maintainer](getting-started/onboarding-run.md) and [isolated dev environments](getting-started/isolated-dev-environments.md).
- **[How-to](how-to/index.md)** — task runbooks: [landing PRs](how-to/pr-landing.md), [review gates](how-to/review-gates.md), [local overrides](how-to/local-overrides.md), [the issue tracker](how-to/manage-issue-tracker.md), [contract pinning](how-to/contract-pinning.md), [the cut-over guard](how-to/cutover-guard.md), [creating a doctrine artifact](how-to/create-a-doctrine-artifact.md), [architectural-gate exemptions](how-to/add-architectural-gate-exemption.md), and [compressing mission history](how-to/compress-mission-history.md).
- **[Reference](reference/index.md)** — policy and ledgers: [friction points](reference/known-friction-points.md), [coverage signals](reference/coverage-signals.md), [CI and architectural gate mechanics](reference/ci-gate-mechanics.md), [issue-matrix verdicts](reference/issue-matrix-verdicts.md), [standing orders](reference/quality-and-tech-debt-standing-orders.md), [the read-side seam ledger](reference/read-side-seam-classification.md), [red-main policy](reference/red-main-and-release-readiness.md), and [terminology exemptions](reference/terminology-exemptions.md).
- **[Testing](testing/index.md)** — [flakiness policy](testing/testing-flakiness.md), [parallel runs](testing/testing-parallel.md), [mutation tests](testing/run-mutation-tests.md), [UI e2e](testing/ui-e2e.md), and [time-dependent tests](testing/write-time-dependent-tests.md).
- **Reporting** — the [executive debrief styleguide](reporting/debrief-styleguide.md).
- **Other records** — [analysis-report transactions (`record-analysis --report-only`)](analysis-report-transactions.md) and the [inline meta-read allowlist baseline deviation](inline-meta-read-allowlist-baseline-deviation.md).

### Historical / prior cycle

Kept as records; not current guidance.

- [`tests/sync/` process-global and thread-seam inventory (#3115)](reference/process-global-inventory-3115.md) — deprecated; the `tests/sync/` cone it maps was deleted with the sync transport.
- [Agent-memory migration manifest](agent-memory-migration-manifest.md) and [agent-memory workflow migration manifest](agent-memory-workflow-migration-manifest.md) — one-off audit records of a migration of operator memory into doctrine.

## Start here

- [Contributing to Spec Kitty](contributing.md) — developer setup, running tests, submitting PRs, AI-assistance disclosure, and the release process.
- [The SkyKitty agent fleet](agent-fleet.md) — the company agent fleet that runs missions on this repo, the roles inside it, and the `ready-for-squad` handshake that hands work to the review squad and CI.

## Non-page artifacts

The `3-2-` prefix on both files below is a frozen historical filename, not a
version scope: they cover every current doc, and are regenerated for 4.x
changes.

- **`3-2-page-inventory.yaml`** — the page-inventory tooling artifact. It STAYS
  PUT by operator directive; the freshness/lockfile tooling
  (`scripts/docs/inventory_lockfile.py`, `check_docs_freshness.py`,
  `version_leakage_check.py`, `_inventory.py`) reads it at this stable path.
  A regression guard (`tests/docs/test_inventory_path_stable.py`) asserts the
  path cannot silently move.
- **`3-2-docs-retrieval-index.yaml`** — the docs retrieval index, regenerated
  by `scripts/docs/docs_index.py` (see below).

## Repo-owned workflow commands

Two commands a mission session runs directly, not through a `spec-kitty` CLI
subcommand — plus the regen command for generated agent copies:

- **Freshen the docs-inventory rollups.** After adding or refrontmattering any
  page under `docs/**`, regenerate both generated rollups and verify no drift
  remains:

  ```bash
  # inventory_lockfile.py: --write takes the OUTPUT PATH as its argument (not a bare flag)
  PYTHONPATH=. .venv/bin/python scripts/docs/inventory_lockfile.py \
    --write docs/development/3-2-page-inventory.yaml

  # docs_index.py: --write IS a bare flag here (rewrites the default --index path in place)
  PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write

  PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci   # must report errors=0; external-URL WARNINGS are fine
  ```

  The two `--write` flags are **not** the same shape — a bare `--write` on
  `inventory_lockfile.py` is a usage error (it needs a path argument), while
  passing a path to `docs_index.py --write` is rejected as an unexpected
  positional. These are two separate generators for two sibling artifacts
  that are never conflated with each other — `inventory_lockfile.py` only
  regenerates the page inventory, `docs_index.py` only regenerates the
  retrieval index. `check_docs_freshness --ci` fails closed with a blocking
  `INVENTORY-LOCKFILE-DRIFT` / `DOCS-INDEX-DRIFT` finding if either rollup is
  stale relative to frontmatter — see
  [Known current friction points](reference/known-friction-points.md). Commit
  both regenerated YAMLs alongside your doc edit.

- **Mission wrap-up sequence.** The standing close-out procedure a mission
  runs between "all work packages approved" and "draft PR handed to the
  operator": accept → retire/split dev-assist tests → resolve issue verdicts
  → independent aggregate-diff review → local consolidation → compact history →
  rebase onto upstream → draft PR + pre-merge squad → hand off. Canonical
  source: the
  [`mission-wrap-up-sequence` procedure](../../packs/built-in/procedures/mission-wrap-up-sequence.procedure.yaml).
  Its three binding quality pillars — linear history, complete scope,
  independent review — are
  [DIRECTIVE_046](../../packs/built-in/directives/046-readable-consistent-prs.directive.yaml)
  ("Readable and Consistent Pull Requests"). Referenced from the
  [onboarding-run cadence](getting-started/onboarding-run.md), step 12.

- **Regenerating generated agent-command copies / skill fixtures.** Run
  `spec-kitty regen` to rewrite the committed generated fixtures from source,
  and `spec-kitty regen --check` to verify them without writing (it exits 1
  and prints the diff when they are stale). CI runs the same check as the
  `regen-check` job in `ci-router.yml`. Added under
  [#3447](https://github.com/spec-kitty/spec-kitty/issues/3447) (automated
  asset/prompt regeneration). Do not hand-roll a substitute regen path.

## See also

- [Documentation home](../index.md)
- [Guides (end-user zone)](../guides/index.md)
