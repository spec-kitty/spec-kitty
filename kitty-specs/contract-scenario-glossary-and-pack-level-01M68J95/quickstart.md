# Quickstart — read the two entries, re-run the gates

## As a reader

1. Open [`docs/context/charter.md`](../../../docs/context/charter.md) and find
   **Contract Scenario**, directly above **Activation preset** and below **Charter
   Pack**. The entry says what a contract scenario names and calls, where the scenario
   files live (`contracts/charter/scenarios/` in `spec-kitty/spec-kitty-charter`), and
   what `@contract` / `@provisional` mean. Its `Do NOT use when` row sends you to the
   acceptance scenarios, the conformance corpus, or BDD the practice.
2. In the same page, the **Charter Pack** entry says a pack declares a *level* — "the
   level token" — not a "tier".
3. Open [`docs/context/governance.md`](../../../docs/context/governance.md) and read
   **Pack Level**: the level a Charter Pack occupies, by `pack_level` in its
   `pack.yaml`, one of `built-in`, `org` or `project`. `kernel.pack_tiers` is still
   named as the one authority for the three level names; the word "tier" is not used
   for a pack's level in prose.
4. If you meant a different sense of "tier": **Organization Tier** (same page as
   Contract Scenario) and the *Three-layer DRG* entry keep their own wording. This
   change does not rename them.

## As a maintainer — the four gates for this diff

Run from the repository root, on the mission branch:

```bash
# 1. The new standing guard (fails on the pre-fix tree, passes after)
uv run --frozen pytest tests/docs/test_context_glossary_contract_scenario_and_pack_level.py -q

# 2. The docs index is committed-fresh after the new ### heading
uv run --frozen python -m scripts.docs.docs_index --write        # regenerate
uv run --frozen pytest tests/docs/test_committed_docs_index_fresh.py -q

# 3. ADR inventory is a no-op (no ADR in this diff) and stays fresh
uv run --frozen python scripts/docs/freshen_adr_inventory.py --check --all

# 4. Docs freshness, spelling/changelog style, and the legacy-terminology scan
uv run --frozen python -m scripts.docs.check_docs_freshness --ci   # errors=0
make docs-lint
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

`check_docs_freshness --ci` exits `0` on a clean tree, `1` on an error-severity
finding, `2` on a missing inventory/reference and `3` on an environmental setup error.
Only `0` is green.

## What must not change

- `kernel.pack_tiers` — the module name (inline code span in the entry).
- **Organization Tier**, the *Three-layer DRG* entry's "three-tier" prose, and the
  `tiered rigour` wording elsewhere in the charter: different senses, separate owners.
- The seed (`.kittify/glossaries/spec_kitty_core.yaml`) and the built-in glossary pack:
  `docs/context/` is the authoring surface for this diff.
- Any gate's selection, allowlist or baseline.
