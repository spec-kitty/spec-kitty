# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · DM 01M66YN5CCFXQF4DBWDSVNSJBG: find_asset_path_escapes(fragment) imports OrgDRGFragment from charter.offering.drg.org_pack_loader rather than a Protocol. One named type beats a restated shape; assets already imports drg.org_pack_config; no import cycle (org_pack_loader imports no asset module).
