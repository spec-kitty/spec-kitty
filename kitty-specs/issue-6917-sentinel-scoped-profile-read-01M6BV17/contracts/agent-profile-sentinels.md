# Contract — `agent_profile_sentinels(ids)`

Pinned surface added by issue #6917 to the charter sole door. It extends — and does not replace —
the `charter-sole-door-bypass-closure-01KZ3WAA` accessor contract
(`kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/contracts/charter-doctrine-service-contract.md`).

## Signature

```python
# src/charter/activation/resolver.py
class ActiveCharterService:
    def agent_profile_sentinels(self, profile_ids: Iterable[str]) -> dict[str, bool]: ...

# src/charter/activation/active_charter_service_builder.py
def build_agent_profile_sentinels(
    repo_root: Path, profile_ids: Iterable[str]
) -> dict[str, bool]: ...
```

## Semantics (pinned)

0. **Total over the request.** The mapping has exactly one key per distinct non-empty
   requested id. `False` means "not a sentinel": the id is unknown to every layer, or its
   profile declares ``sentinel: false``, or the ``applies_to_languages`` gate excluded it.
   Capacity is never signalled by key absence; blank, duplicate and non-``str`` items are
   ignored and contribute no key.

1. **Structural, not activation-gated.** The answer is `profile.sentinel`. No `PackContext`
   activation key participates: narrowing or denying `activated_agent_profiles` never changes it.
   This is the same rationale the FR-001 accessor records for `get_provenance()`.
2. **Same layers, same loader.** Ids resolve through built-in → org packs (declaration order) →
   project overlay using `AgentProfileRepository`'s own parsing, inline-reference rejection, schema
   validation, field merge, skip diagnostics and `applies_to_languages` filter.
3. **Id-scoped.** Only documents that can supply a requested id are parsed, resolved by the
   repository's `<profile-id>.agent.yaml` filename convention in every layer. A profile
   document whose filename stem differs from its `profile-id` is therefore not visible to this
   read; the full repository remains the authority for that case.
4. **No exceptions for data.** An unknown, empty or non-`str` id never raises. An unknown id
   answers `False` (semantics 0); an empty or non-`str` item contributes no key.
5. **Configuration still fails closed.** The accessor performs the same project/org layer
   resolution (and therefore the same config reads) as the builder's other entry points: a
   malformed `.kittify/config.yaml` propagates its structured charter configuration error instead
   of degrading to an empty mapping.
6. **Cheap by construction.** It does not build `PackContext`, the activation ledger, or the shipped
   lineage graph, and it does not materialise the profile catalogue.

## Surface decision (the issue's open question)

The accessor **is** part of the frozen sole-door surface. Rationale: `specify_cli` must not read
profiles outside the door, and the door already owns the two narrower, ungated reads
(`agent_profile_repository`, `raw_repository(kind)`). Adding the scoped form here keeps one
authority for "how a caller asks the charter layer about profiles" and needs no new gate
exclusion. The full repository stays the authority for catalogue, provenance and lineage answers;
this accessor explicitly answers one structural field for a named id set and nothing else.

## Call sites

| Caller | Use |
| --- | --- |
| `specify_cli/cli/commands/agent/tasks_status_cmd.py` | builds the 👤 marker map once per render from the rows' distinct `agent_profile` ids |

No other caller is expected; a future caller that needs activation-filtered governance must use
the gated properties instead.

## Non-goals

- Not a profile catalogue (`list_all()` equivalent).
- Not a governance/activation query.
- Not a replacement for `agent_profile_repository` where provenance, overlays or lineage are needed.
