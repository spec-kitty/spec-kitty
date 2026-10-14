---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-mission-detail-01M4S6D5
reproduction_command:
reviewed_at: '2026-10-14T04:46:26Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review feedback, cycle 1 (reviewer-renata)

Everything the brief asks me to verify passes except one item (F1). The goldens, the census, the oracle drift measurement and the gates are sound; the single finding is a dangling marker that nothing forces WP08 to resolve.

| ID | Severity | Location | Finding | Remedy |
|---|---|---|---|---|
| F1 | 2 | `tests/contract/test_mission_status_conformance.py:1368` (`divergence_problems`); `tests/contract/_mission_status_conformance.py:299` (`RESOLVED_STATE_PENDING`); manifest entries V21 to V25; WP08 prompt `tasks/WP08-p4b-resolved-state-goldens.md` | V21 to V25 carry `fixture: "resolved-state (fixtures arrive with WP08)"` and `fixtures: []`. `divergence_problems` accepts that marker unconditionally, forever. WP08's prompt, named edits and wps.yaml block never mention V21 to V25, D-159 or filling `fixtures` (grep for `V2[1-5]`, `D-159` and `knownDivergence` finds nothing that assigns the work). So the marker names an owner who was never told. If WP08 lands the `resolved-state` class and leaves the entries pending, every test stays green and WP10's `ResolvedStateGoldenTest` has no pinned fixture for five divergences (silent success). | (a) In `divergence_problems`: when the manifest holds a class tagged `resolved-state`, an entry whose `fixture` is `RESOLVED_STATE_PENDING` (or whose `fixtures` is empty with that marker) is a problem, with a control that plants a `resolved-state` class beside a pending entry and expects red. This is green now and turns red the moment WP08 lands without filling the entries. (b) Orchestrator: add to the WP08 prompt (T052/T053 and Definition of Done) that WP08 fills `fixtures` of V21 to V25 (D-159 a to e) in the generator's `KNOWN_DIVERGENCES` rows and tags the covering fixtures `knownDivergence`. (b) is a planning-artifact edit and is not WP07 code. |

## Verified and passing (for the record)
- `--check`: 305 files, 0 differences (lane venv resolves `specify_cli` to the lane's `src`).
- Oracle fidelity: independent script over `detail-populated` (8), `detail-planning-only`, `phases-matrix` Work Packages (12 WPs) calling the real `read_authored_wp_frontmatter`, `reconstruct_wp_view`, `read_events_raw`, `materialize_snapshot`: title, history event ids (time order), resolved subtasks, lane, eventCount and lastEventId equal the goldens, 0 mismatches. Artifact listing sizes equal `stat` for all 14 entries; `status.events.jsonl` is excluded by `ROOT_STATUS_FILES`.
- Drift: #5953 (0730137f4), #6127 (8c89aa90f), #6122 (cabbb47ab) all MERGED on main per `gh pr view`, none an ancestor of lane HEAD. All three `src/` diffs applied to a scratch worktree: `--check` 305 files, 0 differences.
- ASCII-name test `test_the_committed_tree_holds_no_symlink_no_git_entry_and_no_forbidden_name_character` goes red when a `café.md` is added and green when removed; `git ls-files` holds no non-ASCII name.
- Census red-first: deleting `detail-populated/populated/golden/get-mission.json` turns `DetailManifestCensusTest.everyDetailFixtureHoldsTheGoldensItsParityDemands` red; an unlisted fixture directory turns `GoldenSuiteTest.everyFixtureTreeOnDiskIsInTheManifest...` red. Perturbing one byte of three goldens turns `--check` and four honesty tests red.
