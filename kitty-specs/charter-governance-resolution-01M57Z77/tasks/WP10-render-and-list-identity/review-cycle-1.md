---
affected_files: []
cycle_number: 1
mission_slug: charter-governance-resolution-01M57Z77
reproduction_command:
reviewed_at: '2026-10-19T00:42:06Z'
reviewer_agent: claude
wp_id: WP10
---

# WP10 review feedback (reviewer-renata), cycle 1

The behaviour is correct. Red-first holds: b1ed6e49a fails 15 tests and 4fba49b79 turns them green. The --include unknown control passes, the list text and JSON checks pass, and so does the preset check. The boundary and JSON-contract gates, the NFR-004 snapshot, ruff, format, mypy --strict and C901 are all clean. Three items block approval: two mechanical ones and one timing regression.

## 1. Missing changelog entry for the `charter list --json` contract change (required)

The WP prompt asks for this twice: Objectives says "note it for the changelog", and Risks says "contract change -> changelog". The `--all --json` `available[]` entries now carry a third key, `declared_id`, and `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py:308` was changed for it. `docs/changelog/CHANGELOG.md` has no WP10 entry. WP09 added its own entry for its schema change, so this WP should add one too.

Add an Unreleased entry that names #6406 and covers these points:
- Before: an artifact activated by its declared id while its file stem differs (for example `qa-seven` in `qa-tactic-seven.tactic.yaml`) was listed as available, not activated.
- After: it lists as activated under either spelling, and the text output shows `stem (declared_id)`.
- `charter list --all --json` `available[]` entries gain a `declared_id` key. The change is additive, but a consumer that checks the exact key set has to update.
- `--include <kind>:<stem>` now resolves for every kind.

## 2. New suppressions in tests (Shared Rules: "no new `# noqa` / `# type: ignore`")

- `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py` (`TestListIdentity`): four `# type: ignore[...]` with no rationale. Type the parsed payload as `dict[str, Any]` (and the rows as `list[dict[str, Any]]`), then delete all four.
- `tests/charter/test_context_include.py`: `from tests.charter.org_pack_identity_support import write_identity_org_pack  # noqa: E402`. Move the import to the module's import block and drop the `noqa`.

## 3. Regression: preset application breaks its timing budget (required)

`tests/specify_cli/cli/commands/charter/test_preset_cli_timing.py::test_preset_and_pack_list_within_budget_of_charter_list` (the #3732 timing budget: preset application must take at most 1.5x the time of `charter list`) fails on the lane head and passes on `b1ed6e49a^`. Run serially, it fails reproducibly: `AssertionError: (2.08, 1.28)`. An identical probe, median of 5:
- base: list=1.06s, preset=1.14s (1.07x)
- head: list=0.98s, preset=1.88s (1.91x)

Cause: `plan_preset_application` now calls `IdentityIndex.build(repo_root)`, which builds a fresh index. That index re-resolves the pack chain and re-scans every kind the preset lists, with its own `ResolutionPass`, on top of the scan `_resolve_preset_ids` already does. The WP prompt said "build the index from `_Roots`". Build it from the already-resolved `_Roots`, meaning its `org_roots` and the shared `resolution_pass`, or thread one index through `_resolve_preset_ids` and `_target_state`, so each (kind, layer set) is scanned once per plan. This is the same NFR-003 principle. Then re-run that test serially (`-n0`) and confirm it passes.

## Non-blocking notes (no change required in this WP)

- NFR-003: in bootstrap mode, `bootstrap_text.py:312` calls `_render_selection_block` without `identity=`, so it builds its own `IdentityIndex`. That index is in addition to the resolver's and to the one WP03 threads through context.py, so one `charter context` invocation can scan a (kind, layer set) more than once. Threading the index into `bootstrap_text` is outside this WP's file map. Flag it for WP03 or mission review. The two `IdentityIndex.build` calls in `build_charter_context_include` are on mutually exclusive branches, so only one runs per call.
- WP03 also edits `src/charter/activation/context.py`. WP10 changed only the include call sites (around lines 446-471), so a textual conflict is unlikely. Coordinate when the lanes are consolidated.
- Without `--all`, `charter list --show-available --json` keeps `available` as a list of stems with no `declared_id`. That is acceptable, since the shape is a list of strings, but the changelog line should say the key is `--all` only.
