# Data Model: Exit 0 means your data is intact

No new persisted schemas. This mission changes how existing records are read, folded and protected.

## Decision Moment lifecycle (fold view)

| From \ event | `DecisionPointOpened` | `DecisionPointResolved(deferred)` | `DecisionPointResolved(resolved)` | `DecisionPointResolved(canceled)` |
|---|---|---|---|---|
| (none) | → open | malformed | malformed | malformed |
| open | malformed (opened twice) | → deferred | → resolved | → canceled |
| deferred | malformed | malformed | **→ resolved (allowed; the #4919 fix)** | malformed (the service refuses it too) |
| resolved | malformed | malformed | malformed | malformed |
| canceled | malformed | malformed | malformed | malformed |

**Invariants:**
- One transition rule (this table) is shared by the service (write side) and the fold (read side).
- The fold is order-independent: the event-log merge driver re-sorts by `(at, event_id)`. For one decision, exactly one `deferred` outcome plus one `resolved` outcome folds to `resolved` in either order. Any other multi-outcome set is malformed.
- A decision whose events fold to *malformed* is reported by diagnose. Repair keeps it and exits non-zero; it never removes it from the index.

## Mission number

- Field: `mission_number` in `kitty-specs/<mission>/meta.json` on the **target branch**.
- "Assigned" means an integer ≥1 (`is_assigned_mission_number`, the shared leaf in `consolidation/mission_number.py`). `null`, missing and non-integer values are unassigned.
- Assignment: `max(assigned numbers on target) + 1`, under the consolidation lock.
- Invariant: the number printed by `spec-kitty consolidate` equals the number read back from the target branch after the bake. Otherwise the command exits non-zero.
- Merge-driver rule: an assigned target value wins; an unassigned target value never overrides an assigned mission-side value.

## Spec Kitty-owned mission metadata (dirty-tree exemption)

- Exempt paths (git-root-relative): `(?:^|/)kitty-specs/[^/]+/meta\.json$` and `.kittify/meta.json`.
- Every other tracked `meta.json` is user-owned. If it is dirty, consolidation refuses.

## Agent settings file decode outcome

| Input bytes | Outcome |
|---|---|
| strict UTF-8 | decode, merge, write UTF-8 (unchanged behaviour) |
| UTF-8 BOM / UTF-16 LE/BE BOM (/ UTF-32 BOM) | decode, back up the original bytes, merge, write UTF-8 |
| decodes but invalid JSON | existing `.invalid.<uuid>` backup path (unchanged) |
| anything else (for example cp1252) | typed refusal: file untouched, non-zero exit naming the file |

## Installed skill

- Rendered output = the render of `normalize_newlines(source)`, with exactly one frontmatter block.
- Repair rewrites a file only when its on-disk hash equals the manifest-recorded hash (`unchanged_owned`). Otherwise the file needs consent.
