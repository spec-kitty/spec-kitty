---
work_package_id: WP16
title: 'Phase 5e: Host/Origin smoke stage, README, docs and changelog close-out'
dependencies:
- WP11
- WP15
requirement_refs:
- FR-015
- FR-009
- NFR-008
- C-010
- C-011
- C-012
- C-013
- SC-004
- SC-005
- SC-007
- SC-008
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T080
- T081
- T082
- T083
- T084
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/
create_intent:
- .github/workflows/mission-status-api.yml
- services/mission-status-api/README.md
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/nativesmoke/**
- services/mission-status-api/src/test/resources/nativesmoke/**
- services/mission-status-api/README.md
- docs/development/reference/ci-gate-mechanics.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP16 - Phase 5e: Host/Origin smoke stage, README, docs and changelog close-out

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Complete the Mission: add stage `hostOrigin` to the native smoke request set (so AC-15b and AC-15e are met), extend the service README, document the workflow in `ci-gate-mechanics.md`, add the changelog line, and run the Mission-level close-out checks (Reflexivity diff check, terminology, leak scan, glossary check). Reviewers of different expertise read the parts separately (the `hostOrigin` stage is Java/JSON plus one workflow argument; T081-T083 are documentation); T084 is the only cross-WP check, and it reads the diff of the other WPs without editing any of their files.

## Context

- Plan phase 5 close (plan.md section 11 row 5, "Docs impact", section 1 shared-surface bullets, section 4 review diff check, section 2 "Terms decision (NFR-008)", section 14 E-3/E-5/E-9). Spec FR-015 (AC-15b Host and Origin refusals, AC-15e), FR-009, NFR-008, C-010..C-013, SC-004, SC-005, SC-007, SC-008, Reflexivity items 1-6.
- Depends on WP11 (the filter, for stage `hostOrigin`) and WP15 (the last workflow edit; so docs describe the final workflow). The `nativesmoke` package and `requests.json` were created by WP03/WP12 and extended by WP13 (ordering-based, PLAN-NEW5-001); `README.md` was created by WP19 as a stub with the allowlist fenced list (keep that fence EXACT: the AC-10b parity test parses it); `ci-gate-mechanics.md` and `CHANGELOG.md` are shared surfaces (nine of the eleven open PRs measured on 2026-10-10, #6004, #6002, #5957, #5954, #5953, #5950, #5945, #5944 and #5540, also edit the changelog; re-run the query before the claim: expect a textual conflict on `[Unreleased]`; resolve by keeping both sides, never reorder their lines).
- Terms (NFR-008): use only glossary terms in prose - Mission, Work Package, Lane (verified with `.venv/bin/spec-kitty glossary list`), Tail cursor and `log_truncated` (defined in `docs/context/system-events.md`; Tail cursor has status `candidate`). "Reducer", "status event", `Diagnostic`, "overview read model", "conformance golden" are code identifiers: the README defines each in its own short terms list at first use and never presents them as glossary terms. No `docs/context` file and no `contextive-map.yaml` change; `.venv/bin/python scripts/generate_contextive_glossaries.py check` must stay clean. Mission, never "feature".
- The docs spelling/changelog/freshness gates bite `docs/` edits: `scripts.docs.check_spelling` (scope `docs/`, `packs/built-in/`, root `README.md`; `services/**/*.md` is outside it, but write the README to the same standard), `scripts.docs.check_changelog_style` (headings `Breaking`, `Upgrade Notes`, `Added`, `Changed`, `Fixed`, `Internal`; impact-first one-liners), the page's `updated:` frontmatter must be refreshed. No new docs page (so no `toc.yml`, inventory lockfile, Divio frontmatter or index changes).
- Public repo / C-010: no absolute home paths, no private or customer detail anywhere in the diff.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The workflow and the build test are created by WP04 and WP03, amended here (and the README is created by WP19 for WP16). This WP creates: no file.

## Subtask T080: Stage `hostOrigin` of `requests.json` and the smoke replay

**Purpose**: AC-15b's Host and Origin refusals on all four legs; raises the digest request floor.

**Steps** (red-first: add the stage entries with a deliberately wrong expected status, see the smoke red, then correct):
1. Append a stage `hostOrigin` group set: one request per refusal class with LITERAL expectations: foreign Host (`evil.example:<port>`) => 403 `request_refused`; the container-rejected Host `evil.example@127.0.0.1:<port>` => 400 (container; assert status only, and that the body holds no secret/path); a foreign Origin (`https://evil.example`) with an accepted Host => 403; the accepted-Host/Origin controls => 200. Placeholders `<port>` are substituted by the harness. Raw-socket requests need a harness extension (the HTTP client normalises headers): extend the WP12 helper in the same package, test code only.
2. Raise `stages.hostOrigin.requestCountFloor` and the workflow's `digests --request-floor` argument (the sum over stages present) - the pin of WP12 ties them. This is an in-map edit of the workflow: `.github/workflows/mission-status-api.yml` is in this WP's `owned_files` and this WP is last in the serialisation order of `tasks-overview.md` section 7. Keep it minimal, commit it separately, and keep the WP12 request-floor tie pin green.
3. Revert-fails (observed red once): change one expected status; drop the stage; leave the floor unchanged while adding requests (the tie pin goes red).
4. Rebuild the binary on this workstation (Linux x64, toolchain precondition) and run `./gradlew nativeSmoke -PnativeBinary=<path>`; the other three legs are CI's proof, stated as owed.

**Files**: `requests.json` (+~60 lines), harness extension (~120 lines).
**Validation**: `cd services/mission-status-api && ./gradlew nativeCompile && ./gradlew nativeSmoke -PnativeBinary=<built binary>` (the smoke class is tagged `native-binary`, excluded from `test`/`check`, so `./gradlew test --tests 'org.speckitty.missionstatus.nativesmoke.*'` runs only its untagged JVM-side classes: use it for the `requests.json` parse test); `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_gate_checks.py -q`.

## Subtask T081: Service README

**Purpose**: How to build, run and trust the service (NFR-008).

**Steps**:
1. Extend the WP19 stub: what it is (a detached, read-only, loopback-only service that answers `/api/v1/project`, `/api/v1/missions`, `/api/v1/events` and serves the contract document at `/api/v1/openapi.yaml`); how to run it (`java -jar build/libs/mission-status-api.jar --mission-status.project-root=<project root> --mission-status.port=8787` and the native binary with the same two properties); the complete configuration keys (`mission-status.project-root` required, `mission-status.port` default 8787, `mission-status.stream.queue-capacity` default 1024, the heartbeat key); the loopback and accepted-Host rule (`127.0.0.1:<port>` and `localhost:<port>`; `[::1]` is not accepted and a client resolving `localhost` to `::1` first falls back to `127.0.0.1`); the read allowlist fence (UNCHANGED: AC-10b); what it never reads or writes; the SSE reconnect notes (a scoped client reconnects with its last `id:`; an unscoped client reconnects and sees later rows only after a `slow_consumer` close); the native-binary limitations (unsigned: macOS Gatekeeper and Windows SmartScreen will warn; no auto-update; not on PyPI, not in the wheel); the release procedure pointer (tag `mission-status-api-v*.*.*`, cut by the maintainer).
2. The short terms list (code identifiers, not glossary terms) and a "Tests" section with the exact local commands (`./gradlew check`, `./gradlew nativeCompile nativeTest`, `./gradlew nativeSmoke -PnativeBinary=<path>`, the Python pins) using placeholders only.
3. Verify the fence: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` and the AC-10b Java test (`cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.AllowlistReadmeParityTest'`).

**Files**: `README.md` (~200 lines final).
**Validation**: the AC-10b test green; `grep -nE "/(home|Users)/" services/mission-status-api/README.md` empty.

## Subtask T082: `ci-gate-mechanics.md` subsection

**Purpose**: Maintainers find how the workflow is wired (plan "Docs impact" 1).

**Steps**:
1. Under "Contracts gates" add a "Mission Status API workflow" subsection: what triggers it (path-filtered push/PR, schedule, dispatch, release tag), that it is NOT a router dependency but IS registered in the fleet verdict (`ci-fleet-verdict.yml`, `fleet_verdict.PR_WORKFLOWS`; E-3 superseded 2026-10-11), so a red gate posts the PR `[ci]` comment, that required-check status is a maintainer decision at merge (E-9), the one-slot workflow ceiling (`test_reusable_workflow_ceiling_respected`: 20 files; any further CI need must be a job of this file: E-5), the jobs (`jvm`, `native` x4, `mission-status-api-gate`, `nightly-corpus`, `release`), the digest comparison, how to run locally (commands of section 5), and that the nightly has no exemption mechanism.
2. Refresh the page's `updated:` date. Keep the subsection short; use the page's existing heading style (symptom/repro style).
3. Run `.venv/bin/python -m scripts.docs.check_spelling && .venv/bin/python -m scripts.docs.check_changelog_style` and `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.

**Files**: `docs/development/reference/ci-gate-mechanics.md` (+~40 lines).
**Validation**: the three commands green.

## Subtask T083: Changelog line

**Purpose**: One impact-first `### Added` line (plan "Docs impact" 2).

**Steps**:
1. In `docs/changelog/CHANGELOG.md` under `## [Unreleased]` add `### Added` (if absent) with one line, impact first: a read-only, loopback-only local Mission Status API service is built from `services/mission-status-api/` (Java, Spring Boot, native binaries on four targets); it answers the project header, paged Mission overviews and a change stream from each Mission's ledger and is not part of the PyPI package. Cite #5529. Keep the root `CHANGELOG.md` symlink untouched.
2. If another PR already created `### Added` in `[Unreleased]`, add your line to it; resolve conflicts by keeping both sides.
3. Refresh the `updated:` frontmatter only if the style guard requires it.

**Files**: `docs/changelog/CHANGELOG.md` (+3 lines).
**Validation**: `.venv/bin/python -m scripts.docs.check_changelog_style`.

## Subtask T084: Mission-level close-out checks (Reflexivity diff check, hygiene)

**Purpose**: SC-007, SC-008, C-010..C-013 verified, not assumed.

**Steps** (record each result for the PR "Tests run" section; targeted commands only, never `make test-full` or the bare `tests/architectural/`):
1. Review diff check (plan section 4, spec Reflexivity): `git diff --name-status main...HEAD` shows NO `src/`, `contracts/`, `packs/`, `pyproject.toml`, `uv.lock` or other Mission's `kitty-specs/` path; the `ci-router.yml` diff is ONE filter-group line; the `packs.yml` diff is ONE `--deselect` token; the `.gitattributes` diff is ONE scoped line; exactly two existing pinning tests edited beyond the new ones (`tests/ci/test_contracts_workflows.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`); the only new workflow file is `mission-status-api.yml` (count 20). List any deviation.
2. Selection (SC-007): `scripts.ci.gate_selection.select_gates` with synthetic path sets: a `services/**`-only diff selects no `src`-backed shard; a conformance-only diff selects `tests (contract tools)` and nothing else Python; a `src/**` change does not trigger the native matrix (the routing tests of WP07 already assert it: run them).
3. Leak scan (C-010): `git diff main...HEAD | grep -nE "/(home|Users)/"` finds nothing; no private names. The username-leak policy applies: fix agent-caused leaks before any push.
4. Windows filenames: `.venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py tests/ci/test_mission_status_api_build.py -q`.
5. Glossary and terminology: `.venv/bin/python scripts/generate_contextive_glossaries.py check`; `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`; grep the diff for `feature` in new prose.
6. Mission-wide targeted blast radius (the commands of plan section 5), with a time bound of one run each and no retry: first `test "$(git rev-parse --show-toplevel)" = "<repo root>"` (the checkout this WP runs in; whole-repo commands never run from another directory), then `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` (whole-repo, as CI runs them); the router and pin tests, as the explicit file lists of WP07 T041 step 6 (`.venv/bin/python -m pytest tests/ci/test_contracts_routing.py tests/ci/test_contracts_workflows.py tests/ci/test_mission_status_routing.py tests/ci/test_corpus_blocking_home.py tests/architectural/test_ci_corpus_trigger_completeness.py -q`) and WP04 T022 step 1 (the workflow-enumerating sweep, same file list, `-q`) plus `tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_gate_checks.py -q`; `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py tests/contract/test_gradle_pin_check.py tests/contract/test_verify_pins.py -m "corpus and not windows_ci" -q`. This WP does NOT run `make test-fast` or any whole-repo suite: the `make test-fast` baseline comparison against `research/baseline-red.md` is the orchestrator's pre-PR re-run (`tasks-overview.md` section 10), and pre-existing reds are cited by issue there, never fixed or hidden.
7. Append the Mission-closing tracer entries (approach, friction, decisions) and list the unresolved items for the retrospective: E-5/E-9 (PR notes), E-12/E-13 (awareness), Unverified 1, 7, 15, runner labels, the first nightly result, the maintainer's first tag.

**Validation**: every check listed with its result; deviations reported, not hidden.

## Definition of Done

- Stage `hostOrigin` exists with literal expectations and a tied floor; the four legs and the gate are green on the PR run (CI evidence from the orchestrator) with stage `base` and `hostOrigin`; AC-15b/AC-15e are then met.
- README, `ci-gate-mechanics.md` subsection and changelog line present; docs gates green; AC-10b fence intact.
- The close-out checks of T084 recorded; the shared-surface diff equals the planned list; nothing hosted, no version number, no absolute path.

## Risks

- Changelog conflicts with the open PRs that edit `docs/changelog/CHANGELOG.md` (nine of the eleven open PRs when measured on 2026-10-10 with `gh pr list --repo spec-kitty/spec-kitty --state open --limit 100 --json number,files`: #6004, #6002, #5957, #5954, #5953, #5950, #5945, #5944, #5540; re-run the query before the claim, the count drifts): keep both sides; never reorder.
- The smoke raw-socket requests on the Windows leg: first CI run decides; the JVM leg (WP11) proves the same rows.
- Docs spelling gate rejects code identifiers in prose: put them in code spans.

## Reviewer Guidance

- Confirm the diff check of T084 against the actual `git diff --name-status`.
- Confirm no glossary claim for code identifiers and no "feature" wording.
- Confirm the changelog line is impact-first and the README says what is NOT done (unsigned, no PyPI, no auto-update).

## Implementation command

`spec-kitty agent action implement WP16 --agent claude`
