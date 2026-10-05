---
affected_files: []
cycle_number: 1
mission_slug: frozen-started-lanes-01M444FM
reproduction_command:
reviewed_at: '2026-10-04T22:05:55Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback (cycle 1) - reviewer-renata

**Verdict: changes requested.** One blocking defect. The prose itself checks out against the code.

## Blocking

**[HIGH] docs/development/docs-retrieval-index.yaml: not regenerated, so the docs freshness gate is red.**
`PYTHONPATH=.:src python -m scripts.docs.check_docs_freshness` reports `errors=4`. The base commit d7a2b9a1 reports 0 errors, so this WP introduced all four:
- `DOCS-INDEX-DRIFT docs/adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md`: present in docs/ tree, absent from committed index
- `DOCS-INDEX-DRIFT docs/api/finalize-tasks-internals.md`: index row disagrees with regenerated page
- `DOCS-INDEX-DRIFT docs/architecture/execution-lanes.md`: same
- `DOCS-INDEX-DRIFT docs/context/topology.md`: same

`scripts/docs/docs_index.py --strict` confirms it: added=1, changed=3.

**Fix:** follow the workflow in `docs/development/index.md` ("Freshen the docs-inventory rollups"):
1. `PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write`
2. `PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci` must report errors=0. Warnings about external URLs are fine.

Commit the regenerated index. This is another required out-of-map edit, the same kind as the page-inventory.yaml row, and it is acceptable.

## Non-blocking (fold if cheap)

- **[LOW] docs/api/finalize-tasks-internals.md "Refusal envelope":** "The key set is fixed" leaves out the owned-checkout extra `stale_repository_root_copy`. `_OWNED_ENVELOPE_EXTRAS` in `mission_finalize_seams._emit_json` adds that key on owned-checkout runs. Mention it alongside `target_branch_override_revert_error` and `status_commits_not_undone`, or say "plus finalize's standard envelope extras".
- **[LOW] ADR Decision bullet 3 and execution-lanes.md step 2:** "reads back the unused prior lane id it shares the most members with". In the code (`_read_back_by_overlap`), a group that shares **no** members mints a fresh id. Consider "shares at least one member with (the most wins)".

## Verified correct against the code (no action)

- Error code, the four reasons and their precedence, the remedy texts (verbatim from `frozen_membership.py`), the JSON keys, and the console form (`_print_membership_conflicts`).
- Exit code 1, and the preflight placement after `_run_finalize_ownership_gates` and before `_emit_tasks_started`. Skipped for `--refresh-planning-commit` and single_branch; runs under `--validate-only`.
- The started-WP definition, the lane-work-tip fallback and the planning-lane exception. The tie-break rule (lowest prior id), the reserved ids, the frozen union rule, and its exclusion from `independent_wps_collapsed`.
- The absent-vs-unreadable nuance. A corrupt line is refused earlier with `Invalid JSON on line N`, and `test_refinalize_frozen_lane_refusals.py` covers it.
- The two stale-page corrections in execution-lanes.md are right. Dependency edges do not merge lanes (compute.py module docstring and union rules), and the new `collapse_report` example matches `CollapseReport.to_dict()` and the `_describe_overlap` evidence format.
- `Applicable to 4.x` is correct for the current line (charter: 4.x active, pyproject 4.0.0rc6).
- CHANGELOG.md is a symlink to docs/changelog/CHANGELOG.md, and the entry sits under Unreleased / Fixed.
- No broken relative links, and the anchors resolve. Remedies are non-destructive. No "feature" terminology.
