---
work_package_id: WP17
title: 'Phase 2a-2: projection component and ledger line codec'
dependencies:
- WP05
requirement_refs:
- FR-004
- FR-009
- FR-012
- NFR-003
- NFR-005
- NFR-006
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/projection/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/projection/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/**
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP17 - Phase 2a-2: projection component and ledger line codec

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the `domain.projection` component (the port of the oracle's `Projector`, framework-free) and the JSON-capable `adapter.out.filesystem.codec.LedgerLineDecoder` (the one place ledger lines are decoded), each test-first, and raise the `domain` line of the JaCoCo class-count floor for the classes added here.

## Context

- This WP is the second half of what the plan calls phase 2a-1; the first half (domain core) is WP05, which this WP depends on. Sequence in lane-b: WP05, this WP, WP06 (application layer, which uses the codec through the in-memory source), WP18. WP07 (Python oracle) is independent and concurrent.
- Plan sections 13 "Who decodes ledger lines", "Projection", ArchUnit rules 1 and 12 (WP18 enforces them; write to them now); data-model.md. Spec FR-004 (L-rows classification), AC-9g (projection), FR-012, NFR-005, NFR-006.
- **Python references to read before coding**: `tests/contract/_mission_status_payloads.py` (`Projector`), `contracts/tools/leak_patterns.py`, `src/specify_cli/status/store.py` and the installed `spec_kitty_events` 10.4.0 `status`/`diary` modules (`read_events_raw`, `parse_diary`: read the INSTALLED source in `.venv`, not memory), `contracts/mission-status/schemas/{Project,MissionHead,MissionOverview}.yaml`.
- JaCoCo: `domain.projection` is covered by the `domain.*` thresholds (line >= 90%, branch >= 80%); the codec package is outside the scope (adapter). The floor file `src/test/resources/jacoco-class-floor.properties` was created by WP05 with the `domain` line: raise it to the real class count after this WP's classes exist (T027 step 5). Never lower it.
- Public repo: test data uses synthetic ULIDs and `<repo>` placeholders; no absolute home paths.
- Cross-WP appends: the tracer files are appended (append-only, own commit; they are in no WP's `owned_files`).
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The floor file is created by WP05 and raised here. This WP creates: no file by that list.

## Subtask T027: `domain.projection` (the port of the oracle's `Projector`)

**Purpose**: AC-9g redaction, with the leak-class value built by the caller (the domain does no I/O).

**Steps**:
1. Read `Projector` in `tests/contract/_mission_status_payloads.py` and `contracts/tools/leak_patterns.py` (STRICT and HUMAN host-path patterns, email pattern, secret patterns, two tokens `[path]` and `[email]`). Which of `missionId`, `slug`, `friendlyName`, `targetBranch`, `missionType` is strict or human is the oracle's; WP07 records it in the manifest. Implement `LeakClasses` (a value holding compiled `java.util.regex.Pattern`s handed to the constructor), `Projector` (strict field: served clean, nulled when nullable and not clean, refused when non-nullable and not representable; human field: each host path replaced by `[path]`, each email by `[email]`, a leak left after redaction is refused) and `ProjectionError` carrying the field name only, never the value.
2. Tests on INLINE patterns (the real `leak-patterns.json` is WP07/WP10): friendly name with a host path and an email; a nullable strict field with a path-shaped value => `null`; a non-nullable strict field with a token-shaped value => `ProjectionError` whose message has no value.
3. Note the Python `re` versus `java.util.regex` risk (PR in plan.md section 13): do not "fix" a pattern here; per-pattern probe tests belong to WP09 against the generated file.
4. Revert-fails: serve `friendlyName` unprojected and the host-path test goes red.
5. Floor: after the projection classes exist run `./gradlew jacocoTestReport`, recount the classes under `org.speckitty.missionstatus.domain.*` and raise the `domain.*` line of `jacoco-class-floor.properties` to that count (never lower it).

**Files**: `domain/projection/*` (~200 lines), tests (~200).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.domain.projection.*'`.

## Subtask T028: `LedgerLineDecoder` codec (the one place ledger lines are decoded)

**Purpose**: Python-parity decoding in a JSON-capable, file-API-free sub-package of the outbound adapter (plan.md section 13; E-13).

**Steps**:
1. Package `adapter.out.filesystem.codec`: depends only on `domain..` and itself (ArchUnit rule 12), uses no file API and no `SafeFiles`; JSON via the Jackson dependency the build already declares (WP03), or a minimal parser if the WP02 record says so. Decide duplicate keys, number forms and non-UTF-8 by reading Python's behaviour (`json.loads` with its defaults: last duplicate key wins; `NaN`/`Infinity` accepted by Python; large ints; the exact failure classes). Pin each decision with a test and cite the Python behaviour in the test name.
2. Produce the `domain.model.LedgerLine` records (declared by WP05 T023 step 3 together with the sealed kind, the `MalformedReason` enum and the tail-classification enum; the codec declares none of these types, so the application port can carry them without importing the codec, ArchUnit rules 2 and 12) per data-model: 1-based physical line number, SHA-256 of the raw line bytes (the cursor invariant), `byteLength`, `kind` = `Status(StatusEvent)` | `Lifecycle(LifecycleEvent)` | `Ignored` | `Blank` | `Malformed(reason)` with `not_json`, `not_object`, `not_utf8`; plus the unterminated-tail classification `none` / `whitespace` / `non_whitespace` (a whitespace-only tail is no event and no tear). Malformed meaning mirrors `read_events_raw`/`parse_diary`: non-JSON line, non-object line, lane row missing a required key, unknown lane, unknown `kind` are all classified so the application can map them to L3a/L3b (`ledger_unparseable` with the 1-based line number; none for invalid UTF-8) and L4/L4b (`ledger_torn_tail`).
3. CRLF: the raw line includes `\r` for the digest and position (a CRLF ledger differs from its LF twin in `streamCursor`, equal in counts).
4. Test each class at the codec (this is the "tested once at the codec" half; the in-memory source in WP06 and the filesystem adapter in WP19 test it again through the sources).
5. Revert-fails: treat an unknown lane as a default lane and the L3a classification test goes red; strip `\r` before hashing and the CRLF cursor test goes red.

**Files**: `adapter/out/filesystem/codec/*` (~300 lines), tests (~400).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.codec.*'`.

## Definition of Done

- `domain.projection` and the codec exist, every behaviour red-first with its revert-fails mutation observed; the projection tests run with no Spring context.
- `cd services/mission-status-api && ./gradlew check` is GREEN at this WP's tip with the raised `domain` floor; a red `check` is not an exit state (report BLOCKED instead).
- The codec is the only decoder of ledger lines and has no file API; no JSON, Spring or file API in `domain`.
- Native legs stay green at this tip (nothing here touches the hello route).
- Evidence recorded per subtask with `spec-kitty agent tasks mark-status <Txxx> --status done`; tracer entries appended.

## Risks

- Python parity subtleties (duplicate keys, `NaN`, number forms): decided only from the installed Python source, never from memory.
- Python `re` versus `java.util.regex`: do not "fix" a pattern here; per-pattern probe tests belong to WP09 against the generated file.

## Reviewer Guidance

- Verify `ProjectionError` and every diagnostic carry no value, path or line text.
- Verify the codec is the only decoder and has no file API; check each revert-fails row was observed.
- Verify the `domain` floor was raised to the real count, not guessed.

## Implementation command

`spec-kitty agent action implement WP17 --agent claude`
