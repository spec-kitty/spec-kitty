# Fixture — TEMPLATE + ASSET org pack (WP08 e2e)

Mission `doctrine-template-asset-kinds-01KX2YQ7` (#2495 + #2469). These
fixtures are consumed by `tests/charter_offering/test_template_asset_e2e.py` and
exercise the **real** loader (`charter.offering.drg.org_pack_loader.load_org_pack`),
merge (`charter.offering.drg.merge.merge_three_layers`), and query
(`charter.offering.drg.query.resolve_transitive_refs`) path — no mocked shortcuts.

Modeled on a realistic Regnology-shaped org pack (see
`kitty-specs/doctrine-template-asset-kinds-01KX2YQ7/quickstart.md`).

## Layout

- `valid_pack/` — the positive e2e fixture (TT-1 / AT-1 / AT-7):
  - `drg/fragment.yaml` declares the DRG nodes (a `styleguides` node, two
    `templates` nodes, one `assets` node) and two `requires` edges:
    `styleguide:regnology-house-style --requires--> template:meeting-minutes
    --requires--> asset:company-logo`. `template:meeting-minutes-orphan` is
    declared with **no** edges (the valid-orphan-template case).
  - `styleguides/regnology-house-style.styleguide.yaml` — a real, schema-valid
    styleguide artifact (for `pack_validator` parity; the DRG node itself
    comes from `fragment.yaml`, not this file).
  - `templates/regnology/meeting-minutes-template.md` — the template content
    (TEMPLATE has an empty glob pattern — this file is not schema-scanned by
    `pack_validator`; it exists for on-disk realism only).
  - `assets/company-logo.asset.yaml` — the sidecar manifest (`pack_validator`
    scans `assets/*.asset.yaml` **non-recursively** — the manifest file itself
    must sit directly under `assets/`, matching `_scan_files`'s non-styleguide
    branch). `path: regnology/company-logo.png` — the referenced blob is
    nested (real PNG bytes, never schema-validated).

- `duplicate_asset_pack_a/`, `duplicate_asset_pack_b/` — two independent org
  packs each declaring `assets` node id `company-logo` (AT-3 /
  `duplicate_asset_id`).

- `duplicate_template_pack_a/`, `duplicate_template_pack_b/` — two independent
  org packs each declaring `templates` node id `quarterly-report` (TT-3 /
  `duplicate_template_id`).

- `path_escape_pack/assets/evil-manifest.asset.yaml` — `path: ../../../etc/passwd`
  (AT-4 / `asset_path_escape`).

- `bad_mime_pack/assets/*.asset.yaml` — a malformed-shape mime and a
  path-extension mismatch (AT-5 / `asset_mime_invalid`).

## Non-goals

These fixtures do not exercise charter activation (`asset`/`template` are
excluded from `CHARTER_KIND_TOKENS` by design — see `_NON_AUGMENTATION_ELIGIBLE_KINDS`)
or the migration extractor (WP05's scope).
