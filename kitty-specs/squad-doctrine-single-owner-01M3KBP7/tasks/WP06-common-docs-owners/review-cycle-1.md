---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T13:13:41Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review — cycle 1: CHANGES REQUESTED

Reviewer: claude (reviewer-renata). The content work is mostly sound. Red→green was confirmed: 25 failed / 6 passed at b072f10f, 31 passed at 74f40e39. Target suites pass: 1818 passed and 8 skipped; the doctrine `-k` slice gives 260 passed with only the expected `test_shipped_graph_is_fresh` red. Ruff and mypy are clean on the touched tests. DIRECTIVE_037 is unchanged and remains the owner. The curation fold is faithful in content.

## Blocking

1. **Dangling reference in a WP06-owned file.** `packs/built-in/directives/042-common-docs.directive.yaml:91-92` still lists `type: tactic, id: common-docs-curation` under `references:`. 042 is in WP06's `owned_files`, so this does not belong to WP09. Remove the entry. Add a test assertion that 042's `references` does not contain `common-docs-curation`. The styleguide and find-tactic checks already follow this pattern.

2. **The fold/A1 pins are vacuous; mutation probes survive.** Each of these mutations kept all 31 tests green:
   - **M1:** changing the scaffold ADR step to say "`doc_status` field (draft | active | superseded)". The A1 test only rejects two exact legacy strings.
   - **M2:** deleting the whole "Run the live gates before handoff" step from `common-docs-write`. The `docs_structural_lint` failure_mode line still satisfies the `or`.
   - **M3:** deleting the whole "File a new ADR under its era, with MADR status" step from `common-docs-scaffold`. `adr/<era>` still appears in step 1, and `"status" in text.lower()` is always true because of `doc_status`.

   Pin the carried steps structurally. Load the YAML, find the step by title, and assert its description names the pieces that matter:
   - For the ADR step: `adr/<era>`, MADR `status`, and DIRECTIVE_042.
   - For the gates step: `regenerate-graph --check`, the `related:` validator, the lockfile freshness gate, and `docs_structural_lint`.

   For A1, assert that no scaffold or write step that mentions ADRs prescribes a `doc_status:` value for an ADR.

3. **The lint asset still points consumers at the styleguide.** `packs/built-in/assets/docs_structural_lint.py` is WP06-owned. Its module docstring (~L26-40), `_CONFIG_KEY` comment (L95-96), `load_config` docstring (L255-265), `ConfigError` message (L290-292: "add the block to the common-docs styleguide") and `--styleguide` help (L849) still say the default policy lives in the common-docs styleguide. After the A5 move that is wrong, and the error message now gives incorrect recovery advice. Reword these to "a file carrying the `structural_lint_config:` block (built-in default: `assets/docs_structural_lint.config.yaml`)". No behaviour change is needed.

## Non-blocking

- `docs_structural_lint.config.yaml` comments carry mission-internal labels `(A3)` (L18) and `(A2)` (L83), which mean nothing to consumers. Drop them. The same applies to the `WP06 A5, #5221` comments in `tests/docs/test_doc_status_durable.py`. Those are allowed in tests but are noise.
- A3: `asset_owned_marker_values` is declarative only, because `load_config` ignores it. That is acceptable as a recorded decision, but the test only checks the YAML against itself. Consider having the lint's self-test or `load_config` assert that every `point_in_time_markers` value is in the declared set, so the declaration cannot drift from the markers.
- A2: 042:19-21 and the scaffold tactic still list all 13 section names inline. The count word is gone, but the list is duplicated. Consider referring to the styleguide list without enumerating it.
- The default routing change is a behaviour change to the built-in default. It drops `generated_report`/`generated_nav`, sends `how_to_internal` to `guides/` and `reference_policy` to `api/`, and changes `point_in_time` from `plans/engineering-notes/` to `plans/`. It is justified by A2 and does not affect this repo, which uses the internal override. Record it in the commit or PR body for consumers.
