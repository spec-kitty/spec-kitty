# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-08 · claude · Seed (operator rulings, all recorded as Decision Moments): #5884 remove rollback (not kernel verified truncate); 'for feature' -> 'mission' at all 5 commit builders + the CLI error strings, legacy finalize subject still accepted; analyze = new DAG step (not tasks-guard) AND canonicalize runtime templates on packs (src/specify_cli/missions copy is what next reads today, packs copy wrongly says DEPRECATED); Rule 4 + fix every meta.json/frontmatter writer; glossary full fix (topic branch added, Mission/Mission Run rewritten, feature branch demoted to alias).

2026-10-08 · python-pedro · WP01: _mission_specs_dir_name keeps its trailing-dash path-composition grammar (pinned by test_coord_dir_seam); the transaction LOCK site moved to legacy_resolution._transaction_lock_key -> branch_naming.mission_lock_dir_name (bare slug when no mid8). mission_lock_key reads the canonical primary meta via new public _read_path_resolver.literal_primary_meta (raw kitty-specs joins are gated). A coordination dir is named by the key itself, so no stem-pairing is needed. Held keys are a thread-local map registered by mission_write_lock.

2026-10-08 · python-pedro · WP01 cycle 2: transaction lock key now = mission_write.transaction_lock_key (shares mission_lock_key's coordination-routing decision; meta-less slug falls back to slug-mid8 composition). Legacy NNN- slug + coordination_branch + no mid8 -> bare name (cascade carve-out); MissionLockKeyUnresolved only for the modern case where resolve_transaction_mid8 itself raises (the transaction would fail too). Transaction hold registered via transaction._transaction_hold. Note 2: literal_primary_meta's primary leaf already resolves a worktree .git pointer to the main checkout, so no extra canonicalisation was added; test pins it. Handoff WP13: coord_seed holds are not registered.
