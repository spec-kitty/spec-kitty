# Contract: the shared selection resolver (#6686)

An internal seam contract, not an HTTP/JSON contract. It pins the interface two
writers depend on and the behaviour each of them is allowed to assume. The
implementation is `src/charter/activation/selection.py`, exposed on
`charter.activation.api`.

## Why it exists

`charter interview` and `4.0.0rc8_promote_interview_selections` both turn an
interview selection (`answers.yaml` `selected_<kind>`) into an activation-list
stem. They each owned a copy of that resolution loop, and they disagreed: the
interview resolved through the layer-aware identity index, the upgrade against
the built-in pack alone, so a valid org-pack selection was reported unresolved
and never promoted. This resolver is the one rule.

## Surface

```python
from charter.activation.api import (
    SelectionResolution,   # (stems, unresolved)
    SelectionResolver,     # the resolver
    UnresolvedSelection,   # (kind, raw_id, ambiguous) + .urn
)

resolver = SelectionResolver.build(repo_root)                       # layers from the project
resolver = SelectionResolver.build(repo_root, offering_root=root)   # caller already resolved the built-in layer
```

| Member | Contract |
| --- | --- |
| `build(repo_root, *, offering_root=None)` | Indexes exactly the layers `charter context` reads: project pack, org packs, built-in (`IdentityIndex.build`). One build per run is the caller's budget. |
| `knows(kind, raw_id) -> bool` | Whether any layer declares the token (declared id, stem or `<kind>:` URN). |
| `stem(kind, raw_id) -> str \| None` | The activation stem, or `None` when no layer knows the token. Raises `ActivationIdCollisionError` for a known identity no file stem can represent (Decision `file_name_collision`). |
| `spell(kind, token) -> str` | The stored spelling: the stem when one answers, else the token as written. This is the comparison form for a list already stored (#6423). |
| `stems(kind, raw_ids) -> set[str]` | `spell` over a list; the set form a caller compares a stored list with. |
| `resolve(selections, *, refuse_ambiguous=False) -> SelectionResolution` | Resolves `{kind: ids}` in the caller's order. `stems` is keyed `activated_<kind.plural>`, deduped by stem, first spelling wins, and holds only kinds with at least one stem. `unresolved` lists every id that did not resolve. |

## Policies the caller owns (deliberately not the resolver's)

| Case | Upgrade (`refuse_ambiguous=False`) | Interview (`refuse_ambiguous=True`) |
| --- | --- | --- |
| Id no layer knows | Recorded in `unresolved` (`ambiguous=False`), **reported** in the warning, not promoted | Recorded in `unresolved`, **warned** per kind, not promoted |
| Known identity, no representable stem | Recorded in `unresolved` (`ambiguous=True`), reported in the same warning, not promoted | Raises `ActivationIdCollisionError` **before any write** |

Both writers format their own message from `UnresolvedSelection`; the resolver
never prints.

## Invariants

1. **One authority.** The resolver holds no precedence rule of its own; it
   delegates to `IdentityIndex`. It must not rescan doctrine roots or cache
   across runs.
2. **Stem spelling only.** A declared id resolves to its file stem and is never
   returned verbatim for a known, representable artifact (#6423, #2529).
3. **No writes.** The resolver returns values; the write path stays
   `resolve_activation_write_target` + `promote_activations`.
4. **Seam only.** `src/specify_cli` reaches the resolver through
   `charter.activation.api`; a direct `charter.activation.selection` import from
   a consumer fails the boundary ratchet.

## Callers

| Caller | Where |
| --- | --- |
| `charter interview` | `src/specify_cli/cli/commands/charter/interview.py`, `_promote_interview_selections` (and `_stem_spelled_config` via `spell`) |
| Upgrade step | `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py`, `_resolve_selections` |

## Free consequence, recorded on purpose

`IdentityIndex` indexes mission-step contracts, so a `selected_mission_step_contracts`
entry now resolves and promotes in the upgrade step, where `kind_vocabulary`
could resolve neither writer before (#6686 "Notes"). Pinned by
`test_a_mission_step_contract_selection_resolves_and_promotes`. The interview
does not capture step contracts, so that side is unchanged.
