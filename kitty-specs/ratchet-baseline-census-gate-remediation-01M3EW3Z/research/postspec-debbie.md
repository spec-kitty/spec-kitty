# Post-spec adversarial squad — Debugger Debbie (code-truth / live evidence)

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z`. HEAD `6f24a8d7` (shallow clone, 53 commits; git history for deleted gates is not available locally).
Mode: READ-ONLY. I did not edit or commit anything. The only scratch output is under the session scratchpad.

## Governance applied
- **Profile `debugger-debbie`:** investigator role. I used the Falsifier (tried to disprove each claim), the Matrix-Maker (enumerated every allowlist and baseline cell, not a sample) and the Stenographer (every verdict comes from a command I ran). I did not patch anything and I hand off to the architect/planner. I ran one oracle pass instead of five sub-agents, because this is a verification point-cut and not a recurring-bug hunt (budget boundary).
- **Charter `specify` context:** DIRECTIVE_001/003/030/032 (the profile refs), the ATDD-first and red-first rules (C-011), canonical sources (I re-derived everything rather than trusting `research/grounding-*.md`), and the Pre-existing Failure Reporting Rule (I recorded baselines as pre-mission state).

## Pre-mission baseline (HEAD)
- `pytest test_ratchet_positional_anchor_ban.py test_no_inert_schema_slots.py test_ratchet_baselines.py -q -p no:cacheprovider` → **78 passed, 1 warning, 7.5 s**.
  - Warning: `inert-slot baseline shrank; delete cleared ledger rows: styleguide-references, model`. The ledger is already stale by 2 rows.
- Affected gates (`built_in_location_authority`, `kernel_no_doctrine_import`, `destructive_op`, `mutation`, `overwrite`, `single_mission_surface_resolver`, `no_worktree_name_guess`) → **64 passed, 75 s**.
- `tests/next/test_internal_runtime_parity.py` → **8 passed**.
- `tests/runtime/test_bridge_parity.py` → **24 passed, 438 s**.
- `python tests/architectural/surface_resolution_audit/audit.py` → **exit 1, "AUDIT FAILED"**.

## Findings

[INFO] Grounding table / FR-001..006 / SC-001 — "88 line-pinned entries = 6 join + 2 kernel + 80 census (22+56+2)" — **TRUE**.
- An AST scan of every module-level assignment under `tests/architectural/` for `(str|Path(...), int)` tuples and `path.ext:N[:x]` string keys gave:
  - `test_built_in_location_authority.py:138 _KNOWN_JOIN_ALLOWLIST`: 6
  - `test_kernel_no_doctrine_import.py:127 _PRE_EXISTING_EXEMPTIONS`: 2
  - `test_destructive_op_routing.py:158 _ALLOWLIST`: 22
  - `test_mutation_ownership_routing.py:238 _ALLOWLIST`: 56
  - `test_overwrite_ownership_routing.py:267 _ALLOWLIST`: 2
- Nothing else matched. The YAML files only carry `line:` fields, which are non-authoritative (`test_charter_path_literal_authority.py:219`, `test_inline_meta_read_gate.py:138`), plus prose `x.py:N` inside comments.
- Recommendation: none. The count is sound.

[INFO] Grounding #5085 — "2 of 6 join entries are dead" — **TRUE**.
- Running `_find_builtin_joins` against each entry gave:
  - `src/kernel/paths.py:88` → no offenders in the file (that line is `if is_windows():`).
  - `src/specify_cli/runtime/home.py:79` → the file has 60 lines.
  - The other 4 entries are live: `kind_vocabulary.py:273`, `neutrality/lint.py:379`, `template/manager.py:161` and `:304`.
- The join gate has **no** stale-entry check, which is why these rotted.

[INFO] Grounding #5085 — "three blind spots" — **TRUE**.
1. Scoping on a substrate import (`test_ratchet_positional_anchor_ban.py:117-130`).
2. The tuple arm needs a string literal, and the join list uses `Path("...")`.
3. `is_file_line_anchor("src/x.py:98:reset_hard")` returns **False**, while `"src/x.py:98"` returns True.

[HIGH] FR-002 vs C-005 — the spec implies widening the line-pin predicate — **conflict risk**.
- `is_file_line_anchor` lives in `src/specify_cli/contracts/anchoring.py:295`.
- It is used by the production Contract Registry (`src/specify_cli/contracts/registry.py:297,328`) and pinned by `tests/specify_cli/contracts/test_registry.py:181-183`.
- Widening it to accept the `:op` suffix changes `src/` behaviour, which C-005 forbids.
- Recommendation: FR-002 must say that the suffix-key predicate is test-local, in the ban module. Otherwise C-005 needs an explicit exception.

[HIGH] Edge case "operation appears more than once in the same function" — **FALSE framing: it is the majority problem, not an edge case**.
- Re-keying the 80 census keys as `(path, enclosing_qualname, op)` gives:
  - destructive: 22 → 21 unique (1 group of 2)
  - mutation: 56 → **40 unique; 26 entries in 10 colliding groups**, for example `FixMemoryStructureMigration.apply` × `Path.unlink` ×6
  - overwrite: 2 → 2
- In total, 28 of 80 entries (35%) need a token or occurrence discriminator.
- Also, `destructive_op_allowlist: 56` in `_baselines.yaml` is `len(_ALLOWLIST)`. Any collapse to counted keys changes what that number means.
- Recommendation: promote this to an FR with the sizing above. Decide in the plan whether the key is token-line or occurrence.

[MEDIUM] C-004 vs FR-006 "through the census helper" — **PARTIAL**.
- `tests/architectural/_destructive_op_census.py:148` defines its **own** `enclosing_qualname`. That is a second qualname algorithm next to the canonical `_ratchet_keys.enclosing_qualname` (which re-exports `specify_cli.contracts.anchoring`).
- "Through the census helper" without re-pointing it keeps two identity mechanisms alive, which is what C-004 prohibits.
- Recommendation: require the census helper to delegate to `_ratchet_keys.composite_key`/`enclosing_qualname`.

[MEDIUM] FR-007 stale-entry detection — **PARTIAL**: it already exists in two places, with different policy.
- Kernel: `test_pre_existing_exemption_is_still_a_real_violation` (`test_kernel_no_doctrine_import.py:244`) already fails on stale entries.
- Census gates: `diff_against_allowlist` (`_destructive_op_census.py:189`) only **warns** on stale entries. This is documented as a deliberate "shrink-only, never block cleanup" contract (module docstring lines 14-18; `test_destructive_op_routing.py:274`, `mutation:518`, `overwrite:349`).
- FR-007 reverses a documented design decision.
- Recommendation: say that explicitly (an ADR or tracer note) and update the census helper docstring. Otherwise a reviewer will read it as a regression.

[INFO] FR-011 / US2-AS3 — "nothing reads `unassigned_entries` / `masking_suppressions`" — **TRUE**.
- The only mentions are prose: `test_reference_enum_ratchet.py:192` and `_inert_slots.py:661`.
- `test_ratchet_baselines.py` never indexes either key.

[INFO] FR-011 sizing — "what OTHER nested keys are unread" — **exactly those 2, no others**.
- I checked all 23 nested keys across 12 top-level sections. The other 21 are indexed by `test_ratchet_baselines.py`, with two caveats:
  - `test_no_dead_modules.category_1_auto_discovered_migrations` is read but **decorative**: its baseline is derived from the frozenset (`test_ratchet_baselines.py:198`) and it is only pinned for equality.
  - `test_example_round_trip.skip_marker_blocks` is read but **advisory**: `record_property` only, never fails (`:201-233`, `:901-931`).
- Recommendation: FR-011 has to define "read". If it means "influences pass/fail", those 2 keys also trip it. If it means "indexed", they pass.
- Note: the top-level equivalent already exists. `_GRANDFATHERED_UNREGISTERED_KEYS` is empty (`:145`), so FR-011 is a nested extension of that mechanism, not a new one.

[MEDIUM] Same defect class as FR-011, not in scope — orphaned whole allowlist files.
- `tests/architectural/resolution_gate_allowlist.yaml` names its gate `test_resolution_authority_gates.py`, which **does not exist**. The only remaining reader is the positional-anchor ban's field-name rule (`:141`). Its `canonicalizer_baseline: 3` and `coord_authority_baseline: 3` are dead caps, exactly the #3026 class.
- `tests/architectural/surface_resolution_audit/write_candidate_classification.yaml` has zero readers.
- `surface_resolution_audit/audited-surfaces.md` and `RULESET.md` are orphaned alongside `inventory.md`. `RULESET.md:6` tells readers to run `audit.py`.
- Recommendation: add these to FR-008/FR-009/FR-010, or record them as follow-ups. SC-004 ("0 baseline keys unread") scopes only `_baselines.yaml` and misses these.

[INFO] Grounding #3011 — "gate deleted; audit fails with 8 missing + 8 ghost; nothing runs `--check`" — **TRUE**.
- `tests/architectural/test_surface_resolution_audit.py` is absent.
- `audit.py` exits 1 with exactly 8 "MISSING from inventory.md" and 8 "NO live discovered callsite" lines.
- There is no CI or Makefile reference to `rekey_inventory` or `--check`.

[HIGH] Assumption (spec:162) — "scanner functions remain in use by `test_single_mission_surface_resolver.py`, `test_no_worktree_name_guess.py` and `_ratchet_keys.py`" — **PARTIAL / FALSE for 2 of the 3**.
- Only `test_single_mission_surface_resolver.py:163-182` uses `audit.py`. It loads the file by path and uses `discover_rows`, `discover_selection_callsites`, `KITTY_SPECS_NAMES` and `ALLOWLISTED_SELECTION_CALLSITES`, plus their transitive helpers (`_audit_file`, `_find_*`, the `*_CALLS`/`*_STEMS`/`SLUG_NAMES` constants, `ResolutionRow`/`SelectionRow`, `_composite_from_file`).
- `test_no_worktree_name_guess.py:155` mentions `inventory.md` only in a comment. It imports only `_ratchet_keys.composite_key` (`:78`).
- `_ratchet_keys.py:49,124` mentions `audit.py` only in docstrings. The dependency runs the other way: `audit.py:86` imports **from** `_ratchet_keys`.
- The FR-008 kept surface is: the discovery walkers and constants listed above.
- Removable: `main`, `_parse_inventory_rows`, `_parse_selection_rows`, `_inventory_composites`, `_composite_from_locator`, `_collect_table`, `_unwrap`, `check_undercount`/`check_overcount`, `_fail`, `_resolution_checks`/`_selection_checks`, `INVENTORY_PATH`, `KNOWN_CANDIDATE_FILES`, `VALID_DISPOSITIONS`, and `if __name__`.
- FR-009 targets the spec misses:
  - the **assertion message** at `test_single_mission_surface_resolver.py:508` ("Run `python …/audit.py`")
  - `RULESET.md:6`
  - the two prose mentions above
  - the two entries in `pyproject.toml:954-955`, which are the `[tool.ruff.format] exclude` entries
  - `tests/architectural/untrusted_path_audit/inventory.md:76`, which cross-references the sibling `inventory.md`
- Recommendation: correct the assumption line and enumerate the kept surface in the plan.

[INFO] Importers of the #3011 retirement targets — **no breakage risk**.
- `rekey_inventory` has no importers anywhere; it loads `audit.py` itself.
- `audit` is loaded only by `test_single_mission_surface_resolver.py`.
- `docs/plans/engineering-notes/research-notes-csf-2670.md:29` and `docs/reports/test-sanitation/...` are historical references.

[INFO] Grounding #3026 — "the enforcing tests were removed; caps read by nothing" — **TRUE, and wider than stated**.
- `test_no_inert_schema_slots.py` imports only `find_inert_slots`, `load_baseline` and `ratchet`. `test_ratchet_baselines.py:421,583` reads `BASELINE_SLOTS`.
- Unused outside the module:
  - `MAX_UNASSIGNED_ENTRIES`, `MAX_MASKING_SUPPRESSIONS`
  - `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners`
  - `find_code_only_suppressions`, `code_only_drift`, `load_code_only_record`, `CODE_ONLY_SUPPRESSIONS`, `CODE_ONLY_VERDICTS`, `code_producer_writes`
  - `MINIMUM_SCHEMA_SLOT_NAMES`, `MINIMUM_MODEL_SLOT_NAMES`, `MINIMUM_*_BASELINE_ENTRIES_STILL_FOUND`, `is_schema_declared`
  - `UNASSIGNED_OWNER`, `COMPLETED_LANES`, `scanned_slots` (still used internally)
  - `ALLOWLIST` (the "`test_allowlist_is_empty` pins this" at `:72` refers to a test that does not exist)
- `_inert_slots.py:35` imports `specify_cli.status.reducer.materialize_snapshot` only for `owner_is_complete`.
- `_inert_slots_baseline.yaml:376` `code_only_suppressions:` is parsed at import time (`:753`) but checked by nothing.
- **Dormant mask:** the non-vacuity floors (`MINIMUM_*`) are dead. The live gate's only floor is `assert found` (`test_no_inert_schema_slots.py:64`), which is weaker than NFR-002's "concrete non-zero floor".
- Recommendation:
  - FR-010 should enumerate this full list.
  - Either keep one `MINIMUM_*` floor wired into `test_live_tree_has_no_new_inert_slots` (NFR-002) or delete all of them.
  - Delete the 2 cleared ledger rows, which shrinks `baseline_entries` 38 → 36.
  - Route the `code_only_suppressions` YAML block explicitly.

[INFO] FR-005 / #3206 — **TRUE**.
- #3206 is OPEN.
- Both entries (`kernel/schema_utils.py` lines 88 and 97) are live; the stale-check test passes.
- Minor: the #3206 issue body says `:96`, while code and exemption say 97. Line drift in the issue text, harmless.

[MEDIUM] FR-012 / US3-AS1 — "import bans scan a nonexistent directory" — **TRUE**.
- `tests/next/test_internal_runtime_parity.py:96-103,121-128` scans `src/specify_cli/next/_internal_runtime`, which has 0 `.py` files (the directory is absent). Both tests pass anyway (8 passed).
- The live `src/runtime/next/_internal_runtime` has 16 files and **0** violations. So the converted bans go GREEN immediately. C-001 red-first can only be met with the floor or empty-dir mutation test, not a red on HEAD.
- The `spec_kitty_runtime` ban is **already duplicated** by `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package` (`:59`, whole production tree). Only the rich/typer ban is unique.
- "Live runtime package" must mean `_internal_runtime` specifically: `src/runtime/next/runtime_bridge_retrospective.py:158` imports `rich.prompt`, so a scan of all of `src/runtime` would go red.
- Recommendation:
  - Retire the `spec_kitty_runtime` arm as a duplicate; do not convert it.
  - Convert rich/typer with the path pinned to `_internal_runtime`.
  - Rewrite the C-001 wording for this WP.

[MEDIUM] Grounding #2631 / FR-016 — "`test_bridge_parity` holds 17 P0 acceptance tests" — **FALSE count**.
- The #4980/#4975 block (`:1401-1862`) has **13 functions / 14 collected items** (`coord_family` is parametrized ×2).
- The grounding's 17 counts from `:1383` and so includes the 2 oracle-era `*_fail_closed_default_direct_call` tests (15 functions / 16 items). It still does not reach 17.
- Total collected: 24, split as 10 oracle-section and 14 P0.
- Oracle cost: `test_every_fixture_pair_is_parity_stable` **setup 389.1 s** out of 438 s wall time. The P0 calls sum to about 48 s.
- The P0 tests take only `tmp_path` and never touch the module-scoped oracle fixture. They already run without the oracle under `-k`, so the split is about organisation and cost, not correctness.
- Recommendation:
  - Fix the number to 13 functions / 14 nodes.
  - Decide where the 2 `direct_call` fail-closed tests go (they pin behaviour and are not oracle-dependent).
  - Make the acceptance check "node count 14 (or 16) unchanged".

[INFO] Grounding #2972 — "#1842 closed" — **TRUE** (closed 2026-07-07 by PRs #2429 and #2432). #2633 is OPEN at P2.

[LOW] NFR-004 (< 10 s) — the current ban call takes 1.9 s. Headroom is ample.

[LOW] Spec self-containment — FR-015 and FR-013 depend on "named in the grounding report". FR-017 and SC-005 need the sweep list pinned; the grounding catalog is the only source.

## Verdict
**PASS WITH REQUIRED CORRECTIONS before plan.**

The core numerics hold: 88 = 6 + 2 + 80, 2 dead join entries, 2 unread baseline keys (and only those 2), 8 + 8 audit drift, and the vacuous runtime bans.

Must be fixed in the spec or plan:
1. The P0 count is 13/14, not 17.
2. The kept-surface assumption is wrong for `test_no_worktree_name_guess` and `_ratchet_keys`.
3. FR-002 must not widen the `src/` `is_file_line_anchor` (C-005).
4. The census "edge case" affects 28 of 80 entries and needs an FR.
5. FR-007 reverses the documented warn-only stale policy; that needs a recorded decision.
6. The census helper's duplicate `enclosing_qualname` conflicts with C-004.
7. FR-011 needs a definition of "read" (decorative and advisory keys).
8. The orphaned `resolution_gate_allowlist.yaml` and `write_candidate_classification.yaml` are the same defect class and are unscoped.
9. The `spec_kitty_runtime` ban is a duplicate and should be retired, not converted.
