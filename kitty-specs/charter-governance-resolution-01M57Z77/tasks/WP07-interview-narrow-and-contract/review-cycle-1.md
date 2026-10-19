---
affected_files: []
cycle_number: 1
mission_slug: charter-governance-resolution-01M57Z77
reproduction_command:
reviewed_at: '2026-10-18T23:23:26Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review feedback (reviewer-renata)

The code is sound. Red-first is real: 6 new tests fail at 029048548 and pass at 63a24f008. The acceptance tests (narrow vs default against a computed count, an empty-selection kind left untouched, org-required ids kept as stems, JSON `narrowed`) are good. ruff, format, C901, `regenerate-graph --check` and `vendor --check` are all clean. Three small fixes are needed before approval.

## 1. Contract text does not match shipped behaviour (prompt.md)

- `packs/built-in/missions/mission-steps/software-dev/charter/prompt.md` (end of file): "`--defaults` fills paradigms from the profile defaults, so combined with `--narrow-activation` it narrows paradigms to those defaults." This is not true today. `defaults.yaml` sets `selected_paradigms: []` and `_DEFAULT_MISSION_PARADIGMS` resolves to `[]` for every Mission type. An empty selection is never narrowed, so `--defaults --narrow-activation` leaves `activated_paradigms` untouched. Change the sentence to match: paradigms are narrowed only when the interview selects some (for example `--selected-paradigms ...`), because `--defaults` selects none today. You can also just remove the sentence, since "kinds with no selection are untouched" already covers it.
- In the bullet near line 84, "the interview adds them to what is already in force and never removes anything" contradicts `--narrow-activation`, which the same bullet lists two lines later. Qualify it, for example "by default the interview adds them ... and never removes anything".

## 2. Revert the unrelated regenerated drift

`scripts/docs/check_cli_reference_freshness.py` exits 0 on the base (96a4bf813) without these hunks. It only prints a non-blocking HELP-DRIFT warning for `migrate ledger`, so the gate does not need them:
- Revert `docs/api/agent-subcommands.md` entirely. The only change there is an `agent mission accept` column-width reflow.
- In `docs/api/cli-commands.md`, keep only the `--only` and `--narrow-activation` option hunks. Revert the `spec-kitty migrate ledger` move and rewrite: it relocates the section, drops the italic summary line and renders a literal `\b` and `**bold**` inside the code block, which is worse than the current text.
- Re-run the freshness script (with `PYTHONPATH=.`) and confirm it still exits 0.

## 3. Make the defaults pin deterministic

`test_interview_narrow_activation_with_defaults_only_follows_default_paradigm_selection` branches on `if selected:`, and only the `else` branch can run today. Assert the current fact directly: `payload["selected_paradigms"] == []`, `"activated_paradigms" not in config`, `"activated_paradigms" not in payload["narrowed"]`. Add a positive control that `activated_directives` was narrowed in the same run. If the defaults ever change, the test should fail loudly rather than silently switch branches.

## Pre-existing reds (verified identical on base 96a4bf813, not yours)

- 10 in `tests/specify_cli/cli/commands/test_upgrade_command.py`, plus 1 in `test_upgrade_command_skill_drift.py`
- `test_doctrine_asset.py` x3
- `test_doctrine_regenerate_graph.py::test_shipped_graph_orphan_count_within_documented_residual` (not caused by the prompt.md edit)
- `charter/test_resynthesize_and_hotpath.py` x2
- 6 packaging/wheel errors (environment)
