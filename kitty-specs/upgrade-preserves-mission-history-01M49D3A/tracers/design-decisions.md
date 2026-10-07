# Design decisions

- **D-1** (operator, 2026-10-06): `upgrade` never runs the repair. It reports only, and only under drain. New ADR in `docs/adr/4.x/`, because no existing ADR records the #4775 consent.
- **D-2** (operator): #5812 is part of this Mission.
- **D-3** (boundary squad): there is one row serializer, the store's, and lane rows round-trip through `StatusEvent`.
- **D-4** (boundary squad): there is one `is_mission_dir` predicate in `context/mission_resolver.py`. Unifying the other walkers is deferred.
- **D-5 (WP02):** string actors are kept verbatim; the repair used to lower-case them, which broke byte-identity. `lanes.json` absent-recovery (#4758) is kept but scoped to lanes topology; this cut the dogfooding corpus errors from 52 to 2 (both genuine fail-closed). Rows with explicit null optional keys from earlier repairs are kept verbatim, so 374 files are not re-churned.
- **D-6 (WP02):** no `errored_missions` field. The doctor already renders `validation_errors`, which stays the single source.
- **D-7 (pre-PR):** the nested-project path base was fixed (`--show-prefix`). The existence fallback now applies only outside a git work tree.
- **D-8 (deferred):** `upgrade --json` does not report blockers under drain; this needs an operator ruling. `_select_mission_dirs` still walks `kitty-specs/` itself instead of through `_iter_mission_dirs`; a follow-up is needed.
