# Contract: the org containment predicates judge a fragment's carried root

**Mission**: `org-drg-fragment-pack-root-01M66YJG` (spec-kitty/spec-kitty#6731, follow-up to #6418)
**Status**: Current — shipped by this mission
**Owners**: `charter.offering.drg.org_pack_loader.find_body_path_escapes`,
`charter.offering.assets.find_asset_path_escapes` (both re-exported by `charter.drg`)

## Why this contract exists

One fact — which filesystem root an org pack was loaded from — must have one
authority. Before #6731 there were two: `load_org_pack` resolved the effective
root (`subdir` applied) and stamped it into `OrgDRGFragment.source_ref` as a
display string, while the doctor's containment wrappers re-read the pack
registry through `_org_pack_roots_by_name` to recover the same root. A change to
`.kittify/config.yaml` between those two reads could make the doctor judge a
pack against a root it was not loaded from.

## The contract

1. **The loader stamps the root, once.** `load_org_pack(pack_name, pack_root,
   layer_index)` receives the effective root and sets it on the returned
   fragment at a single success return. `OrgDRGFragment.pack_root` returns it.
2. **The root is not serialized.** It is a pydantic `PrivateAttr`. It is absent
   from `model_dump()`, `model_dump_json()` and `model_json_schema()`, so the
   doctor's `--json` output and any fragment comparison are unchanged. It
   survives `model_copy()`; it does **not** survive a
   `model_validate(model_dump())` round-trip.
3. **A fragment that cannot supply its root refuses.**
   `OrgDRGFragment.pack_root` raises `OrgPackRootUnavailableError(pack_name)`
   when the attribute was never stamped. There is no default root and no
   fallback lookup: a containment check must report "the check could not run".
4. **The predicates take only the fragment.**
   - `find_body_path_escapes(fragment) -> list[BodyPathEscape]` judges each
     authored node's `body_path` against `fragment.pack_root`.
   - `find_asset_path_escapes(fragment) -> list[AssetPathEscape]` judges each
     org-provenance asset sidecar's `path` against `<fragment.pack_root>/assets`.
   Neither accepts a root argument, so a caller cannot pair a pack with a root
   from a second source.
5. **Consumers aggregate per fragment, in fragment order.**
   `specify_cli.cli.commands` calls both through the `charter.drg` facade and
   concatenates per-fragment results, which preserves finding order, messages,
   JSON keys and exit codes.
6. **One registry read per doctor run.** The containment flow reads
   `.kittify/config.yaml` exactly once, inside `load_org_drg`. No containment
   code path calls `load_pack_registry`.

## What the tests pin

| Guarantee | Test |
| --- | --- |
| The loader stamps the effective root (incl. `subdir`) | `tests/charter_offering/drg/test_org_body_path_escapes.py::test_loaded_fragment_carries_its_effective_root`, `::test_configured_pack_carries_the_subdir_effective_root` |
| The root is outside the serialized surface | `::test_carried_root_is_not_part_of_the_serialized_or_schema_surface` (with `pack_name` as positive control) |
| `model_copy` keeps it; a dump/reload drops it | `::test_a_copy_of_a_loaded_fragment_keeps_its_root`, `::test_a_fragment_rebuilt_from_a_dump_cannot_supply_its_root`, `tests/charter_offering/assets/test_org_asset_path_escapes.py::test_a_fragment_rebuilt_from_a_dump_cannot_supply_its_root` |
| The predicates take one argument | the whole of both offering test modules |
| The activation wrappers and the re-read are gone | `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py::test_the_activation_layer_no_longer_owns_the_containment_wrappers` (with `load_org_drg` as positive control) |
| Exactly one registry read per doctor run | `::test_collect_org_layer_data_reads_the_pack_registry_once`, `::test_render_org_layer_section_reads_the_pack_registry_once`, `::test_org_layer_containment_flow_reads_the_registry_exactly_once` |
| Doctor refusals unchanged | the #6418 refusal matrix in the same module (`exit_code_reflects_*_containment`, human-output tests) |

## Deliberately out of scope

`charter.offering.drg.override_policy.pack_roots_from_fragments` still derives a
pack root from `source_ref` for the override-sanction half. That is a second
*derivation* of the same fact (not a registry re-read) and is tracked as
spec-kitty/spec-kitty#6828.
