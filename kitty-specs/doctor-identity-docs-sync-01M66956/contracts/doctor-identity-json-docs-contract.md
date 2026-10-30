# Contract — `docs/migrations/mission-id-canonical-identity.md` mirrors the live doctor identity report (FR-001..FR-004)

The migration runbook page is a **projection of a live CLI contract**, not a standalone spec. It must track the code that actually emits the report; when they drift, the page lies to operators mid-migration.

## Source of truth (never re-stated elsewhere in prose)

| Page element | Live authority |
|---|---|
| Identity state list + per-state bullets | `IDENTITY_STATES` / `IdentityState.to_dict()` in `src/specify_cli/status/identity_audit.py` |
| Audit JSON sample shape (`summary` counts, `missions[]` row keys, `duplicate_prefixes`, `ambiguous_selectors`, `fail_on_triggered`) | `_build_identity_json` in `src/specify_cli/cli/commands/_identity_audit.py` |
| `residue_remedies` presence | conditional on ≥1 `residue` row in the report (rule landed with #5875) |
| Step 3 backfill transcript | live `spec-kitty migrate backfill-identity` summary table (per-mission walk and git-commit line were fiction) |
| "Backfill commits the change" claim | none — the command writes to the working tree and does **not** commit |

## Enforcement (SC-001..SC-003)

`tests/docs/test_mission_id_migration_page.py` imports the production contract and pins the page to it:

- the page's documented state list equals `set(IDENTITY_STATES)` exactly (no `ok`/`conflict` era states, no missing `residue`);
- every JSON sample's `summary` and row keys match `_build_identity_json`'s output keys (conditional `residue_remedies` included);
- the Step 3 transcript carries the live summary lines and none of the retired fiction;
- no removed contract token (`"status"`, `"conflicts"`, `"total"`, `legacy_present`, …) survives anywhere on the page.

Proven red-first: 6/6 assertions failed against the pre-fix page (recorded in WP01 history); 8/8 pass after the rewrite.

## Non-goals

- The page does not re-derive or re-explain the migration policy itself; it links to the canonical identity docs.
- Reformatting the page into the `docs/api/cli-commands.md` shape is out of scope — only the stale contract surface was synced.
