# Contract: historical mission-override repair

The seam `4.0.0rc8_repair_historical_sweep_overrides` owns. Every clause is asserted by
`tests/upgrade/migrations/test_m_4_0_0rc8_repair_historical_sweep_overrides.py`; a change that
breaks one of them is a contract change, not a bug fix.

## Scope

The step reads **only** `<project>/.kittify/overrides/missions/**`. It never reads
`.kittify/missions/**`, the global runtime home, or git history, and it makes no network call.

## Provenance verdicts

For each regular file at `<project>/.kittify/overrides/missions/<type>/<rest>`, resolve the
shipped counterpart through
`specify_cli.runtime.migrate.shipped_mission_counterpart(Path("missions/<type>/<rest>"), get_package_asset_root())`
— the one `missions/<type>/<rest>` mapping in the codebase, shared with `classify_asset`.

| Verdict | Test | Outcome |
|---|---|---|
| identical | bytes equal the shipped counterpart | removed |
| differs | a shipped counterpart exists, bytes differ | preserved byte-for-byte, and the path is named in a warning |
| no counterpart | no shipped file at that mission-relative path | never read, never named, never touched |

Comparison is **exact bytes** — the same question `classify_asset` asks with `filecmp`. A CRLF
working-tree copy of a shipped LF file is therefore `differs`: it is preserved and named, never
deleted.

## Removal

- Removal goes through `specify_cli.asset_preservation.guard_destructive_removal`; the migration
  module carries no raw `unlink`/`rmtree`/`rmdir` literal
  (`tests/architectural/test_mutation_ownership_routing.py` pins the module as routed).
- The prover is `CanonicalContentProver(canonical=<shipped bytes>, check_marker=False)`. A version
  marker alone never authorizes a delete, and neither does a path name (#4961).
- No directory is created or removed. An emptied `templates/` directory stays.

## Refusals

| Condition | Behaviour |
|---|---|
| a `.kittify`, `overrides` or `missions` path component is a symlink or not a directory | refuse the whole tree, warn naming the component, change nothing |
| an override file is a symlink | skip and warn naming it; nothing outside the project is read or removed |
| the shipped counterpart is unreadable | report an error on the result; no removal |
| `get_package_asset_root()` raises `FileNotFoundError` | `can_apply()` refuses visibly; `apply()` fails closed; `detect()` reports nothing to do |

## Idempotency and the ledger

- `apply()` on a repaired project makes zero changes.
- One successful run records the step in `.kittify/migration-ledger.jsonl` (tracked partition), so
  `spec-kitty migrate ledger` reads it as *already in place* and no later upgrade repeats it.
- `detect()` is true for a `differs` candidate as well, so the operator is actually told the file
  shadows the shipped one.

## Frozen neighbours

`2.0.7_fix_stale_overrides` and `4.0.0rc8_retire_stale_mission_template_forks` keep their bytes
(DIRECTIVE_044). This step is a new id in `order_manifest.txt`, ordered after the #5280 step
because that step owns the 15 named documentation/research fork copies.
