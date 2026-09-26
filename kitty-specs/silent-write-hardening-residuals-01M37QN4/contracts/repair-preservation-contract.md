# Contract — mission-state repair preservation (Finding A)

**Surface**: `migration/mission_state.py` — `_is_preserved_non_lane_row`, `_rule_reject_non_status_event`, `_canonicalize_status_row`, `_registry_authoritative_quarantine_violations`. Reference contract: `status/store.py::is_non_lane_event`.

## Guarantees

1. **Preserve-by-default, by DELEGATION.** `_is_preserved_non_lane_row` DELEGATES to the reader:
   `(row.get("kind") == ANNOTATION_KIND) or is_non_lane_event(row)` (minus the empty denylist). The reader
   is the single authority — the repair is not a parallel classifier. The annotation OR-clause is the only
   intended divergence (reader returns False to route annotations to their own partition; repair returns
   True to keep them on disk). *(Squad fold: re-enumerating the reader's branches would recreate the
   two-classifiers-in-lockstep mechanism that generated the whack-a-field class.)*
2. **Empty denylist.** The only rows pruned from the non-lane path are those on an explicit prunable-mirror denylist. That denylist is empty; it is a named, documented constant, so any future entry is a reviewed decision.
3. **Lane passthrough precedence.** A flat legacy typed lane transition (`WPStatusChanged` + top-level `wp_id`/`from_lane`/`to_lane`) is classified as a lane transition and canonicalized into `status.json` (with `event_type` stripped) — evaluated **before** the delegated preserve call. (Protects #3066; delegation is behavior-identical precisely because this runs first.)
4. **Quarantine scope.** Only rows for which `is_non_lane_event` is False AND that are not valid lane rows are quarantined ("genuinely non-status" — in practice `event_name`-only non-retrospective rows).
5. **Fail-closed guard (strengthened, reader-keyed).** `_registry_authoritative_quarantine_violations` fails the repair (non-zero / recorded error, never `errors=0` success) if **any row where `is_non_lane_event(obj)` is True** is quarantined — keyed on the reader predicate, NOT `"event_type" in obj`. This is a genuine reader==repair check and covers reader-preserved rows with no `event_type` (retrospective `event_name`), which an `event_type`-keyed guard would silently miss.
6. **Duplicate-`event_id` carve-out (preserved).** A benign duplicate-`event_id` drop whose survivor stays in `canonical_rows` (via `surviving_event_ids`) does not trip the guard (regression folded in #4938 stays green; every duplicate has a prior survivor, so the carve-out is provably sufficient).
7. **Known disposition edges (safe, ADR-noted).** The nested-payload `WPStatusChanged` replay envelope and a partial-field `WPStatusChanged` corruption shape shift from quarantine to preserve-verbatim under the inversion; both align with the reader's existing behavior (fail-closed toward retention) and are pinned by ACs + docstring notes, not regressions.

## Behavioral change (ADR-recorded)

Before: an `event_type` absent from `AUTHORITATIVE_NON_LANE_EVENT_TYPES` (and not retrospective/annotation) was quarantined and dropped, exit-0. After: it is preserved. This changes what `--fix` prunes — recorded in the FR-003 ADR under `docs/adr/3.x/`.

## Acceptance (red-first)

- **AC-A1**: a row with an authoritative-shaped `event_type` NOT in the registry survives `--fix` (present in active state, not quarantined). Fails against pre-inversion repair, passes after. (SC-001)
- **AC-A2**: a repair that would quarantine any `event_type`-bearing row reports a non-zero/error outcome (guard). Fails against the registry-only guard for an unregistered type, passes after.
- **AC-A3**: legacy `WPStatusChanged` lane row is still canonicalized into `status.json`, not preserved verbatim (no #3066 regression).
- **AC-A4**: benign duplicate-`event_id` mission dedupes without the guard hard-erroring (no #4938 regression).
- **AC-A5**: all previously-preserved classes (annotation, retrospective, lifecycle, DecisionPoint, WPStatusChanged-as-lane, review_result) remain handled identically (NFR-002 / SC-005).
