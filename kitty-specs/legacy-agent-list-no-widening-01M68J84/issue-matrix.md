# Issue matrix — legacy-agent-list-no-widening-01M68J84

One row per issue referenced in spec.md. `in-mission` = fixed by a WP in this mission (non-terminal;
must reach `fixed` / `verified-already-fixed` / `deferred-with-followup` before mission `done`).

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #6501 | A missing `.kittify/config.yaml`, or one with no agents section, makes migrations and doctor act on every agent folder | in-mission | WP01 (observed-set read + warning), WP02 (documented default + changelog) |
