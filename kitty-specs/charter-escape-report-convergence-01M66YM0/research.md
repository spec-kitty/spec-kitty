# Research: Charter escape-report convergence (#6733)

Discovery step, 2026-10-30. Mission `charter-escape-report-convergence-01M66YM0`, maintainer-agent P1.
Base: `main@512567ee` (root checkout `/home/exedev/work/sk-6733`), `spec-kitty` 4.0.0rc8.

## D1 — The issue reproduces on current `main`, and the three surfaces really do disagree

Built a throwaway project (`/tmp/repro6733`) with one configured org pack
(`.kittify/config.yaml` → `charter_packs.org.packs[0] = {name: example-org, local_path: …}`),
a `pack.yaml` (`pack_level: org`), a `drg/fragment.yaml` with one authored node
`{id: team-asset, kind: assets, body_path: ../../../../etc/hostname}`, and one sidecar
`assets/team-logo.asset.yaml` with `path: ../../../../etc/hostname`.

Observed on 4.0.0rc8 (installed CLI = current `main`):

| Surface | `body_path` escape | asset `path` escape |
| --- | --- | --- |
| `doctor charter-packs --json` | `org_drg.body_path_escapes[0].code = ORG_FRAGMENT_BODY_PATH_ESCAPE`, one `org_drg.errors` entry | `org_drg.asset_path_escapes[0].code = ORG_ASSET_PATH_ESCAPE`, one `org_drg.errors` entry |
| `charter status --json` | nothing — `org_layer.errors = []` | nothing — `org_layer.errors = []` |
| `charter org validate <pack>` | nothing — exit 0 for that fault | `asset_path_escape` error, exit 1 |

That is the issue, exactly. Not superseded: `git log -S ORG_FRAGMENT_BODY_PATH_ESCAPE` shows only
`a4369f9b6d` (the #6418 fix, PR #6756), which deliberately scoped itself to `doctor charter-packs`
and left #6733 open; no changelog entry, ADR or later commit touches these two surfaces.

**Decision**: fix both surfaces in place. No re-scoping of `doctor charter-packs`.

## D2 — The predicates to route through already exist and are already the authority

- `charter.offering.drg.org_pack_loader.find_body_path_escapes(fragment, pack_root)` → `BodyPathEscape`
  (`code = ORG_FRAGMENT_BODY_PATH_ESCAPE`), judging only `OrgDRGFragment.authored_nodes` through
  `resolve_relative_path_within_root` (#6418).
- `charter.offering.assets.repository.find_asset_path_escapes(pack, pack_root)` → `AssetPathEscape`
  (`code = ORG_ASSET_PATH_ESCAPE`), resolving each org asset through `AssetRepository.resolve_path`.
- Registry-aware wrappers beside `load_org_drg`: `find_org_body_path_escapes(repo_root, fragments)` and
  `find_org_asset_path_escapes(repo_root, fragments)`, both pairing each fragment with its pack's
  **effective root** from `load_pack_registry`.

`doctor charter-packs` already uses the registry-aware wrappers
(`src/specify_cli/cli/commands/_charter_pack_collect.py::_record_body_path_escapes/_record_asset_path_escapes`).
`charter status` (`src/specify_cli/cli/commands/charter/_status_collectors.py::_collect_org_layer_status`)
loads the same fragments through the same `load_org_drg` but never asks for the escapes.

**Decision**: `_collect_org_layer_status` calls the same two registry-aware wrappers, in the same
position relative to the merge (immediately after the fragments load, before `merge_three_layers`), and
appends each `escape.message` to its existing `errors` list. No new `org_layer` key (an unread payload
slot is the inert-schema defect the collector's own docstring ratchets against), and no structured
finding object on a `list[str]` channel.

## D3 — `charter org validate`: mirror the existing asset finding, do not restyle it

`pack_validator.validate_pack` already has an asset containment leg
(`_validate_asset_manifests` → `_check_asset_path_containment`, category `asset_path_escape`, message
`asset path '…' escapes the pack's assets/ root: …`). It has no fragment `body_path` leg, even though
it loads the pack through `load_org_pack` (the single schema authority) at `_validate_org_fragment`.

**Decision**: add a `body_path` leg that calls `find_body_path_escapes(loaded_fragment, pack_dir)` — the
same predicate doctor uses — and reports each escape as a `ValidationIssue(category="body_path_escape")`
with `artifact_type="drg"`, `artifact_id=<node id>`, `file=<drg/fragment.yaml>`. Rationale for
`body_path_escape` rather than doctor's `ORG_FRAGMENT_BODY_PATH_ESCAPE`: the validator's `category`
vocabulary is snake_case and already carries `asset_path_escape`; reusing it keeps
`charter org validate` backward compatible (C-002) while the finding stays structured and stable. The
message is the predicate's own (`BodyPathEscape.message`), so the three surfaces say the same sentence.

The validator's asset leg keeps its own message/category; it is not restyled.

## D4 — The "conformance-corpus case" bullet, and what the repository actually has

The issue's fourth bullet asks for a conformance-corpus case "so the spec-kitty-charter replacement
inherits the rule". Surveyed the ground:

- `tests/charter/conformance/activation_ledger_cases.yaml` — `schema: activation-ledger-conformance/1`,
  the portable corpus for **activation answers** (#6099, #6534). Its header states the file itself is
  the corpus; its sections are `effective_set`, `identity`, `readers`, `cascade`, `deactivation`,
  `ledger_migration`. It has no pack-validation section, and #6534 (the corpus export task) is **on
  hold** by operator ruling while the spec-kitty-charter contract changes.
- `tests/scenarios/charter/` — the BDD promise suite; `PR-CHARTER-SHARING-004` already gates the
  guarantee through `doctor charter-packs` only.
- `contracts/charter/` is planned but absent.

**Decision**: add the case as a second, small, plain-data corpus in the same directory
(`pack_containment_cases.yaml`, `schema: pack-containment-conformance/1`) with a runner that asserts
**all three surfaces** against each pack shape. It is additive, touches no existing schema or corpus
row, and states the rule as data a replacement offering can be run against. Extending the
activation-ledger corpus instead would have meant a schema change on a corpus another (on-hold) task
owns.

**Open question for the operator** (not blocking): should the pack-containment table later be folded
into the #6099 harness corpus as its own section, so the replacement consumes one file rather than two?

## D5 — Red-first, and what "red" means here

Each fix gets its failing test through the pre-existing entry point (charter, ATDD-first):
`charter status --json` via the CLI, `charter org validate` via the CLI, and the corpus runner which
drives those same two plus `_collect_org_layer_data` (doctor's real collector).

The corpus runner is red today on the status surface and on the validate/body_path surface, which is
also the non-vacuity control for the convergence claim (SC-001/SC-002: today 1 of 3 and 2 of 3).
The contained-pack case is the paired positive control (SC-003).

## D6 — Blast radius and boundaries

Files: `_status_collectors.py` (status), `pack_validator.py` (validate), the new corpus + runner,
`docs/api/charter-commands.md`, `docs/changelog/CHANGELOG.md`. No change to `charter.offering.api`,
the layer chain, `pyproject.toml`, the doctor collector, or the predicate modules (C-003).

## Open questions

1. Corpus home for the long term (D4) — operator decision, not blocking this Mission.
2. Whether `charter status` should ever grow structured escape records instead of messages
   (NFR-003 keeps the schema unchanged here; a structured key would be a separate, additive change).
