# WP05 independent review, cycle 2 — approved

Reviewer: codex:gpt-6:reviewer-renata:reviewer, freshly resolved via AgentProfileRepository.
Official invocation: e92629ffbb214a10ac0821d84c9739f0.
Reviewed HEAD60d2d0b1a; cycle1a2aea67b0; original dependency105ef7167.
Full official prompt content checked against the previously read cycle1 prompt: only invocation/topology/review-cycle metadata differs. Primary mission contracts, original R1/R2 findings and cycle2 handoff reviewed. No product edits.

## Findings disposition

R1 FIXED: archive create, materialize and verify catch MissionSelectorAmbiguous at owned command boundaries. JSON uses the existing canonical json_error authority, retaining handle and candidates. Human and JSON both exit1. Verify diagnostics also uses the selector renderer, retaining useful identity rather than collapsing into a generic diagnostic failure. New materialize helper is private and has its live caller in materialize; resolution algorithm unchanged.

R2 FIXED: tasks status opts into a typed NoReturn error-handler hook before the shared selector prints or exits. Missing flag produces canonical mission_required and exit1; missing/ambiguous mission produces canonical diagnostic code and exit2, matching established human behavior. Opted-in fallback calls the same pure resolve_mission used by the legacy wrapper, without duplicating selector rules. Callback raises before legacy rendering, preventing double output. Default error_handler=None leaves other task families on their original code paths, envelope shapes and exits; status human mode also retains that path.

Independently reran the original12case real filesystem/Git/metadata probe. Every result is controlled SystemExit. All6JSON outputs parse as one canonical error object with empty stderr. Paired exits: archive/materialize/verify1; status ambiguous/missing2; status absent1. No active-mission mutation or mocks. Full output: parent/WP05-cycle2-independent-repro.log.

Independently ran new ambiguous-selector/status-selector/default-helper regressions:9passed16deselected1.34s. Includes verify diagnostics sibling, candidate metadata, exact exit parity, unchanged mission files, and old shared-helper absent/missing envelope behavior. Log: parent/WP05-cycle2-independent-tests.log.

## History, wiring and scope

- Red99e37ca93 precedes functional60d2d0b1a; red log7failed16deselected32.01s confirms failures before implementation. Original cycle1 evidence and rejection remain intact.
- Root explicitly authorized tasks_shared optional hook, tasks.py two identity reexports and narrow existing status/selector/compatibility assertions. No overlap with other WP product files. Existing patch seam tasks._find_mission_slug retained.
- Compatibility map adds both production helpers and raises exact count179→181. Completeness and identity assertions remain active; no exemption/removal. Historical unrelated symbol families unchanged.
- New private _status_selector_error is used by live _st_resolve_dirs; _report_ambiguous_selector is used by verify plus diagnostics; _resolve_selected_dir by materialize. Existing public build_kanban_status remains called by show_kanban_status. No unused authority/module.
- Unchanged first-cycle zero-WP status, pure builder/wrapper, glossary errors/empties, dashboard registry return and success-schema behavior remain covered. This correction only adapts failure branches; no new CLI flag, dependency, successful schema, selector algorithm or hosted setting change.

## Validation evidence

- Independently: ruff check all12cycle2changed files passes; whole-repo ruff format check1934files passes; git diff --check clean; lane checkout clean at reviewed HEAD.
- Independent strict mypy over all12files reports one inherited tasks_shared no-any-return at572. Standalone shared-file logs show the two pre-existing errors at572/766; exact baseline source at552/746 reproduced the same two. Verified baseline source bytes equal git show a2aea67b0:tasks_shared.py. No changed hunk touches those sites and no suppression added. Other11files strict-clean per handoff. This is documented baseline debt, not a clean-all-files claim.
- Verified final affected gate390passed52.84s and selectors/architecture68passed56.39s. The unchanged92remaining caller cases passed in the immediately preceding expanded run; its sole failure was the subsequently corrected compatibility count, now covered by final390. No failed case omitted; intermediate failures retained in logs.
- Earlier1553pass8skip33baselinefailures remain tracked under#4671/#4672; no waiver or assertion they were fixed. Root owns integrated full CLI/mission gates.
- Original first-cycle lack of separate tidy commit remains recorded as process deviation; cycle2 fix-mode red/fix separation is correct and narrow extraction serves the complexity gate.

## Eight mandatory checks

| Check | Verdict | Evidence |
|---|---|---|
| Dead code | PASS | Every introduced helper has live registered production caller; identity reexports enforced |
| Synthetic-fixture test | PASS | Real temporary Git/config/metadata, registered callbacks, no literal-output substitution |
| Silent empty return | PASS | Error hook is NoReturn and emits controlled failure; legitimate empty status remains success |
| FR coverage | PASS | R1/R2 close selector C1/C2/C4/C5 gaps; prior status/glossary/root-helper/empty coverage retained |
| Frozen surface | PASS | Only owned files plus explicit authorized scope extensions changed; frozen doctor authority untouched |
| Locked decision | PASS | Canonical errors, exit fidelity, happy payload invariance and bounded opt-in scope retained |
| Shared ownership | PASS | Root coordination authorized shared-helper/test/reexport changes before implementation; no WP overlap |
| Production fragility | PASS | Expected ambiguity now controlled; handler raises only at error boundary; default clients unaffected |

## Verdict

APPROVE WP05 at60d2d0b1a. R1/R2 fixed, no remaining blocking finding within reviewed scope. No issue-matrix terminal verdict fabricated and no GitHub publication performed.
