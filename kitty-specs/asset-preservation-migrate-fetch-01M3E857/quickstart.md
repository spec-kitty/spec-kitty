# Quickstart — reproduce (red) and verify (green)

All commands use the branch venv, never bare `uv run` (it destroys the `.venv`). Prefix `PWHEADLESS=1`.

## FR-001/FR-002 — migrate preserves a customised template (#4961)

Red-first (before fix) / green (after): focused unit + integration.

```bash
# Focused classifier probe (fast): a customised shipped template must NOT be a raw-deletable disposition.
PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/test_migrate_integration.py -q -p no:xdist \
  -k "superseded or customized or version_skew or preserve"
```
Expected after fix: a `.kittify/templates/spec-template.md` that differs from the package default is
preserved (in place / overrides / reported backup); `migrate --dry-run` labels it customised, not
"superseded"; a byte-identical default is still removed.

## FR-003 — first-install never deletes a pre-existing pack (#4960)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/doctrine/test_sources.py -q -p no:xdist \
  -k "TestGitSource and (first_install or preexisting or refuse or checkout)"
```
Expected after fix: with a non-empty `local_path` that is not a clone of `url` and a failing clone, the
hand-authored files survive; only a fetch-created temp is ever removed.

## FR-004 — update preserves local edits and advances (#4989)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/doctrine/test_sources.py -q -p no:xdist \
  -k "TestGitSource and (update or dirty or advance or origin)"
```
Expected after fix: dirty/committed local edits are preserved/backed up before any reset; a `ref: main`
update targets `origin/main` and the pack advances.

## FR-005 — the class stays closed (arch gate)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_mutation_ownership_routing.py -q -p no:xdist
```
Expected after fix: green with both product modules in the scanned set. Fail-ability: adding an
un-rationalised raw destructive literal to either module reds the gate (verified in review).

## Blast-radius battery (pre-merge, over the combined tip)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/ tests/specify_cli/doctrine/ tests/architectural/ tests/ci/ -q
```
Baseline-red gotcha applies: classify any failure per CLAUDE.md before attributing it to this mission.

## Mutation-testing spot-check (review gate)

For each fixed site, hand-mutate the guard back to the raw destroy (e.g. restore `path.unlink()`,
restore the unconditional `rmtree`, restore bare-`<ref>` reset), confirm a test goes RED, then revert.
A site whose mutant stays green is unprotected — reject.
