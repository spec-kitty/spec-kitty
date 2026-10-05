---
affected_files: []
cycle_number: 2
mission_slug: mission-status-contract-1-1-01M42XJC
reproduction_command:
reviewed_at: '2026-10-05T05:42:10Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 reopened: operator ruling, no new contract version (2026-10-05)

**Ruling.** The contract is unreleased on `main` (`1.0.0-SNAPSHOT`, never tagged). This mission's additions ship in that same release. There is no 1.1.0 and no tag. The spec and plan are amended (c225cd525) and analyze is `ready` (5109b4d80). The spec wins over the WP07 prompt wherever they differ.

**Required rework (lane-a):**
1. `contracts/mission-status/openapi.yaml`: set `info.version` back to `1.0.0-SNAPSHOT`. WP03 set it to `1.1.0-SNAPSHOT`.
2. `contracts/mission-status/CHANGELOG.md`: remove the `## 1.1.0-SNAPSHOT` section and merge its content (the additions, the 12 snake_case kinds, the ReviewCycle null rule, deferred gaps, route coverage, provisional names) into the existing `## 1.0.0-SNAPSHOT` section. Follow that section's structure and style, with no duplicate headings. Fix the wrap-up item while you are there: do not claim "snake_case like every enumeration", because `MissionLifecycleEvent` types are PascalCase.
3. The proof module (`tests/contract/test_mission_status_contract_1_1.py`):
   - Rename `minor_proof_problems` to `additive_proof_problems` (plan D-P10) and drop every version-bump rule and mutation (`1.0.1`, `2.0.0`, `1.1.0`).
   - Assert additivity against the main contract tree. `breaking_check.py` fails any bundle change against a baseline with the SAME `info.version` (`BUNDLE_CHANGED_VERSION_SAME`), so the proof uses a scratch copy of the main tree with a lowered version and asserts the `counts:` line (`baselines=1`, `breaking=0`), as the amended plan describes.
   - Add a permanent test that the tree's `info.version` equals main's (`1.0.0-SNAPSHOT`).
   - The CHANGELOG assertions target the merged `1.0.0-SNAPSHOT` section.
   - Keep every non-version rule: scope, terminology, credential kinds, refusal pairing, required examples, route coverage. Also fix the wrap-up item: narrow the terminology scan's `x-derived` exemption to symbol names, so that prose `rule:` text is scanned.
4. Tests from other WPs that assert `1.1.0-SNAPSHOT`, if any (grep), follow the ruling.
5. Make no kitty-specs edits. The WP07 prompt and tasks.md wording is superseded by the spec (analysis D6 to D8).

**Proof:**
- red-first for the new version-equality test and the additive proof;
- revert experiments on the merged CHANGELOG assertions and on the additive rule;
- the ten contract checks, especially `provisional_check`, `structure_check` and the CHANGELOG/version checks, which now expect a matching `1.0.0-SNAPSHOT` heading;
- `breaking_check` per the plan recipe;
- the full architectural battery;
- the tool-job selection, ruff, `ruff format --check .`, TID251 and cutover-guard.
