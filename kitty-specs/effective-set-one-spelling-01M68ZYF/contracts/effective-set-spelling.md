# Contract: one activation spelling (effective set and its consumers)

Applies to `charter.activation.effective_set.resolve_effective_sets`,
`charter.activation.pack_manager.ActiveCharterManager.activate` and every writer
that materialises an absent activation key. Issue #6435; the stored-format
contract itself stays with #6527/#6518.

## Terms

| Term | Meaning |
| --- | --- |
| Activation stem | the artifact file name without its extensions (`acme-skill-file`) |
| Declared id | the artifact's `id:` field (`acme-skill-id`), or `profile-id:` for agent profiles |
| Effective set | what is in force for an activation key while that key is absent |
| Required floor | the org packs' `required_<plural>` ids, in force for a required-only kind (`skill`) |

## Guarantees

1. **One stored spelling.** Every `activated_<plural>` list entry this code writes
   is an activation stem. Declared ids and `<kind>:<id>` URNs are accepted as
   input and stored as the stem (`IdentityIndex.stored_spelling`).
2. **One spelling rule.** The effective set unions scanned stems with the service
   mapping's declared ids through `IdentityIndex` in **one** place, used by both
   the resolved path and `fallback_ids`.
3. **Every applicable kind and layer.** An id≠stem artifact in any declared org
   pack, the project layer or the built-in layer appears exactly once in the set,
   by its stem, whichever pack order declares it.
4. **Required floor.** An absent required-only key materialises the org-required
   ids as stems, including those inherited through an `extends:` chain.
5. **Collision refusal preserved.** A required id whose file name another layer
   uses for a different id raises `ActivationIdCollisionError` (Decision
   `file_name_collision`) before anything is written; nothing is written.
6. **Fail closed.** An unresolvable set reports `resolved=False` with a reason;
   `mission-type` and `skill` never resolve through the seam.
7. **Unknown tokens tolerated.** An id the identity index does not know (a
   service-only artifact) stays in the set as given, so it cannot vanish; this is
   not a spelling guarantee and does not change the ambiguity policy (#6433).

## Out of scope

- Stored-format or id-spelling contract changes (#6518/#6527 own those).
- Unknown-token / ambiguity policy (#6433 owns it).
- Migrating existing lists to the stem spelling: they take the new spelling on
  their next write (#6527).
