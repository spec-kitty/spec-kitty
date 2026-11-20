---
affected_files: []
cycle_number: 1
mission_slug: skill-surfaces-converge-01M7VRS0
reproduction_command:
reviewed_at: '2026-11-20T07:29:11Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback 1 — changes requested

Reviewer: claude::reviewer-renata (independent). Reviewed range 4a9e8eb6d3d9..8a3ff95676b2.

Verified: red commit 739add0ecf precedes the fix; the new tests plus `tests/runtime/` pass (2417 passed, 1 skipped);
the in-memory anchor-relative semantics are unchanged; the retire byte proof never proves a symlink.

## Blocking

### B1. Schema 2 makes every older CLI on the machine exit 1 on every command

Every pre-mission release accepts only `schema_version == 1` and raises `ValueError("Invalid global asset
inventory")`; `assess_*` turns that into `incomplete(...)`, and `ensure_runtime` / `ensure_global_agent_skills`
raise the terminal `StartupAssetError`. The first run of this build rewrites every existing schema-1 inventory
(`_rewrite_inventory`), on every machine, whether or not a root moved.

Reproduced with an isolated `HOME`: run this lane's CLI once, then the base (a053b674) CLI:

```
Error: runtime_bootstrap: Invalid global asset inventory: <HOME>/.kittify/cache/runtime_bootstrap-assets.json; re-run the command; ...
```

Any user with two installs (a global `uv tool` plus a project-pinned `uv run spec-kitty`), or anyone who rolls
back an rc, loses every command of the older CLI, and the hint does not lead to a fix. Neither research R-3 nor
the data model considers older readers.

Fix direction (pick one; the first is the smallest):

- Write schema 2 to a new file name (e.g. `<owner>-assets.v2.json`). Read v2 first, else migrate from the v1 file.
  Leave the v1 file in place, untouched: older CLIs keep reading their own record, which is stale but valid and
  only ever proves bytes it recorded.
- Or keep writing schema 1 (anchor-relative under `home.parent`) when every entry fits, and use schema 2 only for
  entries outside it. This still breaks older CLIs in the moved-root case, so it needs an operator ruling.

Add a test that a schema-1 file present before the run is still a valid schema-1 inventory afterwards, or name
the operator ruling that accepts the break.

## Non-blocking (fix while there)

- N1. `_validate_inventory_entry` accepts `~//etc/x` and empty segments: `Path.home() / "/etc/x"` resolves to
  `/etc/x`, so a `~/` key can name a path outside home. Reject empty segments (and a leading `/` after `~/`).
- N2. Schema-1 placement probes existence (`os.path.lexists`) at each ancestor of `$HOME` and accepts the first
  hit. R-3 and T008 said to place a key only when it lands under `$HOME`, the kittify home or an owner root
  (`known_roots`). Proof stays bounded by the recorded sha256, but either implement the confinement or record the
  deviation in the WP.
- N3. The schema-1 path no longer rejects `:` in keys (the old validator did). Keep schema-1 validation as strict
  as before.
- N4. `_foreign_entries` are carried through forever, with nothing to prune them. That's acceptable, but say so in
  the docstring.
