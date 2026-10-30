# Discovery: audit collisions only between selectable Missions (#6757)

Mission: `audit-collision-selectable-missions-only-01M66YHT`
Grounded on `origin/main` = `512567eee71e31bb39f580c4f7acf8b865e9d1b2`
(repo `spec-kitty/spec-kitty`), 2026-10-30.

## 1. The issue still reproduces on current main

A scratch fixture — git repo, committed `kitty-specs/001-real` (with
`mission_id` + `mission_number`) beside a committed `kitty-specs/001-tracked-spec-only`
holding only `spec.md` — run through the audit engine's public entry point
(`run_audit(AuditOptions(repo_root=...))`, which is what
`doctor mission-state --audit` calls):

```
001-real                [('AMBIGUOUS_SELECTOR', 'warning'), ('DUPLICATE_PREFIX', 'warning')]
001-tracked-spec-only   [('AMBIGUOUS_SELECTOR', 'warning'), ('DUPLICATE_PREFIX', 'warning'), ('IDENTITY_MISSING', 'error')]
{"findings_by_severity": {"error": 1, "info": 0, "warning": 4}, ...}
```

So the healthy Mission `001-real` is reported as colliding with a folder that
Mission selection cannot reach. Reproduced exactly as the issue describes.

## 2. Not superseded

- `git log -S "residue_aware" -- src/` finds exactly one commit:
  `9ffe19ab9a fix(doctor): keep the audit engine on its own Mission rule; residue
  is doctor-identity only (#5875)`. That commit *created* the behaviour in
  question, at the operator's instruction; nothing later touches it.
- No open or merged PR mentions #6757 (`gh pr list --search 6757`).
- #5875 (PR #6775, merged) carries the operator ruling of 2026-10-27: "folders
  with only a `spec.md` (no `meta.json`) are residue, not Missions; selection and
  the resolver will stop listing them, with a doctor finding and remedy."
  #6757 is the follow-up that finishes that ruling inside the audit engine's
  collision reports; it does not contradict the ruling — it applies it.
- #5812 (`b84d94d539`) introduced `is_mission_dir` and `RESIDUE_DIRECTORY`;
  #5875 then split the read-side rule (`is_selectable_mission_dir`,
  `residue_aware=True`) from it. Both are already on main and unchanged here.
- Nothing in `docs/changelog/CHANGELOG.md` claims the collision population was
  narrowed. The #5875 entry explicitly says the engine's findings "must not
  change", which is the state #6757 asks to correct for the two collision codes
  only.

## 3. Where the defect lives

`src/specify_cli/audit/engine.py`, `run_audit()`:

- `identity_states = audit_repo(options.repo_root)` — the **default** walk
  (`residue_aware=False`), deliberately chosen in #5875 so the engine keeps its
  looser `is_mission_dir` population for `IDENTITY_MISSING`.
- `_compute_repo_findings_by_slug()` then feeds that same population into the
  three repo-level identity reports:
  - `find_duplicate_prefixes(repo_root)` — default walk again,
  - `find_ambiguous_selectors(identity_states)` — the default-walk states,
  - `DUPLICATE_MISSION_ID` grouping — over the same states.

A residue folder is therefore a first-class collision member even though
`is_selectable_mission_dir` says no selector can reach it.

`src/specify_cli/status/identity_audit.py` already has everything needed:
`find_duplicate_prefixes(..., residue_aware=True)` skips residue rows, and
`find_ambiguous_selectors()` skips `state == "residue"` rows. Calling those two
with the residue-aware population is the whole fix — no new predicate.

## 4. Decisions

**D-1 — Two populations, one code path.** The engine keeps
`audit_repo(options.repo_root)` (default) for the per-mission
`IDENTITY_MISSING`/identity findings and for `DUPLICATE_MISSION_ID`, and adds
`audit_repo(options.repo_root, residue_aware=True)` as the **collision**
population: `find_ambiguous_selectors(selectable_states)` and
`find_duplicate_prefixes(repo_root, residue_aware=True)`. Rationale: the issue's
ask, and #5875's own two helpers already encode exactly the split.

**D-2 — Do not narrow `IDENTITY_MISSING`.** The residue folder must keep its
`IDENTITY_MISSING` (error) finding, so `doctor mission-state --audit --fail-on
error` keeps exiting 1 on the repro fixture. That is the #5875 contract and
`tests/audit/test_engine_keeps_its_mission_rule.py` pins it; only the collision
half of that test changes. Keeping the error also keeps the existing
`_residue_result`/`RESIDUE_DIRECTORY` behaviour for folders the engine's rule
already rejects untouched.

**D-3 — Recompute the group, never drop a member.** Filtering the *reported
members* of a group after grouping would silence a real collision when a residue
folder joins it (`082-alpha`, `082-beta`, `082-leftover`). The group must be
built over the selectable population, which is what
`find_duplicate_prefixes(residue_aware=True)` already does; the engine must not
post-filter.

**D-4 — A pre-identity Mission still collides.** `is_selectable_mission_dir`
accepts a folder with a tracked `meta.json` and no `mission_id` (the `legacy`
state, which `backfill-identity` repairs). Collision detection must keep
reporting those, so the residue rule is the filter — never "has a `mission_id`".
Pinned by a test.

**D-5 — No change to `doctor identity`.** It already passes
`residue_aware=True`; this Mission does not touch it. Pinned by the existing
`tests/doctor/test_identity_audit.py` residue assertions.

**D-6 — Cost, and the stale-docstring obligation.** One extra `audit_repo` walk
plus one extra `find_duplicate_prefixes` walk. Each builds its own
`TrackedMissionPaths` memo and `find_duplicate_prefixes` takes no `tracked=`, so
the worst case is **two** additional batch `git ls-files` probes (never one per
Mission); measured, the full engine stays ~0.07 s on a 210-Mission scratch repo.
Because the population split changes the truth of four docstrings in
`specify_cli/status/identity_audit.py` (module, `audit_repo`,
`find_duplicate_prefixes`, `find_ambiguous_selectors`) and of the inline
`#5875 / FR-008` comment in `run_audit()`, those comments are part of the change:
one canonical contract description, corrected in the same PR (C-003).

## 5. Open questions

None blocking. Two things a reviewer should know, and one documented non-goal:

- **Non-goal, named by the issue but not asked for:** the `IDENTITY_MISSING`
  finding on a `meta.json`-less folder carries the `backfill-identity` remedy,
  and `backfill-identity` skips folders with no `meta.json`. The issue lists that
  as context ("Refs #5875"), and its ask is explicitly to *keep* the engine's
  population for `IDENTITY_MISSING`. Changing that remedy is a separate,
  user-facing decision; this Mission leaves it as is and says so in the PR's
  `## Deferred`.
- **Fixture/custom scan root:** the engine treats a non-default `scan_root`
  (audit fixtures) as all-Missions and passes `repo_root=None` down to the scan.
  The collision pass stays anchored on `repo_root` (as it is today), so fixtures
  behaviour is unchanged; the pin tests cover the default scan.
- **`--mission` scoping:** `--mission` filters the per-mission scan, not the
  repo-level collision groups (today's behaviour). Unchanged by this Mission.
