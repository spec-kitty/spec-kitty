---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: charter-pack-cutover-01M491G6
mission_id: 01M491G6102N7NRMAW3219Z2F9
generated_at: '2026-10-06T19:51:46.430639+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/charter-pack-cutover-01M491G6/spec.md
    sha256: 5608a77a83e9faa6512f209e4c2ef90c1be935b8beaa7be15ee213119034e578
  plan.md:
    path: kitty-specs/charter-pack-cutover-01M491G6/plan.md
    sha256: 10495adc85ae3d7608ad549592a2399c69751fc9566464eca1fce997cd4ed6a2
  tasks.md:
    path: kitty-specs/charter-pack-cutover-01M491G6/tasks.md
    sha256: 4ed09fd18fa44d48534dbb368e7f789c8a50d82657c88f6179e9597bb19f0a59
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 39e75cd05429257095cd1d6111fa75460e0430e5f147d3a97d8c921916bd76af
verdict: ready
issue_counts:
  critical: 0
  low: 8
  medium: 0
  high: 0
  info: 0
findings:
- id: I2
  severity: low
  category: inconsistency
  summary: Plan Technical Context and spec OD-10 say about 19 work packages; tasks.md has 25.
- id: I3
  severity: low
  category: inconsistency
  summary: 'Plan IC-08 (package split) is sequenced after IC-03 and IC-06, but tasks puts WP04/WP05 before WP06 and WP13 (deliberately: the move carries the default_pack import).'
- id: U2
  severity: low
  category: underspecification
  summary: The FR-018 closed token list leaves out some renamed spellings (CLI --kind doctrine-skill, project_doctrine_graph, DefaultCharterPackMissingError, LegacyDoctrineRootWarning); only per-WP tests guard them.
- id: C2
  severity: low
  category: coverage
  summary: WP01 test_fr011_exempt_invocations covers only upgrade/init/--version/--help; the merge-driver and hook exemptions in FR-011 are tested only in WP14 unit tests.
- id: I5
  severity: low
  category: inconsistency
  summary: occurrence_map.yaml leaves out the FR-018 tombstone files, the tests/doctrine -> tests/charter_offering move and the kernel/doctrine_root.py -> kernel/charter_pack_paths.py replacement as explicit entries.
- id: I6
  severity: low
  category: inconsistency
  summary: The U1 fold landed only in WP11's Done-means; contracts/upgrade-migration.md detect() and WP12 T062 step 5 still say a reportable [] makes detect() true with no first-application condition.
- id: C3
  severity: low
  category: coverage
  summary: The C1 fold gives WP14 T070 the FR-016 allowlist sites, but neither WP14 owned_files nor its T070 Files line nor its DoD lists them; two belong to downstream WP19/WP20, and WP03 still names WP25 as their allowlist owner.
- id: A2
  severity: low
  category: ambiguity
  summary: data-model.md now fixes the org-charter schema_version 1 rule, but WP17 T085 step 3 still tells the implementer to decide it, and no test pins v1 acceptance.
---

## Specification Analysis Report

Mission `charter-pack-cutover-01M491G6` (#3732). This is a re-run after commit `1cc1d4f1`, which folded findings I1, C1, A1, D1, I4 and U1 of the previous report (`bd91fc6e`) into spec.md, data-model.md and tasks WP05, WP07, WP08, WP11 and WP14. The analysis started from the previous report. Each folded finding was checked against the artifacts, the five LOW findings it did not fold were re-checked, and the fold diff was checked for new issues. plan.md and tasks.md are unchanged since the previous run; only spec.md changed among the three core artifacts.

### Status of the folded findings

| Prior ID | Prior severity | Status | Evidence |
|----------|----------------|--------|----------|
| I1 | MEDIUM | Resolved | spec.md:126 now says "upgrade the repository root, then merge the target branch into the lane; never rebase". This matches plan.md:108, contracts/cli.md:70 and quickstart.md:12. |
| C1 | MEDIUM | Resolved, with residue C3 | WP14 T070 gains a step that repoints `drg_activation.py:163`, `_drg_helpers.py:177`, `org_pack_loader.py:536`, `org_pack_discovery.py:158,269`, `mission_step_contracts/executor.py:583` and `_doctrine_collect.py:94,141,173`, and deletes their allowlist rows. The work is assigned now. The ownership bookkeeping is incomplete (C3). |
| A1 | MEDIUM | Resolved, with residue A2 | data-model.md "Enforced activations" now fixes the rule. New files declare `schema_version: 2`. A `schema_version: 1` file validates while it carries no retired field. `doctrine_pack_id` is rejected with `RETIRED_PACK_FIELD`. WP17 still calls this a decision (A2). |
| D1 | MEDIUM | Resolved | The DoD of WP07:278 and WP08:243 now requires `__all__` in `presets.py` and `preset_application.py`. No artifact contradicts the charter convention. |
| I4 | LOW | Resolved | WP05:164 now attributes the `default_pack` deletion to WP06 (dead caller) and WP09 (module). This matches WP06:116 and WP06:202. |
| U1 | LOW | Resolved in WP11, with residue I6 | WP11 Done-means makes `detect()` evaluate the reset predicates only before the migration is recorded as applied. The contract and WP12 were not updated to match (I6). |

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I2 | Inconsistency | LOW | plan.md:26; spec.md:242 (OD-10) | Both say "~19 work packages"; tasks.md has 25. | Update the figure, or leave it as historical. |
| I3 | Inconsistency | LOW | plan.md IC-08 vs tasks.md dependency graph | IC-08 is sequenced after IC-03 and IC-06, but WP04/WP05 run before WP06 and WP13. This is deliberate: WP05 carries the `default_pack` import, which is legal inside `charter`. | Optionally align the plan IC-08 line with the tasks order. |
| U2 | Underspecification | LOW | spec.md FR-018 closed lists; contracts/cli.md:22 | Some renamed consumer-visible spellings are missing from the closed token list: `--kind doctrine-skill`, `project_doctrine_graph`, `DefaultCharterPackMissingError`, `LegacyDoctrineRootWarning`, `LegacyTrackerOwnershipKeyWarning`. Only per-WP acceptance tests guard them. | Accept as is, or add them in a later spec revision before WP25. |
| C2 | Coverage | LOW | tasks/WP01:329; tasks/WP14 | The acceptance-level exempt test lists only `upgrade`, `init`, `--version` and `--help`. The merge-driver and hook exemptions in FR-011 and US2-5 are tested only in WP14's unit tests. | Optionally extend the WP01 regression guard with a `merge-driver-*` invocation and the hook entry points. |
| I5 | Inconsistency | LOW | occurrence_map.yaml | The map covers these items only through category rules (`import_paths` names `kernel.doctrine_root`). It has no explicit entry for the FR-018 tombstone files (`skills/retired.py`, `offering/packs/retired_fields.py`), the `tests/doctrine/` → `tests/charter_offering/` move (WP23) or the `kernel/doctrine_root.py` → `kernel/charter_pack_paths.py` replacement. | Add do_not_change entries for the tombstones and move entries for the two moves. |
| I6 | Inconsistency | LOW | tasks/WP11:97; contracts/upgrade-migration.md:12 (`detect`); tasks/WP12 T062 step 5 (the second "5.") | WP11 now limits the `[]`, stale-list and kind-gate predicates in `detect()` to the first application. The contract's `detect()` section still lists "an `activated_*` key ... is `[]`" with no condition. WP12, which wires the resets into `detect()` after WP11, still says "a reset or a reportable `[]` makes `detect()` true". An implementer who follows WP12 or the contract would bring back the U1 defect. The effect is dry-run and doctor noise only; runner selection is unaffected. | Add the first-application condition to the contract's `detect()` section and to WP12 T062 step 5, and add the restored-`[]` case to WP12's test list. Optionally renumber WP12's duplicate step "5." |
| C3 | Coverage | LOW | tasks/WP14:132 (T070), :153 (Files), frontmatter owned_files, DoD; tasks/WP03:193 | WP14 T070 must now edit `drg_activation.py`, `_drg_helpers.py`, `org_pack_loader.py`, `org_pack_discovery.py`, `mission_step_contracts/executor.py`, `_doctrine_collect.py` and `charter_pack_path_allowlist.yaml`. None of these is in WP14 `owned_files`, the T070 "Files" line or the DoD. Ownership is split: `org_pack_loader.py` belongs to WP19 and `org_pack_discovery.py` to WP20, both downstream, so the "files owned by completed upstream WPs are logged follow-up edits" rule (WP14:111) does not cover them. `drg_activation.py` has no owner. WP03:193 still tells the allowlist author to name WP25 as the owner of these entries, which no longer matches WP14. | List the sites in the T070 Files line and add a DoD item ("FR-016 allowlist holds no entry owned by WP14"). State that edits to WP19/WP20-owned files are logged pre-emptive edits. Change the owner in WP03:193 to WP14. |
| A2 | Ambiguity | LOW | tasks/WP17:251 (T085 step 3), :328; contracts/errors.md; data-model.md "Enforced activations" | data-model.md now fixes the v1 rule, but WP17 T085 still says "Decide and record whether ... still validates (recommended: yes)". Its scope ("no activations") is also narrower than data-model's ("as long as it carries no retired field"). contracts/errors.md is unchanged. No WP01 or WP17 test pins v1 acceptance, which A1 had recommended. | Point WP17 T085 step 3 at the data-model rule instead of a decision. Add a WP17 test that a `schema_version: 1` org-charter with `charter_pack_id` entries validates and one with `doctrine_pack_id` is rejected. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 activate-a-preset | Yes | WP08 (T041–T045), WP01 T004 | |
| FR-002 built-in-presets-as-pack-data | Yes | WP07 (T037, T040) | After FR-015 (WP06) |
| FR-003 init-equals-default-preset | Yes | WP09 (T046–T049) | |
| FR-004 presets-from-any-pack | Yes | WP07 T036, WP08 T043 | |
| FR-005 retire-preset-registry | Yes | WP06 T033, WP09 T048, WP13 T066–T069 | I4 attribution now correct |
| FR-006 charter-homes | Yes | WP15 (T075–T079) | |
| FR-007 remove-doctrine-group | Yes | WP16 (T080–T082) | |
| FR-008 skill-families | Yes | WP18 (T088–T091), WP12 T063 | |
| FR-009 three-names | Yes | WP17 (T083–T087) | See A2 |
| FR-010 rename-retired-tier | Yes | WP04, WP05, WP17, WP19–WP23 | |
| FR-011 remove-read-side-shims | Yes | WP14 (T070–T074) | |
| FR-012 one-upgrade-migration | Yes | WP10, WP11, WP12 | See I6 |
| FR-013 glossary-and-citations | Yes | WP24 T107 | |
| FR-014 reachability-pins | Yes | WP25 T112 | |
| FR-015 promotion-from-effective-set | Yes | WP06 (T030–T034) | |
| FR-016 project-pack-root | Yes | WP02, WP03, WP14 T070 | Allowlist drain now assigned (C1 resolved); see C3 |
| FR-017 messaging | Yes | WP24 T108, T109 | |
| FR-018 vocabulary-gate | Yes | WP25 T111 | |
| FR-019 preset-format | Yes | WP07 T035, T038, T039 | |
| NFR-001 effective-set-preserved | Yes | WP01 T002–T003, WP12 T065 | |
| NFR-002 gates-close-empty | Yes | WP05 T028, WP14 T070, WP16, WP25 T113 | |
| NFR-003 cli-latency | Yes | WP08 T045 | |
| NFR-004 upgrade-idempotence | Yes | WP11 T060, WP12 T065 | See I6 |
| SC-001..SC-005 | Yes | WP08, WP12, WP25, WP15, WP24 | |

The C-008 ordering edges are unchanged by the fold. WP14 depends on WP12 and WP13 and precedes WP19 and WP20, so its new edits to `org_pack_loader.py` and `org_pack_discovery.py` land before those renames.

**Charter Alignment Issues:** none. D1 is resolved. No artifact conflicts with a charter MUST.

**Unmapped Tasks:** none. T001–T115 map through each WP's `requirement_refs`.

**Fold side effects checked:** no edits outside the seven files. No new requirement, WP or dependency edge. No new placeholder or `rc7` mention. The two new DoD items in WP07 and WP08 are separated from the rest of their list by a blank line, which is cosmetic only. The three LOW findings I6, C3 and A2 are incomplete propagations of the fold, not new defects in the plan.

**Metrics:**

- Total Requirements: 23 (19 FR + 4 NFR); plus 8 constraints and 5 success criteria
- Total Tasks: 115 subtasks in 25 work packages
- Coverage %: 100% (23/23)
- Ambiguity Count: 1 (A2)
- Duplication Count: 0
- Critical Issues Count: 0 (high: 0, medium: 0, low: 8)

**Issue-matrix heads-up (non-gating):** unchanged from the previous report. #3732, #4400, #5323, #5826, #4573, #5825 and #5409 are addressed or bound issues and will need issue-matrix rows. Follow-up and context citations need none.

### Next Actions

- No CRITICAL, HIGH or MEDIUM findings. All four previous MEDIUM findings are resolved. Implementation (WP01) can start.
- Optional hygiene, best done before the WP each one affects:
  - I6 before WP12: add the first-application condition to the `detect()` section of contracts/upgrade-migration.md and to WP12 T062 step 5.
  - C3 before WP14: list the repointed files in T070 Files and the DoD, and change the owner in WP03:193 to WP14.
  - A2 before WP17: point T085 step 3 at the data-model rule and add the v1-acceptance test.
- I2, I3, U2, C2 and I5 can be left as is or folded into the next edit of an artifact.
