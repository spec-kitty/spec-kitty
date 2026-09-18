# Data Model: Consistent Mission-Handle Resolution

This mission introduces no persistent schema and no migration. The only new
in-memory structure is the listing surfaced by discovery.

## Entities / Value Objects

### MissionListing (new, in-memory)

One row per existing mission, produced by `list_missions_for_selection(main_repo)`
(name avoids the `mission.py:809` `discover_missions` collision) and rendered by
the missing-handle discovery path.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `mission_slug` | str | mission directory / meta | The copy-pasteable handle. |
| `mid8` | str \| None | `meta.json` `mission_id`[:8] | Short disambiguator; `None` for legacy missions without a `mission_id`. |
| `friendly_name` | str | `meta.json` `friendly_name` → slug fallback | Human title; read from meta, not on `ResolvedMission`. Falls back to the slug when absent so the listing never blanks. |

- **Population rule (decided post-squad)**: count any mission directory bearing
  `spec.md` **or** `meta.json` — the SAME rule the plan/tasks auto-detect uses
  (`_list_feature_spec_candidates`), so `next` and plan/tasks never disagree on
  the count. This deliberately **includes legacy missions without a
  `mission_id`** (which `FsMissionResolver.all_missions()` would silently drop).
- **Legacy nudge**: when ≥1 listed mission lacks a `mission_id`, the render adds a
  one-line "N mission(s) need `spec-kitty migrate backfill-identity`".
- **Ordering**: stable and deterministic (by `mission_slug`) so listings and
  tests are reproducible.

### DiscoveryOutcome (new, in-memory)

The resolution of a *missing* `--mission` on `next`.

| Variant | Trigger | Effect |
|---------|---------|--------|
| `auto_selected(slug)` | exactly 1 mission | resolve to that slug, proceed |
| `needs_choice(listings)` | >1 missions | render listings, clean non-usage exit |
| `none_found` | 0 missions | render setup nudge, non-usage exit |

## Existing types referenced (unchanged)

- `ResolvedMission` (`context/mission_resolver.py`) — `mission_id`,
  `mission_slug`, `feature_dir`, `mid8`. **Not modified.**
- `AmbiguousHandleError` / `MissionNotFoundError` (`context/mission_resolver.py`)
  — the ambiguous-selector and not-found signals. Behavior preserved; the
  not-found *message text* is unified via the canonical template.
- `MissingLanesError` (`lanes/persistence.py`) — must no longer be the surface a
  user sees for a *nonexistent* mission passed to `merge` (it stays correct for a
  real-but-unfinalized mission).

## State transitions

None. This mission changes error/branching behavior only; no mission lifecycle
state is added or altered. Auto-selection resolves a handle but does not change
the selected mission's runtime state.
