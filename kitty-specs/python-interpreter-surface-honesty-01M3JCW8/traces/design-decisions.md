# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-27 — The primitive restores the 3.11/3.12 contract (loop ⇒ error) rather than adopting 3.13's (loop ⇒ path). Every affected guard was written against the older contract, and most already `except OSError` expecting the loop to land there.
- 2026-09-27 — The primitive raises `OSError(ELOOP)`, not `RuntimeError`, so that existing `except OSError` guards catch it as authored. The containment seams translate it into their documented `ValueError` refusal (squad F6).
- 2026-09-27 — The primitive lives in `kernel` (not `specify_cli.core`) because `charter` consumers exist (`org_pack_config`, `path_guard`) (squad F9).
- 2026-09-27 — Landing fold: `invocation/writer.normalise_ref` migrated although FR-004 first excluded it. The WP04 gate surfaced it and a red test showed 3.13+ records `sub/../loop` as `loop` while 3.11/3.12 keep the raw ref. Alternatives: allowlist it as a follow-up. Rationale: fold-first; a two-line change with a focused test.
- 2026-09-27 — Landing fold: `safe_commit_cmd` file arguments migrated (pre-PR squad F1). A looping `a`/`b` pair was refused on 3.11 but committed on 3.13+, so its allowlist reason ("identical on every interpreter") was false.
- 2026-09-27 — `mission.get_active_mission` stays allowlisted: its fallback is unreachable for a loop because `active_mission_link.exists()` reports a loop as absent on every interpreter. The WP04 draft reason called it a gap; review corrected it.
- 2026-09-27 — The gate keys its allowlist through `tests/architectural/_content_identity.py` (pre-PR squad blocker): raw `(path, function, ordinal)` tuples trip the positional-anchor ban, and D-OP-9 forbids another hand-rolled matcher.
- 2026-09-27 — Caller audit for the new `ValueError` from `ensure_within_*` (plan, FR-002): `core/owned_mission`, `status/store`, `migration/backfill_runtime_state` and `migration/runtime_state_cutover` already catch `ValueError` and keep their refusal; `upgrade/skill_update`, `merge/bookkeeping_projection`, `coordination/atomic_write` and `invocation/writer` propagate it as before. On 3.11/3.12 each already received an exception (`RuntimeError`) for a loop, so no caller moves from success to failure. Verified by the WP02 implementer and again by the pre-PR correctness review.
