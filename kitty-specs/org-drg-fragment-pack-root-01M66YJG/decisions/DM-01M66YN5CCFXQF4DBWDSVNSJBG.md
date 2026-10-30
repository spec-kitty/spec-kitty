# Decision Moment `01M66YN5CCFXQF4DBWDSVNSJBG`

- **Mission:** `org-drg-fragment-pack-root-01M66YJG`
- **Origin flow:** `specify`
- **Slot key:** `specify.api.asset_predicate_signature`
- **Input key:** `asset_predicate_signature`
- **Status:** `resolved`
- **Created:** `2026-10-30T17:45:23.596976+00:00`
- **Resolved:** `2026-10-30T17:45:29.833372+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Both containment predicates must take only the fragment. find_body_path_escapes lives beside OrgDRGFragment; find_asset_path_escapes lives in charter.offering.assets and has no fragment type today. Which type contract should the asset predicate take on its new fragment-only signature?

## Options

- Import OrgDRGFragment from charter.offering.drg.org_pack_loader (explicit, one named type, sibling import inside charter.offering)
- A narrow structural Protocol in charter.offering.assets (pack_name + pack_root) so the asset module never imports the org fragment type

## Final answer

Import OrgDRGFragment from charter.offering.drg.org_pack_loader. One named type beats a Protocol that restates the fragment's shape as a second authority, and charter.offering.assets already imports charter.offering.drg.org_pack_config, so the sibling direction is established. The org_pack_loader module imports no asset module, so there is no cycle.

## Rationale

_(none)_

## Change log

- `2026-10-30T17:45:23.596976+00:00` — opened
- `2026-10-30T17:45:29.833372+00:00` — resolved (final_answer="Import OrgDRGFragment from charter.offering.drg.org_pack_loader. One named type beats a Protocol that restates the fragment's shape as a second authority, and charter.offering.assets already imports charter.offering.drg.org_pack_config, so the sibling direction is established. The org_pack_loader module imports no asset module, so there is no cycle.")
