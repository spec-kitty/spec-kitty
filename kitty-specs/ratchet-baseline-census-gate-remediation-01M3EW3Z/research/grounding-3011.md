# #3011 grounding — rekey_inventory.py round-trip safety

Profile: researcher-robbie (investigation mode, read-only). HEAD `34f19c6f` (shallow clone, 50 commits — `git rev-parse --is-shallow-repository` = true, so history claims older than that are UNVERIFIABLE here).

## 0. Headline (changes the ticket's framing)

1. **The defect is still live.** `_disposition()` is at `tests/architectural/surface_resolution_audit/rekey_inventory.py:48-60` (issue said 49-60), `_rationale()` at `:63-92`. The renderer rebuilds every row from those rules (`:106-114`) and has no read of the existing inventory — there is no preservation path.
2. **The gate the issue cites no longer exists.** `tests/architectural/test_surface_resolution_audit.py` is absent on HEAD. `docs/reports/test-sanitation/assertive-test-suite-sanitation-01KZME3P/dispositions.yaml:112661-112747` records its 17 tests as candidate `WP13-architectural-test-surface-resolution-audit`, action "Delete generated topology/report/prose audit and exact route inventory", `verdict: DELETE`, `survivor: null`.
3. **Because of that, `audit.py` is ungated and RED on HEAD.** `.venv/bin/python tests/architectural/surface_resolution_audit/audit.py` → `AUDIT FAILED`, exit 1: 8 undercount + 8 ghost findings (resolution.py ×5, surface_resolver.py `_coord_mid8`:820 and `resolve_status_surface`:943, mission_creation.py now `_create_mission_core_impl`:993). The cause is real source drift: call args collapsed onto one line, and `create_mission_core` was split. This is not a tooling bug. No workflow, Makefile, pytest.ini or test invokes `audit.main()`. The only live consumer is `tests/architectural/test_single_mission_surface_resolver.py:163-167`. It imports `audit.py` for `discover_rows()`/`composite_key_from_file` only, and its own docstring (`:90-97`) says "Neither inventory is a live-pinned CI gate; both are reviewer reference snapshots." That file: 8 passed (114.6 s).
4. **The accept.py row is moot on HEAD.** `grep accept inventory.md` shows only prose at `:124`. `_stamp_birth_cutover_for_accept` (`src/specify_cli/cli/commands/accept.py:266`) is not discovered by `discover_rows()`: it is absent from the rendered output, and the rendered raw-bypass count is 2, all `_coord_mid8`. The triage comment already noted the row never landed on main. The structural defect is shown below with other rows.

## 1. What the converter would do today (verified)

`--check`: `inventory.md is STALE — re-run without --check to freshen.` exit 1.

Dry run: `_render_inventory()` was imported and rendered to `scratchpad/inventory.rendered.md`, and the repo was not written. The diff is 71 lines (`scratchpad/3011.diff`). Row-level comparison by composite key (`scratchpad/rt3011.py`):

| Effect | Rows | Legit? |
|---|---|---|
| **Hand-edit narrative deleted.** The WP08/T038 paragraph (`inventory.md:47-67`) is dropped because the header is a fixed f-string (`rekey_inventory.py:173-243`). | 1 block | NO — destroys adjudication provenance |
| **`[inventory-only]` row dropped.** `surface_resolver.py:748` (`resolve_status_surface_with_anchor`, `_compose_primary_feature_dir`, WP08 foundation site 4/4). The renderer emits only live-discovered rows (`:106`). | 1 | NO — a second overwrite class the issue does not name |
| **Adjudicated rationale overwritten** on `_read_path_resolver.py:1303` `_compose_primary_feature_dir`. Old text: "WP08 T035 direct successor … permanent (C-004)". New text calls it "the topology-blind primitive definition (`primary_feature_dir_for_mission`)", naming a **deleted** function. `_rationale` has the old name hard-coded (`:71-76`). | 1 | NO — factually stale output |
| **Disposition summary rewritten.** The "meaning" column is hard-coded (`:226-229`). Counts go topology-blind 2→1, raw-bypass 3→2, total 17→15. | table | Partly. The hand summary is **itself inconsistent**: it claims raw-bypass 3 with "1 write-side local staging path (genuine FS write)", but the table has only 2 raw-bypass rows (`inventory.md:92-94` vs table `:70-85`). |
| Composite re-key of drifted rows (resolution.py ×5, `_coord_mid8`:528→820, `resolve_status_surface`, mission_creation) | 8 | YES — this is what would green `audit.py` |
| `:line`-only change (composite unchanged): status_transition 618→761, surface_resolver 533→821 and 675→995, `_read_path_resolver` 1142/1303/1460, aggregate 542→556, plus all 3 selection rows | 10 | Noise |

No rows had their `disposition` value flipped on HEAD: all 8 re-keyed rows get the same bucket they had before. Disposition flips remain a structural risk, shown by the accept.py case in the issue, but none occurs in today's diff.

## 2. Is `--check` permanently STALE because of `:line`? — Yes, by construction

The render embeds `row.line` in every locator (`:112`, `:139`), and `--check` compares whole files byte for byte (`:260-263`). Any insertion above a tracked callsite makes it STALE, even though the audit ignores `line`. The audit builds its keys from `rel = loc.rsplit(":",1)[0]` (`audit.py:643`), and the docstring says as much (`rekey_inventory.py:16-18`, `inventory.md` header). Nothing gates `--check`: its only mention outside the script is a historical review note (`kitty-specs/mission-resolver-port-01KX1C05/tasks/WP03-thread-resolver-trunk/review-cycle-2.md:31`, reporting "fresh" at the time).

## 3. Who tells agents to run it

- `rekey_inventory.py:11-14` (docstring: "Run to freshen after a legitimate seam edit").
- `inventory.md:34` and the generated header `rekey_inventory.py:205-209`: "Freshen procedure … re-run the recorded converter". **This is the trap instruction.**
- `RULESET.md`: no mention of rekey, converter or surgical editing, so there is no warning (grep empty).
- History only: `kitty-specs/read-side-placement-seam-migration-01KYHP67/pr-summary.md:178,195` (files #3011), `kitty-specs/mission-resolver-port-01KX1C05/tasks/WP03…:145-147` plus review-cycle-1/2 ("census regenerated via the canonical tool"), and `kitty-specs/refactor-stable-gate-substrate-01KWK3FY/tasks/WP03-surface-audit-identity.md:179`.
- `tests/architectural/test_single_mission_surface_resolver.py:207` cites "inventory.md's WP08 hand-edit note". The converter deletes that note.
- `pyproject.toml:954-955`: both `audit.py` and `rekey_inventory.py` are in `[tool.ruff.format].exclude` (`:253`). Any edit to them escapes the format gate. This is worth a campsite fix.

## 4. Design options (operator must choose — main ambiguity)

**Option A — Retire (aligns with the sanitation verdict).** WP13 of `assertive-test-suite-sanitation-01KZME3P` already deleted the inventory's only gate as "generated … exact route inventory". The survivor guard runs `discover_rows()` live, and `test_no_read_side_bypass.py` is the terminal census (`test_single_mission_surface_resolver.py:195-207` comment).
- Delete `rekey_inventory.py`, `inventory.md`, and `audit.py::main()` together with its inventory-parsing helpers (the inventory-parsing half of `audit.py` from `:477`).
- Keep `discover_rows`/`discover_selection_callsites`/`_composite_from_file`, which the survivor imports.
- Update `pyproject.toml:954-955`, `RULESET.md`, and the `:207` comment.
- This closes #3011 as "tool removed", with no round-trip test needed. Scope: small, about 0.5 WP.
- Hypothesis to confirm first: `audited-surfaces.md` and `write_candidate_classification.yaml` in the same dir are not read by `rekey_inventory.py`/`inventory.md`, and the dir's other consumers are unaffected.

**Option B — Fix the converter (the issue's direction), if the inventory is kept as a reviewer artefact.**
1. **Default mode `--rekey`:**
   - Parse the existing inventory with `audit._parse_inventory_rows`.
   - For each discovered row whose composite key matches an existing row, preserve `handle source`/`sink`/`disposition`/`rationale` verbatim and refresh only the locator.
   - For a discovered row with no match, look for a secondary match on `(rel_path, qualname, sink)`. Code drift changes the token (8 rows today), so this recovers most of them. Still-unmatched rows get `disposition = UNADJUDICATED` and a `[needs-adjudication]` rationale. `UNADJUDICATED` is not in `VALID_DISPOSITIONS`, so `audit.py` Check 1 (`:764-771`) fails closed and a human must decide. The rule may appear only as a suggestion in the notes.
   - Carry `[inventory-only]` rows through untouched.
   - Carry free prose between the "## Sink table" heading and the table (the hand-edit narrative) through verbatim.
   - Compute summary counts, but keep the "meaning" cells.
2. **`--reclassify`:** explicit opt-in that applies `_disposition`/`_rationale`, never the default. Also fix the stale `primary_feature_dir_for_mission` reference in `_rationale` (`:74`).
3. **`:line` handling:** keep writing the jump-to line, but make `--check` compare a normalized form with the locator trailing `:\d+` stripped. Alternatively, drop the line from locators entirely; `audit.py:643` already accepts a bare `rel_path`. Recommend normalization, which keeps the reviewer convenience.
4. **Surgical-edit warning:** update the docstring, `RULESET.md`, and `inventory.md:34`.
5. **Separate campsite:** re-adjudicate the 8 drifted rows plus the inconsistent summary so `audit.py` is green again. Decide whether to re-add an `audit.main()` pytest gate. Its removal was a deliberate sanitation verdict, so re-adding it needs the operator's approval.

Scope: 1 WP (M). Converter refactor into pure `merge_rows(existing, discovered)` + `render` helpers, about 150 LOC; tests; inventory re-adjudication. Complexity ≤15 is needed, and extracting pure helpers aids Sonar coverage.

## 5. RED-first acceptance tests (Option B)

File: `tests/architectural/test_rekey_inventory_round_trip.py`. Load the module via `importlib` as the survivor test does.

- `test_rekey_preserves_adjudicated_cells`: monkeypatch `_INVENTORY_PATH` to a tmp copy of the committed `inventory.md` and render. For every existing row whose composite key re-appears, assert `disposition`/`handle_source`/`sink`/`rationale` are byte-identical. **RED today, verified:** the `_read_path_resolver.py:1303` rationale changes (`scratchpad/rt3011.py` output "CELL CHANGED … rationale").
- `test_rekey_preserves_inventory_only_rows`: assert every `[inventory-only]` row survives. **RED today:** `surface_resolver.py:748` is not re-emitted.
- `test_rekey_preserves_sink_table_preamble`: the hand-edit narrative survives. RED today, since the fixed header drops `inventory.md:47-67`.
- `test_rekey_unmatched_row_is_unadjudicated_not_rule_classified`: use a synthetic fixture with a monkeypatched `discover_rows` returning one novel raw-join row. Assert the rendered disposition is `UNADJUDICATED`, and that `audit.main()` over it exits non-zero. RED today, since the rule returns `raw-bypass`.
- `test_check_is_line_insensitive`: render, shift every `row.line` by +1 through a monkeypatched `discover_rows`, and assert `--check` reports fresh. RED today, because of the byte-equality at `:260-263`.

Use a synthetic fixture (a hand-built inventory string plus stubbed `discover_rows`) as the primary form, so the tests do not depend on the real, drifting inventory. The real-inventory variant is the tracer.

## 6. Blast-radius commands

```
.venv/bin/python -m pytest tests/architectural/test_rekey_inventory_round_trip.py tests/architectural/test_single_mission_surface_resolver.py -q
.venv/bin/python tests/architectural/surface_resolution_audit/audit.py        # must go green after re-adjudication
.venv/bin/python tests/architectural/surface_resolution_audit/rekey_inventory.py --check
make test-fast
uv run --frozen ruff check tests/architectural/surface_resolution_audit && uv run --frozen ruff format --check .
uv run --frozen mypy tests/architectural/surface_resolution_audit/rekey_inventory.py
```
If `pyproject.toml` is touched (the ruff-format exclude, or retirement under Option A), the change is cross-cutting, so also run the full `tests/architectural/` suite.

## 7. Open questions for operator

1. Option A (retire; consistent with the sanitation DELETE verdict) or Option B (fix)? Recommend **A** unless a reviewer still actively uses `inventory.md`. Its gate is gone and it is already 16/32 rows out of sync.
2. Under B, should the `audit.main()` pytest gate return? That reverses a sanitation verdict and needs explicit approval.
3. Under B, may `--reclassify` stay at all, or should rule-based classification be deleted outright?
4. The issue's parent/milestone metadata (#5104 / "CLI 4.x stable") differs from the triage comment (#1931 / 3.2.x). This is harmless, but the triage comment is outdated.
