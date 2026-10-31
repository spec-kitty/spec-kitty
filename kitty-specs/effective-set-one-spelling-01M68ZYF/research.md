# Discovery: one activation spelling at the effective-set seam (#6435)

## Decisions

### D1 — The reported union symptom is fixed; the defect is in a consumer of the seam

The issue's *Observed* section describes the union of scanned stems and service
mapping keys. That union is already converged: `a8dd1812a6` ("one stored
activation spelling", #6527 local slice, cites #6435) added
`_as_stems(...)` in `src/charter/activation/effective_set.py`, which maps the
service half through `IdentityIndex.stem` before unioning it with the scanned
stems (`_scanned_ids` → `ActiveCharterManager.list_available`, which emits
`_config_stem`). Verified on `main` @ 6f73b2a98e:

- fixture: two declared org packs, each carrying id≠stem artifacts, plus a
  project-layer tactic → `resolve_effective_sets` returns stems only;
- every activatable kind, real built-in layer + the internal org pack →
  0 declared ids in the resolved sets and 0 service-mapping keys the index does
  not know (`_service_keys` ⊂ `IdentityIndex`).

So re-fixing the union would be a no-op; the Mission boundary is therefore the
**remaining** acceptance in the issue's *Expected* section: the effective set
*and its consumers* keep one spelling, and the union's mapping is pinned before
any compensating conversion is touched.

### D2 — A required-only kind's absent-key materialisation still mixes spellings

`charter.activation.pack_manager._preservation_ids` materialises an absent key
from `PackContext.allow_for(kind)` when `effective_when_absent != "all"` (today
only `skill`). That value is the raw org `required_<kind>` list — declared ids —
and it is written verbatim into `activated_<kind>`. Every other writer routes
through `IdentityIndex.stored_spelling` (or `org_required_stems`, which wraps
it). Reproduced on `main` through the production CLI:

```
org pack: skills/acme-skill-file.skill.yaml  (id: acme-skill-id)
          org-charter.yaml: required_skills: [acme-skill-id]
$ spec-kitty charter activate skill other-skill-file
activated_skills: [acme-skill-id, other-skill-file]
```

`acme-skill-id` is a declared id sitting beside `other-skill-file`, a stem —
exactly the mixing #6435 asks to end, and the failure mode #6527's
"every writer stores the file stem" contract forbids. The same function already
calls `org_required_stems(...)` one line earlier, purely to make a colliding
required id raise `ActivationIdCollisionError`; it discards the stems that call
returns.

### D3 — The union's spelling rule has two copies, and the fallback copy is unguarded

`_resolve_one` and `_fallback_ids` each apply `_as_stems(...)` to the service
half. Mutation check: deleting the mapping from `_fallback_ids` leaves all 19
tests in `tests/charter/activation/test_effective_set.py` green. That copy is
production-relevant — `ActivationResult` seeds an unresolvable absent key from
`fallback_ids`, and `activate` writes that list.

### D4 — Scope exclusions (coordination, not deferral)

- Activation-id spelling as a *contract* belongs to #6518/#6527; this Mission
  converges call sites and changes no stored format.
- Unknown-token / ambiguity policy belongs to #6433. The collision case stays
  `file_name_collision` (refuse, name the files); no new tolerance or refusal is
  invented.
- Do not reimplement `list_available_detailed` (the issue says so explicitly);
  the identity authority is `IdentityIndex` / `org_required_stems`.

## Evidence

| Claim | Evidence |
| --- | --- |
| Union is stem-only today | `src/charter/activation/effective_set.py:148-154, 193-205`; probe over the internal pack: 0 declared ids, 0 index-unknown service keys |
| Union mapping is pinned on the resolved path | reverting `_as_stems` in `_resolve_one` reds `test_procedure_whose_id_differs_from_its_stem_appears_in_stem_spelling` |
| Fallback mapping is unpinned | reverting `_as_stems` in `_fallback_ids` keeps 19/19 green |
| Required-floor mixing is live | CLI repro above (`activated_skills: [acme-skill-id, other-skill-file]`) |
| Collision refusal already exists on that path | `pack_manager._refuse_required_collisions` → `org_required_stems` → `IdentityIndex.stored_spelling` → `ActivationIdCollisionError` |
| Only one required-only kind | `ArtifactKind.effective_when_absent`; `_REQUIRED_WHEN_ABSENT_KINDS = {SKILL}` |

## Prior art / related issues

- #6527 (local slice) — one stored activation spelling; `stored_spelling`,
  the collision refusal, preset/interview/org-required writers.
- #6408 — `--only` narrowing, which already maps the org-required floor through
  `org_required_stems`; the plain `activate` path is the one that does not.
- #6406 — identity index (`IdentityIndex.stem` / `declared_id` / `stored_spelling`).
- #6433 — unknown-token / ambiguity policy (out of scope here).
- #6457/#6458/#6459 — the neighbouring `activate` output contracts in `a8dd1812a6`.

## Open questions

1. Does any consumer rely on the *declared id* being written for a required-only
   kind? (Searched: `activated_skills` readers resolve tokens through
   `_gated`/`IdentityIndex`, which accepts either spelling, so storing the stem
   is safe. No migration is needed; existing lists keep their spelling until
   their next write, per #6527.)
2. Should the fallback union also map the *scanned* half? (No: it comes from
   `list_available`, stems by construction; mapping it would be a second copy of
   the rule.)
