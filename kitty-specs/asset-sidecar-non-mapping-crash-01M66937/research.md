# Research: asset-sidecar-non-mapping-crash-01M66937

Issue: spec-kitty/spec-kitty#6735. Grounded 2026-10-30 on `main@512567eee7`.

## Reproduction on current main (confirmed)

`AssetRepository(built_in_dir, org_dirs=[<dir containing a sidecar whose YAML
top level is a list>])` raises:

```
AttributeError: 'list' object has no attribute 'get'
```

at `src/charter/offering/base.py:319` (`item_id = data.get("id")` inside
`BaseArtifactRepository._apply_overlay_file`). The per-file
`except (YAMLError, ValidationError, OSError)` envelope cannot catch it, so the
whole repository load aborts instead of skipping the malformed file. Reproduced
directly on `main@512567ee` (fresh clone, `uv sync --frozen --all-extras`).

Not superseded: `git log -S "'list' object has no attribute"` over
`src/charter/offering/` finds no fix; the changelog has no entry; the issue is
open and unassigned (claimed by this mission: comment, assignee `Ivan-Melck`,
labels `status:claimed` + `taken-by-human`).

## Root cause and affected surfaces

`BaseArtifactRepository` loads each overlay file raw (`yaml_parser.load`),
checks only for `None` (empty file → early return), then calls
`self._pre_validate(data, yaml_file)` and `data.get("id")` with no
type guard. A YAML document that parses cleanly but is not a mapping
(top-level list, scalar, bool) passes the parse, then crashes on the first
`data` use. Pre-fix crash lines, per kind:

- six kinds whose `_pre_validate` reads `data` (directive, tactic, toolguide,
  paradigm, styleguide, procedure — all route through `reject_inline_refs`,
  which does `data.get("id", "?")`): crash at `base.py:317` (overlay) or in
  `_load_built_in_items` before Pydantic can reject the document;
- the remaining kinds (default no-op `_pre_validate`): crash at
  `base.py:319` (`item_id = data.get("id")`) on overlay; on the built-in
  tier Pydantic rejects the document as a catchable `ValidationError`.

Two load sites share this shape:

1. `_apply_overlay_file` (org **and** project overlays — both go through
   `_apply_overlay_layer`): the reported crash (#6735 names the org layer;
   the project layer is the same seam).
2. `_load_built_in_items`: calls `_pre_validate(data, yaml_file)` before
   `model_validate`. For the six kinds whose `_pre_validate` reads `data`
   (directive, tactic, toolguide, paradigm, styleguide, procedure — all route
   through `reject_inline_refs`, which does `data.get("id", "?")`), a
   non-mapping built-in file crashes in the hook before Pydantic can reject it
   with a catchable `ValidationError`. Confirmed by direct call:
   `reject_inline_refs(['a'], ...)` raises `AttributeError`. For kinds with the
   no-op default `_pre_validate` (asset, glossary pack, pack skill, mission
   step contract, mission type profile), Pydantic already rejects a
   non-mapping as `ValidationError` and the file is skipped today.

Repository kinds sharing `BaseArtifactRepository` (the "per repository kind"
test matrix, 11 kinds): asset (`AssetRepository`), directive, tactic,
toolguide, glossary pack, pack skill, styleguide, paradigm, procedure, mission
step contract (`MissionStepContractRepository`), mission type profile
(`MissionTypeProfileRepository`). `AgentProfileRepository`,
`MissionTypeRepository` and `MissionTemplateRepository` do **not** inherit the
base class and are out of scope.

## Decisions

- **D1 — fix in the base loader, both tiers.** The guard belongs once in
  `src/charter/offering/base.py`, applied after the `None` early-return and
  before any `data.get` / `_pre_validate` use, in both `_apply_overlay_file`
  and `_load_built_in_items`. Rationale: the issue's proposal says "treat a
  non-mapping document as malformed in the base loader"; fixing only the
  overlay tier would leave the built-in tier crashable for six kinds and split
  the malformed-file semantics by tier. A non-mapping document is malformed in
  both tiers.
- **D2 — skip semantics, not a broader except.** Adding `AttributeError` (or
  `TypeError`) to the `except` tuple would be over-broad (it would also mask
  genuine bugs in merge hooks). An explicit `isinstance(data, Mapping)` guard
  with the usual skip warning is precise. Precedent:
  `src/charter/offering/missions/repository.py` (present-but-non-mapping →
  structured malformed error) and
  `src/charter/offering/model_task_routing/loader.py`
  (`_read_yaml_document` → `None` for non-dict). This mission's seam is the
  warn-and-skip envelope, so the guard warns and skips.
- **D3 — warning text keeps the pinned shape.** The skip warning must read
  `Skipping invalid <layer> <kind> <file>: <reason>` because
  `src/specify_cli/cli/commands/_charter_pack_collect.py`
  (`_parse_skipped_glossary_pack_warning`) parses that fixed shape to build
  structured skip diagnostics. Reason text: `expected a YAML mapping, got
  <type name>` (mirrors the missions repository's wording).
- **D4 — `None` stays absence.** An empty file (parse → `None`) is already an
  early return today; it is absence, not malformed. Only the
  present-but-non-mapping case warns.
- **D5 — tests per repository kind, parametrized.** One parametrized
  regression test covering all 11 kinds on the org-overlay path (the reported
  entry point: repository construction with `org_dirs`), plus built-in-tier
  tests for the two representative shapes: a kind whose `_pre_validate` reads
  `data` (directive — crashes pre-fix) and a kind relying on Pydantic (asset —
  already skipped pre-fix; pins the uniform semantics). Red-first: the
  parametrized org-overlay test fails on pre-fix main.

## Open questions

None — the fix site, semantics and warning shape are decided above. The
`doctor charter-packs` fail-closed behavior named in the issue is a downstream
symptom of the crash; once the repository load no longer raises, that path
returns to its normal per-escape reporting.
