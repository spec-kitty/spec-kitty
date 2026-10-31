# Issue matrix — upgrade-cutover-preserves-retired-commands-01M68J8W

One row per issue referenced in spec.md. `in-mission` = fixed by a WP in this mission (non-terminal; must
reach `fixed` / `verified-already-fixed` / `deferred-with-followup` before mission `done`).

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #6547 | upgrade: ledger cutover restores the per-project command files 3.1.2 retired | in-mission | WP01 red-first reproduction + WP02 supersession declaration; verdict set at wrap-up |
| #6431 | fix(upgrade): settle the version floor on first ledger adoption; cap selection at the requested target | not-applicable | Cited for context only: its adoption baseline covers first adoption, but a ledger cut over before it (the defect shape) is not re-baselined. No work owed; C-004 keeps it untouched. |
| #6589 | fix(upgrade): supersede the 3.2.5 and 3.2.6rc3 gitignore backfills by rc8's narrowing | not-applicable | Cited for context only: the supersession seam this mission declares through. No work owed. |

Valid `Verdict` values: `fixed`, `verified-already-fixed`, `deferred-with-followup`, `in-mission`, `not-applicable`.
