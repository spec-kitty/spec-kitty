# Change 2 research: stop committing the docs retrieval index in PRs

Op `01M6B0VY6YKM181BKXNSPNDAXG`. Read against `origin/main` at `bf8d27ce`; both generated files
matched the tree (915/915 entries, no drift).

## Findings

- **Why it conflicts.** `scripts/docs/docs_index.py` (`generate_index`, 200-217) renders one sorted
  15,901-line file (915 pages, about 11,300 anchor lines) through `src/specify_cli/docs/index_model.py`
  (`render_index`, 153-164). The header is fixed: no timestamp, SHA or count. Conflicts come from
  adjacent hunks in one sorted file (new ADRs dated close together, pages many PRs edit; the changelog
  page alone carries about 660 anchor lines). `page-inventory.yaml` (`scripts/docs/inventory_lockfile.py`)
  conflicts the same way. `freshen_adr_inventory.py` also appends a row to the ADR era table
  `docs/adr/<era>/index.md` (240-273), a third per-PR conflict source, out of scope here.
- **Runtime reader.** `spec-kitty docs query` (`src/specify_cli/cli/commands/docs.py:79`) loads the
  committed file relative to the current directory. **The index is not in the wheel**
  (`pyproject.toml:150` packages `src/*`; the only force-include is `pins`). From an installed wheel in
  a consumer project, `docs query` already reports an opt-in-artifact error (`docs.py:51-60, 78-90`).
  Nothing changes for wheel users under any option.
- **Gates.** No workflow runs `check_docs_freshness.py`; its sub-checks 5 (inventory drift) and 6
  (`DOCS-INDEX-DRIFT`) bind only through docs instructions. CI binds through `tests (docs)`
  (`ci-router.yml:1205-1226`): `tests/docs/test_committed_docs_index_fresh.py:51-71` is the only test
  comparing the live tree with the committed index. No live-tree test guards `page-inventory.yaml`.
  `test_no_legacy_terminology.py:500-507` and `test_retired_charter_vocabulary.py:409-413` require the
  index file to exist, so it must stay committed.
- **Precedent for a bot regeneration.** `ci-shard-recapture.yml` runs on schedule/dispatch, pushes a fixed
  branch and opens or updates a PR with `gh`, authenticated by the PAT secret
  `CHARTER_SHARD_RECAPTURE_TOKEN` so the PR triggers normal CI. `protect-main.yml:3-20` says the
  required checks live in the `main` branch settings; no ruleset is defined in the repo.

## Options

- **A. Regenerate on `main` after merge (recommended).** A push-to-`main` workflow on `docs/**`
  regenerates both files and opens or updates one bot PR on a fixed branch, reusing the recapture
  pattern. The per-PR test becomes "the index regenerates cleanly from the tree" (one entry per page,
  sorted unique paths, valid types, render/parse round-trip) instead of "the committed copy matches".
  A stale index on `main` then only means `docs query` is slightly behind until the bot PR merges.
- **B. Generate at build or query time.** Rejected: query-time generation measured about 1.3 s, against
  the command's load-once budget (`docs.py:7-8`); the generator would have to move from `scripts/` to
  `src/`; and two existence tests depend on the committed file.
- **C. Split per page.** Feasible but heavy: about 915 generated files, a new directory loader, and a
  drift gate still needed.

## Open for the operator

A bot commit straight to `main` or a bot PR. A bot PR needs no branch-protection exception and
matches the recapture precedent; it needs a PAT secret (reuse `CHARTER_SHARD_RECAPTURE_TOKEN` or a new one).
