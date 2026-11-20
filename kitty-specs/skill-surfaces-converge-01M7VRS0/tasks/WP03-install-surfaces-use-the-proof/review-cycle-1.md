---
affected_files: []
cycle_number: 1
mission_slug: skill-surfaces-converge-01M7VRS0
reproduction_command:
reviewed_at: '2026-11-20T09:37:49Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review feedback 1: changes requested

Reviewer: claude::reviewer-renata (independent). Reviewed c759fe3f85 (red) → 04689e37b4 (fix).

Verified:
- `test_global_skills_historical_proof.py` + `test_project_skills_historical_proof.py`: 9 passed. On the red commit's
  sources, 7 fail (the 2 that pass there are the "edited stays" controls).
- The proof is per `<skill>/<rel>`, a symlink or directory is never proven by bytes, and a retired directory's
  files are proven at their own paths.
- The stamp is withheld only for `stale_canonical`; a custom skill does not block it.
- The project path keeps its backup, because the backup branch keys off the original `canonical`.
- The FR-011 agreement test is present.

## Blocking

### B1. The historical lookup re-reads every destination file (NFR-001, plan "one JSON read per process")

`_is_shipped_render` calls `prepared.observe(target, role="destination_probe")` for every destination file, and
`AssetPreparation.asset()` then observes the same target again. `observe` has no cache (it calls
`node_state(path, read_content=True)` each time), so every installed global skill file is read and hashed twice
per assessment.

Measured on an isolated HOME (553 files, warm, no effects), `assess_global_agent_skills()` median of 7, two runs:

| build | median |
|---|---|
| base a053b674 | 0.708 / 0.718 s |
| lane-b (WP02) | 0.808 / 0.814 s |
| lane-c (WP03) | 0.908 / 0.857 s |

WP03 adds roughly +6–12% on top of lane-b. The mission is at about +24% against NFR-001's budget of "within 10% of
base" on the startup sync. That runs on every command.

Fix direction: decide predecessor proof from the observation `asset()` already makes, not from a second one. For
example, `asset(..., canonical_predecessor: bool | Callable[[FileState], bool])` (or a separate
`predecessor=` callable) evaluated on `asset()`'s own `before`. Do the same in `_prepare_project_skills`, which
already holds `before`, so it's fine. Include a timing figure (base vs. this lane) in the hand-back.

## Non-blocking

- N1. `kept_global_skill_files()` recomputes the catalog and roots (`_discover_registry()`,
  `_unique_global_roots()`) independently of the ones the assessment used, while the stamp rule uses the
  assessment's own `skills` / `roots`. Under a `selection`, or with a catalog that changed between calls, the two
  could disagree. Consider deriving both from the assessment (or recording `canonical` on it).
- N2. The `bool(...)` wraps around `is_historical_render` paper over its `functools.cache` return type. Annotating
  the cached `_renders` (or wrapping it in a typed accessor) in WP01's module would remove them. This is
  cosmetic.

Note for the orchestrator, outside WP03's scope: lane-b (WP02) alone measures +14% over base (two inventory
files read, a per-key `lexists` placement probe, and `_stage_inventories` serializing on every run). That is
reported separately.
