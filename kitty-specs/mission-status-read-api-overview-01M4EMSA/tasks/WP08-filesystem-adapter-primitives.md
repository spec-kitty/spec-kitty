---
work_package_id: WP08
title: 'Phase 3a-1: filesystem adapter primitives (resolver, containment, allowlist, listing)'
dependencies:
- WP18
requirement_refs:
- FR-006
- FR-010
- FR-016
- C-005
- NFR-003
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T042
- T043
- T044
- T045
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/ReadDirResolver*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/SafeFiles*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/Allowlist*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/Listing*
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP08 - Phase 3a-1: filesystem adapter primitives

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Implement the primitives of `adapter.out.filesystem`: the read-directory resolver, the NOFOLLOW/containment `SafeFiles`, the explicit read allowlist behind an instrumented recording seam, and the sorted listing, each test-first. `FilesystemMissionEventSource` (which composes them), the flow-level allowlist and read-only tests and the README stub are WP19.

## Context

- Plan phase 3 (the adapter half; the golden half is WP09). Plan sections 7 (Q-3, no git), 11 row 3, 13 (layout, "Cache probe versus read", ArchUnit rules 4, 7, 10, 12), data-model.md "Ports". Spec FR-006 (AC-6a..6f), FR-010 (AC-10a, AC-10e at primitive level), FR-016 (AC-16a recorder), C-005, NFR-003. WP19 continues with the event source and the flow-level checks.
- Depends on WP18 (so the ArchUnit rules guard every adapter class from its first commit), through it WP06 (the outbound port, in-memory source) and WP17 (the codec). It runs CONCURRENTLY with WP07 (Python oracle): no shared files. It must not read WP07's fixtures (they may not exist yet); build tree fixtures in temporary directories inside the tests. WP09 later runs the goldens against this adapter.
- `ProjectRootCheck*` was created by WP03 and is not edited here unless a defect is found (then an out-of-map edit with a one-line rationale, in its own commit).
- This adapter is the ONLY code that touches `java.io`/`java.nio.file` file APIs (rule 7; the `codec` sub-package is excluded and has none). It starts no process and writes nothing (FR-016, AC-10c static rule 10).
- The service reads NO git: path decision is by directory existence and the stored topology only (FR-006; plan Q-3 interim). Do not read `.git/worktrees`, `packed-refs` or `refs/`. The one `.git` exception: `.git/HEAD`, or a `.git` pointer file with a `gitdir:` line and the single file `HEAD` of the directory it names.
- The README stub is WP19 (it needs the `Allowlist` constant this WP creates); WP16 extends it.
- Public repo: tests build trees under JUnit temp dirs; no absolute home paths in sources or messages; fault injection never prints paths.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.

## Subtask T042: `ReadDirResolver` (FR-006 rules 1-4) and the resolver-case table loader

**Purpose**: Which directory is the Mission's ledger read from, decided by stored topology and directory existence only.

**Steps** (test-first, table-driven):
1. Rules: (1) stored `single_branch`/`lanes` => PRIMARY directory, a husk beside it is never consulted; (2) stored `coord`/`lanes_with_coord` => coordination Mission directory `<root>/.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/` when it exists, else (worktree root exists without its Mission directory, or absent) the primary directory; (3) absent `topology` => classified once from `meta.json` `coordination_branch` and the `lanes.json` signal; a corrupt or unreadable `lanes.json` degrades to "no lanes"; an empty/malformed `meta.json` leaves topology unclassified and the read maps to L7 (the application maps; the resolver reports); (4) `meta.json` is read from the Mission's OWN primary directory only; the coordination copy of `meta.json` is never read.
2. A coordination read directory whose REAL path is outside the real path of the project root is treated as "outside this checkout": read the primary directory instead (this fallback covers the ledger directory only). A Mission's OWN primary directory or own `meta.json` that is a symbolic link or resolves outside the root is a different case: L9 (T043).
3. Read `src/specify_cli/missions/_read_path_resolver.py` (`_resolve_existing_for_slug`, `probe_coord_state`, `classify_from_meta`) before coding; cite the function in the test name that mirrors it.
4. A loader reads `conformance/resolver-cases.json` (WP07 writes it; WP09 consumes it for AC-6e) - NOT in this WP: here the table-driven test uses an inline case list of the same shape and WP09 swaps in the file. Keep the case record type compatible: `{id, storedTopology, coordRootPresent, coordMissionDirPresent, lanesJson, expectedClass}`.
5. Revert-fails: ignore stored topology (read the husk when present) and the husk case is red (AC-6d); read the coordination `meta.json` and the allowlist test (T044) is red.

**Files**: `ReadDirResolver*` (~250 lines), tests (~350).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver*'` (every test class of this subtask has a name starting with `ReadDirResolver`, in test package `adapter.out.filesystem`).

## Subtask T043: `SafeFiles` - NOFOLLOW reads and root containment (FR-010, AC-10d)

**Purpose**: Every read opens its target without following a final-component symbolic link and every resolved directory stays inside the real project root.

**Steps**:
1. `SafeFiles.openRead(Path)` uses `LinkOption.NOFOLLOW_LINKS` plus a file-attribute check (regular file) - the equivalent of the `O_NOFOLLOW` of `_read_text_without_following_symlinks` in `store.py`, which Windows lacks. Directory resolution checks the real path against the real path of the project root.
2. Refusal mapping: a symlinked LEDGER => L2 (unreadable, diagnostic `ledger_unreadable`); a symlinked `meta.json` or a Mission directory symlink escaping the root => L9 (Mission omitted, `path_refused`; all other Missions still served). The target's content is never read and never appears in any response or log (instrumented port records no read of it).
3. Symlink fixtures are created at TEST time, never committed. On Windows create a link the runner allows; if the runner cannot create one, the test records an explicit "not run on this leg" line into the JUnit output / job summary (never a silent skip; AC-10d). A control: an ordinary regular file at the same path is read normally.
4. Revert-fails: follow links in `openRead` and the symlink tests are red.

**Files**: `SafeFiles*` (~150 lines), tests (~250).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.SafeFiles*'` (Linux here; the Windows/macOS legs run in CI; every test class of this subtask has a name starting with `SafeFiles`).

## Subtask T044: `Allowlist` and the instrumented recording read port (AC-10a, AC-10e, AC-16a)

**Purpose**: "Ledger and events only" made checkable.

**Steps**:
1. `Allowlist*`: ONE test-visible constant listing the EXPLICIT allowlist with the directory each file is read from (FR-010 items 1-6): resolved-dir `status.events.jsonl`; own primary dir `meta.json`; own primary dir `lanes.json` only when classification needs it; `.kittify/config.yaml` (`project.slug`); `.kittify/metadata.yaml` (`spec_kitty.version`, `spec_kitty.schema_version`); `.git/HEAD` or pointer file + the named git dir's `HEAD`; plus directory listings of `kitty-specs/` and `.worktrees/` (names only, and a stat of the coordination Mission directory). Never `tasks/*.md`, `spec.md`, `plan.md`, artifacts, WP frontmatter, `status.json`, the personal `config.toml`.
2. The instrumented recording port (class names `AllowlistAccess` for the pass-through seam, so it matches this WP's `Allowlist*` ownership glob, and `RecordingAllowlistAccess` for the test recorder): every file operation goes through a small internal seam that records `(path class, open mode)` BEFORE the OS answers (so a swallowed failure is still recorded). Production wiring uses the pass-through implementation; tests substitute the recording one (as a collaborator of `FilesystemMissionEventSource`, not a new named port). Source sets: `AllowlistAccess` (the interface plus its pass-through) lives in `src/main` under the `Allowlist*` glob; `RecordingAllowlistAccess` lives in `src/test` (so it never ships in the production or native image), in package `org.speckitty.missionstatus.adapter.out.filesystem`, covered by this WP's owned test glob `.../adapter/out/filesystem/**`. Visibility is deliberate: both are PUBLIC classes of `adapter.out.filesystem` so that `testsupport` (the only test package allowed to import `adapter.out.filesystem`, ArchUnit rule 11) can pass the recorder in; WP19 T046 gives `FilesystemMissionEventSource` the public constructor taking an `AllowlistAccess` (the production constructor delegates with the pass-through, which `ServiceWiring` uses). The chain that exposes the recorder to the HTTP-served flow is WP08 (public seam), WP19 (constructor), WP09 (`FilesystemFixtureFactory`/`FixtureHandles`), WP10 (`testsupport.http` harness).
3. Primitive-level tests (the flow-level AC-10a/AC-16 checks need the event source and are WP19 T046 step 8): `Allowlist` classifies each path class of the constant as allowed and rejects `tasks/WP01.md`, `spec.md`, `status.json`, the coordination `meta.json` and the personal `config.toml`; the recording seam records `(path class, open mode)` BEFORE the OS answers, so a swallowed failure (a hook that throws on open) is still recorded; the recorder can report the violations of a recorded sequence against the allowlist and flags any non-read-only open mode (create, write, append, truncate, delete-on-close, rename, delete). Positive controls (scratch edits, each observed red once): feed a recorded read of `tasks/WP01.md` and, separately, of the coordination `meta.json`: the violation report is non-empty; feed one write open: flagged.
4. The AC-10b parity test (the constant equals the README's fenced allowlist list) is WP19 T047, which writes the README; expose the constant in a form that test can compare (ordered list of path patterns).
5. AC-10e / rule 10: ArchUnit coverage is WP18's rule set; here only confirm the adapter does not reference `ProcessBuilder`/`Runtime.exec`.

**Files**: `Allowlist*` + recording seam (~200 lines), tests (~400).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.Allowlist*' --tests 'org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlist*'` (every test class of this subtask has a name starting with `Allowlist` or `RecordingAllowlist`).

## Subtask T045: `Listing` (sorted by the code, never by file-system order)

**Purpose**: NFR-005 determinism and L6/L9/L11.

**Steps**:
1. List `kitty-specs/` entries; a directory WITHOUT `meta.json` is not a Mission (silently not listed, no diagnostic: matches `enumerate_missions`); sort names by code point yourself (never `Files.list` order). Directory names that differ in case-folded order versus byte order are in the `crlf-and-listing` golden class (WP07/WP09).
2. Faults: `kitty-specs/` unlistable => L11 `mission_dir_unreadable` (whole read refused); a Mission directory that vanishes between listing and read => L6 (`mission_vanished`, omitted, `missionCount` agrees); a Mission refused by symlink/containment => L9.
3. Fault injection through the recording seam (a hook that throws `AccessDeniedException`/`IOException` for a path class), never through real permissions on Windows.
4. Tests: unsorted creation order vs sorted output on this OS; vanish-between-list-and-read; unlistable root.

**Files**: `Listing*` (~120 lines), tests (~200).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.Listing*'` (every test class of this subtask has a name starting with `Listing`).

## Definition of Done

- Resolver, `SafeFiles`, `Allowlist` + recording seam and `Listing` implemented test-first; all FR-006 rules at the resolver, symlink/containment, the allowlist classification and the recorder (including the swallowed-failure case) pass; every positive control was observed red once.
- `cd services/mission-status-api && ./gradlew check` is GREEN at this tip; the new classes are the only file-API users besides the codec-free adapter (rule 7 passes); no process started; no write opened by any primitive.
- Native legs stay green at this tip (nothing here touches the hello route).
- Tracer entries appended (any Python-parity decision in the resolver).

## Risks

- Size: this WP is the four primitives (about 1,900 lines with tests); `FilesystemMissionEventSource`, the flow-level allowlist/read-only tests and the README stub were split into WP19 (sequential, depends on this WP).
- Windows has no `O_NOFOLLOW`: the NOFOLLOW_LINKS + attribute check must be confirmed on the Windows leg; if CI shows a difference, record it as a finding.
- mtime resolution differences across file systems are WP19's concern (AC-7c/7d); do not widen the allowlist to chase real-corpus behaviours (the nightly, WP14, owns those).

## Reviewer Guidance

- Check there is no read outside the allowlist and no `.git` registry/ref read; check the controls.
- Check sorting is by code and independent of listing order; check L9 versus L2 distinction.
- Check the recorder records BEFORE the OS answers.

## Implementation command

`spec-kitty agent action implement WP08 --agent claude`
