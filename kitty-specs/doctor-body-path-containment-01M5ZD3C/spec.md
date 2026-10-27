# Mission Specification: Doctor flags org-pack nodes whose body_path escapes the pack

**Mission Branch**: `issue-6418-doctor-body-path-containment`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "#6418: doctor charter-packs must not report an org pack healthy when an authored drg/fragment.yaml node's body_path escapes the pack root"

## Intent Summary (confirmed 2026-10-27)

- **Primary actor**: a governance author who shares governance through a team (org) pack.
- **Trigger**: the author runs `spec-kitty doctor charter-packs`, in its human or `--json` form, to check that the pack is sound.
- **Desired outcome**: when a node that the pack's own graph fragment (`drg/fragment.yaml`) declares has a `body_path` that leaves the pack folder, the doctor reports the pack unhealthy, exits non-zero, and names every such node and path.
- **Rule**: there is one containment authority for pack-relative paths. The doctor reuses it rather than adding a second "does this path escape" check. A `body_path` that stays inside the pack is never reported, whether or not its target exists.
- **Domain terms**: *org pack* / *team pack* (a configured `charter_packs.org.packs` entry); *graph fragment* (the pack's `drg/fragment.yaml`); *authored node* (a node the fragment declares itself, as opposed to one discovered from an artifact file); *pack root* (the pack's effective folder after `subdir` is applied); *escape* (a path that is absolute, has a `..` part, or resolves outside the pack root).

Decision Moments: JSON shape → add a structured list; node scope → authored fragment nodes only; intent → confirmed with the doctor-only scope below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An escaping body_path is not accepted as sound (Priority: P1)

A governance author ships a team pack whose fragment declares a node with `body_path: ../../../../etc/hostname`. They run `spec-kitty doctor charter-packs` before sharing it. Today the command exits 0 and the JSON says `errors: []`. After this mission the command exits non-zero, and the output names the pack, the node and the escaping path.

**Why this priority**: it is the GA-gating defect (#6418, P1, 4.0.0 release scope). The doctor is the author's trust check, and a false "healthy" is a silent wrong result on a trust surface.

**Independent Test**: build a project with one team pack whose fragment declares an escaping node, run the command, and assert the exit code and the named finding.

**Acceptance Scenarios**:

1. **Given** a team pack whose fragment declares a node with a `..` `body_path`, **When** the author runs `doctor charter-packs --json`, **Then** the exit code is 1, `org_drg.errors` contains a message naming the pack, the node and the `body_path`, and `org_drg.body_path_escapes` holds one entry for it.
2. **Given** the same pack, **When** the author runs `doctor charter-packs` without `--json`, **Then** the exit code is 1 and the org-layer section names the escaping node and path.
3. **Given** a node whose `body_path` is absolute (`/etc/hostname`), **When** the doctor runs, **Then** it is reported as an escape exactly like the `..` case.
4. **Given** a node whose `body_path` is a symlink inside the pack that resolves outside it, **When** the doctor runs, **Then** it is reported as an escape.

---

### User Story 2 - A sound pack stays healthy (Priority: P1)

The same author ships a pack whose fragment nodes point inside the pack (`bodies/secret-handling.md`, as the org-pack how-to shows), including a path whose file has not been written yet. The doctor still reports it healthy with exit 0, and the new structured list is present and empty.

**Why this priority**: a containment check that also fires on sound packs would break every existing user. It is the positive control for Story 1.

**Independent Test**: the same fixture with a contained `body_path` exits 0 and reports `body_path_escapes: []`.

**Acceptance Scenarios**:

1. **Given** a team pack whose fragment nodes all have contained `body_path` values (or none), **When** the doctor runs, **Then** the exit code is 0 and `org_drg.body_path_escapes` is `[]`.
2. **Given** a contained `body_path` whose target does not exist, **When** the doctor runs, **Then** no escape is reported for it.

---

### User Story 3 - The gating scenario binds (Priority: P2)

The consumer-promise scenario `PR-CHARTER-SHARING-004` ("A shared asset that reaches outside its pack is not accepted as sound") was set to `@wip @defect:6418` because it was red. After this mission it gates again, and the promise ledger records it as bound.

**Why this priority**: it closes the loop from the nightly red (#6369) back to a green, gating promise.

**Independent Test**: the scenario's tags and the PROMISES.md binding row no longer mark it `@wip` / `@defect:6418`.

**Acceptance Scenarios**:

1. **Given** the fix, **When** the scenario file and PROMISES.md are read, **Then** PR-CHARTER-SHARING-004 carries no `@wip` or `@defect:6418` tag and its binding reads `bound`.

### Edge Cases

- Several escaping nodes in one pack, or escapes in two packs, are each reported once, naming their own pack.
- A node with no `body_path` is not checked.
- A `body_path` on a node discovered from an artifact file (not declared in the fragment) is out of scope. Its kind's own validator owns it; for example, pack skills already refuse a body that escapes the skill folder.
- If the containment check itself cannot run (for example, the pack registry cannot be read), the doctor reports that as an error rather than reading it as "no escapes".
- A Windows-form absolute path (`C:\x`, `\\server\share`) or a `..\` part counts as an escape on every OS, as the shared primitive already rules.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Escaping body_path makes the pack unhealthy | As a governance author, I want `doctor charter-packs` to exit non-zero when an authored fragment node's `body_path` escapes its pack root (absolute, a `..` part, or a symlink resolving outside), so that an unsound pack is never reported healthy. | High | Open | [build] | no — today's code exits 0 on the same fixture (red-first reproduction) |
| FR-002 | Each escape is named in the error channel | As a governance author, I want each escape added to `org_drg.errors` as a message naming the pack, the node id and the offending `body_path`, so that I know what to fix. | High | Open | [build] | no — today `errors` is `[]` on the fixture |
| FR-003 | Structured escape list in JSON | As a tool author, I want `org_drg.body_path_escapes` always present in `--json` output: a list of `{pack, node, kind, body_path, reason}` entries, empty when nothing escapes, so that tooling need not parse message strings. | Medium | Open | [build] | no — the key does not exist today; paired with the contained-path control on the same fixture |
| FR-004 | Human output names the escape | As a governance author reading the human output, I want the org-layer section to list each escaping node and path, so that the human and JSON views of one command agree. | High | Open | [build] | no — today the section prints only "✓ loaded" |
| FR-005 | Contained paths stay healthy | As a governance author, I want a contained `body_path`, including one whose target does not exist, never reported as an escape, so that sound packs keep exiting 0. | High | Open | [ratchet] | yes — so it is paired with FR-001 on the same fixture, differing only in the `body_path` value |
| FR-006 | Scenario PR-CHARTER-SHARING-004 binds | As a maintainer, I want the scenario's `@wip @defect:6418` tags removed and PROMISES.md updated to `bound`, so that the consumer promise gates again. | Medium | Open | [build] | no — the tags are present today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added filesystem reads of node bodies | The check reads no `body_path` target's contents; besides path resolution it does 0 file reads, so a hostile path is never opened. | Security | High | Open |
| NFR-002 | Existing doctor output unchanged for sound packs | For a project with no escaping nodes, every pre-existing `--json` key and value is identical to before; the only addition is `org_drg.body_path_escapes: []`. | Reliability | High | Open |
| NFR-003 | Quality gates | Touched code passes ruff, `ruff format --check --force-exclude` and mypy with 0 new findings and 0 new suppressions; every touched function stays at cyclomatic complexity ≤ 15; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One containment authority | Escape detection reuses `resolve_relative_path_within_root` (the primitive behind `OrgPackSubdirEscapeError`, `AssetPathEscapeError` and the pack validator's asset containment). No new path-escape algorithm. | Technical | High | Open |
| C-002 | Doctor-only scope | Pack loading, activation and runtime resolution are not changed; `charter org validate`, `charter status` and spec-kitty-charter's validator are follow-ups, not changed here. | Technical | High | Open |
| C-003 | Never edit packs in core | No file under `packs/built-in/` or `packs/internal/` is edited. | Technical | High | Open |
| C-004 | Charter stays in core | The new predicate lives in the in-core charter layer and is reached through an existing `charter` facade; the enforced layer chain and `pyproject.toml` package set are unchanged (ADR 2026-10-16-1, Amendment 2026-10-19). | Technical | High | Open |

### Key Entities

- **Body-path escape finding**: one authored fragment node whose `body_path` escapes its pack root, carrying the pack name, node id, node kind, the `body_path` as written, and the reason the shared primitive gave.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #6418 reproduction fixture (both the `..` and the absolute form), `doctor charter-packs` exits 1 in 2 out of 2 runs, where today it exits 0 in both. — [build] · no-op passable: no
- **SC-002**: On the same fixture with a contained `body_path`, the command exits 0 and reports 0 escapes. — [ratchet] · no-op passable: yes (paired with SC-001 on the same fixture)
- **SC-003**: Consumer promise PR-CHARTER-SHARING-004 moves from `@wip` to bound, so 0 charter-sharing promises remain `@wip` for defect #6418. — [build] · no-op passable: no

## Assumptions

- `body_path` on an authored fragment node is pack-root-relative, as the org-DRG contract and `docs/guides/how-to/governance/create-an-org-doctrine-pack.md` show. The scenario fixture (`kind: assets` + `body_path`) is a production-shaped declaration, so the fixture does not change (#6137 not needed).
- Nothing in core reads an org fragment node's `body_path` target today (only the merge's layer-rule heuristic reads the string), so a doctor-side diagnostic closes the trust gap without changing load behaviour.

## Out of Scope (follow-ups)

- `charter org validate` and `charter status` also accept the escaping fragment.
- Refusing such a pack at load or activation time.
- The `(degraded)` label, which comes from having no org agent profiles and is unrelated.
- spec-kitty-charter's `PackPolicy` checks asset manifest paths but not fragment `body_path`; it has the same gap and needs an issue in that repository.
